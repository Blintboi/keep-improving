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
    PhoneStore(Context context) { super(context,"usage.sqlite3",null,1); }
    @Override public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)");
        db.execSQL("CREATE TABLE usage (day TEXT NOT NULL, package TEXT NOT NULL, name TEXT NOT NULL, game INTEGER NOT NULL, millis INTEGER NOT NULL, PRIMARY KEY(day,package))");
        db.execSQL("CREATE TABLE remote (device TEXT PRIMARY KEY, revision TEXT NOT NULL, payload TEXT NOT NULL)");
    }
    @Override public void onUpgrade(SQLiteDatabase db,int oldVersion,int newVersion) { throw new IllegalStateException("Unknown schema"); }
    String get(String key,String fallback) {
        try(Cursor c=getReadableDatabase().rawQuery("SELECT value FROM meta WHERE key=?",new String[]{key})) { return c.moveToFirst()?c.getString(0):fallback; }
    }
    long number(String key,long fallback) { try { return Long.parseLong(get(key,"")); } catch(NumberFormatException e) { return fallback; } }
    void put(String key,String value) {
        ContentValues row=new ContentValues(); row.put("key",key); row.put("value",value);
        getWritableDatabase().insertWithOnConflict("meta",null,row,SQLiteDatabase.CONFLICT_REPLACE);
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
        String started=get("started",LocalDate.now().toString());
        long revision=Math.max(number("revision",0)+1,System.currentTimeMillis()*1_000_000L);
        put("revision",Long.toString(revision));
        return new JSONObject().put("format",SyncProtocol.STATISTICS).put("group",code).put("device",device()).put("name",name())
            .put("started",started).put("revision",revision).put("rows",rows(true)).put("activity_started",started).put("activity",rows(false));
    }
    JSONObject known() throws Exception {
        JSONObject result=new JSONObject();
        try(Cursor c=getReadableDatabase().rawQuery("SELECT device,revision FROM remote",null)) { while(c.moveToNext()) result.put(c.getString(0),c.getString(1)); }
        return result;
    }
    void accept(JSONArray entries) throws Exception {
        SQLiteDatabase db=getWritableDatabase(); db.beginTransaction();
        try {
            for(int i=0;i<entries.length();i++) {
                JSONObject entry=entries.getJSONObject(i); String device=entry.getString("device"); long revision=Long.parseLong(entry.getString("revision"));
                try(Cursor c=db.rawQuery("SELECT revision FROM remote WHERE device=?",new String[]{device})) { if(c.moveToFirst()&&Long.parseLong(c.getString(0))>=revision) continue; }
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
