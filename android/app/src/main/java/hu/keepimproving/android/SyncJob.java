package hu.keepimproving.android;
import android.app.job.*;
import android.content.*;
/** Android batches network work; local alarms and protection have a separate worker. */
public final class SyncJob extends JobService {
    static void schedule(Context c){JobScheduler jobs=c.getSystemService(JobScheduler.class);try{if(Vault.read(c).isEmpty()){jobs.cancel(101);return;}if(jobs.getPendingJob(101)==null)jobs.schedule(new JobInfo.Builder(101,new ComponentName(c,SyncJob.class)).setPersisted(true).setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setPeriodic(900000).build());}catch(Exception ignored){jobs.cancel(101);}}
    static void soon(Context c,long delay){c.getSystemService(JobScheduler.class).schedule(new JobInfo.Builder(102,new ComponentName(c,SyncJob.class)).setPersisted(true).setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setMinimumLatency(Math.max(1000,delay)).build());}
    @Override public boolean onStartJob(JobParameters p){CollectionJob.LOAD.execute(()->{try(PhoneStore store=new PhoneStore(this)){PhoneSync.run(this,store);}finally{CollectionJob.WORK.execute(()->{try{PhoneRuntime.refresh(this,false);PhoneRuntime.changed(this);}finally{jobFinished(p,false);}});}});return true;}
    @Override public boolean onStopJob(JobParameters p){return false;}
}
