package hu.keepimproving.android;

import android.database.Cursor;
import java.util.List;
import org.json.JSONObject;

/** Activity lifecycle callbacks inside one app are not application switches.
 * Merge only boundaries witnessed in the OS event stream; usage time is untouched.
 */
final class SessionTransitions {
    static final long TRANSITION_MILLIS=1000;

    static void reconcile(PhoneStore store,List<UsageLedger.Event> events,long end,boolean replay) {
        if(replay)store.getWritableDatabase().execSQL("CREATE TABLE IF NOT EXISTS sessions_activity_backup AS SELECT * FROM sessions");
        JSONObject saved=replay?new JSONObject():store.json("session_pending_pause",new JSONObject());
        long paused=saved.optLong("at",-1);String pkg=saved.optString("package","");
        for(var event:events) {
            if(event.time()>=end)continue;
            if(event.type()==2) {paused=event.time();pkg=event.pkg();}
            else if(event.type()==1) {
                if(pkg.equals(event.pkg())&&paused>=0&&event.time()>=paused&&event.time()-paused<=TRANSITION_MILLIS)
                    join(store,pkg,paused,event.time());
                paused=-1;pkg="";
            } else if(event.type()==16||event.type()==17||event.type()==26||event.type()==27) {
                paused=-1;pkg="";
            }
        }
        JSONObject pending=new JSONObject();
        if(paused>=0&&end-paused<=TRANSITION_MILLIS) {
            try {pending.put("at",paused).put("package",pkg);}catch(org.json.JSONException e){throw new IllegalStateException(e);}
        }
        store.put("session_pending_pause",pending.toString());
    }

    private static void join(PhoneStore store,String pkg,long pause,long resume) {
        if(pause==resume||!store.coverage(pkg,pause,resume).isEmpty())return;
        var db=store.getWritableDatabase();long left,right;
        try(Cursor c=db.rawQuery("SELECT start FROM sessions WHERE package=? AND finish=?",new String[]{pkg,Long.toString(pause)})) {
            if(!c.moveToFirst())return;left=c.getLong(0);
        }
        try(Cursor c=db.rawQuery("SELECT finish FROM sessions WHERE package=? AND start=?",new String[]{pkg,Long.toString(resume)})) {
            if(!c.moveToFirst())return;right=c.getLong(0);
        }
        // Keep the original starting day, also across the daily reset boundary.
        db.delete("sessions","package=? AND start=?",new String[]{pkg,Long.toString(resume)});
        db.execSQL("UPDATE sessions SET finish=? WHERE package=? AND start=?",new Object[]{right,pkg,left});
    }
}
