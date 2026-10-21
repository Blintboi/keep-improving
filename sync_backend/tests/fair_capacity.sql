begin;
set local role service_role;
do $$
declare
 g text:=repeat('f2',32); ip text:=repeat('a2',32); device text:=repeat('b2',16); r jsonb;
begin
 if exists(select 1 from public.gametime_sync_groups where group_hash like repeat('f2',28)||'%') then raise exception 'Fair capacity fixture collision'; end if;
 insert into public.gametime_sync_groups(group_hash) values(g);
 insert into public.gametime_sync_groups(group_hash)
  select repeat('f2',28)||lpad(to_hex(i),8,'0') from generate_series(1,100-(select count(*) from public.gametime_sync_groups where enabled)) i;
 update public.gametime_sync_groups set month_start=date_trunc('month',now() at time zone 'UTC') at time zone 'UTC',month_requests=3499 where group_hash=g;
 r:=public.gametime_sync_exchange(g,ip,device,'1',null,'{}');
 if r ? 'error' then raise exception 'Hundred-group fair allowance blocked early: %',r; end if;
 r:=public.gametime_sync_exchange(g,ip,device,'1',null,'{}');
 if r->>'error' is distinct from 'rate' then raise exception 'Hundred-group fair allowance exceeded'; end if;
 update public.gametime_sync_groups set enabled=false where group_hash like repeat('f2',28)||'%' and group_hash<>g;
 update public.gametime_sync_groups set month_requests=11999 where group_hash=g;
 r:=public.gametime_sync_exchange(g,ip,device,'1',null,'{}');
 if r ? 'error' then raise exception 'Small-population allowance not restored'; end if;
 r:=public.gametime_sync_exchange(g,ip,device,'1',null,'{}');
 if r->>'error' is distinct from 'rate' then raise exception 'Small-population cap bypassed'; end if;
 update public.gametime_sync_groups set month_requests=0,used_bytes=2097152 where group_hash=g;
 r:=public.gametime_sync_exchange(g,ip,device,'1',repeat('A',44),'{}');
 if r->>'error' is distinct from 'quota' then raise exception 'Fair storage cap bypassed'; end if;
 update public.gametime_sync_groups set used_bytes=0,month_egress=134217728 where group_hash=g;
 r:=public.gametime_sync_exchange(g,ip,device,'1',null,'{}');
 if r->>'error' is distinct from 'rate' then raise exception 'Fair egress cap bypassed'; end if;
end $$;
reset role;
rollback;
select 'fair request allowance at 100 and few groups, bounded storage and egress passed' as checks;
