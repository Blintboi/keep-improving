package hu.keepimproving.android;

import android.app.job.JobInfo;
import android.app.job.JobParameters;
import android.app.job.JobScheduler;
import android.app.job.JobService;
import android.content.ComponentName;
import android.content.Context;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class CollectionJob extends JobService {
    static final ExecutorService WORK=Executors.newSingleThreadExecutor();
    private static final int ID=100;
    static void schedule(Context context) {
        try(PhoneStore store=new PhoneStore(context)) {
            JobScheduler jobs=context.getSystemService(JobScheduler.class);
            if(!store.get("enabled","false").equals("true")||!PhoneUsage.allowed(context)) { jobs.cancel(ID); return; }
            if(jobs.getPendingJob(ID)==null) jobs.schedule(new JobInfo.Builder(ID,new ComponentName(context,CollectionJob.class))
                .setPeriodic(15*60*1000L).setPersisted(true).build());
        }
    }
    @Override public boolean onStartJob(JobParameters params) {
        WORK.execute(()->{ try(PhoneStore store=new PhoneStore(this)) { PhoneUsage.collect(this,store); } catch(RuntimeException ignored) {
            // Revoked access, locked profiles and transient storage errors leave the checkpoint intact.
        } finally { jobFinished(params,false); } });
        return true;
    }
    @Override public boolean onStopJob(JobParameters params) { return false; }
}
