package hu.keepimproving.android;

import android.database.Cursor;
import org.json.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.*;
import java.util.*;

/** Common PC/phone rule registers. Only locally measured counters are exported. */
final class PhoneShared {
    static void set(JSONObject v,String k,Object x){PhoneRules.set(v,k,x);}
    static String hash(String text){try{StringBuilder hex=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8)))hex.append(String.format(Locale.ROOT,"%02x",b&255));return hex.toString();}catch(Exception e){throw new IllegalStateException(e);}}
    static String connection(String code){return code.isEmpty()?"":"local-v1:"+hash("GameTimeMonitor/local-group/v1\0"+code);}
    static String connection(PhoneStore s){return s.get("shared_connection","");}
    static JSONObject records(PhoneStore s){return s.json("shared_records:"+connection(s),new JSONObject());}
    static JSONObject aliases(PhoneStore s){return s.json("shared_aliases:"+connection(s),new JSONObject());}
    static JSONObject groups(PhoneStore s){JSONObject out=new JSONObject(),r=records(s);for(String id:keys(r)){JSONObject x=r.optJSONObject(id);if(x.optString("kind").equals("group")&&!x.isNull("value"))set(out,id,x.optJSONObject("value"));}return out;}
    static List<String> keys(JSONObject o){List<String> out=new ArrayList<>();if(o!=null)o.keys().forEachRemaining(out::add);return out;}
    static void schema(android.database.sqlite.SQLiteDatabase db){
        db.execSQL("CREATE TABLE IF NOT EXISTS shared_usage (id TEXT NOT NULL,day TEXT NOT NULL,minute INTEGER NOT NULL,millis INTEGER NOT NULL,PRIMARY KEY(id,day))");
        db.execSQL("CREATE TABLE IF NOT EXISTS shared_remote_usage (device TEXT NOT NULL,id TEXT NOT NULL,day TEXT NOT NULL,minute INTEGER NOT NULL,millis INTEGER NOT NULL,PRIMARY KEY(device,id,day))");
        db.execSQL("CREATE TABLE IF NOT EXISTS shared_remote_sessions (device TEXT NOT NULL,id TEXT NOT NULL,day TEXT NOT NULL,minute INTEGER NOT NULL,count INTEGER NOT NULL,PRIMARY KEY(device,id,day))");
    }
    static void scope(JSONObject v){
        if(v==null)return;String mode=v.optString("mode");if(!Set.of("device","group","all").contains(mode))throw new IllegalArgumentException("scope");
        if(!mode.equals("all")&&!v.optString(mode).matches("[0-9a-f]{32}"))throw new IllegalArgumentException("scope");
        if(v.has("connection")&&!v.optString("connection").matches("local-v1:[0-9a-f]{64}"))throw new IllegalArgumentException("connection");
    }
    static boolean applies(PhoneStore s,JSONObject v){return applies(s,v,s.device());}
    static boolean applies(PhoneStore s,JSONObject v,String device){
        if(v==null)return true;if(!v.optString("connection").equals(connection(s)))return false;
        return switch(v.optString("mode")){case "all"->true;case "device"->device.equals(v.optString("device"));case "group"->{JSONObject g=groups(s).optJSONObject(v.optString("group"));yield g!=null&&PhoneRules.contains(g.optJSONArray("devices"),device);}default->false;};
    }
    static JSONObject empty(){JSONObject v=new JSONObject();set(v,"records",new JSONObject());set(v,"usage",new JSONArray());return v;}
    static void validate(JSONObject payload) throws Exception {
        JSONObject records=payload.getJSONObject("records");JSONArray usage=payload.getJSONArray("usage");if(records.length()>500||usage.length()>2000||payload.toString().getBytes(StandardCharsets.UTF_8).length>240000)throw new IllegalArgumentException("size");
        for(String id:keys(records)){
            JSONObject r=records.getJSONObject(id);if(!id.matches("[0-9a-f]{32}")||!r.getString("device").matches("[0-9a-f]{32}")||r.getLong("clock")<=0||r.getLong("clock")>=9007199254740992L||!Set.of("group","budget","notification").contains(r.getString("kind")))throw new IllegalArgumentException("record");
            if(r.isNull("value"))continue;JSONObject v=r.getJSONObject("value");String kind=r.getString("kind");
            if(kind.equals("group")){if(v.getString("name").isBlank()||v.getString("name").length()>80||!v.getString("connection").matches("local-v1:[0-9a-f]{64}")||v.getJSONArray("devices").length()>20)throw new IllegalArgumentException("group");Set<String> seen=new HashSet<>();for(int i=0;i<v.getJSONArray("devices").length();i++){String device=v.getJSONArray("devices").getString(i);if(!device.matches("[0-9a-f]{32}")||!seen.add(device))throw new IllegalArgumentException("device");}continue;}
            scope(v.getJSONObject("devices"));if(!v.getJSONObject("devices").has("connection"))throw new IllegalArgumentException("connection");
            if(!(v.get("enabled") instanceof Boolean))throw new IllegalArgumentException("enabled");
            if(v.has("days")){JSONArray days=v.getJSONArray("days");Set<Integer> selected=new HashSet<>();for(int i=0;i<days.length();i++){Object raw=days.get(i);int day=days.getInt(i);if(!(raw instanceof Integer||raw instanceof Long)||day<0||day>6||!selected.add(day))throw new IllegalArgumentException("days");}}
            if(kind.equals("budget")){
                for(String key:List.of("enforce","usage_limit"))if(!(v.get(key) instanceof Boolean))throw new IllegalArgumentException(key);
                double seconds=v.getDouble("seconds");if(!Double.isFinite(seconds)||seconds<0||seconds>86400||v.getString("name").isBlank()||v.getString("name").length()>80)throw new IllegalArgumentException("budget");
                PhoneRules.bounded(v,"reset_minute",0,1439);JSONArray days=v.getJSONArray("days"),members=v.getJSONArray("members");Set<Integer> seen=new HashSet<>();for(int i=0;i<days.length();i++){int d=days.getInt(i);if(d<0||d>6||!seen.add(d))throw new IllegalArgumentException("days");}if(members.length()==0||members.length()>200)throw new IllegalArgumentException("members");
                for(int i=0;i<members.length();i++){JSONObject m=members.getJSONObject(i);String k=m.getString("kind"),x=m.getString("value");if(!Set.of("category","game","app","site","android").contains(k)||x.isEmpty()||x.length()>2048||x.indexOf(0)>=0||k.equals("category")&&!Set.of("games","apps","sites").contains(x)||k.equals("android")&&!x.matches("[A-Za-z0-9_]+(?:\\.[A-Za-z0-9_]+)+"))throw new IllegalArgumentException("member");}
            }else{
                if(!Set.of("time","startup","pomodoros","warning","limit","session","bedtime").contains(v.getString("trigger"))||v.getString("title").length()>80||v.getString("text").length()>1000||!v.getString("icon").startsWith("preset:")||!Set.of("none","pomodoro").contains(v.getJSONObject("action").getString("kind")))throw new IllegalArgumentException("notification");
                PhoneRules.bounded(v,"minute",0,1439);PhoneRules.bounded(v,"count",1,1000);
            }
        }
        JSONArray sessions=payload.optJSONArray("session_usage");if(payload.has("session_usage")&&sessions==null)throw new IllegalArgumentException("sessions");
        if(sessions!=null){if(sessions.length()>2000)throw new IllegalArgumentException("sessions");Set<String> unique=new HashSet<>();for(int i=0;i<sessions.length();i++){JSONArray row=sessions.getJSONArray(i);String id=row.getString(0),day=row.getString(1);SyncProtocol.date(day);Object count=row.get(3);if(row.length()!=4||!id.matches("[0-9a-f]{32}")||!unique.add(id+day)||row.getInt(2)<0||row.getInt(2)>1439||!(count instanceof Number)||((Number)count).doubleValue()!=row.getLong(3)||row.getLong(3)<0||row.getLong(3)>1000000)throw new IllegalArgumentException("sessions");}}
        Set<String> seen=new HashSet<>();for(int i=0;i<usage.length();i++){JSONArray row=usage.getJSONArray(i);double seconds=row.getDouble(3);String id=row.getString(0),day=row.getString(1);SyncProtocol.date(day);if(row.length()!=4||!id.matches("[0-9a-f]{32}")||!seen.add(id+day)||row.getInt(2)<0||row.getInt(2)>1439||!Double.isFinite(seconds)||seconds<0||seconds>172800)throw new IllegalArgumentException("usage");}
    }
    static void update(PhoneStore s,JSONObject r,String id,String kind,JSONObject value){long clock=System.currentTimeMillis();for(String k:keys(r))clock=Math.max(clock,r.optJSONObject(k).optLong("clock"));JSONObject entry=new JSONObject();set(entry,"clock",clock+1);set(entry,"device",s.device());set(entry,"kind",kind);set(entry,"value",value==null?JSONObject.NULL:value);set(r,id,entry);}
    static JSONObject portable(PhoneStore s,String kind,JSONObject local,JSONObject previous){
        JSONObject v=new JSONObject();set(v,"devices",local.optJSONObject("devices"));
        if(kind.equals("budget")){
            for(String key:new String[]{"name","enabled"})set(v,key,local.opt(key));set(v,"seconds",local.optInt("minutes")*60);set(v,"enforce",local.optBoolean("block"));set(v,"usage_limit",local.optBoolean("limit"));set(v,"reset_minute",local.optInt("renewal",(int)s.number("day_start",0)));
            JSONArray days=new JSONArray(),members=new JSONArray();for(int i=0;i<7;i++)if((local.optInt("days")&(1<<i))!=0)days.put(i);set(v,"days",days);
            String category=local.optString("category");for(String c:List.of("games","apps"))if(category.equals(c)||category.equals("all")){JSONObject m=new JSONObject();set(m,"kind","category");set(m,"value",c);members.put(m);}
            JSONArray apps=local.optJSONArray("apps");if(apps!=null)for(int i=0;i<apps.length();i++){JSONObject m=new JSONObject();set(m,"kind","android");set(m,"value",apps.optString(i));members.put(m);}
            JSONArray old=previous==null?null:previous.optJSONArray("members");if(old!=null)for(int i=0;i<old.length();i++){JSONObject m=old.optJSONObject(i);if(m!=null&&!m.optString("kind").equals("android")&&(!m.optString("kind").equals("category")||m.optString("value").equals("sites")))members.put(m);}
            set(v,"members",members);
        }else{
            JSONArray days=new JSONArray();for(int i=0;i<7;i++)if((local.optInt("days",127)&(1<<i))!=0)days.put(i);set(v,"days",days);for(String k:new String[]{"title","text","enabled"})set(v,k,local.opt(k));set(v,"icon","preset:"+local.optString("icon","bell"));set(v,"minute",local.optInt("clock"));set(v,"count",local.optInt("rounds",4));set(v,"timeout",local.optInt("timeout"));set(v,"template",local.optString("_template"));set(v,"trigger",switch(local.optString("trigger")){case "clock"->"time";case "rounds"->"pomodoros";case "startup"->"startup";default->local.optString("trigger");});
            JSONObject action=new JSONObject();set(action,"kind",local.optString("action").equals("focus")?"pomodoro":"none");if(action.optString("kind").equals("pomodoro")){set(action,"work",local.optInt("work"));set(action,"short_break",local.optInt("short"));set(action,"long_break",local.optInt("long"));set(action,"rounds",local.optInt("cycles"));}set(v,"action",action);
        }return v;
    }
    static void observe(PhoneStore s){
        if(connection(s).isEmpty())return;JSONObject records=records(s),aliases=aliases(s);Map<String,JSONObject> values=new HashMap<>();
        for(String kind:List.of("budget","reminder")){JSONArray rules=s.rules(kind);for(int i=0;i<rules.length();i++){JSONObject v=rules.optJSONObject(i);values.put(kind+":"+v.optString("id"),v);JSONObject scope=v.optJSONObject("devices");if(scope==null||!scope.optString("connection").equals(connection(s)))continue;
            String sharedKind=kind.equals("budget")?kind:"notification",id=v.optString("_shared");if(id.isEmpty())id=hash(s.device()+":"+sharedKind+":"+v.optString("id")).substring(0,32);
            JSONObject alias=aliases.optJSONObject(id);if(alias==null||!v.toString().equals(alias.optString("baseline"))){JSONObject old=records.optJSONObject(id);update(s,records,id,sharedKind,portable(s,sharedKind,v,old==null?null:old.optJSONObject("value")));alias=new JSONObject();set(alias,"kind",kind);set(alias,"native",v.optString("id"));set(alias,"baseline",v.toString());set(aliases,id,alias);}
        }}
        for(String id:keys(aliases)){JSONObject alias=aliases.optJSONObject(id);if(!alias.optString("baseline").isEmpty()&&!values.containsKey(alias.optString("kind")+":"+alias.optString("native"))){update(s,records,id,alias.optString("kind").equals("budget")?"budget":"notification",null);set(alias,"baseline","");}}
        try{JSONObject check=empty();set(check,"records",records);validate(check);}catch(Exception ex){throw new IllegalArgumentException("shared rule",ex);}s.put("shared_records:"+connection(s),records.toString());s.put("shared_aliases:"+connection(s),aliases.toString());
    }
    static void merge(PhoneStore s,JSONObject snapshot,String code) throws Exception {
        String conn=connection(code);if(!conn.equals(connection(s))){clear(s);s.put("shared_connection",conn);}JSONObject payload=snapshot.optJSONObject("scoped_rules");if(payload==null)return;validate(payload);
        JSONObject records=records(s),incoming=payload.getJSONObject("records");for(String id:keys(incoming)){JSONObject r=incoming.getJSONObject(id),old=records.optJSONObject(id);if(old!=null&&!old.getString("kind").equals(r.getString("kind")))throw new IllegalArgumentException("kind");if(old==null||r.getLong("clock")>old.getLong("clock")||r.getLong("clock")==old.getLong("clock")&&r.getString("device").compareTo(old.getString("device"))>0)set(records,id,r);}
        JSONObject check=empty();set(check,"records",records);validate(check);s.put("shared_records:"+conn,records.toString());
        var db=s.getWritableDatabase();String device=snapshot.getString("device");db.delete("shared_remote_usage","device=?",new String[]{device});JSONArray usage=payload.getJSONArray("usage");for(int i=0;i<usage.length();i++){JSONArray r=usage.getJSONArray(i);db.execSQL("INSERT INTO shared_remote_usage VALUES (?,?,?,?,?)",new Object[]{device,r.getString(0),r.getString(1),r.getInt(2),Math.round(r.getDouble(3)*1000)});}db.delete("shared_remote_sessions","device=?",new String[]{device});JSONArray sessions=payload.optJSONArray("session_usage");if(sessions!=null)for(int i=0;i<sessions.length();i++){JSONArray r=sessions.getJSONArray(i);db.execSQL("INSERT INTO shared_remote_sessions VALUES (?,?,?,?,?)",new Object[]{device,r.getString(0),r.getString(1),r.getInt(2),r.getLong(3)});}s.put("shared_received_at",Long.toString(System.currentTimeMillis()));apply(s);
    }
    static void apply(PhoneStore s){
        JSONObject records=records(s),aliases=aliases(s);for(String id:keys(records)){
            JSONObject entry=records.optJSONObject(id);String kind=entry.optString("kind");if(kind.equals("group"))continue;String nativeKind=kind.equals("budget")?"budget":"reminder";JSONObject alias=aliases.optJSONObject(id);String nativeId=alias==null?id:alias.optString("native");JSONObject old=null;
            JSONArray rules=s.rules(nativeKind);for(int i=0;i<rules.length();i++)if(rules.optJSONObject(i).optString("id").equals(nativeId))old=rules.optJSONObject(i);
            JSONObject v=entry.optJSONObject("value"),local=null;
            if(v!=null){local=old==null?(kind.equals("budget")?PhoneRules.budget():PhoneRules.reminder()):PhoneRules.copy(old);set(local,"id",nativeId);set(local,"devices",v.optJSONObject("devices"));set(local,"enabled",v.optBoolean("enabled"));set(local,"_shared",id);set(local,"_sharedClock",entry.optLong("clock"));set(local,"_sharedWriter",entry.optString("device"));if(!local.has("_sharedSince"))set(local,"_sharedSince",System.currentTimeMillis());
                if(kind.equals("budget")){
                    set(local,"name",v.optString("name"));set(local,"minutes",(int)Math.ceil(v.optDouble("seconds")/60));set(local,"limit",v.optBoolean("usage_limit"));set(local,"block",v.optBoolean("enforce"));set(local,"renewal",v.optInt("reset_minute"));int days=0;JSONArray d=v.optJSONArray("days");for(int i=0;i<d.length();i++)days|=1<<d.optInt(i);set(local,"days",days);
                    JSONArray members=v.optJSONArray("members"),apps=new JSONArray();boolean games=false,applications=false;for(int i=0;i<members.length();i++){JSONObject m=members.optJSONObject(i);if(m.optString("kind").equals("android"))apps.put(m.optString("value"));if(m.optString("kind").equals("category")){games|=m.optString("value").equals("games");applications|=m.optString("value").equals("apps");}}
                    set(local,"category",games&&applications?"all":games?"games":applications?"apps":"");set(local,"apps",apps);
                }else{
                    JSONArray selectedDays=v.optJSONArray("days");int selectedMask=selectedDays==null?127:0;if(selectedDays!=null)for(int i=0;i<selectedDays.length();i++)selectedMask|=1<<selectedDays.optInt(i);set(local,"days",selectedMask);set(local,"title",v.optString("title"));set(local,"text",v.optString("text"));set(local,"icon",v.optString("icon","preset:bell").replace("preset:",""));set(local,"clock",v.optInt("minute"));set(local,"rounds",v.optInt("count",4));set(local,"timeout",v.optInt("timeout"));set(local,"_template",v.optString("template"));set(local,"trigger",switch(v.optString("trigger")){case "time"->"clock";case "pomodoros"->"rounds";default->v.optString("trigger");});
                    JSONObject action=v.optJSONObject("action");if(action.optString("kind").equals("pomodoro")){set(local,"action","focus");set(local,"work",action.optInt("work"));set(local,"short",action.optInt("short_break"));set(local,"long",action.optInt("long_break"));set(local,"cycles",action.optInt("rounds"));}else if(old==null||!old.optString("action").equals("app"))set(local,"action","none");
                }
            }
            if(local==null)s.getWritableDatabase().delete("rules","kind=? AND id=?",new String[]{nativeKind,nativeId});else if(old==null||!old.toString().equals(local.toString()))s.getWritableDatabase().execSQL("INSERT OR REPLACE INTO rules VALUES (?,?,?)",new Object[]{nativeKind,nativeId,local.toString()});
            JSONObject a=new JSONObject();set(a,"kind",nativeKind);set(a,"native",nativeId);set(a,"baseline",local==null?"":local.toString());set(aliases,id,a);
        }s.put("shared_aliases:"+connection(s),aliases.toString());
    }
    static JSONObject snapshot(PhoneStore s,String code) throws Exception {
        if(code.isEmpty()||code.equals("00000000000000000000000000000000"))return empty();String conn=connection(code);if(!connection(s).equals(conn)){clear(s);s.put("shared_connection",conn);}observe(s);apply(s);JSONObject payload=empty();set(payload,"records",records(s));JSONArray usage=new JSONArray();JSONArray rules=s.rules("budget");
        for(int i=0;i<rules.length();i++){JSONObject r=rules.optJSONObject(i);String id=r.optString("_shared");if(id.isEmpty()||!applies(s,r.optJSONObject("devices")))continue;localUsed(s,r,System.currentTimeMillis());try(Cursor c=s.getReadableDatabase().rawQuery("SELECT day,minute,millis FROM shared_usage WHERE id=? AND day>=?",new String[]{id,LocalDate.now().minusDays(7).toString()})){while(c.moveToNext())usage.put(new JSONArray().put(id).put(c.getString(0)).put(c.getInt(1)).put(c.getLong(2)/1000.0));}}
        JSONArray sessions=new JSONArray();for(int i=0;i<rules.length();i++){JSONObject r=rules.optJSONObject(i);String id=r.optString("_shared");if(id.isEmpty()||!applies(s,r.optJSONObject("devices")))continue;int minute=r.optInt("renewal",(int)s.number("day_start",0));LocalDate today=LocalDate.parse(PhoneRules.day(System.currentTimeMillis(),minute,ZoneId.systemDefault()));for(int n=0;n<8;n++){String day=today.minusDays(n).toString();long count=SessionCounts.budget(s,r,day,minute);if(count>0)sessions.put(new JSONArray().put(id).put(day).put(minute).put(count));}}
        set(payload,"session_usage",sessions);
        set(payload,"usage",usage);validate(payload);return payload;
    }
    static long localUsed(PhoneStore s,JSONObject rule,long now){
        String id=rule.optString("_shared");int minute=rule.optInt("renewal",(int)s.number("day_start",0));String day=PhoneRules.day(now,minute,ZoneId.systemDefault());if(id.isEmpty())return s.used(rule,day);String marker="shared_seed:"+id;int old=(int)s.number(marker,-1);
        if(old!=minute){long seed=s.used(rule,PhoneRuntime.day(s,now));if(old>=0)try(Cursor c=s.getReadableDatabase().rawQuery("SELECT millis FROM shared_usage WHERE id=? AND day=?",new String[]{id,PhoneRules.day(now,old,ZoneId.systemDefault())})){if(c.moveToFirst())seed=c.getLong(0);}s.getWritableDatabase().delete("shared_usage","id=?",new String[]{id});s.getWritableDatabase().execSQL("INSERT INTO shared_usage VALUES (?,?,?,?)",new Object[]{id,day,minute,seed});s.put(marker,Integer.toString(minute));}
        try(Cursor c=s.getReadableDatabase().rawQuery("SELECT millis FROM shared_usage WHERE id=? AND day=? AND minute=?",new String[]{id,day,Integer.toString(minute)})){return c.moveToFirst()?c.getLong(0):0;}
    }
    static long used(PhoneStore s,JSONObject rule,long now){
        long total=localUsed(s,rule,now);String id=rule.optString("_shared");if(id.isEmpty())return total;int minute=rule.optInt("renewal");String day=PhoneRules.day(now,minute,ZoneId.systemDefault());
        try(Cursor c=s.getReadableDatabase().rawQuery("SELECT device,millis FROM shared_remote_usage WHERE id=? AND day=? AND minute=?",new String[]{id,day,Integer.toString(minute)})){while(c.moveToNext())if(!c.getString(0).equals(s.device())&&applies(s,rule.optJSONObject("devices"),c.getString(0)))total+=c.getLong(1);}return total;
    }
    static long sessions(PhoneStore s,JSONObject rule,long now){
        int minute=rule.optInt("renewal",(int)s.number("day_start",0));String day=PhoneRules.day(now,minute,ZoneId.systemDefault());long total=SessionCounts.budget(s,rule,day,minute);String id=rule.optString("_shared");
        JSONObject scope=rule.optJSONObject("devices");if(id.isEmpty()||scope!=null&&!scope.optString("accounting","shared").equals("shared"))return total;
        try(Cursor c=s.getReadableDatabase().rawQuery("SELECT device,count FROM shared_remote_sessions WHERE id=? AND day=? AND minute=?",new String[]{id,day,Integer.toString(minute)})){while(c.moveToNext())if(!c.getString(0).equals(s.device())&&applies(s,scope,c.getString(0)))total+=c.getLong(1);}return total;
    }
    static void credit(PhoneStore s,UsageLedger.Slice slice,boolean game){
        JSONArray rules=s.rules("budget");ZoneId zone=ZoneId.systemDefault();for(int i=0;i<rules.length();i++){JSONObject r=rules.optJSONObject(i);String id=r.optString("_shared");if(id.isEmpty()||!PhoneRules.matches(r,slice.pkg(),game))continue;int minute=r.optInt("renewal");localUsed(s,r,slice.start());
            long start=slice.start(),end=start+slice.millis();while(start<end){long next=Math.min(end,PhoneRules.nextDay(start,minute,zone));String day=PhoneRules.day(start,minute,zone);long visible=CoverageLedger.visible(s.coverage(slice.pkg(),start,next),start,next);s.getWritableDatabase().execSQL("INSERT OR IGNORE INTO shared_usage VALUES (?,?,?,0)",new Object[]{id,day,minute});s.getWritableDatabase().execSQL("UPDATE shared_usage SET millis=millis+? WHERE id=? AND day=?",new Object[]{visible,id,day});start=next;}
        }
    }
    static void changed(PhoneStore s){observe(s);apply(s);}
    static String nativeId(PhoneStore s,String id){JSONObject a=aliases(s).optJSONObject(id);return a==null?id:a.optString("native",id);}
    static void clear(PhoneStore s){s.put("shared_connection","");s.getWritableDatabase().delete("shared_remote_usage",null,null);s.getWritableDatabase().delete("shared_remote_sessions",null,null);}
}
