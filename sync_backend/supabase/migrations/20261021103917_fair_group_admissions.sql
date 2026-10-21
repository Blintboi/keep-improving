begin;
create or replace function public.gametime_sync_account(p_owner uuid,p_session uuid,p_action text,p_group text)
returns jsonb language plpgsql security invoker set search_path='' set lock_timeout='2s' as $$
declare
  budget public.gametime_sync_budget%rowtype;
  account public.gametime_sync_accounts%rowtype;
  target public.gametime_sync_groups%rowtype;
  old_group text; freed bigint; removed integer;
  utc_day date:=(now() at time zone 'UTC')::date;
  utc_month timestamptz:=date_trunc('month',now() at time zone 'UTC') at time zone 'UTC';
  exists_group boolean; management_hits integer;
begin
  if p_action not in ('status','activate','rotate','revoke') or p_action is null
    or (p_action<>'revoke' and (p_group is null or p_group !~ '^[0-9a-f]{64}$')) then
    return jsonb_build_object('error','input');
  end if;
  -- A valid, verified provider identity AND a live session are mandatory.
  -- JWT user_metadata, owner IDs and group hashes supplied by clients are not proof.
  if not exists(select 1 from auth.users u join auth.sessions s on s.user_id=u.id
    where u.id=p_owner and s.id=p_session and (s.not_after is null or s.not_after>now())
      and u.email_confirmed_at is not null and not coalesce(u.is_anonymous,false) and u.deleted_at is null
      and (u.banned_until is null or u.banned_until<=now())
      and exists(select 1 from auth.identities i where i.user_id=u.id and i.provider='github')) then
    return jsonb_build_object('error','session');
  end if;
  select * into budget from public.gametime_sync_budget where singleton for update;
  delete from public.gametime_sync_rate where bucket<date_trunc('minute',now())-interval '2 minutes';
  insert into public.gametime_sync_rate values(date_trunc('minute',now()),'account:'||p_owner::text,1)
    on conflict(bucket,identity_hash) do update set hits=public.gametime_sync_rate.hits+1
      where public.gametime_sync_rate.hits<=12 returning hits into management_hits;
  if not found or management_hits>12 then return jsonb_build_object('error','rate'); end if;

  select * into account from public.gametime_sync_accounts where owner_id=p_owner for update;
  if found and not account.enabled then return jsonb_build_object('error','disabled'); end if;
  if p_action='status' then
    return jsonb_build_object('owned',coalesce(account.current_group=p_group,false),
      'has_group',account.current_group is not null);
  end if;
  if p_action<>'revoke' and not budget.enabled then return jsonb_build_object('error','disabled'); end if;
  if p_action='revoke' then
    if account.current_group is null then return jsonb_build_object('ok',true); end if;
  else
    select * into target from public.gametime_sync_groups where group_hash=p_group for update;
    exists_group:=found;
    if exists_group and not target.enabled then return jsonb_build_object('error','revoked'); end if;
    if exists_group and target.owner_id is not null then
      -- Possession of an existing group's capability allows linking, not takeover.
      if p_action='rotate' and target.owner_id<>p_owner then return jsonb_build_object('error','exists'); end if;
      return jsonb_build_object('ok',true,'owned',target.owner_id=p_owner);
    end if;
    if p_action='activate' and account.current_group is not null and account.current_group<>p_group then
      return jsonb_build_object('error','other_group');
    end if;
    if p_action='rotate' and exists_group then return jsonb_build_object('error','exists'); end if;
    if not exists_group and not budget.registration_enabled then return jsonb_build_object('error','closed'); end if;
    if not exists_group and (select count(*) from public.gametime_sync_groups)>=10000 then return jsonb_build_object('error','capacity'); end if;
    if not exists_group and account.current_group is null and
      (select count(*) from public.gametime_sync_groups where enabled)>=budget.account_limit then
      return jsonb_build_object('error','capacity');
    end if;
    if account.owner_id is null then
      if not exists_group and (case when budget.admission_day=utc_day then budget.admissions_today else 0 end)>=25 then
        return jsonb_build_object('error','capacity');
      end if;
      insert into public.gametime_sync_accounts(owner_id) values(p_owner) returning * into account;
      if not exists_group then
        update public.gametime_sync_budget set admission_day=utc_day,
          admissions_today=case when admission_day=utc_day then admissions_today+1 else 1 end where singleton;
      end if;
    end if;
    if account.month_start<>utc_month then
      update public.gametime_sync_accounts set month_start=utc_month,creations=0,month_requests=0,month_egress=0
        where owner_id=p_owner returning * into account;
    end if;
    if account.creations>=3 then return jsonb_build_object('error','rotation_limit'); end if;
  end if;
  old_group:=account.current_group;
  if old_group is not null and old_group is distinct from p_group or p_action='revoke' then
    -- Revocation removes only this owner's server ciphertext, never local history.
    with retired as (
      delete from public.gametime_sync_devices where group_hash=old_group returning octet_length(payload) as bytes
    ) select coalesce(sum(bytes),0),count(*) into freed,removed from retired;
    update public.gametime_sync_budget set used_bytes=used_bytes-freed,device_count=device_count-removed where singleton;
    update public.gametime_sync_groups set enabled=false,owner_id=null,used_bytes=0 where group_hash=old_group and owner_id=p_owner;
  end if;
  if p_action='revoke' then
    update public.gametime_sync_accounts set current_group=null where owner_id=p_owner;
    return jsonb_build_object('ok',true);
  end if;
  if exists_group then
    update public.gametime_sync_groups set owner_id=p_owner where group_hash=p_group;
    -- Claiming a legacy group carries over all existing consumption.
    update public.gametime_sync_accounts set current_group=p_group,creations=creations+1,
      month_requests=account.month_requests+case when target.month_start=utc_month then target.month_requests else 0 end,
      month_egress=account.month_egress+case when target.month_start=utc_month then target.month_egress else 0 end,
      day_start=utc_day::timestamptz,
      day_ingress=case when account.day_start=utc_day::timestamptz then account.day_ingress else 0 end
        +case when target.day_start=utc_day::timestamptz then target.day_ingress else 0 end,
      day_egress=case when account.day_start=utc_day::timestamptz then account.day_egress else 0 end
        +case when target.day_start=utc_day::timestamptz then target.day_egress else 0 end where owner_id=p_owner;
  else
    insert into public.gametime_sync_groups(group_hash,owner_id) values(p_group,p_owner);
    update public.gametime_sync_accounts set current_group=p_group,creations=creations+1 where owner_id=p_owner;
  end if;
  return jsonb_build_object('ok',true,'owned',true);
end;
$$;
revoke all on function public.gametime_sync_account(uuid,uuid,text,text) from public,anon,authenticated;
grant execute on function public.gametime_sync_account(uuid,uuid,text,text) to service_role;


commit;
