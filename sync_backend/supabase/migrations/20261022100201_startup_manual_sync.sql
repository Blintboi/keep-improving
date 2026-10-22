begin;

-- Independent ledgers: existing month/day traffic resets and code rotation must
-- not clear the personal-use daily request guard. No user data is rewritten.
alter table public.gametime_sync_accounts add column sync_day date,
  add column sync_hits integer not null default 0 check(sync_hits between 0 and 20);
alter table public.gametime_sync_groups add column sync_day date,
  add column sync_hits integer not null default 0 check(sync_hits between 0 and 20);
alter table public.gametime_sync_devices add column next_sync_at timestamptz;

create function public.gametime_sync_exchange_limited(
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
  if (g.month_start=utc_month and g.month_requests>=600)
    or (a.month_start=utc_month and a.month_requests>=600) then
    return jsonb_build_object('error','rate','retry_after',least(86400,ceil(extract(epoch from next_month-now()))));
  end if;
  if (g.sync_day=utc_day and g.sync_hits>=20) or (a.sync_day=utc_day and a.sync_hits>=20) then
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
    update public.gametime_sync_devices set next_sync_at=now()+interval '10 minutes'
      where group_hash=p_group and device_id=p_device;
  end if;
  return result;
end;
$$;
revoke all on function public.gametime_sync_exchange_limited(text,text,text,text,text,jsonb) from public,anon,authenticated;
grant execute on function public.gametime_sync_exchange_limited(text,text,text,text,text,jsonb) to service_role;

commit;
