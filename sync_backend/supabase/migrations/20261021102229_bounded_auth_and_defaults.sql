begin;

-- New app objects must not accidentally become client APIs between migrations.
-- PostgreSQL's global PUBLIC function default must be revoked globally, too.
alter default privileges for role postgres revoke execute on functions from public;
alter default privileges for role postgres in schema public revoke all on tables from public,anon,authenticated;
alter default privileges for role postgres in schema public revoke all on sequences from public,anon,authenticated;
alter default privileges for role postgres in schema public revoke all on functions from public,anon,authenticated,service_role;

create table public.gametime_auth_usage (
  owner_id uuid primary key references auth.users(id) on delete cascade,
  minute_start timestamptz not null,
  minute_issues integer not null check(minute_issues between 0 and 12),
  day_start date not null,
  day_issues integer not null check(day_issues between 0 and 120)
);
alter table public.gametime_auth_usage enable row level security;
revoke all on public.gametime_auth_usage from public,anon,authenticated,service_role;
grant select,insert,update on public.gametime_auth_usage to supabase_auth_admin;
create policy auth_usage_read on public.gametime_auth_usage for select to supabase_auth_admin using(true);
create policy auth_usage_insert on public.gametime_auth_usage for insert to supabase_auth_admin with check(true);
create policy auth_usage_update on public.gametime_auth_usage for update to supabase_auth_admin using(true) with check(true);

alter table public.gametime_sync_budget
  add column auth_token_day date not null default (now() at time zone 'UTC')::date,
  add column auth_tokens_today integer not null default 0 check(auth_tokens_today between 0 and 1000);
grant select(auth_token_day,auth_tokens_today),update(auth_token_day,auth_tokens_today)
  on public.gametime_sync_budget to supabase_auth_admin;

create function public.gametime_access_token_guard(event jsonb)
returns jsonb language plpgsql security invoker set search_path='' set lock_timeout='2s' as $$
declare
  owner uuid; session uuid; claims jsonb:=event->'claims';
  usage public.gametime_auth_usage%rowtype;
  utc_day date:=(now() at time zone 'UTC')::date;
  utc_minute timestamptz:=date_trunc('minute',now());
  allowed boolean; token_day date; total integer; issued integer; minute_issued integer;
begin
  -- Auth invokes this hook inside the same transaction as session/token creation.
  -- A rejected issue therefore rolls back the newly created session/refresh token.
  if event->>'authentication_method' not in ('oauth','token_refresh')
    or coalesce(event->>'authentication_method','')=''
    or coalesce(event->>'user_id','') !~ '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$'
    or coalesce(claims->>'session_id','') !~ '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$'
    or claims->>'sub' is distinct from event->>'user_id'
    or claims->>'role' is distinct from 'authenticated' then
    return jsonb_build_object('error',jsonb_build_object('http_code',403,'message','Verified GitHub sign-in is required.'));
  end if;
  owner:=(event->>'user_id')::uuid; session:=(claims->>'session_id')::uuid;
  if not exists(select 1 from auth.users u join auth.sessions s on s.user_id=u.id
    where u.id=owner and s.id=session and (s.not_after is null or s.not_after>now())
      and u.email_confirmed_at is not null and not coalesce(u.is_anonymous,false)
      and u.deleted_at is null and (u.banned_until is null or u.banned_until<=now())
      and exists(select 1 from auth.identities i where i.user_id=u.id and i.provider='github')) then
    return jsonb_build_object('error',jsonb_build_object('http_code',403,'message','Verified GitHub sign-in is required.'));
  end if;
  select enabled,auth_token_day,auth_tokens_today into allowed,token_day,total
    from public.gametime_sync_budget where singleton for update;
  if not found or not allowed then
    return jsonb_build_object('error',jsonb_build_object('http_code',503,'message','Cloud account access is temporarily unavailable.'));
  end if;
  -- Row lock serializes concurrent sign-ins before counting committed sessions.
  -- Include the session just created by Auth. No managed Auth-table triggers.
  if (select count(*) from auth.sessions where user_id=owner)>10 then
    return jsonb_build_object('error',jsonb_build_object('http_code',429,'message','Too many signed-in devices. Sign out of unused devices first.'));
  end if;
  insert into public.gametime_auth_usage values(owner,utc_minute,0,utc_day,0)
    on conflict(owner_id) do nothing;
  select * into usage from public.gametime_auth_usage where owner_id=owner for update;
  issued:=case when usage.day_start=utc_day then usage.day_issues else 0 end;
  minute_issued:=case when usage.minute_start=utc_minute then usage.minute_issues else 0 end;
  total:=case when token_day=utc_day then total else 0 end;
  if issued>=120 or minute_issued>=12 or total>=1000 then
    return jsonb_build_object('error',jsonb_build_object('http_code',429,'message','Too many account sign-ins or refreshes. Try again later.'));
  end if;
  update public.gametime_auth_usage set minute_start=utc_minute,minute_issues=minute_issued+1,
    day_start=utc_day,day_issues=issued+1 where owner_id=owner;
  update public.gametime_sync_budget set auth_token_day=utc_day,auth_tokens_today=total+1 where singleton;
  -- User-editable metadata is neither needed nor trusted in an access token.
  -- Keep the required standard claims, including session_id for revocation.
  return jsonb_build_object('claims',claims-'user_metadata'-'app_metadata');
end $$;
revoke all on function public.gametime_access_token_guard(jsonb) from public,anon,authenticated,service_role;
grant execute on function public.gametime_access_token_guard(jsonb) to supabase_auth_admin;

commit;
