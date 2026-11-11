package hu.keepimproving.android;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
public final class BootReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context,Intent intent) {
        if(Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())||Intent.ACTION_MY_PACKAGE_REPLACED.equals(intent.getAction())||android.app.AlarmManager.ACTION_SCHEDULE_EXACT_ALARM_PERMISSION_STATE_CHANGED.equals(intent.getAction())||Intent.ACTION_TIME_CHANGED.equals(intent.getAction())||Intent.ACTION_TIMEZONE_CHANGED.equals(intent.getAction())) {
            CollectionJob.schedule(context);SyncJob.schedule(context);PendingResult result=goAsync();PhoneAlarms.invalidate(context);
            CollectionJob.WORK.execute(()->{try{PhoneRuntime.refresh(context,false);PhoneRuntime.changed(context);}catch(RuntimeException ignored){}finally{result.finish();}});
        }
    }
}
