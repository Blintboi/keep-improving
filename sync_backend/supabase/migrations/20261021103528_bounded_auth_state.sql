begin;
-- These small invoker triggers protect Auth-owned writes as well as app RPCs.
-- They must be rechecked after provider schema upgrades; no Auth table is replaced.
create function public.gametime_auth_metadata_guard() returns trigger
language plpgsql security invoker set search_path='' as $$
begin
 if octet_length(coalesce(new.raw_user_meta_data,'{}')::text)
   +octet_length(coalesce(new.raw_app_meta_data,'{}')::text)>32768 then
   raise exception using errcode='23514',message='Account metadata is too large.';
 end if;
 return new;
end $$;
revoke all on function public.gametime_auth_metadata_guard() from public,anon,authenticated,service_role;
grant execute on function public.gametime_auth_metadata_guard() to supabase_auth_admin;
create trigger gametime_bound_metadata before insert or update of raw_user_meta_data,raw_app_meta_data
 on auth.users for each row execute function public.gametime_auth_metadata_guard();

create function public.gametime_auth_state_guard() returns trigger
language plpgsql security invoker set search_path='' set lock_timeout='2s' as $$
begin
 if octet_length(to_jsonb(new)::text)>16384 then
   raise exception using errcode='23514',message='Authentication state is too large.';
 end if;
 if tg_op='INSERT' then
   -- No attacker-keyed counter rows or write on denial. Serializing this tiny
   -- admission check closes concurrent insertion races before allocating rows.
   if not pg_try_advisory_xact_lock(1196707149,1) then
     raise exception using errcode='54000',message='Authentication is busy. Try again later.';
   end if;
   if (select count(*) from (
     select id from auth.flow_state union all select id from auth.oauth_client_states limit 1000
   ) states)>=1000 then
     raise exception using errcode='54000',message='Authentication capacity is temporarily full.';
   end if;
 end if;
 return new;
end $$;
revoke all on function public.gametime_auth_state_guard() from public,anon,authenticated,service_role;
grant execute on function public.gametime_auth_state_guard() to supabase_auth_admin;
create trigger gametime_bound_flow_state before insert or update on auth.flow_state
 for each row execute function public.gametime_auth_state_guard();
create trigger gametime_bound_oauth_state before insert or update on auth.oauth_client_states
 for each row execute function public.gametime_auth_state_guard();

create function public.gametime_auth_state_cleanup() returns jsonb
language plpgsql security invoker set search_path='' set lock_timeout='2s' as $$
declare flows integer; clients integer;
begin
 perform pg_advisory_xact_lock(1196707149,1);
 -- The app's login timeout is three minutes. One hour also retains a generous
 -- margin beyond the provider's default flow/code expiry. Never touch sessions.
 delete from auth.flow_state where id in (
   select id from auth.flow_state where created_at<now()-interval '1 hour' order by created_at limit 1000
 );
 get diagnostics flows=row_count;
 delete from auth.oauth_client_states where id in (
   select s.id from auth.oauth_client_states s where s.created_at<now()-interval '1 hour'
     and not exists(select 1 from auth.flow_state f where f.oauth_client_state_id=s.id)
   order by s.created_at limit 1000
 );
 get diagnostics clients=row_count;
 return jsonb_build_object('flows',flows,'clients',clients);
end $$;
revoke all on function public.gametime_auth_state_cleanup() from public,anon,authenticated,service_role;
select cron.schedule('gametime-auth-state-retention','*/5 * * * *',
 $job$select public.gametime_auth_state_cleanup(); delete from cron.job_run_details where jobid in (select jobid from cron.job where jobname='gametime-auth-state-retention') and end_time<now()-interval '7 days';$job$);
commit;
