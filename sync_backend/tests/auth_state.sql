begin;
do $$ begin
 if exists(select 1 from auth.flow_state where id::text like 'a5c0de00-%') or exists(select 1 from auth.oauth_client_states where id::text like 'a5c0de00-%')
   or exists(select 1 from auth.users where id::text like 'a5c0de00-%') then raise exception 'Auth state fixture collision'; end if;
end $$;
insert into auth.users(id,email_confirmed_at,raw_user_meta_data) values('a5c0de00-0000-4000-3000-000000000001',now(),'{"fixture":true}');
do $$ begin
 begin
  update auth.users set raw_user_meta_data=jsonb_build_object('junk',repeat('x',32768)) where id='a5c0de00-0000-4000-3000-000000000001';
  raise exception 'Oversized account metadata accepted';
 exception when check_violation then null; end;
 begin
  insert into auth.oauth_client_states(id,provider_type,code_verifier,created_at) values('a5c0de00-0000-4000-2000-000000000001','github',repeat('x',16384),now());
  raise exception 'Oversized OAuth state accepted';
 exception when check_violation then null; end;
end $$;
-- The trigger checks the combined table count, including the orphan-state path.
insert into auth.oauth_client_states(id,provider_type,code_verifier,created_at)
 select ('a5c0de00-0000-4000-2000-'||lpad(i::text,12,'0'))::uuid,'github','fixture',now()-interval '2 hours'
 from generate_series(1,1000-(select count(*) from auth.flow_state)-(select count(*) from auth.oauth_client_states)) i;
do $$ begin
 begin
  insert into auth.oauth_client_states(id,provider_type,code_verifier,created_at) values('a5c0de00-0000-4000-1000-000000000001','github','fixture',now());
  raise exception 'OAuth state ceiling bypassed';
 exception when program_limit_exceeded then null; end;
 begin
  insert into auth.flow_state(id,provider_type,code_challenge_method,code_challenge,authentication_method,created_at,updated_at)
   values('a5c0de00-0000-4000-1000-000000000002','github','s256','fixture','oauth',now(),now());
  raise exception 'Combined flow state ceiling bypassed';
 exception when program_limit_exceeded then null; end;
end $$;
select public.gametime_auth_state_cleanup();
do $$ begin
 if exists(select 1 from auth.oauth_client_states where id::text like 'a5c0de00-%') then raise exception 'Expired OAuth state not cleaned'; end if;
end $$;
insert into auth.oauth_client_states(id,provider_type,code_verifier,created_at) values('a5c0de00-0000-4000-1000-000000000003','github','fixture',now());
select public.gametime_auth_state_cleanup();
do $$ begin
 if not exists(select 1 from auth.oauth_client_states where id='a5c0de00-0000-4000-1000-000000000003') then raise exception 'Current OAuth state removed'; end if;
 if has_function_privilege('service_role','public.gametime_auth_state_cleanup()','execute') or has_function_privilege('authenticated','public.gametime_auth_state_guard()','execute') then raise exception 'Public Auth control access'; end if;
end $$;
rollback;
select 'metadata/state byte caps, combined pre-auth state ceiling, orphan-state path, expiry cleanup and active-flow preservation passed' as checks;
