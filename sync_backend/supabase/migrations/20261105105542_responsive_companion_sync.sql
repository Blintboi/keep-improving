begin;

-- Responsive companion polls reuse published snapshots; full history is coalesced.
-- Preserve all counters and ciphertext, and retain the existing global/traffic
-- guards and fair monthly allocation in gametime_sync_exchange.
alter table public.gametime_sync_accounts drop constraint gametime_sync_accounts_sync_hits_check,
  add constraint gametime_sync_accounts_sync_hits_check check(sync_hits between 0 and 10000);
alter table public.gametime_sync_groups drop constraint gametime_sync_groups_sync_hits_check,
  add constraint gametime_sync_groups_sync_hits_check check(sync_hits between 0 and 10000);

create or replace function public.gametime_sync_exchange_limited(
  p_group text,p_ip text,p_device text,p_revision text,p_payload text,p_known jsonb
) returns jsonb language plpgsql security invoker set search_path='' set lock_timeout='2s' as $$
declare
  g public.gametime_sync_groups%rowtype;
  a public.gametime_sync_accounts%rowtype;
  blocked_until timestamptz;
  utc_day date:=(now() at time zone 'UTC')::date;
  utc_month timestamptz:=date_trunc('month',now() at time zone 'UTC') at time zone 'UTC';
  next_day timestamptz:=((now() at time zone 'UTC')::date+1)::timestamp at time zone 'UTC';
  next_month timestamptz:=(date_trunc('month',now() at time zone 'UTC')+interval '1 month') at time zone 'UTC';
  result jsonb;
begin
  if not exists(select 1 from public.gametime_sync_groups where group_hash=p_group and enabled) then
    return jsonb_build_object('error','admission');
  end if;
  -- Same lock order as exchange, management and maintenance. Serializing checks
  -- with accounting also closes concurrent requests from different Edge isolates.
  perform 1 from public.gametime_sync_budget where singleton for update;
  select * into g from public.gametime_sync_groups where group_hash=p_group and enabled;
  if not found then return jsonb_build_object('error','admission'); end if;
  if g.owner_id is not null then
    select * into a from public.gametime_sync_accounts where owner_id=g.owner_id for update;
  end if;
  select * into g from public.gametime_sync_groups where group_hash=p_group for update;
  if (g.month_start=utc_month and g.month_requests>=250000)
    or (a.month_start=utc_month and a.month_requests>=250000) then
    return jsonb_build_object('error','rate','retry_after',least(86400,ceil(extract(epoch from next_month-now()))));
  end if;
  if (g.sync_day=utc_day and g.sync_hits>=10000) or (a.sync_day=utc_day and a.sync_hits>=10000) then
    return jsonb_build_object('error','rate','retry_after',ceil(extract(epoch from next_day-now())));
  end if;
  select next_sync_at into blocked_until from public.gametime_sync_devices
    where group_hash=p_group and device_id=p_device;
  if blocked_until>now() then
    return jsonb_build_object('error','cooldown','retry_after',ceil(extract(epoch from blocked_until-now())));
  end if;
  -- The existing transport retains validation, encryption isolation, storage,
  -- upload/egress budgets, revocation and service-role-only grants.
  result:=public.gametime_sync_exchange(p_group,p_ip,p_device,p_revision,p_payload,p_known);
  if result ? 'error' then return result; end if;
  update public.gametime_sync_groups set sync_day=utc_day,
    sync_hits=case when sync_day=utc_day then sync_hits+1 else 1 end where group_hash=p_group;
  if g.owner_id is not null then
    update public.gametime_sync_accounts set sync_day=utc_day,
      sync_hits=case when sync_day=utc_day then sync_hits+1 else 1 end where owner_id=g.owner_id;
  end if;
  -- A missing-copy probe may be followed immediately by its repair upload.
  -- Probes still consume daily/monthly requests, including when IDs are varied.
  if result->>'need_upload'='false' then
    update public.gametime_sync_devices set next_sync_at=now()+interval '15 seconds'
      where group_hash=p_group and device_id=p_device;
  end if;
  return result;
end;
$$;
revoke all on function public.gametime_sync_exchange_limited(text,text,text,text,text,jsonb) from public,anon,authenticated;
grant execute on function public.gametime_sync_exchange_limited(text,text,text,text,text,jsonb) to service_role;

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
  active_groups integer; fair_requests integer; fair_egress bigint; fair_ingress bigint;
  global_ingress bigint; global_ingress_day bigint; group_ingress bigint; owner_ingress bigint;
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
    owner_ingress:=case when account.month_start=month_bucket then account.month_ingress else 0 end;
    owner_requests:=case when account.month_start=month_bucket then account.month_requests else 0 end;
    owner_egress:=case when account.month_start=month_bucket then account.month_egress else 0 end;
    owner_ingress_day:=case when account.day_start=day_bucket then account.day_ingress else 0 end;
    owner_egress_day:=case when account.day_start=day_bucket then account.day_egress else 0 end;
  end if;
  select * into owner_group from public.gametime_sync_groups where group_hash=p_group and enabled for update;
  if not found then return jsonb_build_object('error','admission'); end if;
  global_ingress:=case when budget.month_start=month_bucket then budget.month_ingress else 0 end;
  global_ingress_day:=case when budget.ingress_day_start=day_bucket then budget.day_ingress else 0 end;
  group_ingress:=case when owner_group.month_start=month_bucket then owner_group.month_ingress else 0 end;
  global_requests:=case when budget.month_start=month_bucket then budget.month_requests else 0 end;
  global_egress:=case when budget.month_start=month_bucket then budget.month_egress else 0 end;
  group_requests:=case when owner_group.month_start=month_bucket then owner_group.month_requests else 0 end;
  group_egress:=case when owner_group.month_start=month_bucket then owner_group.month_egress else 0 end;
  daily_ingress:=case when owner_group.day_start=day_bucket then owner_group.day_ingress else 0 end;
  daily_egress:=case when owner_group.day_start=day_bucket then owner_group.day_egress else 0 end;
  select greatest(1,count(*))::integer into active_groups from public.gametime_sync_groups where enabled;
  fair_requests:=least(250000,350000/active_groups);
  fair_ingress:=least(805306368,1073741824/active_groups);
  fair_egress:=least(805306368,3221225472/active_groups);
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
    if global_ingress+new_size>1073741824 or group_ingress+new_size>fair_ingress
      or coalesce(owner_ingress,0)+new_size>fair_ingress then
      return jsonb_build_object('error','rate','retry_after',86400);
    end if;
    if global_ingress_day+new_size>67108864 or daily_ingress+new_size>33554432
      or coalesce(owner_ingress_day,0)+new_size>33554432 then
      return jsonb_build_object('error','rate','retry_after',3600);
    end if;
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
    or daily_egress+sent_bytes>33554432 or coalesce(owner_egress,0)+sent_bytes>fair_egress
    or coalesce(owner_egress_day,0)+sent_bytes>33554432 then
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
    month_ingress=global_ingress+case when uploading then new_size else 0 end,
    ingress_day_start=day_bucket,day_ingress=global_ingress_day+case when uploading then new_size else 0 end,
    used_bytes=budget.used_bytes+case when uploading then new_size-coalesce(old_size,0) else 0 end,
    device_count=budget.device_count+case when uploading and is_new then 1 else 0 end where singleton;
  update public.gametime_sync_groups set last_seen=now(),month_start=month_bucket,month_requests=group_requests+1,
    month_egress=group_egress+sent_bytes,month_ingress=group_ingress+case when uploading then new_size else 0 end,day_start=day_bucket,
    day_ingress=daily_ingress+case when uploading then new_size else 0 end,day_egress=daily_egress+sent_bytes,
    used_bytes=owner_group.used_bytes+case when uploading then new_size-coalesce(old_size,0) else 0 end where group_hash=p_group;
  if owner is not null then
    update public.gametime_sync_accounts set month_start=month_bucket,month_requests=owner_requests+1,
      month_egress=owner_egress+sent_bytes,month_ingress=owner_ingress+case when uploading then new_size else 0 end,day_start=day_bucket,
      day_ingress=owner_ingress_day+case when uploading then new_size else 0 end,
      day_egress=owner_egress_day+sent_bytes where owner_id=owner;
  end if;
  return result;
end;
$$;
revoke all on function public.gametime_sync_exchange(text,text,text,text,text,jsonb) from public,anon,authenticated;
grant execute on function public.gametime_sync_exchange(text,text,text,text,text,jsonb) to service_role;





-- Shorten outstanding cooldowns from the retired policy without resetting usage.
update public.gametime_sync_devices set next_sync_at=least(next_sync_at,now()+interval '15 seconds');
commit;
