package hu.keepimproving.android;

import android.app.*;
import android.content.*;
import android.database.Cursor;
import android.os.*;
import android.provider.Settings;
import org.json.*;
import java.time.*;
import java.util.*;

/** All calls use CollectionJob.WORK. Counters, transitions and delivery receipts are durable. */
final class PhoneRuntime {
    private static boolean recovered;
    static final String CHANGED="hu.keepimproving.android.STATE_CHANGED";
    record BudgetView(JSONObject rule,long used,PhoneRules.Result result,long sessions) { BudgetView(JSONObject rule,long used,PhoneRules.Result result){this(rule,used,result,0);} }
    record Decision(String pkg,boolean blocked,boolean focus,boolean pause,String title,long until,int allowance,List<String> groups) {
        static Decision clear(String pkg){return new Decision(pkg,false,false,false,"",0,0,List.of());}
    }
    record State(JSONObject focus,JSONObject config,List<BudgetView> budgets,JSONArray reminders,int rounds,long next,Decision decision) {}
    static PhoneFocus.Time now(Context context) {return new PhoneFocus.Time(System.currentTimeMillis(),SystemClock.elapsedRealtime(),Settings.Global.getInt(context.getContentResolver(),Settings.Global.BOOT_COUNT,0));}
    static String day(PhoneStore store,long now){return PhoneRules.day(now,(int)store.number("day_start",0),ZoneId.systemDefault());}
    static boolean game(Context context,PhoneStore store,String pkg) {
        if(PhoneRules.contains(PhoneRules.array(store.get("nongame_apps","[]")),pkg))return false;
        if(PhoneRules.contains(PhoneRules.array(store.get("game_apps","[]")),pkg))return true;
        try{return context.getPackageManager().getApplicationInfo(pkg,0).category==android.content.pm.ApplicationInfo.CATEGORY_GAME;}catch(Exception e){return false;}
    }
    static State refresh(Context context,boolean startup) {
        try(PhoneStore store=new PhoneStore(context)) {
            if(!recovered){recovered=true;store.getWritableDatabase().execSQL("UPDATE coverage SET finish=? WHERE finish=0",new Object[]{System.currentTimeMillis()});}
            PhoneUsage.collect(context,store);
            PhoneFocus.Time time=now(context);int renewal=(int)store.number("day_start",0);ZoneId zone=ZoneId.systemDefault();String day=day(store,time.wall());
            JSONObject config=store.json("focus_config",PhoneFocus.defaults()),focus=store.json("focus_timer",PhoneFocus.state(config));
            JSONArray rules=store.rules("budget"),reminders=store.rules("reminder");List<PhoneRules.Notice> notices=new ArrayList<>();List<PhoneFocus.Completion> completions=new ArrayList<>();List<BudgetView> views=new ArrayList<>();
            String pkg=ShieldService.foregroundPackage();if(pkg.isEmpty())pkg=store.get("active","");
            boolean interactive=context.getSystemService(PowerManager.class).isInteractive()&&!context.getSystemService(KeyguardManager.class).isKeyguardLocked();
            if(!interactive||AppCatalog.safe(context,pkg))pkg="";boolean game=game(context,store,pkg);
            long next=Long.MAX_VALUE;Decision decision=Decision.clear(pkg);List<String> blocked=new ArrayList<>(),breaks=new ArrayList<>();String title="";long until=0;int allowance=60;
            var db=store.getWritableDatabase();db.beginTransaction();
            try {
                PhoneFocus.advance(focus,config,time,renewal,zone,completions,notices);
                for(var c:completions)db.execSQL("INSERT OR IGNORE INTO focus_rounds VALUES (?,?,?,?)",new Object[]{c.day(),c.token(),c.round(),c.at()});
                store.put("focus_timer",focus.toString());
                if(focus.optBoolean("running"))next=time.wall()+focus.optLong("remaining");
                for(int i=0;i<rules.length();i++) {
                    JSONObject rule=rules.optJSONObject(i);if(rule==null)continue;String id=rule.optString("id");
                    JSONObject state=store.json("budget:"+id,new JSONObject());long used=PhoneShared.used(store,rule,time.wall());boolean matches=PhoneRules.matches(rule,pkg,game);int ruleRenewal=rule.optInt("renewal",renewal);
                    JSONObject effective=rule;if(!PhoneShared.applies(store,rule.optJSONObject("devices"))){effective=PhoneRules.copy(rule);PhoneRules.set(effective,"enabled",false);}
                    long sessions=PhoneRules.sessionSteps(effective)?PhoneShared.sessions(store,rule,time.wall()):0;
                    var result=PhoneRules.evaluate(effective,state,used,sessions,time.wall(),ruleRenewal,zone,matches&&!pkg.equals(ShieldService.coveredPackage())&&!PhoneRules.contains(PhoneRules.array(store.get("excluded","[]")),pkg)&&store.get("enabled","false").equals("true"),notices);
                    store.put("budget:"+id,state.toString());views.add(new BudgetView(rule,used,result,sessions));
                    if(rule.optBoolean("enabled",true))next=Math.min(next,result.next());
                    boolean granted=!(rule.optBoolean("limit")&&rule.optInt("minutes")==0)&&pkg.equals(state.optString("grantPackage"))&&state.optLong("grantUntil")>time.wall();
                    if(matches&&result.blocked()&&!granted) {
                        if(result.pause()){breaks.add(id);until=Math.max(until,result.until());if(title.isEmpty())title=rule.optString("name");}
                        else {blocked.add(id);title=rule.optString("name");allowance=Math.min(allowance,result.allowance()?rule.optInt("allowance"):0);}
                    }
                }
                boolean focusBlock=focus.optBoolean("running")&&focus.optString("phase").equals("work")&&PhoneRules.contains(config.optJSONArray("apps"),pkg);
                if(focus.optBoolean("running")&&focus.optString("phase").equals("work"))for(var view:views)if(PhoneRules.contains(config.optJSONArray("groups"),view.rule.optString("id"))&&PhoneRules.matches(view.rule,pkg,game))focusBlock=true;
                if(!pkg.isEmpty()) {
                    if(focusBlock)decision=new Decision(pkg,true,true,false,"",time.wall()+focus.optLong("remaining"),0,List.of());
                    else if(!blocked.isEmpty())decision=new Decision(pkg,true,false,false,title,0,allowance,blocked);
                    else if(!breaks.isEmpty())decision=new Decision(pkg,true,false,true,title,until,0,breaks);
                }
                int rounds=PhoneCompanion.rounds(store,day);
                next=Math.min(next,PhoneCompanion.notices(store,time.wall(),notices));
                for(int i=0;i<reminders.length();i++) {
                    JSONObject r=reminders.optJSONObject(i);if(r==null||!r.optBoolean("enabled",true)||!PhoneShared.applies(store,r.optJSONObject("devices")))continue;
                    String trigger=r.optString("trigger");long at=PhoneRules.clock(day,r.optInt("clock"),renewal,zone);
                    boolean active=PhoneRules.active(r,day);
                    boolean due=active&&(trigger.equals("clock")&&time.wall()>=at&&at>=r.optLong("_sharedSince",0)||trigger.equals("rounds")&&rounds>=r.optInt("rounds",4)||trigger.equals("startup")&&startup);
                    if(due)notices.add(new PhoneRules.Notice("reminder:"+r.optString("id")+":"+day,r.optString("title"),r.optString("text"),r.optBoolean("sound",true),r.optString("action"),r));
                    if(trigger.equals("clock"))for(int d=0;d<8;d++) {String candidate=LocalDate.parse(day).plusDays(d).toString();long when=PhoneRules.clock(candidate,r.optInt("clock"),renewal,zone);if(when>time.wall()&&PhoneRules.active(r,candidate)){next=Math.min(next,when);break;}}
                }
                for(var n:notices) {
                    JSONObject row=new JSONObject();PhoneRules.set(row,"title",n.title());PhoneRules.set(row,"text",n.text());PhoneRules.set(row,"sound",n.sound());PhoneRules.set(row,"action",n.action());PhoneRules.set(row,"details",n.details());
                    db.execSQL("INSERT OR IGNORE INTO notices (id,value,at) VALUES (?,?,?)",new Object[]{n.id(),row.toString(),time.wall()});
                }
                db.setTransactionSuccessful();
            } finally {db.endTransaction();}
            State result=new State(focus,config,views,reminders,PhoneCompanion.rounds(store,day),next,decision);
            PhoneAlarms.schedule(context,next);PhoneNotifications.deliver(context,store);PhoneNotifications.timer(context,focus);
            PhoneNotifications.budget(context,store,result,pkg,game,time.wall());
            return result;
        }
    }
    static void changed(Context context) {context.sendBroadcast(new Intent(CHANGED).setPackage(context.getPackageName()));ShieldService.refreshSoon();}
    static boolean command(Context context,String action,String expected) {
        State before=refresh(context,false);
        try(PhoneStore store=new PhoneStore(context)) {
            if(expected!=null&&!expected.equals(before.focus.optString("token")))return false;
            PhoneFocus.command(before.focus,before.config,action,now(context));store.put("focus_timer",before.focus.toString());
        }
        refresh(context,false);changed(context);return true;
    }
    static boolean allowance(Context context,String pkg) {
        State current=refresh(context,false);Decision d=current.decision;
        if(!pkg.equals(d.pkg)||d.allowance<=0||d.focus||d.pause)return false;
        try(PhoneStore store=new PhoneStore(context)) {
            var db=store.getWritableDatabase();db.beginTransaction();try {
                for(String id:d.groups) {JSONObject state=store.json("budget:"+id,new JSONObject());if(state.optBoolean("usedAllowance"))return false;}
                for(String id:d.groups) {JSONObject state=store.json("budget:"+id,new JSONObject());PhoneRules.set(state,"usedAllowance",true);PhoneRules.set(state,"grantUntil",System.currentTimeMillis()+d.allowance*60000L);PhoneRules.set(state,"grantPackage",pkg);store.put("budget:"+id,state.toString());}
                db.setTransactionSuccessful();
            } finally {db.endTransaction();}
        }
        refresh(context,false);changed(context);return true;
    }
    static boolean startNotice(Context context,String id) {
        State current=refresh(context,false);if(current.focus.optBoolean("running"))return false;
        try(PhoneStore store=new PhoneStore(context);Cursor c=store.getReadableDatabase().rawQuery("SELECT value FROM notices WHERE id=?",new String[]{id})) {
            if(!c.moveToFirst())return false;JSONObject notice=PhoneRules.object(c.getString(0));if(!notice.optString("action").equals("focus"))return false;
            JSONObject details=notice.optJSONObject("details"),config=PhoneRules.copy(current.config);if(details==null)return false;
            for(String key:new String[]{"work","short","long","cycles"})PhoneRules.set(config,key,details.optInt(key));PhoneFocus.validate(config);
            JSONObject state=PhoneFocus.state(config);PhoneFocus.command(state,config,"start",now(context));
            var db=store.getWritableDatabase();db.beginTransaction();try{store.put("focus_config",config.toString());store.put("focus_timer",state.toString());db.setTransactionSuccessful();}finally{db.endTransaction();}
        }
        PhoneNotifications.cancel(context,id);refresh(context,false);changed(context);return true;
    }
}
