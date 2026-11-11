package hu.keepimproving.android;
import android.app.*;
import android.content.*;
import android.database.Cursor;
import android.graphics.Color;
import android.os.Build;
import org.json.*;

final class PhoneNotifications {
    private static String timerSignature="";
    private static String budgetSignature="";
    static boolean allowed(Context context) {return context.getSystemService(NotificationManager.class).areNotificationsEnabled()&&(Build.VERSION.SDK_INT<33||context.checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)==android.content.pm.PackageManager.PERMISSION_GRANTED);}
    static String t(Context c,String en,String hu){return PhoneLocale.text(c,en,hu);}
    static void channels(Context base) {
        Context c=PhoneLocale.context(base);NotificationManager manager=c.getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel("reminders",t(c,"Reminders and limits","Emlékeztetők és korlátok"),NotificationManager.IMPORTANCE_HIGH));
        NotificationChannel silent=new NotificationChannel("quiet",t(c,"Quiet reminders","Csendes emlékeztetők"),NotificationManager.IMPORTANCE_DEFAULT);silent.setSound(null,null);manager.createNotificationChannel(silent);
        NotificationChannel timer=new NotificationChannel("focus",t(c,"Focus timer","Fókuszidőzítő"),NotificationManager.IMPORTANCE_LOW);timer.setSound(null,null);manager.createNotificationChannel(timer);
        NotificationChannel budget=new NotificationChannel("budget_counter",t(c,"Budget counter","Keret számlálója"),NotificationManager.IMPORTANCE_LOW);budget.setSound(null,null);budget.enableVibration(false);manager.createNotificationChannel(budget);
    }
    static int identifier(String id){return 1000+(id.hashCode()&0x3fffffff);}
    static void cancel(Context context,String id){context.getSystemService(NotificationManager.class).cancel(identifier(id));}
    static PendingIntent open(Context context,int page,String identity) {return PendingIntent.getActivity(context,identifier(identity),new Intent(context,MainActivity.class).setData(android.net.Uri.parse("keepimproving://open/"+identity)).putExtra("page",page).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP|Intent.FLAG_ACTIVITY_SINGLE_TOP),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);}
    private static PendingIntent action(Context context,String command,String token,String notice) {return PendingIntent.getBroadcast(context,identifier(command+token+notice),new Intent(context,ReminderReceiver.class).setAction(command).putExtra("token",token).putExtra("notice",notice),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);}
    static void deliver(Context base,PhoneStore store) {
        channels(base);if(!allowed(base))return;Context c=PhoneLocale.context(base);NotificationManager manager=c.getSystemService(NotificationManager.class);
        try(Cursor cursor=store.getReadableDatabase().rawQuery("SELECT id,value,at FROM notices WHERE delivered=0 ORDER BY at LIMIT 30",null)) {
            while(cursor.moveToNext()) {
                String id=cursor.getString(0);JSONObject row=PhoneRules.object(cursor.getString(1)),details=row.optJSONObject("details");if(details==null)details=new JSONObject();
                // Mark before display. Repeating the same persisted event cannot ring again.
                store.getWritableDatabase().execSQL("UPDATE notices SET delivered=1 WHERE id=?",new Object[]{id});
                if(System.currentTimeMillis()-cursor.getLong(2)>86400000L)continue;
                String title=row.optString("title"),text=row.optString("text");
                if(id.startsWith("focus_")||id.startsWith("break_done:")) {
                    title=t(c,"Focus mode","Fókusz mód");text=switch(text){case "focus_break"->t(c,"Focus complete. Time for a break.","Fókusz kész. Ideje szünetet tartani.");case "break_done"->t(c,"Break complete. Start the next focus session when ready.","A szünet véget ért. Indítsd a következő fókuszt, amikor készen állsz.");default->t(c,"Focus session complete.","Fókuszszakasz befejezve.");};
                } else if(id.startsWith("budget:"))text=t(c,"You have reached a reminder in this budget.","Elérted a keretben beállított figyelmeztetést.");
                else if(id.startsWith("budget_end:"))text=t(c,"Your daily budget has run out.","Elfogyott a napi kereted.");
                else if(id.startsWith("budget_break:"))text=t(c,"Time for your scheduled break.","Ideje megtartani a beállított szünetet.");
                if(title.isBlank())title=t(c,"Reminder","Emlékeztető");
                if(text.isBlank())text=switch(details.optString("template")) {
                    case "warning"->t(c,"Your daily game allowance is nearly used up.","Hamarosan elfogy a napi játékkereted.");
                    case "limit","session"->t(c,"Your daily game allowance has run out. Time to finish playing.","Elfogyott a napi játékkereted. Ideje befejezni a játékot.");
                    case "bedtime"->t(c,"Finish what you are doing and get ready for bed.","Fejezd be, amit csinálsz, és készülj a lefekvésre.");
                    default->t(c,"Your scheduled reminder is due.","Elérkezett a beállított emlékeztetőd ideje.");
                };
                Notification.Builder b=new Notification.Builder(c,row.optBoolean("sound",true)?"reminders":"quiet").setSmallIcon(R.drawable.ic_notification).setColor(Color.rgb(125,229,191)).setContentTitle(title).setContentText(text)
                    .setStyle(new Notification.BigTextStyle().bigText(text)).setContentIntent(open(c,3,id)).setAutoCancel(true).setOnlyAlertOnce(true).setShowWhen(true).setWhen(cursor.getLong(2));
                if(details.optInt("timeout")>0)b.setTimeoutAfter(details.optInt("timeout")*1000L);
                if(row.optString("action").equals("focus"))b.addAction(new Notification.Action.Builder(null,t(c,"Start focus","Fókusz indítása"),action(c,"notice.focus","",id)).build());
                else if(row.optString("action").equals("app")) {Intent intent=c.getPackageManager().getLaunchIntentForPackage(details.optString("package"));if(intent!=null)b.setContentIntent(PendingIntent.getActivity(c,identifier(id),intent,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE));}
                try{manager.notify(identifier(id),b.build());}catch(SecurityException ignored){}
            }
        }
        store.getWritableDatabase().delete("notices","at<? AND delivered=1",new String[]{Long.toString(System.currentTimeMillis()-30*86400000L)});
    }
    static void timer(Context base,JSONObject state) {
        NotificationManager manager=base.getSystemService(NotificationManager.class);
        if(!state.optBoolean("running")){manager.cancel(100);timerSignature="";return;}
        if(!allowed(base))return;channels(base);Context c=PhoneLocale.context(base);
        long end=state.optLong("wall")+state.optLong("remaining");String token=state.optString("token"),signature=token+":"+state.optString("phase")+":"+(end/1000);
        if(signature.equals(timerSignature))return;timerSignature=signature;
        String title=state.optString("phase").equals("work")?t(c,"Focus in progress","Fókusz folyamatban"):t(c,"Break in progress","Szünet folyamatban");
        Notification.Builder b=new Notification.Builder(c,"focus").setSmallIcon(R.drawable.ic_notification).setColor(Color.rgb(125,229,191)).setContentTitle(title).setContentText(t(c,"Tap to open the timer","Koppints az időzítő megnyitásához"))
            .setOngoing(true).setOnlyAlertOnce(true).setWhen(end).setUsesChronometer(true).setChronometerCountDown(true).setContentIntent(open(c,4,"focus"));
        b.addAction(new Notification.Action.Builder(null,t(c,"Pause","Szüneteltetés"),action(c,"pause",token,"")).build());
        b.addAction(new Notification.Action.Builder(null,t(c,"Stop","Leállítás"),action(c,"stop",token,"")).build());
        try{manager.notify(100,b.build());}catch(SecurityException ignored){}
    }
    static void budget(Context base,PhoneStore store,PhoneRuntime.State state,String pkg,boolean game,long now){
        NotificationManager manager=base.getSystemService(NotificationManager.class);PhoneRuntime.BudgetView selected=null;boolean matches=false;long remaining=Long.MAX_VALUE;
        if(store.get("budget_counter","true").equals("true")&&store.get("enabled","false").equals("true"))for(var view:state.budgets()){
            JSONObject rule=view.rule();String day=PhoneRules.day(now,rule.optInt("renewal",(int)store.number("day_start",0)),java.time.ZoneId.systemDefault());
            if(!rule.optBoolean("limit")||!PhoneRules.active(rule,day)||!PhoneShared.applies(store,rule.optJSONObject("devices")))continue;
            // Rules covering only remote executables do not become a phone counter.
            if(rule.optString("category").isEmpty()&&(rule.optJSONArray("apps")==null||rule.optJSONArray("apps").length()==0))continue;
            boolean active=PhoneRules.matches(rule,pkg,game);long left=Math.max(0,rule.optLong("minutes")*60000-view.used());
            if(selected==null||active&&!matches||active==matches&&left<remaining){selected=view;matches=active;remaining=left;}
        }
        if(selected==null){manager.cancel(101);budgetSignature="";return;}
        if(!allowed(base)){budgetSignature="";return;}channels(base);Context c=PhoneLocale.context(base);
        boolean running=remaining>0&&matches&&ShieldService.connected()&&!state.decision().blocked()&&!pkg.equals(ShieldService.coveredPackage())&&!PhoneRules.contains(PhoneRules.array(store.get("excluded","[]")),pkg)&&PhoneUsage.allowed(base);
        String id=selected.rule().optString("id"),name=selected.rule().optString("name");long end=now+remaining;
        String status=remaining==0?t(c,"Budget reached","Elfogyott a keret"):running?t(c,"Counting while you use this app","Használat közben visszaszámol"):ShieldService.connected()?t(c,"Counting paused","A számlálás szünetel"):t(c,"Last measured remaining time","Legutóbb mért hátralévő idő");
        if(selected.rule().has("devices"))status=t(c,"Shared allowance · ","Közös keret · ")+status;
        String signature=id+":"+name+":"+status+":"+(running?end/1000:remaining/1000)+":"+c.getResources().getConfiguration().getLocales().get(0).getLanguage();
        if(signature.equals(budgetSignature))return;
        String clock=String.format(java.util.Locale.ROOT,"%d:%02d:%02d",remaining/3600000,(remaining/60000)%60,(remaining/1000)%60);
        Notification.Builder b=new Notification.Builder(c,"budget_counter").setSmallIcon(R.drawable.ic_notification).setColor(Color.rgb(125,229,191)).setContentTitle(name)
            .setSubText(t(c,"Time remaining","Hátralévő idő")).setContentText((running?"":clock+" · ")+status).setOnlyAlertOnce(true).setOngoing(true).setCategory(Notification.CATEGORY_PROGRESS)
            .setContentIntent(open(c,2,"budget-counter")).setShowWhen(running).setUsesChronometer(running).setChronometerCountDown(true).setWhen(end);
        try{manager.notify(101,b.build());budgetSignature=signature;}catch(SecurityException ignored){}
    }
}
