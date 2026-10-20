begin;
-- Bound Auth storage too, before a provider can allocate a new user/session.
alter table public.gametime_sync_budget
  add column auth_signup_total integer not null default 0,
  add column auth_signup_day date not null default (now() at time zone 'UTC')::date,
  add column auth_signups_today integer not null default 0;

grant usage on schema public to supabase_auth_admin;
grant select(singleton,enabled,registration_enabled,auth_signup_total,auth_signup_day,auth_signups_today)
  on public.gametime_sync_budget to supabase_auth_admin;
grant update(auth_signup_total,auth_signup_day,auth_signups_today) on public.gametime_sync_budget to supabase_auth_admin;
create policy auth_signup_budget_read on public.gametime_sync_budget for select to supabase_auth_admin using(singleton);
create policy auth_signup_budget_write on public.gametime_sync_budget for update to supabase_auth_admin using(singleton) with check(singleton);

create function public.gametime_before_user_created(event jsonb)
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
 if not found or not allowed or not opened or total>=50 or (day=utc_day and today>=5) then
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
commit;
