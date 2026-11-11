package hu.keepimproving.android;

import android.app.AppOpsManager;
import android.app.usage.UsageEvents;
import android.app.usage.UsageStatsManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.os.Process;
import android.os.UserManager;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.HashMap;

final class PhoneUsage {
    record App(String name,boolean game) {}
    static boolean allowed(Context context) {
        return context.getSystemService(AppOpsManager.class).checkOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS,Process.myUid(),context.getPackageName())==AppOpsManager.MODE_ALLOWED;
    }
    static void collect(Context context,PhoneStore store) {
        if(!store.get("enabled","false").equals("true")||!context.getSystemService(UserManager.class).isUserUnlocked()) return;
        if(!allowed(context)) {store.resetCursor(System.currentTimeMillis());store.put("access_missing","true");return;}
        if(store.get("access_missing","false").equals("true")) {store.resetCursor(System.currentTimeMillis());store.put("access_missing","false");}
        long now=System.currentTimeMillis(); ZoneId zone=ZoneId.systemDefault();
        long start=store.number("cursor",LocalDate.now().atStartOfDay(zone).toInstant().toEpochMilli());
        String pkg=store.get("active",""),activity=store.get("activity","");
        if(start>now) { store.resetCursor(now); return; }
        // Android retains events only for a few days. Never extrapolate an old active app across a gap.
        if(now-start>3*86400000L) { start=now-3*86400000L; pkg=""; activity=""; store.put("history_gap","true"); }
        // One-time repair uses retained lifecycle evidence, never recredits old usage.
        boolean repairSessions=!store.get("session_activity_boundaries_v1","false").equals("true");
        long eventsStart=repairSessions?Math.min(start,Math.max(store.number("sessions_since",now),now-3*86400000L)):start;
        UsageEvents source=context.getSystemService(UsageStatsManager.class).queryEvents(eventsStart,now);
        if(source==null) return;
        ArrayList<UsageLedger.Event> events=new ArrayList<>(); UsageEvents.Event event=new UsageEvents.Event();
        while(source.hasNextEvent()) {
            source.getNextEvent(event); int type=event.getEventType();
            if(type==1||type==2||type==16||type==17||type==26||type==27)
                events.add(new UsageLedger.Event(event.getTimeStamp(),type,event.getPackageName()==null?"":event.getPackageName(),event.getClassName()==null?"":event.getClassName()));
        }
        var result=UsageLedger.collect(new UsageLedger.State(start,pkg,activity),events,now,zone,(int)store.number("day_start",0));
        PackageManager pm=context.getPackageManager();
        Intent home=new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME);
        var launcher=pm.resolveActivity(home,PackageManager.MATCH_DEFAULT_ONLY);
        String homePackage=launcher==null?"":launcher.activityInfo.packageName;
        HashMap<String,App> metadata=new HashMap<>();
        var excluded=PhoneRules.array(store.get("excluded","[]"));var games=PhoneRules.array(store.get("game_apps","[]"));
        var db=store.getWritableDatabase(); db.beginTransaction();
        try {
            for(var slice:result.slices()) {
                if(slice.pkg().equals(context.getPackageName())||slice.pkg().equals(homePackage)||slice.pkg().equals("com.android.systemui")||slice.pkg().equals("android")) continue;
                if(PhoneRules.contains(excluded,slice.pkg()))continue;
                App app=metadata.get(slice.pkg());
                if(app==null) {
                    try {
                        ApplicationInfo info=pm.getApplicationInfo(slice.pkg(),0);
                        app=new App(pm.getApplicationLabel(info).toString(),info.category==ApplicationInfo.CATEGORY_GAME);
                    } catch(PackageManager.NameNotFoundException e) { app=new App(slice.pkg(),false); }
                    metadata.put(slice.pkg(),app);
                }
                var visible=CoverageLedger.parts(store.coverage(slice.pkg(),slice.start(),slice.start()+slice.millis()),slice.start(),slice.start()+slice.millis());
                long allowed=0;for(var part:visible){allowed+=part.end()-part.start();SessionCounts.record(store,slice.pkg(),part.start(),part.end());}
                boolean isGame=(app.game()||PhoneRules.contains(games,slice.pkg()))&&!PhoneRules.contains(PhoneRules.array(store.get("nongame_apps","[]")),slice.pkg());
                PhoneShared.credit(store,slice,isGame);
                if(allowed>0)store.add(new UsageLedger.Slice(slice.day(),slice.pkg(),allowed),app.name(),isGame);
            }
            SessionTransitions.reconcile(store,events,now,repairSessions);
            store.put("session_activity_boundaries_v1","true");
            store.put("cursor",Long.toString(result.state().cursor())); store.put("active",result.state().pkg()); store.put("activity",result.state().activity());
            db.delete("coverage","finish>0 AND finish<=?",new String[]{Long.toString(now)});
            if(store.get("started","").isEmpty()) store.put("started",LocalDate.now().toString());
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
    }
}
