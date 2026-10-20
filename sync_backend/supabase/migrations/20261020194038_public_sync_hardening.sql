begin;

-- New groups require explicit admission. Existing connections retain their
-- opaque capability and ciphertext; no connection/encryption key is stored.
create table public.gametime_sync_groups (
  group_hash text primary key check (group_hash ~ '^[0-9a-f]{64}$'),
  enabled boolean not null default true,
  owner_id uuid unique references auth.users(id),
  created_at timestamptz not null default now(),
  last_seen timestamptz not null default now(),
  used_bytes bigint not null default 0 check (used_bytes>=0),
  month_start timestamptz not null default date_trunc('month',now()),
  month_requests integer not null default 0 check (month_requests>=0),
  month_egress bigint not null default 0 check (month_egress>=0),
  day_start timestamptz not null default date_trunc('day',now()),
  day_ingress bigint not null default 0 check (day_ingress>=0),
  day_egress bigint not null default 0 check (day_egress>=0)
);
alter table public.gametime_sync_groups enable row level security;
revoke all on public.gametime_sync_groups from public,anon,authenticated;
grant select,insert,update,delete on public.gametime_sync_groups to service_role;
insert into public.gametime_sync_groups(group_hash,used_bytes)
  select group_hash,sum(octet_length(payload)) from public.gametime_sync_devices group by group_hash;

alter table public.gametime_sync_devices add column last_seen timestamptz not null default now();
create index gametime_sync_devices_last_seen on public.gametime_sync_devices(last_seen);
alter table public.gametime_sync_budget
  add column enabled boolean not null default true,
  add column month_start timestamptz not null default date_trunc('month',now()),
  add column month_requests integer not null default 0,
  add column month_egress bigint not null default 0;
grant delete on public.gametime_sync_devices to service_role;

create function public.gametime_sync_authorize(p_group text) returns boolean
language sql stable security invoker set search_path='' as $$
  select exists(select 1 from public.gametime_sync_groups where group_hash=p_group and enabled)
    and exists(select 1 from public.gametime_sync_budget where singleton and enabled);
$$;
revoke all on function public.gametime_sync_authorize(text) from public,anon,authenticated;
grant execute on function public.gametime_sync_authorize(text) to service_role;

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
  old_revision bigint; old_size integer:=0; new_size integer:=0;
  is_new boolean; uploading boolean; snapshots jsonb; result jsonb;
  hits integer; identity text; maximum integer; sent_bytes integer;
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
  select * into owner_group from public.gametime_sync_groups where group_hash=p_group and enabled for update;
  if not found then return jsonb_build_object('error','admission'); end if;
  global_requests:=case when budget.month_start=month_bucket then budget.month_requests else 0 end;
  global_egress:=case when budget.month_start=month_bucket then budget.month_egress else 0 end;
  group_requests:=case when owner_group.month_start=month_bucket then owner_group.month_requests else 0 end;
  group_egress:=case when owner_group.month_start=month_bucket then owner_group.month_egress else 0 end;
  daily_ingress:=case when owner_group.day_start=day_bucket then owner_group.day_ingress else 0 end;
  daily_egress:=case when owner_group.day_start=day_bucket then owner_group.day_egress else 0 end;
  if global_requests>=350000 or group_requests>=60000 then
    return jsonb_build_object('error','rate','retry_after',86400);
  end if;
  delete from public.gametime_sync_rate where bucket<minute_bucket-interval '2 minutes';
  for identity,maximum in select * from (values
    ('group:'||p_group,40),('device:'||p_group||':'||p_device,4),('ip:'||p_ip,600)
  ) limits loop
    insert into public.gametime_sync_rate values(minute_bucket,identity,1)
      on conflict(bucket,identity_hash) do update
        set hits=least(public.gametime_sync_rate.hits+1,maximum+1) returning gametime_sync_rate.hits into hits;
    if hits>maximum then return jsonb_build_object('error','rate','retry_after',60); end if;
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
      or owner_group.used_bytes-coalesce(old_size,0)+new_size>4194304 then
      return jsonb_build_object('error','quota','retry_after',3600);
    end if;
    if daily_ingress+new_size>67108864 then return jsonb_build_object('error','rate','retry_after',3600); end if;
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
  if global_egress+sent_bytes>4294967296 or group_egress+sent_bytes>536870912
    or daily_egress+sent_bytes>67108864 then
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
  return result;
end;
$$;
revoke all on function public.gametime_sync_exchange(text,text,text,text,text,jsonb) from public,anon,authenticated;
grant execute on function public.gametime_sync_exchange(text,text,text,text,text,jsonb) to service_role;

create function public.gametime_sync_cleanup() returns jsonb
language plpgsql security invoker set search_path='' set lock_timeout='2s' as $$
declare removed integer; freed bigint;
begin
  perform 1 from public.gametime_sync_budget where singleton for update;
  with retired as (
    delete from public.gametime_sync_devices where (group_hash,device_id) in (
      select group_hash,device_id from public.gametime_sync_devices where last_seen<now()-interval '90 days'
      order by last_seen limit 1000
    ) returning group_hash,octet_length(payload) as bytes
  ), totals as (select group_hash,count(*) as count,sum(bytes) as bytes from retired group by group_hash),
  adjusted as (
    update public.gametime_sync_groups g set used_bytes=g.used_bytes-t.bytes
    from totals t where g.group_hash=t.group_hash returning t.count,t.bytes
  ) select coalesce(sum(count),0),coalesce(sum(bytes),0) into removed,freed from adjusted;
  update public.gametime_sync_budget set used_bytes=used_bytes-freed,device_count=device_count-removed where singleton;
  delete from public.gametime_sync_rate where bucket<date_trunc('minute',now())-interval '2 minutes';
  return jsonb_build_object('removed',removed,'freed_bytes',freed);
end;
$$;
revoke all on function public.gametime_sync_cleanup() from public,anon,authenticated;
grant execute on function public.gametime_sync_cleanup() to service_role;
commit;
