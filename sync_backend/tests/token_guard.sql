begin;
do $$ begin
 if exists(select 1 from auth.users where id='a5c0de00-0000-4000-7000-000000000001') then raise exception 'Token fixture collision'; end if;
end $$;
insert into auth.users(id,aud,role,email,email_confirmed_at,raw_app_meta_data,is_anonymous)
 values('a5c0de00-0000-4000-7000-000000000001','authenticated','authenticated','gametime-token-fixture@example.invalid',now(),'{"provider":"github"}',false);
insert into auth.identities(provider_id,user_id,identity_data,provider)
 values('gametime-token-rollback','a5c0de00-0000-4000-7000-000000000001','{}','github');
insert into auth.sessions(id,user_id)
 values('a5c0de00-0000-4000-6000-000000000001','a5c0de00-0000-4000-7000-000000000001');
update public.gametime_sync_budget set enabled=true,auth_token_day=(now() at time zone 'UTC')::date,auth_tokens_today=0 where singleton;
do $$
declare
 u uuid:='a5c0de00-0000-4000-7000-000000000001';
 s uuid:='a5c0de00-0000-4000-6000-000000000001';
 event jsonb; r jsonb; before_rows bigint;
begin
 event:=jsonb_build_object('user_id',u,'authentication_method','oauth','claims',jsonb_build_object('sub',u,'session_id',s,'role','authenticated',
 'iss','https://example.invalid/auth/v1','aud','authenticated','iat',1,'exp',2000000000,'aal','aal1','email','fixture@example.invalid','phone','','is_anonymous',false,
 'user_metadata',jsonb_build_object('admin',true,'junk',repeat('x',20000)),'app_metadata',jsonb_build_object('provider','github')));
 if has_function_privilege('anon','public.gametime_access_token_guard(jsonb)','execute')
   or has_function_privilege('authenticated','public.gametime_access_token_guard(jsonb)','execute')
   or has_function_privilege('service_role','public.gametime_access_token_guard(jsonb)','execute')
   or not has_function_privilege('supabase_auth_admin','public.gametime_access_token_guard(jsonb)','execute')
   or not has_table_privilege('supabase_auth_admin','public.gametime_auth_usage','insert')
   or has_table_privilege('authenticated','public.gametime_auth_usage','select') then raise exception 'Auth hook grants incorrect'; end if;
 r:=public.gametime_access_token_guard(jsonb_set(event,'{authentication_method}','"password"'));
 if r->'error'->>'http_code' is distinct from '403' then raise exception 'Unexpected method allowed'; end if;
 r:=public.gametime_access_token_guard(jsonb_set(event,'{claims,sub}','"00000000-0000-4000-8000-000000000000"'));
 if r->'error'->>'http_code' is distinct from '403' then raise exception 'Spoofed subject allowed'; end if;
 if exists(select 1 from public.gametime_auth_usage where owner_id=u) then raise exception 'Invalid identity allocated a ledger'; end if;
 for i in 1..12 loop
   r:=public.gametime_access_token_guard(event);
   if r->'claims'->>'session_id' is distinct from s::text or r->'claims' ? 'user_metadata' or r->'claims' ? 'app_metadata'
     or r->'claims'->>'iss' is distinct from 'https://example.invalid/auth/v1' then raise exception 'Claims contract failed'; end if;
 end loop;
 r:=public.gametime_access_token_guard(event);
 if r->'error'->>'http_code' is distinct from '429' or (select day_issues from public.gametime_auth_usage where owner_id=u)<>12 then raise exception 'Minute issuance ceiling failed'; end if;
 update public.gametime_auth_usage set minute_start=now()-interval '1 day',day_issues=120 where owner_id=u;
 r:=public.gametime_access_token_guard(event);
 if r->'error'->>'http_code' is distinct from '429' then raise exception 'Daily issuance ceiling failed'; end if;
 update public.gametime_auth_usage set day_start=(now() at time zone 'UTC')::date-1 where owner_id=u;
 r:=public.gametime_access_token_guard(jsonb_set(event,'{authentication_method}','"token_refresh"'));
 if r->'claims'->>'sub' is distinct from u::text or (select day_issues from public.gametime_auth_usage where owner_id=u)<>1 then raise exception 'Next day refresh failed'; end if;
 update public.gametime_sync_budget set auth_tokens_today=1000 where singleton;
 r:=public.gametime_access_token_guard(event);
 if r->'error'->>'http_code' is distinct from '429' then raise exception 'Global issuance budget failed'; end if;
 update public.gametime_sync_budget set auth_tokens_today=0 where singleton;
 insert into auth.sessions(id,user_id) select ('a5c0de00-0000-4000-6000-'||lpad(i::text,12,'0'))::uuid,u from generate_series(2,11) i;
 r:=public.gametime_access_token_guard(event);
 if r->'error'->>'http_code' is distinct from '429' then raise exception 'Session ceiling failed'; end if;
 delete from auth.sessions where id='a5c0de00-0000-4000-6000-000000000011';
 r:=public.gametime_access_token_guard(event);
 if r->'claims'->>'sub' is distinct from u::text then raise exception 'Tenth session blocked'; end if;
 update auth.users set banned_until=now()+interval '1 day' where id=u;
 r:=public.gametime_access_token_guard(event);
 if r->'error'->>'http_code' is distinct from '403' then raise exception 'Banned identity refreshed'; end if;
end $$;
-- Check both the global function ACL and schema-specific explicit defaults.
do $$ begin
 if not exists(select 1 from pg_default_acl where defaclrole='postgres'::regrole and defaclnamespace=0 and defaclobjtype='f')
   or exists(select 1 from pg_default_acl d cross join lateral aclexplode(d.defaclacl) a
     where d.defaclrole='postgres'::regrole
       and (d.defaclnamespace=0 and d.defaclobjtype='f' and a.grantee=0
         or d.defaclnamespace='public'::regnamespace and a.grantee in (0,'anon'::regrole::oid,'authenticated'::regrole::oid)
         or d.defaclnamespace='public'::regnamespace and d.defaclobjtype='f' and a.grantee='service_role'::regrole::oid))
   then raise exception 'Unsafe new-object defaults'; end if;
end $$;
select 'provider/session validation, bounded token issuance and ledger, metadata-free claims, day rollover, bans and safe future object defaults passed' as checks;
rollback;
