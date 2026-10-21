begin;
-- Capacity is shared fairly; it is not an availability or user-count guarantee.
update public.gametime_sync_budget set account_limit=100 where singleton;
alter table public.gametime_sync_budget alter column account_limit set default 100;
create or replace function public.gametime_before_user_created(event jsonb)
returns jsonb language plpgsql security invoker set search_path='' set lock_timeout='2s' as $$
declare allowed boolean; opened boolean; total integer; today integer; day date;
 utc_day date:=(now() at time zone 'UTC')::date;
begin
 -- app_metadata is supplied by Auth, never editable user_metadata.
 if event->'user'->'app_metadata'->>'provider' is distinct from 'github'
   or coalesce(event->'user'->>'email','')='' then
   return jsonb_build_object('error',jsonb_build_object('http_code',403,'message','Verified GitHub sign-in is required.'));
 end if;
 select enabled,registration_enabled,auth_signup_total,auth_signup_day,auth_signups_today
   into allowed,opened,total,day,today from public.gametime_sync_budget where singleton for update;
 if not found or not allowed or not opened or total>=500 or (day=utc_day and today>=25) then
   return jsonb_build_object('error',jsonb_build_object('http_code',403,'message','New cloud registrations are temporarily unavailable. Local statistics are kept.'));
 end if;
 -- Atomic reservations close the race between this hook and Auth user insertion.
 -- Failed registrations may conservatively consume a slot; never reset on logout.
 update public.gametime_sync_budget set auth_signup_total=total+1,auth_signup_day=utc_day,
   auth_signups_today=case when day=utc_day then today+1 else 1 end where singleton;
 return '{}'::jsonb;
end $$;
revoke all on function public.gametime_before_user_created(jsonb) from public,anon,authenticated,service_role;
grant execute on function public.gametime_before_user_created(jsonb) to supabase_auth_admin;

create or replace function public.gametime_sync_exchange(
  p_group text,p_ip text,p_device text,p_revision text,p_payload text,p_known jsonb
) returns jsonb
language plpgsql security invoker set search_path='' set lock_timeout='2s' as $$
declare
  minute_bucket timestamptz:=date_trunc('minute',now());
  month_bucket timestamptz:=date_trunc('month',now() at time zone 'UTC') at time zone 'UTC';
  day_bucket timestamptz:=date_trunc('day',now() at time zone 'UTC') at time zone 'UTC';
  budget public.gametime_sync_budget%rowtype;
  owner_group public.gametime_sync_groups%rowtype;
  account public.gametime_sync_accounts%rowtype;
  owner uuid;
  owner_requests integer; owner_egress bigint; owner_ingress_day bigint; owner_egress_day bigint;
  old_revision bigint; old_size integer:=0; new_size integer:=0;
  is_new boolean; uploading boolean; snapshots jsonb; result jsonb;
  hits integer; identity text; maximum integer; sent_bytes integer;
  active_groups integer; fair_requests integer; fair_egress bigint;
  global_requests integer; global_egress bigint; group_requests integer;
  group_egress bigint; daily_ingress bigint; daily_egress bigint;
begin
  if p_group is null or p_group !~ '^[0-9a-f]{64}$'
    or p_ip is null or p_ip !~ '^[0-9a-f]{64}$'
    or p_device is null or p_device !~ '^[0-9a-f]{32}$'
    or p_revision is null or p_revision !~ '^[1-9][0-9]{0,18}$'
    or p_revision::numeric>9223372036854775807
    or p_known is null or jsonb_typeof(p_known)<>'object'
    or (p_payload is not null and (octet_length(p_payload) not between 44 and 699052
        or p_payload !~ '^[A-Za-z0-9+/]+={0,2}$' or length(p_payload)%4<>0)) then
    return jsonb_build_object('error','input');
  end if;
  if (select count(*) from jsonb_each(p_known))>100 or exists(
    select 1 from jsonb_each(p_known) e where e.key !~ '^[0-9a-f]{32}$'
      or jsonb_typeof(e.value)<>'string' or (e.value#>>'{}') !~ '^[1-9][0-9]{0,18}$'
      or length(e.value#>>'{}')>19
  ) then return jsonb_build_object('error','input'); end if;
  -- Authentication precedes all writes, counters and storage allocation.
  if not exists(select 1 from public.gametime_sync_groups where group_hash=p_group and enabled) then
    return jsonb_build_object('error','admission');
  end if;
  -- A single lock order is shared with maintenance: budget, group, device.
  select * into budget from public.gametime_sync_budget where singleton for update;
  if not budget.enabled then return jsonb_build_object('error','disabled','retry_after',3600); end if;
  select owner_id into owner from public.gametime_sync_groups where group_hash=p_group and enabled;
  if owner is not null then
    select * into account from public.gametime_sync_accounts where owner_id=owner for update;
    if not found or not account.enabled or account.current_group is distinct from p_group or not exists(
      select 1 from auth.users where id=owner and deleted_at is null and (banned_until is null or banned_until<=now())
    ) then return jsonb_build_object('error','admission'); end if;
    owner_requests:=case when account.month_start=month_bucket then account.month_requests else 0 end;
    owner_egress:=case when account.month_start=month_bucket then account.month_egress else 0 end;
    owner_ingress_day:=case when account.day_start=day_bucket then account.day_ingress else 0 end;
    owner_egress_day:=case when account.day_start=day_bucket then account.day_egress else 0 end;
  end if;
  select * into owner_group from public.gametime_sync_groups where group_hash=p_group and enabled for update;
  if not found then return jsonb_build_object('error','admission'); end if;
  global_requests:=case when budget.month_start=month_bucket then budget.month_requests else 0 end;
  global_egress:=case when budget.month_start=month_bucket then budget.month_egress else 0 end;
  group_requests:=case when owner_group.month_start=month_bucket then owner_group.month_requests else 0 end;
  group_egress:=case when owner_group.month_start=month_bucket then owner_group.month_egress else 0 end;
  daily_ingress:=case when owner_group.day_start=day_bucket then owner_group.day_ingress else 0 end;
  daily_egress:=case when owner_group.day_start=day_bucket then owner_group.day_egress else 0 end;
  select greatest(25,count(*))::integer into active_groups from public.gametime_sync_groups where enabled;
  fair_requests:=least(12000,350000/active_groups);
  fair_egress:=least(134217728,3221225472/active_groups);
  if global_requests>=350000 or group_requests>=fair_requests or coalesce(owner_requests,0)>=fair_requests then
    return jsonb_build_object('error','rate','retry_after',86400);
  end if;
  delete from public.gametime_sync_rate where bucket<minute_bucket-interval '2 minutes';
  for identity,maximum in select * from (values
    ('group:'||p_group,40),('device:'||p_group||':'||p_device,4),('ip:'||p_ip,600)
  ) limits loop
    insert into public.gametime_sync_rate values(minute_bucket,identity,1)
      on conflict(bucket,identity_hash) do update
        set hits=public.gametime_sync_rate.hits+1 where public.gametime_sync_rate.hits<=maximum
        returning gametime_sync_rate.hits into hits;
    if not found or hits>maximum then return jsonb_build_object('error','rate','retry_after',60); end if;
  end loop;
  select revision,octet_length(payload) into old_revision,old_size
    from public.gametime_sync_devices where group_hash=p_group and device_id=p_device;
  is_new:=old_revision is null;
  uploading:=p_payload is not null and (is_new or p_revision::bigint>old_revision);
  if uploading then
    new_size:=octet_length(p_payload);
    if (is_new and (select count(*) from public.gametime_sync_devices where group_hash=p_group)>=20)
      or (is_new and budget.device_count>=10000)
      or budget.used_bytes-coalesce(old_size,0)+new_size>209715200
      or owner_group.used_bytes-coalesce(old_size,0)+new_size>2097152 then
      return jsonb_build_object('error','quota','retry_after',3600);
    end if;
    if daily_ingress+new_size>8388608 or coalesce(owner_ingress_day,0)+new_size>8388608 then return jsonb_build_object('error','rate','retry_after',3600); end if;
  end if;
  select coalesce(jsonb_agg(jsonb_build_object('device',device_id,'revision',revision::text,'payload',payload)
      order by device_id),'[]'::jsonb) into snapshots from (
    select device_id,revision,payload,
      sum(octet_length(payload)+192) over(order by device_id) as response_bytes
    from public.gametime_sync_devices where group_hash=p_group and device_id<>p_device
      and revision::text is distinct from p_known->>device_id
  ) pending where response_bytes<=1048576;
  result:=jsonb_build_object('need_upload',is_new and p_payload is null,'snapshots',snapshots);
  sent_bytes:=octet_length(result::text)+128;
  if global_egress+sent_bytes>4294967296 or group_egress+sent_bytes>fair_egress
    or daily_egress+sent_bytes>8388608 or coalesce(owner_egress,0)+sent_bytes>fair_egress
    or coalesce(owner_egress_day,0)+sent_bytes>8388608 then
    return jsonb_build_object('error','rate','retry_after',3600);
  end if;
  if uploading then
    insert into public.gametime_sync_devices(group_hash,device_id,revision,payload,last_seen)
      values(p_group,p_device,p_revision::bigint,p_payload,now())
      on conflict(group_hash,device_id) do update set revision=excluded.revision,payload=excluded.payload,last_seen=excluded.last_seen;
  elsif not is_new then
    update public.gametime_sync_devices set last_seen=now()
      where group_hash=p_group and device_id=p_device and last_seen<now()-interval '1 hour';
  end if;
  update public.gametime_sync_budget set month_start=month_bucket,month_requests=global_requests+1,
    month_egress=global_egress+sent_bytes,
    used_bytes=budget.used_bytes+case when uploading then new_size-coalesce(old_size,0) else 0 end,
    device_count=budget.device_count+case when uploading and is_new then 1 else 0 end where singleton;
  update public.gametime_sync_groups set last_seen=now(),month_start=month_bucket,month_requests=group_requests+1,
    month_egress=group_egress+sent_bytes,day_start=day_bucket,
    day_ingress=daily_ingress+case when uploading then new_size else 0 end,day_egress=daily_egress+sent_bytes,
    used_bytes=owner_group.used_bytes+case when uploading then new_size-coalesce(old_size,0) else 0 end where group_hash=p_group;
  if owner is not null then
    update public.gametime_sync_accounts set month_start=month_bucket,month_requests=owner_requests+1,
      month_egress=owner_egress+sent_bytes,day_start=day_bucket,
      day_ingress=owner_ingress_day+case when uploading then new_size else 0 end,
      day_egress=owner_egress_day+sent_bytes where owner_id=owner;
  end if;
  return result;
end;
$$;
revoke all on function public.gametime_sync_exchange(text,text,text,text,text,jsonb) from public,anon,authenticated;
grant execute on function public.gametime_sync_exchange(text,text,text,text,text,jsonb) to service_role;



commit;
