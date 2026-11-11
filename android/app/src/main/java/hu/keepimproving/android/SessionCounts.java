package hu.keepimproving.android;

import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import java.time.ZoneId;
import java.util.*;
import org.json.JSONArray;
import org.json.JSONObject;

/** Connected measured foreground intervals. Only daily counts leave the device. */
final class SessionCounts {
    static final class Total {
        long count;boolean partial;
        void add(Statistics.Row row,String start){count+=row.sessions();partial|=SessionCounts.partial(row,start);}
        String text(){return display(count,partial);}
    }
    static void schema(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE IF NOT EXISTS sessions (package TEXT NOT NULL,start INTEGER NOT NULL,finish INTEGER NOT NULL,day TEXT NOT NULL,PRIMARY KEY(package,start))");
        db.execSQL("CREATE INDEX IF NOT EXISTS sessions_finish ON sessions(package,finish)");
        db.execSQL("CREATE INDEX IF NOT EXISTS sessions_period ON sessions(start)");
        db.execSQL("INSERT OR IGNORE INTO meta VALUES ('sessions_since',?)",new Object[]{Long.toString(System.currentTimeMillis())});
    }
    static void record(PhoneStore store,String pkg,long start,long finish) {
        start=Math.max(start,store.number("sessions_since",System.currentTimeMillis()));if(finish<=start)return;
        String day=PhoneRules.day(start,(int)store.number("day_start",0),ZoneId.systemDefault());
        SQLiteDatabase db=store.getWritableDatabase();List<Long> remove=new ArrayList<>();
        try(Cursor c=db.rawQuery("SELECT start,finish,day FROM sessions WHERE package=? AND finish>=? AND start<=? ORDER BY start",new String[]{pkg,Long.toString(start),Long.toString(finish)})) {
            while(c.moveToNext()){long old=c.getLong(0);remove.add(old);if(old<start){start=old;day=c.getString(2);}finish=Math.max(finish,c.getLong(1));}
        }
        for(long old:remove)db.delete("sessions","package=? AND start=?",new String[]{pkg,Long.toString(old)});
        db.execSQL("INSERT INTO sessions VALUES (?,?,?,?)",new Object[]{pkg,start,finish,day});
    }
    static JSONObject snapshot(PhoneStore store) throws Exception {
        String since=PhoneRules.day(store.number("sessions_since",System.currentTimeMillis()),(int)store.number("day_start",0),ZoneId.systemDefault());JSONArray rows=new JSONArray();
        try(Cursor c=store.getReadableDatabase().rawQuery("SELECT s.day,s.package,u.game,COUNT(*) FROM sessions s JOIN usage u ON u.day=s.day AND u.package=s.package GROUP BY s.day,s.package,u.game ORDER BY s.day,s.package",null)) {
            while(c.moveToNext()){String day=c.getString(0);if(day.compareTo(since)<0)since=day;rows.put(new JSONArray().put(day).put(c.getInt(2)!=0?"game":"app").put("android:"+c.getString(1)).put(c.getLong(3)));}
        }
        return new JSONObject().put("since",since).put("rows",rows);
    }
    static long budget(PhoneStore store,JSONObject rule,String day,int renewal) {
        ZoneId zone=ZoneId.systemDefault();long start=PhoneRules.clock(day,renewal,renewal,zone),end=PhoneRules.nextDay(start,renewal,zone),total=0;
        // A package is counted once even when both its category and explicit
        // membership match. A session crossing renewal retains its start day.
        try(Cursor c=store.getReadableDatabase().rawQuery("SELECT s.package,COALESCE((SELECT game FROM usage u WHERE u.package=s.package ORDER BY day DESC LIMIT 1),0),COUNT(*) FROM sessions s WHERE s.start>=? AND s.start<? GROUP BY s.package",new String[]{Long.toString(start),Long.toString(end)})) {
            while(c.moveToNext())if(PhoneRules.matches(rule,c.getString(0),c.getInt(1)!=0))total+=c.getLong(2);
        }
        return total;
    }
    static String key(String day,String kind,String key){return day+":"+kind+":"+key;}
    static void validate(JSONObject value) throws Exception {
        if(value.length()!=2)throw new IllegalArgumentException("Invalid sessions");
        String since=value.getString("since");SyncProtocol.date(since);JSONArray rows=value.getJSONArray("rows");if(rows.length()>100000)throw new IllegalArgumentException("Too many sessions");Set<String> seen=new HashSet<>();
        for(int i=0;i<rows.length();i++) {
            JSONArray r=rows.getJSONArray(i);if(r.length()!=4)throw new IllegalArgumentException("Invalid session row");
            String day=r.getString(0),kind=r.getString(1),key=r.getString(2);Object count=r.get(3);SyncProtocol.date(day);SyncProtocol.text(key,512);
            if(day.compareTo(since)<0||!Set.of("game","app","site","browser").contains(kind)||key.indexOf('\0')>=0||!(count instanceof Integer||count instanceof Long)||((Number)count).longValue()<1||((Number)count).longValue()>1000000||!seen.add(key(day,kind,key)))throw new IllegalArgumentException("Invalid session row");
        }
    }
    static List<Statistics.Row> attach(List<Statistics.Row> rows,JSONObject snapshot) throws Exception {
        JSONObject data=snapshot.optJSONObject("sessions");if(data==null)return rows;
        Map<String,Long> counts=new HashMap<>();JSONArray values=data.getJSONArray("rows");
        for(int i=0;i<values.length();i++){JSONArray r=values.getJSONArray(i);counts.put(key(r.getString(0),r.getString(1),r.getString(2)),r.getLong(3));}
        List<Statistics.Row> result=new ArrayList<>();
        for(var r:rows)result.add(new Statistics.Row(r.day(),r.key(),r.name(),r.kind(),r.seconds(),r.device(),counts.getOrDefault(key(r.day(),r.kind(),r.kind().equals("browser")?"other":r.key()),0L),data.getString("since")));
        return result;
    }
    static boolean partial(Statistics.Row row,String start){return row.sessionsSince().isEmpty()||row.day().compareTo(row.sessionsSince())<=0;}
    static String display(long count,boolean partial){return Long.toString(count);}
}
