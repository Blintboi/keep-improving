begin;
set local role service_role;
do $$
declare g text:=repeat('f3',32); ip text:=repeat('a3',32); device text:=repeat('b3',16); r jsonb; before_bytes bigint;
begin
 if exists(select 1 from public.gametime_sync_groups where group_hash=g) then raise exception 'Upload fixture collision'; end if;
 insert into public.gametime_sync_groups(group_hash) values(g);
 select used_bytes into before_bytes from public.gametime_sync_budget where singleton;
 update public.gametime_sync_budget set month_ingress=1073741824 where singleton;
 r:=public.gametime_sync_exchange(g,ip,device,'1',repeat('A',44),'{}');
 if r->>'error' is distinct from 'rate' then raise exception 'Global monthly write budget bypassed'; end if;
 update public.gametime_sync_budget set month_ingress=0,ingress_day_start=date_trunc('day',now() at time zone 'UTC') at time zone 'UTC',day_ingress=67108864 where singleton;
 r:=public.gametime_sync_exchange(g,ip,device,'1',repeat('A',44),'{}');
 if r->>'error' is distinct from 'rate' then raise exception 'Global daily write budget bypassed'; end if;
 update public.gametime_sync_budget set day_ingress=0 where singleton;
 update public.gametime_sync_groups set month_ingress=67108864 where group_hash=g;
 r:=public.gametime_sync_exchange(g,ip,device,'1',repeat('A',44),'{}');
 if r->>'error' is distinct from 'rate' then raise exception 'Group fair write budget bypassed'; end if;
 if (select used_bytes from public.gametime_sync_budget where singleton)<>before_bytes or exists(select 1 from public.gametime_sync_devices where group_hash=g) then raise exception 'Denied overwrite changed storage'; end if;
 delete from public.gametime_sync_rate where identity_hash='device:'||g||':'||device;
 update public.gametime_sync_groups set month_ingress=0 where group_hash=g;
 r:=public.gametime_sync_exchange(g,ip,device,'1',repeat('A',44),'{}');
 if r ? 'error' or (select month_ingress from public.gametime_sync_budget where singleton)<>44
   or (select month_ingress from public.gametime_sync_groups where group_hash=g)<>44 then raise exception 'Accepted upload not accounted'; end if;
 r:=public.gametime_sync_exchange(g,ip,device,'1',repeat('B',44),'{}');
 if r ? 'error' or (select month_ingress from public.gametime_sync_budget where singleton)<>44 then raise exception 'Stale overwrite consumed upload budget'; end if;
end $$;
reset role;
rollback;
select 'global daily/monthly overwrite budgets, fair group allowance, exact upload counters and stale-revision behavior passed' as checks;
