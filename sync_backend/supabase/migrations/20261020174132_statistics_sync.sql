begin;

create table public.gametime_sync_devices (
  group_hash text not null check (group_hash ~ '^[0-9a-f]{64}$'),
  device_id text not null check (device_id ~ '^[0-9a-f]{32}$'),
  revision bigint not null check (revision > 0),
  payload text not null check (octet_length(payload) between 44 and 699052),
  primary key (group_hash, device_id)
);
create table public.gametime_sync_budget (
  singleton boolean primary key default true check (singleton),
  used_bytes bigint not null default 0 check (used_bytes >= 0),
  device_count integer not null default 0 check (device_count >= 0)
);
insert into public.gametime_sync_budget (singleton) values (true);
create table public.gametime_sync_rate (
  bucket timestamptz not null,
  identity_hash text not null,
  hits integer not null,
  primary key (bucket, identity_hash)
);

alter table public.gametime_sync_devices enable row level security;
alter table public.gametime_sync_budget enable row level security;
alter table public.gametime_sync_rate enable row level security;
revoke all on public.gametime_sync_devices, public.gametime_sync_budget, public.gametime_sync_rate from public, anon, authenticated;
grant select, insert, update on public.gametime_sync_devices, public.gametime_sync_budget to service_role;
grant select, insert, update, delete on public.gametime_sync_rate to service_role;

-- Only the server-side service role may call this function. Group identity is
-- derived from the HTTP credential by the Edge Function, never from body input.
create function public.gametime_sync_exchange(
  p_group text, p_ip text, p_device text, p_revision text,
  p_payload text, p_known jsonb
) returns jsonb
language plpgsql security invoker set search_path = '' as $$
declare
  minute_bucket timestamptz := date_trunc('minute', now());
  group_hits integer;
  ip_hits integer;
  old_revision bigint;
  old_size bigint := 0;
  budget_bytes bigint;
  budget_count integer;
  is_new boolean;
  snapshots jsonb;
begin
  if p_group is null or p_group !~ '^[0-9a-f]{64}$'
      or p_ip is null or p_ip !~ '^[0-9a-f]{64}$'
      or p_device is null or p_device !~ '^[0-9a-f]{32}$'
      or p_revision is null or p_revision !~ '^[1-9][0-9]{0,18}$'
      or p_revision::numeric > 9223372036854775807
      or p_known is null or jsonb_typeof(p_known) <> 'object'
      or (p_payload is not null and (octet_length(p_payload) not between 44 and 699052
          or p_payload !~ '^[A-Za-z0-9+/]+={0,2}$' or length(p_payload) % 4 <> 0)) then
    return jsonb_build_object('error', 'input');
  end if;
  -- A hard cap remains in place even on a paid provider account. No automatic
  -- plan change is necessary or performed by this service.
  delete from public.gametime_sync_rate where bucket < minute_bucket - interval '2 minutes';
  insert into public.gametime_sync_rate values (minute_bucket, 'group:' || p_group, 1)
    on conflict (bucket, identity_hash) do update set hits = public.gametime_sync_rate.hits + 1
    returning hits into group_hits;
  insert into public.gametime_sync_rate values (minute_bucket, 'ip:' || p_ip, 1)
    on conflict (bucket, identity_hash) do update set hits = public.gametime_sync_rate.hits + 1
    returning hits into ip_hits;
  if group_hits > 120 or ip_hits > 600 then
    return jsonb_build_object('error', 'rate');
  end if;

  perform pg_advisory_xact_lock(hashtextextended(p_group, 0));
  select revision, octet_length(payload) into old_revision, old_size
    from public.gametime_sync_devices where group_hash = p_group and device_id = p_device;
  is_new := old_revision is null;
  if p_payload is null and is_new then
    return jsonb_build_object('need_upload', true, 'snapshots', '[]'::jsonb);
  end if;

  if p_payload is not null and (is_new or p_revision::bigint > old_revision) then
    if is_new and (select count(*) from public.gametime_sync_devices where group_hash = p_group) >= 20 then
      return jsonb_build_object('error', 'quota');
    end if;
    select used_bytes, device_count into budget_bytes, budget_count
      from public.gametime_sync_budget where singleton for update;
    if budget_bytes - coalesce(old_size, 0) + octet_length(p_payload) > 209715200
        or (is_new and budget_count >= 10000) then
      return jsonb_build_object('error', 'quota');
    end if;
    insert into public.gametime_sync_devices values (p_group, p_device, p_revision::bigint, p_payload)
      on conflict (group_hash, device_id) do update set revision = excluded.revision, payload = excluded.payload;
    update public.gametime_sync_budget set
      used_bytes = budget_bytes - coalesce(old_size, 0) + octet_length(p_payload),
      device_count = budget_count + case when is_new then 1 else 0 end
      where singleton;
  end if;

  -- Revisions are strings on the wire: nanosecond timestamps exceed the exact
  -- integer range of JavaScript numbers. Imported rows are never re-exported.
  select coalesce(jsonb_agg(jsonb_build_object('device', device_id,
      'revision', revision::text, 'payload', payload) order by device_id), '[]'::jsonb)
    into snapshots from public.gametime_sync_devices
    where group_hash = p_group and device_id <> p_device
      and revision::text is distinct from (p_known ->> device_id);
  return jsonb_build_object('need_upload', false, 'snapshots', snapshots);
end;
$$;
revoke all on function public.gametime_sync_exchange(text, text, text, text, text, jsonb) from public, anon, authenticated;
grant execute on function public.gametime_sync_exchange(text, text, text, text, text, jsonb) to service_role;

commit;
