package hu.keepimproving.android;

import android.database.Cursor;
import org.json.*;
import java.time.*;
import java.util.*;

/** Origin-owned snapshots and immutable, explicitly targeted edits. Never re-export imports. */
final class PhoneCompanion {
    static void schema(android.database.sqlite.SQLiteDatabase db){
        db.execSQL("CREATE TABLE IF NOT EXISTS companions (device TEXT PRIMARY KEY,name TEXT NOT NULL,value TEXT NOT NULL,rounds TEXT NOT NULL,first_seen INTEGER NOT NULL)");
        db.execSQL("CREATE TABLE IF NOT EXISTS commands (id TEXT PRIMARY KEY,target TEXT NOT NULL,kind TEXT NOT NULL,resource TEXT NOT NULL,value TEXT NOT NULL,status TEXT NOT NULL,reason TEXT NOT NULL)");
    }
    static void validate(JSONObject snapshot) throws Exception {
        JSONArray rounds=snapshot.optJSONArray("focus_rounds");
        if(snapshot.has("focus_rounds")&&rounds==null)throw new IllegalArgumentException();
        if(rounds!=null){if(rounds.length()>100000)throw new IllegalArgumentException();Set<String> seen=new HashSet<>();for(int i=0;i<rounds.length();i++){JSONArray row=rounds.getJSONArray(i);String day=row.getString(0);SyncProtocol.date(day);Object count=row.get(1);if(row.length()!=2||!seen.add(day)||!(count instanceof Integer||count instanceof Long)||row.getLong(1)<1||row.getLong(1)>10000)throw new IllegalArgumentException();}}
        if(!snapshot.has("companion"))return;JSONObject c=snapshot.getJSONObject("companion");
        if(!c.getString("format").equals("KeepImproving.companion.v1")||c.toString().length()>2*1024*1024)throw new IllegalArgumentException();
        c.getJSONObject("settings");c.getJSONObject("focus");String[] keys={"budgets","notifications","games","events"};int[] caps={2200,110,100000,200};for(int i=0;i<keys.length;i++)if(c.getJSONArray(keys[i]).length()>caps[i])throw new IllegalArgumentException();
        JSONObject icons=c.optJSONObject("icons");if(icons!=null){if(icons.length()>48||icons.toString().length()>140000)throw new IllegalArgumentException();for(Iterator<String> it=icons.keys();it.hasNext();)if(icons.getString(it.next()).length()>11000)throw new IllegalArgumentException();}
    }
    static void accept(PhoneStore store,JSONObject snapshot) throws Exception {
        validate(snapshot);String device=snapshot.getString("device");var db=store.getWritableDatabase();
        JSONObject value=snapshot.optJSONObject("companion");if(value==null)value=new JSONObject();JSONArray rounds=snapshot.optJSONArray("focus_rounds");if(rounds==null)rounds=new JSONArray();
        db.execSQL("INSERT OR IGNORE INTO companions VALUES (?,?,?,?,?)",new Object[]{device,snapshot.getString("name"),"{}","[]",System.currentTimeMillis()});
        db.execSQL("UPDATE companions SET name=?,value=?,rounds=? WHERE device=?",new Object[]{snapshot.getString("name"),value.toString(),rounds.toString(),device});
        JSONArray results=value.optJSONArray("command_results");if(results!=null)for(int i=0;i<results.length();i++){JSONObject r=results.getJSONObject(i);if(!r.optString("origin").equals(store.device())||!List.of("applied","rejected").contains(r.optString("status")))continue;db.execSQL("UPDATE commands SET status=?,reason=? WHERE id=? AND target=?",new Object[]{r.getString("status"),r.optString("reason"),r.getString("id"),device});}
        store.put("companion_revision",Long.toString(store.number("companion_revision",0)+1));
    }
    static JSONArray localRounds(PhoneStore store){JSONArray out=new JSONArray();try(Cursor c=store.getReadableDatabase().rawQuery("SELECT day,COUNT(*) FROM focus_rounds GROUP BY day ORDER BY day",null)){while(c.moveToNext())out.put(new JSONArray().put(c.getString(0)).put(c.getInt(1)));}return out;}
    private static String cachePath="";private static long cacheRevision=-1;private static List<JSONObject> cache=List.of();
    static synchronized List<JSONObject> devices(PhoneStore store){
        long revision=store.number("companion_revision",0);String path=store.getReadableDatabase().getPath();if(revision==cacheRevision&&path.equals(cachePath))return cache;
        List<JSONObject> rows=new ArrayList<>();try(Cursor c=store.getReadableDatabase().rawQuery("SELECT device,name,value,rounds,first_seen FROM companions ORDER BY name,device",null)){while(c.moveToNext()){JSONObject item=PhoneRules.object(c.getString(2));PhoneRules.set(item,"device",c.getString(0));PhoneRules.set(item,"name",c.getString(1));PhoneRules.set(item,"focus_rounds",PhoneRules.array(c.getString(3)));PhoneRules.set(item,"first_seen",c.getLong(4));rows.add(item);}}
        cachePath=path;cacheRevision=revision;cache=List.copyOf(rows);return cache;
    }
    static int rounds(PhoneStore store,String day){int total=store.rounds(day);for(JSONObject d:devices(store)){JSONArray rows=d.optJSONArray("focus_rounds");for(int i=0;i<rows.length();i++){JSONArray row=rows.optJSONArray(i);if(day.equals(row.optString(0)))total+=row.optInt(1);}}return total;}
    static JSONArray commands(PhoneStore store){JSONArray out=new JSONArray();try(Cursor c=store.getReadableDatabase().rawQuery("SELECT value FROM commands WHERE status='pending' ORDER BY rowid LIMIT 100",null)){while(c.moveToNext())out.put(PhoneRules.object(c.getString(0)));}return out;}
    static void queue(PhoneStore store,JSONObject device,String kind,String key,Object value) throws Exception {
        var db=store.getWritableDatabase();db.beginTransaction();try{
            try(Cursor c=db.rawQuery("SELECT COUNT(*) FROM commands WHERE status='pending' AND (target=? AND kind=? AND resource=?)",new String[]{device.getString("device"),kind,key})){if(c.moveToFirst()&&c.getInt(0)>0)throw new IllegalStateException("pending");}
            if(commands(store).length()>=100)throw new IllegalStateException("full");
            JSONObject hashes=device.getJSONObject("hashes");String base=hashes.optString(kind+":"+key,device.optString("empty_hash"));if(!base.matches("[0-9a-f]{64}"))throw new IllegalArgumentException("Unsupported PC version");
            String id=UUID.randomUUID().toString().replace("-","");JSONObject item=new JSONObject().put("id",id).put("target",device.getString("device")).put("kind",kind).put("key",key).put("base",base).put("value",value==null?JSONObject.NULL:value).put("created",System.currentTimeMillis());
            db.execSQL("INSERT INTO commands VALUES (?,?,?,?,?,'pending','')",new Object[]{id,device.getString("device"),kind,key,item.toString()});db.setTransactionSuccessful();
        }finally{db.endTransaction();}
    }
    static void clear(PhoneStore store){var db=store.getWritableDatabase();db.beginTransaction();try{PhoneShared.clear(store);db.delete("remote",null,null);db.delete("companions",null,null);db.delete("commands",null,null);store.put("companion_revision",Long.toString(store.number("companion_revision",0)+1));db.setTransactionSuccessful();}finally{db.endTransaction();}}
    static long notices(PhoneStore store,long now,List<PhoneRules.Notice> out){
        if(!store.get("pc_notifications","true").equals("true"))return Long.MAX_VALUE;long next=Long.MAX_VALUE;
        for(JSONObject device:devices(store)){
            JSONObject settings=device.optJSONObject("settings");if(settings==null)continue;int renewal=settings.optInt("budget_reset_minute");String day=PhoneRules.day(now,renewal,ZoneId.systemDefault());String prefix="pc:"+device.optString("device")+":";
            JSONArray rules=device.optJSONArray("notifications");Map<String,JSONObject> byId=new HashMap<>();if(rules!=null)for(int i=0;i<rules.length();i++){JSONObject r=rules.optJSONObject(i);if(r==null)continue;byId.put(r.optString("id"),r);if(r.has("devices")||!r.optBoolean("enabled")||!r.optString("trigger").equals("time"))continue;
                long at=PhoneRules.clock(day,r.optInt("minute"),renewal,ZoneId.systemDefault());if(now>=at&&at>=device.optLong("first_seen")&&now-at<3600000){JSONObject clock=PhoneRules.copy(r);PhoneRules.set(clock,"sound",!settings.optString("notification_sound").equals("silent"));notice(out,prefix+"scheduled:"+r.optString("id")+":"+day,device,clock);}
                for(int d=0;d<3;d++){long when=PhoneRules.clock(LocalDate.parse(day).plusDays(d).toString(),r.optInt("minute"),renewal,ZoneId.systemDefault());if(when>now){next=Math.min(next,when);break;}}
            }
            JSONArray events=device.optJSONArray("events");if(events!=null)for(int i=0;i<events.length();i++){JSONObject e=events.optJSONObject(i);if(e==null||e.optLong("at")<now-3600000||e.optLong("at")>now+60000)continue;String rule=e.optString("rule_id");JSONObject r=byId.get(rule);if(r!=null&&(!r.optBoolean("enabled")||!PhoneShared.applies(store,r.optJSONObject("devices"))))continue;String id=rule.isEmpty()?prefix+"event:"+e.optString("id"):prefix+"scheduled:"+rule+":"+e.optString("day");if(r!=null&&r.has("devices")){JSONObject ids=device.optJSONObject("shared_ids");String shared=ids==null?"":ids.optString("notification:"+rule);if(shared.isEmpty())continue;id="reminder:"+PhoneShared.nativeId(store,shared)+":"+e.optString("day");}notice(out,id,device,e);}
        }return next;
    }
    static void notice(List<PhoneRules.Notice> out,String id,JSONObject device,JSONObject source){
        JSONObject action=source.optJSONObject("action"),details=new JSONObject();String kind="none";
        if(action!=null&&action.optString("kind").equals("pomodoro")){kind="focus";PhoneRules.set(details,"work",action.optInt("work",25));PhoneRules.set(details,"short",action.optInt("short_break",5));PhoneRules.set(details,"long",action.optInt("long_break",15));PhoneRules.set(details,"cycles",action.optInt("rounds",4));}
        out.add(new PhoneRules.Notice(id,device.optString("name")+" · "+source.optString("title"),source.optString("text"),source.optBoolean("sound",true),kind,details));
    }
}
