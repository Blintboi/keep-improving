-- Probe hook logic transactionally; inspect Auth role grants and RLS separately.
-- Managed postgres cannot SET ROLE supabase_auth_admin; verify that path through Auth.
begin;
update public.gametime_sync_budget set registration_enabled=true,auth_signup_total=0,auth_signups_today=0,
 auth_signup_day=(now() at time zone 'UTC')::date where singleton;
do $$ declare event jsonb:='{"user":{"email":"fixture@example.test","app_metadata":{"provider":"github"}}}'; r jsonb; begin
 r:=public.gametime_before_user_created('{"user":{"email":"fixture@example.test","user_metadata":{"provider":"github"},"app_metadata":{"provider":"email"}}}');
 if r->'error'->>'http_code' is distinct from '403' then raise exception 'Metadata spoof bypassed provider check'; end if;
 for i in 1..5 loop
   r:=public.gametime_before_user_created(event);
   if r is distinct from '{}'::jsonb then raise exception 'Verified signup blocked: %',r; end if;
 end loop;
 r:=public.gametime_before_user_created(event);
 if r->'error'->>'http_code' is distinct from '403' or (select auth_signup_total from public.gametime_sync_budget where singleton)<>5 then raise exception 'Daily Auth allocation limit failed'; end if;
 if has_column_privilege('supabase_auth_admin','public.gametime_sync_budget','enabled','update') or has_function_privilege('authenticated','public.gametime_before_user_created(jsonb)','execute') then raise exception 'Excess hook privilege'; end if;
end $$;
update public.gametime_sync_budget set auth_signup_total=50,auth_signups_today=0 where singleton;
do $$ declare r jsonb; begin
 r:=public.gametime_before_user_created('{"user":{"email":"fixture@example.test","app_metadata":{"provider":"github"}}}');
 if r->'error'->>'http_code' is distinct from '403' then raise exception 'Lifetime Auth ceiling bypassed'; end if;
end $$;
update public.gametime_sync_budget set auth_signup_total=0,registration_enabled=false where singleton;
do $$ declare r jsonb; begin
 r:=public.gametime_before_user_created('{"user":{"email":"fixture@example.test","app_metadata":{"provider":"github"}}}');
 if r->'error'->>'http_code' is distinct from '403' then raise exception 'Closed signup gate bypassed'; end if;
end $$;
rollback;
select 'Auth column grants, provider spoofing, five daily reservations, fifty total ceiling and closed signup gate passed' as checks;
