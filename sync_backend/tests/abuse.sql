-- Bounded rollback probes; never a load test against the public endpoints.
begin;
do $$ begin
 if exists(select 1 from auth.users where id::text like 'a5c0de00-%')
   or exists(select 1 from public.gametime_sync_groups where group_hash like repeat('f0',28)||'%') then raise exception 'Abuse fixture collision'; end if;
end $$;
insert into auth.users(id,email_confirmed_at,is_anonymous) values('a5c0de00-0000-4000-5000-000000000001',now(),false);
insert into auth.identities(provider_id,user_id,identity_data,provider) values('gametime-abuse-rollback','a5c0de00-0000-4000-5000-000000000001','{}','github');
insert into auth.sessions(id,user_id) values('a5c0de00-0000-4000-4000-000000000001','a5c0de00-0000-4000-5000-000000000001');
set local role service_role;
do $$
declare
 g text:=repeat('f0',32); r jsonb; position tid; after_position tid; rows_before bigint;
 u uuid:='a5c0de00-0000-4000-5000-000000000001'; s uuid:='a5c0de00-0000-4000-4000-000000000001';
begin
 insert into public.gametime_sync_groups(group_hash) values(g);
 insert into public.gametime_sync_rate values(date_trunc('minute',now()),'group:'||g,41);
 select ctid into position from public.gametime_sync_rate where bucket=date_trunc('minute',now()) and identity_hash='group:'||g;
 for i in 1..20 loop
   r:=public.gametime_sync_exchange(g,repeat('a0',32),lpad(i::text,32,'0'),'1',null,'{}');
   if r->>'error' is distinct from 'rate' then raise exception 'Saturated group allowed traffic'; end if;
 end loop;
 select ctid into after_position from public.gametime_sync_rate where bucket=date_trunc('minute',now()) and identity_hash='group:'||g;
 if position is distinct from after_position or exists(select 1 from public.gametime_sync_devices where group_hash=g)
   then raise exception 'Rejected traffic rewrote saturated counter or allocated devices'; end if;
 select count(*) into rows_before from public.gametime_sync_accounts;
 for i in 1..12 loop
   r:=public.gametime_sync_account(u,s,'status',g);
   if r->>'has_group' is distinct from 'false' then raise exception 'Management status failed'; end if;
 end loop;
 r:=public.gametime_sync_account(u,s,'activate',g);
 if r->>'error' is distinct from 'rate' or (select count(*) from public.gametime_sync_accounts)<>rows_before then raise exception 'Durable owner throttle bypassed'; end if;
 select ctid into position from public.gametime_sync_rate where bucket=date_trunc('minute',now()) and identity_hash='account:'||u::text;
 r:=public.gametime_sync_account(u,s,'status',g);
 select ctid into after_position from public.gametime_sync_rate where bucket=date_trunc('minute',now()) and identity_hash='account:'||u::text;
 if position is distinct from after_position or r->>'error' is distinct from 'rate' then raise exception 'Denied management rewrote saturated counter'; end if;
end $$;
reset role;
-- Exercise the registry ceiling including retired codes, under a fixed row bound.
insert into public.gametime_sync_groups(group_hash,enabled)
 select repeat('f0',28)||lpad(to_hex(i),8,'0'),false from generate_series(1,10000-(select count(*) from public.gametime_sync_groups)) i;
update public.gametime_sync_budget set registration_enabled=true where singleton;
delete from public.gametime_sync_rate where identity_hash='account:a5c0de00-0000-4000-5000-000000000001';
set local role service_role;
do $$ declare r jsonb; begin
 r:=public.gametime_sync_account('a5c0de00-0000-4000-5000-000000000001','a5c0de00-0000-4000-4000-000000000001','activate',repeat('f1',32));
 if r->>'error' is distinct from 'capacity' then raise exception 'Retired-code registry ceiling bypassed'; end if;
end $$;
reset role;
rollback;
select 'saturated counters cause no tuple rewrites, denied traffic cannot allocate devices/accounts, durable owner throttle and total registry ceiling passed' as checks;
