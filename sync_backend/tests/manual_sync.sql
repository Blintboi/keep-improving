-- Synthetic identities only. Schema, payloads and accounting are rolled back.
begin;
do $$ begin
  if exists(select 1 from auth.users where id='a5c0de00-0000-4000-8000-000000000012') then raise exception 'Manual-sync fixture collision'; end if;
  if exists(select 1 from public.gametime_sync_groups where group_hash in(repeat('d212',16),repeat('e212',16),repeat('f212',16))) then raise exception 'Manual-sync group collision'; end if;
end $$;
insert into auth.users(id,email_confirmed_at,is_anonymous) values('a5c0de00-0000-4000-8000-000000000012',now(),false);
insert into auth.sessions(id,user_id) values('a5c0de00-0000-4000-9000-000000000012','a5c0de00-0000-4000-8000-000000000012');
insert into auth.identities(provider_id,user_id,identity_data,provider) values('gametime-manual-sync-rollback','a5c0de00-0000-4000-8000-000000000012','{}','github');
set local role service_role;
do $$
declare
  u uuid:='a5c0de00-0000-4000-8000-000000000012'; s uuid:='a5c0de00-0000-4000-9000-000000000012';
  g text:=repeat('d212',16); h text:=repeat('e212',16); probe text:=repeat('f212',16);
  ip text:=repeat('a212',16); d text:=repeat('b212',8); other text:=repeat('c212',8);
  r jsonb; tuple_before tid; hits_before integer; utc_day date:=(now() at time zone 'UTC')::date;
begin
  if has_function_privilege('anon','public.gametime_sync_exchange_limited(text,text,text,text,text,jsonb)','execute')
    or has_function_privilege('authenticated','public.gametime_sync_exchange_limited(text,text,text,text,text,jsonb)','execute') then
    raise exception 'Manual RPC exposed to client roles';
  end if;
  r:=public.gametime_sync_exchange_limited(g,ip,d,'1',repeat('A',44),'{}');
  if r->>'error' is distinct from 'admission' then raise exception 'Unknown group accepted'; end if;
  update public.gametime_sync_budget set registration_enabled=true,enabled=true,admissions_today=0,
    account_limit=greatest(account_limit,(select count(*)+1 from public.gametime_sync_groups where enabled)) where singleton;
  r:=public.gametime_sync_account(u,s,'activate',g);
  if r->>'owned' is distinct from 'true' then raise exception 'Fixture admission failed: %',r; end if;
  r:=public.gametime_sync_exchange_limited(g,ip,d,'1',repeat('A',44),'{}');
  if r->>'need_upload' is distinct from 'false' then raise exception 'Initial exchange failed: %',r; end if;
  select ctid,sync_hits into tuple_before,hits_before from public.gametime_sync_groups where group_hash=g;
  for i in 1..3 loop
    r:=public.gametime_sync_exchange_limited(g,repeat('0',64),d,'2',repeat('B',44),'{}');
    if r->>'error' is distinct from 'cooldown' or (r->>'retry_after')::int<>600 then raise exception 'Durable cooldown bypass: %',r; end if;
  end loop;
  if (select ctid from public.gametime_sync_groups where group_hash=g)<>tuple_before
    or (select sync_hits from public.gametime_sync_groups where group_hash=g)<>hits_before
    or (select revision from public.gametime_sync_devices where group_hash=g and device_id=d)<>1 then
    raise exception 'Rejected requests wrote tuples, counters or payload';
  end if;
  update public.gametime_sync_accounts set sync_hits=19,sync_day=utc_day where owner_id=u;
  r:=public.gametime_sync_exchange_limited(g,ip,other,'1',repeat('A',44),'{}');
  if r ? 'error' or jsonb_array_length(r->'snapshots')<>1 then raise exception 'Other device blocked or isolated incorrectly: %',r; end if;
  r:=public.gametime_sync_exchange_limited(g,ip,repeat('1',32),'1',repeat('A',44),'{}');
  if r->>'error' is distinct from 'rate' then raise exception 'Daily owner limit bypassed with a new device'; end if;
  r:=public.gametime_sync_account(u,s,'rotate',h);
  if r->>'ok' is distinct from 'true' then raise exception 'Rotation failed: %',r; end if;
  r:=public.gametime_sync_exchange_limited(h,ip,d,'1',repeat('A',44),'{}');
  if r->>'error' is distinct from 'rate' then raise exception 'Rotation reset daily owner quota'; end if;
  update public.gametime_sync_accounts set sync_day=utc_day-1,sync_hits=20,month_requests=599 where owner_id=u;
  r:=public.gametime_sync_exchange_limited(h,ip,d,'1',repeat('A',44),'{}');
  if r ? 'error' then raise exception 'Next UTC day failed to reset guard: %',r; end if;
  r:=public.gametime_sync_exchange_limited(h,ip,other,'1',repeat('A',44),'{}');
  if r->>'error' is distinct from 'rate' then raise exception 'Monthly 600 limit bypassed'; end if;
  if (select sync_hits from public.gametime_sync_accounts where owner_id=u)<>1 then raise exception 'Daily reset incorrect'; end if;
  insert into public.gametime_sync_groups(group_hash) values(probe);
  r:=public.gametime_sync_exchange_limited(probe,ip,d,'1',null,'{}');
  if r->>'need_upload' is distinct from 'true' then raise exception 'Missing-copy probe failed'; end if;
  r:=public.gametime_sync_exchange_limited(probe,ip,d,'1',repeat('A',44),'{}');
  if r->>'need_upload' is distinct from 'false' then raise exception 'Repair upload was blocked'; end if;
  update public.gametime_sync_devices set next_sync_at=now()-interval '1 second' where group_hash=probe;
  r:=public.gametime_sync_exchange_limited(probe,ip,d,'2',repeat('B',44),'{}');
  if r ? 'error' then raise exception 'Cooldown did not expire: %',r; end if;
  update public.gametime_sync_groups set sync_hits=20,sync_day=utc_day where group_hash=probe;
  r:=public.gametime_sync_exchange_limited(probe,ip,other,'1',null,'{}');
  if r->>'error' is distinct from 'rate' then raise exception 'Unowned-group daily limit bypassed'; end if;
end $$;
reset role;
rollback;
select 'durable cooldown, write-free rejection, daily/monthly owner and group limits, rotation, UTC reset, repair and grants passed' as checks;
