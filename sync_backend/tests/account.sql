-- Live Postgres/Auth fixtures. Every identity, group and counter is rolled back.
begin;
do $$ begin
  if exists(select 1 from auth.users where id::text like 'a5c0de00-%') then raise exception 'Fixture collision'; end if;
end $$;
insert into auth.users(id,email_confirmed_at,is_anonymous) values
 ('a5c0de00-0000-4000-8000-000000000001',now(),false),
 ('a5c0de00-0000-4000-8000-000000000002',now(),false),
 ('a5c0de00-0000-4000-8000-000000000003',null,false),
 ('a5c0de00-0000-4000-8000-000000000004',now(),false);
insert into auth.sessions(id,user_id) select ('a5c0de00-0000-4000-9000-00000000000'||i)::uuid,('a5c0de00-0000-4000-8000-00000000000'||i)::uuid from generate_series(1,4) i;
insert into auth.identities(provider_id,user_id,identity_data,provider) select 'gametime-rollback-fixture-'||i,('a5c0de00-0000-4000-8000-00000000000'||i)::uuid,'{}',case when i=4 then 'email' else 'github' end from generate_series(1,4) i;
set local role service_role;
do $$
declare u uuid:='a5c0de00-0000-4000-8000-000000000001'; v uuid:='a5c0de00-0000-4000-8000-000000000002';
 s uuid:='a5c0de00-0000-4000-9000-000000000001'; t uuid:='a5c0de00-0000-4000-9000-000000000002';
 a text:=repeat('a5',32); b text:=repeat('b5',32); c text:=repeat('c5',32); d text:=repeat('d5',32);
 ip text:=repeat('f5',32); device text:=repeat('e5',16); r jsonb; baseline integer; bytes bigint;
begin
 if exists(select 1 from public.gametime_sync_groups where group_hash in(a,b,c,d)) then raise exception 'Group fixture collision'; end if;
 select count(*) into baseline from public.gametime_sync_accounts;
 r:=public.gametime_sync_account(u,t,'activate',a);
 if r->>'error' is distinct from 'session' then raise exception 'Cross-user session accepted'; end if;
 r:=public.gametime_sync_account('a5c0de00-0000-4000-8000-000000000003','a5c0de00-0000-4000-9000-000000000003','activate',a);
 if r->>'error' is distinct from 'session' then raise exception 'Unverified account accepted'; end if;
 r:=public.gametime_sync_account('a5c0de00-0000-4000-8000-000000000004','a5c0de00-0000-4000-9000-000000000004','activate',a);
 if r->>'error' is distinct from 'session' then raise exception 'Non-GitHub identity accepted'; end if;
 update public.gametime_sync_budget set registration_enabled=false where singleton;
 r:=public.gametime_sync_account(u,s,'activate',a);
 if r->>'error' is distinct from 'closed' then raise exception 'Registration gate ignored'; end if;
 r:=public.gametime_sync_account(u,s,'status',a);
 if r->>'has_group' is distinct from 'false' or (select count(*) from public.gametime_sync_accounts)<>baseline then raise exception 'Denied/status requests allocated account'; end if;
 update public.gametime_sync_budget set registration_enabled=true,admissions_today=0,account_limit=(select count(*)+1 from public.gametime_sync_groups where enabled) where singleton;
 r:=public.gametime_sync_account(u,s,'activate',a);
 if r->>'owned' is distinct from 'true' then raise exception 'Verified admission failed: %',r; end if;
 r:=public.gametime_sync_account(v,t,'activate',a);
 if r->>'ok' is distinct from 'true' or r->>'owned' is distinct from 'false' then raise exception 'Capability linking broken'; end if;
 if exists(select 1 from public.gametime_sync_accounts where owner_id=v) then raise exception 'Link took ownership'; end if;
 r:=public.gametime_sync_account(v,t,'rotate',a);
 if r->>'error' is distinct from 'exists' then raise exception 'Ownership takeover'; end if;
 r:=public.gametime_sync_account(v,t,'activate',b);
 if r->>'error' is distinct from 'capacity' then raise exception 'Capacity gate bypassed'; end if;
 update public.gametime_sync_accounts set month_requests=60000 where owner_id=u;
 r:=public.gametime_sync_exchange(a,ip,device,'1',repeat('A',44),'{}');
 if r->>'error' is distinct from 'rate' then raise exception 'Owner request quota bypassed'; end if;
 update public.gametime_sync_accounts set month_requests=100,day_ingress=500,month_ingress=1000 where owner_id=u;
 r:=public.gametime_sync_exchange(a,ip,device,'1',repeat('A',44),'{}');
 if r ? 'error' then raise exception 'Owned exchange failed: %',r; end if;
 r:=public.gametime_sync_account(u,s,'activate',b);
 if r->>'error' is distinct from 'other_group' then raise exception 'Implicit destructive rotation'; end if;
 r:=public.gametime_sync_account(u,s,'rotate',b);
 if r->>'ok' is distinct from 'true' then raise exception 'Explicit rotation failed: %',r; end if;
 if public.gametime_sync_authorize(a) or exists(select 1 from public.gametime_sync_devices where group_hash=a) then raise exception 'Old code/ciphertext survived revocation'; end if;
 if (select month_requests from public.gametime_sync_accounts where owner_id=u)<>101 or (select day_ingress from public.gametime_sync_accounts where owner_id=u)<>544
   or (select month_ingress from public.gametime_sync_accounts where owner_id=u)<>1044 then raise exception 'Rotation reset owner quotas'; end if;
 r:=public.gametime_sync_account(u,s,'rotate',a);
 if r->>'error' is distinct from 'revoked' then raise exception 'Retired code reused'; end if;
 r:=public.gametime_sync_account(u,s,'rotate',c);
 if r->>'ok' is distinct from 'true' then raise exception 'Third monthly creation failed'; end if;
 r:=public.gametime_sync_account(u,s,'rotate',d);
 if r->>'error' is distinct from 'rotation_limit' then raise exception 'Rotation quota bypass'; end if;
 update public.gametime_sync_budget set account_limit=account_limit+1,admissions_today=25 where singleton;
 r:=public.gametime_sync_account(v,t,'activate',d);
 if r->>'error' is distinct from 'capacity' then raise exception 'Daily admission limit bypass'; end if;
 update public.gametime_sync_budget set admissions_today=0 where singleton;
 insert into public.gametime_sync_groups(group_hash,month_requests,day_ingress) values(d,7,900);
 r:=public.gametime_sync_account(v,t,'activate',d);
 if r->>'owned' is distinct from 'true' or (select month_requests from public.gametime_sync_accounts where owner_id=v)<>7 or (select day_ingress from public.gametime_sync_accounts where owner_id=v)<>900 then raise exception 'Legacy claim lost consumption'; end if;
 r:=public.gametime_sync_account(v,t,'revoke',null);
 if r->>'ok' is distinct from 'true' or public.gametime_sync_authorize(d) or not public.gametime_sync_authorize(c) then raise exception 'Revocation isolation failed'; end if;
 select coalesce(sum(octet_length(payload)),0) into bytes from public.gametime_sync_devices;
 if (select used_bytes from public.gametime_sync_budget where singleton)<>bytes or (select device_count from public.gametime_sync_budget where singleton)<>(select count(*) from public.gametime_sync_devices) then raise exception 'Storage accounting drift'; end if;
end $$;
reset role;
delete from auth.sessions where id='a5c0de00-0000-4000-9000-000000000001';
update auth.users set banned_until=now()+interval '1 day' where id='a5c0de00-0000-4000-8000-000000000001';
set local role service_role;
do $$ declare r jsonb; begin
 r:=public.gametime_sync_account('a5c0de00-0000-4000-8000-000000000001','a5c0de00-0000-4000-9000-000000000001','status',repeat('c5',32));
 if r->>'error' is distinct from 'session' then raise exception 'Revoked session accepted'; end if;
 r:=public.gametime_sync_exchange(repeat('c5',32),repeat('f5',32),repeat('e5',16),'2',null,'{}');
 if r->>'error' is distinct from 'admission' then raise exception 'Banned owner still synchronized'; end if;
 if has_table_privilege('authenticated','public.gametime_sync_accounts','select') or has_function_privilege('authenticated','public.gametime_sync_account(uuid,uuid,text,text)','execute') then raise exception 'Public access to account ledger'; end if;
end $$;
reset role;
rollback;
select 'verified identity/session, ownership, closed/capacity/day gates, linking, rotation/revocation isolation, persistent owner quotas, bans, grants and byte accounting passed' as checks;
