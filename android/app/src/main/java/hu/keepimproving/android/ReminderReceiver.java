package hu.keepimproving.android;
import android.content.*;
public final class ReminderReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context,Intent intent) {
        PendingResult pending=goAsync();Context app=context.getApplicationContext();
        CollectionJob.WORK.execute(()->{try {
            PhoneAlarms.invalidate(app);String action=intent.getAction();
            if("notice.focus".equals(action))PhoneRuntime.startNotice(app,intent.getStringExtra("notice"));
            else if("start".equals(action)||"pause".equals(action)||"stop".equals(action))PhoneRuntime.command(app,action,intent.getStringExtra("token"));
            else {PhoneRuntime.refresh(app,false);PhoneRuntime.changed(app);}
        }catch(RuntimeException ignored){/* Preserve durable state; the next app/service event retries. */}finally{pending.finish();}});
    }
}
