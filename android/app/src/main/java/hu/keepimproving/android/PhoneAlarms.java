package hu.keepimproving.android;
import android.app.*;
import android.content.*;
import android.os.Build;

final class PhoneAlarms {
    static boolean exact(Context context){return Build.VERSION.SDK_INT<31||context.getSystemService(AlarmManager.class).canScheduleExactAlarms();}
    static void schedule(Context context,long deadline) {
        AlarmManager manager=context.getSystemService(AlarmManager.class);
        PendingIntent intent=PendingIntent.getBroadcast(context,102,new Intent(context,ReminderReceiver.class).setAction("tick"),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
        var prefs=context.getSharedPreferences("alarms",0);
        boolean precise=exact(context);String key=deadline+":"+precise;
        if(key.equals(prefs.getString("scheduled","")))return;
        manager.cancel(intent);
        if(deadline<Long.MAX_VALUE) {
            long when=Math.max(System.currentTimeMillis()+500,deadline);
            try {if(precise)manager.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,when,intent);else manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,when,intent);}
            catch(SecurityException e){manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,when,intent);}
        }
        prefs.edit().putString("scheduled",key).apply();
    }
    static void invalidate(Context context){context.getSharedPreferences("alarms",0).edit().remove("scheduled").apply();}
}
