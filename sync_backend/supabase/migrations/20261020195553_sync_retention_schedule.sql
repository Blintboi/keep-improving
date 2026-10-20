begin;
create extension if not exists pg_cron;
-- Database-local housekeeping: no public HTTP endpoint or extra Edge calls.
select cron.schedule('gametime-sync-retention','17 * * * *',
  $job$select public.gametime_sync_cleanup(); delete from cron.job_run_details where jobid in (select jobid from cron.job where jobname='gametime-sync-retention') and end_time<now()-interval '7 days';$job$);
commit;
