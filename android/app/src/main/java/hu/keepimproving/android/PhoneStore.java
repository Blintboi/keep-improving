package hu.keepimproving.android;

import android.content.Context;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import android.os.Build;
import org.json.JSONArray;
import org.json.JSONObject;
import java.time.LocalDate;
import java.util.UUID;

final class PhoneStore extends SQLiteOpenHelper {
    PhoneStore(Context context) { super(context,"usage.sqlite3",null,6); }
    @Override public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)");
        db.execSQL("CREATE TABLE usage (day TEXT NOT NULL, package TEXT NOT NULL, name TEXT NOT NULL, game INTEGER NOT NULL, millis INTEGER NOT NULL, PRIMARY KEY(day,package))");
        db.execSQL("CREATE TABLE remote (device TEXT PRIMARY KEY, revision TEXT NOT NULL, payload TEXT NOT NULL)");
        features(db); PhoneCompanion.schema(db);PhoneShared.schema(db);SessionCounts.schema(db);
    }
    private void features(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE IF NOT EXISTS rules (kind TEXT NOT NULL,id TEXT NOT NULL,value TEXT NOT NULL,PRIMARY KEY(kind,id))");
        db.execSQL("CREATE TABLE IF NOT EXISTS focus_rounds (day TEXT NOT NULL,token TEXT NOT NULL,round INTEGER NOT NULL,at INTEGER NOT NULL,PRIMARY KEY(token,round))");
        db.execSQL("CREATE TABLE IF NOT EXISTS notices (id TEXT PRIMARY KEY,value TEXT NOT NULL,at INTEGER NOT NULL,delivered INTEGER NOT NULL DEFAULT 0)");
        db.execSQL("CREATE TABLE IF NOT EXISTS coverage (id TEXT PRIMARY KEY,package TEXT NOT NULL,start INTEGER NOT NULL,finish INTEGER NOT NULL)");
    }
    @Override public void onUpgrade(SQLiteDatabase db,int oldVersion,int newVersion) {
        if(oldVersion<6)SessionCounts.schema(db);
        if(oldVersion<2)features(db); PhoneCompanion.schema(db);PhoneShared.schema(db);
        // The service raised the obsolete 20/day allowance. Recheck a cached long
        // refusal once after upgrading, retaining the ordinary short guard.
        // Any current server limit still wins and is persisted by PhoneSync.
        if(oldVersion<5)db.execSQL("UPDATE meta SET value=CAST(MIN(CAST(value AS INTEGER),MAX(?,COALESCE((SELECT CAST(value AS INTEGER) FROM meta WHERE key='last_sync'),0)+15000)) AS TEXT) WHERE key='sync_after'",new Object[]{System.currentTimeMillis()});
    }
    JSONObject json(String key,JSONObject fallback) {return PhoneRules.object(get(key,fallback.toString()));}
    JSONArray rules(String kind) {
        JSONArray rows=new JSONArray();try(Cursor c=getReadableDatabase().rawQuery("SELECT value FROM rules WHERE kind=? ORDER BY rowid",new String[]{kind})) {while(c.moveToNext())rows.put(PhoneRules.object(c.getString(0)));}return rows;
    }
    void saveRule(String kind,JSONObject value) {
        PhoneRules.validate(value,kind.equals("reminder"));
        String id=value.optString("_shared");if(!id.isEmpty()){JSONObject r=PhoneShared.records(this).optJSONObject(id);if(r!=null&&(r.optLong("clock")!=value.optLong("_sharedClock")||!r.optString("device").equals(value.optString("_sharedWriter"))))throw new IllegalStateException("conflict");}
        ContentValues row=new ContentValues();row.put("value",value.toString());SQLiteDatabase db=getWritableDatabase();
        db.beginTransaction();try{
        if(db.update("rules",row,"kind=? AND id=?",new String[]{kind,value.optString("id")})==0){row.put("kind",kind);row.put("id",value.optString("id"));db.insertOrThrow("rules",null,row);}
        PhoneShared.changed(this);db.setTransactionSuccessful();}finally{db.endTransaction();}
    }
    void deleteRule(String kind,String id) {var db=getWritableDatabase();db.beginTransaction();try{db.delete("rules","kind=? AND id=?",new String[]{kind,id});PhoneShared.changed(this);db.setTransactionSuccessful();}finally{db.endTransaction();}}
    java.util.List<CoverageLedger.Interval> coverage(String pkg,long start,long end){java.util.List<CoverageLedger.Interval> intervals=new java.util.ArrayList<>();try(Cursor c=getReadableDatabase().rawQuery("SELECT start,finish FROM coverage WHERE package=? AND start<? AND (finish=0 OR finish>?)",new String[]{pkg,Long.toString(end),Long.toString(start)})){while(c.moveToNext())intervals.add(new CoverageLedger.Interval(c.getLong(0),c.getLong(1)==0?end:c.getLong(1)));}return intervals;}
    int rounds(String day) {try(Cursor c=getReadableDatabase().rawQuery("SELECT COUNT(*) FROM focus_rounds WHERE day=?",new String[]{day})){return c.moveToFirst()?c.getInt(0):0;}}
    long used(JSONObject rule,String day) {
        long total=0;try(Cursor c=getReadableDatabase().rawQuery("SELECT package,game,millis FROM usage WHERE day=?",new String[]{day})) {while(c.moveToNext())if(PhoneRules.matches(rule,c.getString(0),c.getInt(1)!=0))total+=c.getLong(2);}return total;
    }
    String get(String key,String fallback) {
        try(Cursor c=getReadableDatabase().rawQuery("SELECT value FROM meta WHERE key=?",new String[]{key})) { return c.moveToFirst()?c.getString(0):fallback; }
    }
    long number(String key,long fallback) { try { return Long.parseLong(get(key,"")); } catch(NumberFormatException e) { return fallback; } }
    void put(String key,String value) {
        if(value.equals(get(key,null)))return;
        ContentValues row=new ContentValues(); row.put("key",key); row.put("value",value);
        if(getWritableDatabase().insertWithOnConflict("meta",null,row,SQLiteDatabase.CONFLICT_REPLACE)<0)throw new android.database.sqlite.SQLiteException("Could not save settings");
    }
    String device() {
        String id=get("device",""); if(id.isEmpty()) { id=UUID.randomUUID().toString().replace("-",""); put("device",id); }
        return id;
    }
    String name() { return get("name",Build.MODEL); }
    void resetCursor(long now) { put("cursor",Long.toString(now)); put("active",""); put("activity",""); }
    void add(UsageLedger.Slice slice,String name,boolean game) {
        SQLiteDatabase db=getWritableDatabase();
        db.execSQL("INSERT OR IGNORE INTO usage VALUES (?,?,?,?,0)",new Object[]{slice.day(),slice.pkg(),name,game?1:0});
        db.execSQL("UPDATE usage SET millis=millis+?,name=?,game=? WHERE day=? AND package=?",new Object[]{slice.millis(),name,game?1:0,slice.day(),slice.pkg()});
    }
    JSONArray rows(boolean games) throws Exception {
        JSONArray rows=new JSONArray();
        try(Cursor c=getReadableDatabase().rawQuery("SELECT day,package,name,millis FROM usage WHERE game=? AND millis>0 ORDER BY day,package",new String[]{games?"1":"0"})) {
            while(c.moveToNext()) rows.put(games
                ?new JSONArray().put(c.getString(0)).put("android:"+c.getString(1)).put(c.getString(2)).put("Android").put(c.getLong(3)/1000.0)
                :new JSONArray().put(c.getString(0)).put("app").put("android:"+c.getString(1)).put(c.getString(2)).put(c.getLong(3)/1000.0));
        }
        return rows;
    }
    JSONObject snapshot(String code) throws Exception {
        SQLiteDatabase db=getWritableDatabase();db.beginTransaction();try{JSONObject result=snapshotLocked(code);db.setTransactionSuccessful();return result;}finally{db.endTransaction();}
    }
    private JSONObject snapshotLocked(String code) throws Exception {
        String started=get("started",LocalDate.now().toString());
        long revision=Math.max(number("revision",0)+1,System.currentTimeMillis()*1_000_000L);
        put("revision",Long.toString(revision));
        return new JSONObject().put("format",SyncProtocol.STATISTICS).put("group",code).put("device",device()).put("name",name())
            .put("started",started).put("revision",revision).put("rows",rows(true)).put("activity_started",started).put("activity",rows(false)).put("sessions",SessionCounts.snapshot(this)).put("focus_rounds",PhoneCompanion.localRounds(this)).put("remote_commands",PhoneCompanion.commands(this)).put("scoped_rules",PhoneShared.snapshot(this,code));
    }
    JSONObject known() throws Exception {
        JSONObject result=new JSONObject();
        try(Cursor c=getReadableDatabase().rawQuery("SELECT device,revision FROM remote",null)) { while(c.moveToNext()) result.put(c.getString(0),c.getString(1)); }
        return result;
    }
    void accept(JSONArray entries) throws Exception {accept(entries,null);}
    void accept(JSONArray entries,String code) throws Exception {
        SQLiteDatabase db=getWritableDatabase(); db.beginTransaction();
        try {
            for(int i=0;i<entries.length();i++) {
                JSONObject entry=entries.getJSONObject(i); String device=entry.getString("device"); long revision=Long.parseLong(entry.getString("revision"));
                try(Cursor c=db.rawQuery("SELECT revision FROM remote WHERE device=?",new String[]{device})) { if(c.moveToFirst()&&Long.parseLong(c.getString(0))>=revision) continue; }
                if(code!=null){JSONObject snapshot=SyncProtocol.decode(entry,code);PhoneShared.merge(this,snapshot,code);PhoneCompanion.accept(this,snapshot);}
                ContentValues row=new ContentValues(); row.put("device",device); row.put("revision",Long.toString(revision)); row.put("payload",entry.getString("payload"));
                db.insertWithOnConflict("remote",null,row,SQLiteDatabase.CONFLICT_REPLACE);
            }
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
    }
    JSONArray remotes(String code) throws Exception {
        JSONArray result=new JSONArray();
        if(code.isEmpty()) return result;
        try(Cursor c=getReadableDatabase().rawQuery("SELECT device,revision,payload FROM remote ORDER BY device",null)) {
            while(c.moveToNext()) result.put(SyncProtocol.decode(new JSONObject().put("device",c.getString(0)).put("revision",c.getString(1)).put("payload",c.getString(2)),code));
        }
        return result;
    }
}
