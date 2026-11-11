package hu.keepimproving.android;

import org.json.*;
import java.time.*;
import java.util.*;

/** Phone-only rules. A package belongs to a group once, even with overlapping selectors. */
final class PhoneRules {
    static JSONObject copy(JSONObject value) { try {return new JSONObject(value.toString());}catch(JSONException e){throw new IllegalArgumentException(e);} }
    static JSONObject object(String value) {try{return new JSONObject(value);}catch(JSONException e){return new JSONObject();}}
    static JSONArray array(String value) {try{return new JSONArray(value);}catch(JSONException e){return new JSONArray();}}
    static void set(JSONObject object,String key,Object value) {try{object.put(key,value);}catch(JSONException e){throw new IllegalArgumentException(e);}}
    static String id(){return UUID.randomUUID().toString().replace("-","");}
    static String day(long now,int renewal,ZoneId zone) {
        var local=Instant.ofEpochMilli(now).atZone(zone);
        var boundary=local.toLocalDate().atTime(renewal/60,renewal%60).atZone(zone);
        return (local.toInstant().isBefore(boundary.toInstant())?local.toLocalDate().minusDays(1):local.toLocalDate()).toString();
    }
    static long clock(String day,int minute,int renewal,ZoneId zone) {
        LocalDate date=LocalDate.parse(day);if(minute<renewal)date=date.plusDays(1);
        return date.atTime(minute/60,minute%60).atZone(zone).toInstant().toEpochMilli();
    }
    static long nextDay(long now,int renewal,ZoneId zone) {
        return LocalDate.parse(day(now,renewal,zone)).plusDays(1).atTime(renewal/60,renewal%60).atZone(zone).toInstant().toEpochMilli();
    }
    static boolean contains(JSONArray values,String key) {if(values!=null)for(int i=0;i<values.length();i++)if(key.equals(values.optString(i)))return true;return false;}
    static boolean matches(JSONObject rule,String pkg,boolean game) {
        String category=rule.optString("category");
        return !pkg.isEmpty() && (category.equals("all") || category.equals(game?"games":"apps") || contains(rule.optJSONArray("apps"),pkg));
    }
    static boolean active(JSONObject rule,String day) {return rule.optBoolean("enabled",true) && (rule.optInt("days",127)&(1<<(LocalDate.parse(day).getDayOfWeek().getValue()-1)))!=0;}
    static JSONObject budget() {
        JSONObject b=new JSONObject();set(b,"id",id());set(b,"name","");set(b,"enabled",true);set(b,"days",127);set(b,"limit",true);
        set(b,"minutes",60);set(b,"block",true);set(b,"allowance",5);set(b,"category","");set(b,"apps",new JSONArray());set(b,"steps",new JSONArray());return b;
    }
    static JSONObject step() {
        JSONObject s=new JSONObject();set(s,"id",id());set(s,"kind","notify");set(s,"mode","usage");set(s,"minutes",30);
        set(s,"clock",1200);set(s,"duration",5);set(s,"sound",true);return s;
    }
    static JSONObject reminder() {
        JSONObject r=new JSONObject();set(r,"id",id());set(r,"title","");set(r,"text","");set(r,"enabled",true);set(r,"days",127);
        set(r,"trigger","clock");set(r,"clock",720);set(r,"rounds",4);set(r,"sound",true);set(r,"action","none");set(r,"package","");
        set(r,"timeout",0);set(r,"icon","bell");set(r,"work",25);set(r,"short",5);set(r,"long",15);set(r,"cycles",4);return r;
    }
    static void bounded(JSONObject value,String key,int min,int max) {
        Object raw=value.opt(key);if(!(raw instanceof Number) || ((Number)raw).doubleValue()!=((Number)raw).intValue() || value.optInt(key)<min||value.optInt(key)>max)throw new IllegalArgumentException(key);
    }
    static void validate(JSONObject rule,boolean reminder) {
        PhoneShared.scope(rule.optJSONObject("devices"));
        if(!rule.optString("id").matches("[a-f0-9]{32}"))throw new IllegalArgumentException("id");
        String title=rule.optString(reminder?"title":"name").trim();if(title.isEmpty()&&rule.optString("_template").isEmpty()||title.length()>100)throw new IllegalArgumentException("name");
        set(rule,reminder?"title":"name",title);bounded(rule,"days",0,127);
        if(reminder) {
            if(!(rule.optString("_shared").isEmpty()?Set.of("clock","rounds","startup"):Set.of("clock","rounds","startup","warning","limit","session","bedtime")).contains(rule.optString("trigger")) || !Set.of("none","focus","app").contains(rule.optString("action")))throw new IllegalArgumentException("reminder");
            bounded(rule,"clock",0,1439);bounded(rule,"rounds",1,100);bounded(rule,"timeout",0,3600);
            if(rule.optString("text").length()>2000||rule.optString("package").length()>255)throw new IllegalArgumentException("text");
            if(rule.optString("action").equals("focus"))PhoneFocus.validate(rule);
        } else {
            bounded(rule,"minutes",0,10080);bounded(rule,"allowance",0,60);
            if(!Set.of("","apps","games","all").contains(rule.optString("category")))throw new IllegalArgumentException("category");
            JSONArray apps=rule.optJSONArray("apps"),steps=rule.optJSONArray("steps");
            if(apps==null||apps.length()>1000||steps==null||steps.length()>20||apps.length()==0&&rule.optString("category").isEmpty()&&rule.optString("_shared").isEmpty())throw new IllegalArgumentException("members");
            for(int i=0;i<apps.length();i++)if(!apps.optString(i).matches("[A-Za-z0-9_]+(?:\\.[A-Za-z0-9_]+)+"))throw new IllegalArgumentException("package");
            HashSet<String> ids=new HashSet<>();
            for(int i=0;i<steps.length();i++) {
                JSONObject s=steps.optJSONObject(i);if(s==null||!s.optString("id").matches("[a-f0-9]{32}")||!ids.add(s.optString("id"))||!Set.of("notify","break","block").contains(s.optString("kind"))||!Set.of("usage","clock","relative","sessions").contains(s.optString("mode")))throw new IllegalArgumentException("step");
                if(s.optString("mode").equals("sessions"))bounded(s,"sessions",1,10000);
                if(!s.optString("mode").equals("sessions"))bounded(s,"minutes",s.optString("mode").equals("relative")?-10080:1,10080);bounded(s,"clock",0,1439);bounded(s,"duration",1,180);
                if(s.optString("mode").equals("relative")&&(!rule.optBoolean("limit")||s.optString("kind").equals("break")))throw new IllegalArgumentException("relative");
            }
        }
    }
    record Notice(String id,String title,String text,boolean sound,String action,JSONObject details) {}
    record Result(boolean blocked,boolean pause,long until,long next,boolean allowance) {}
    static Result evaluate(JSONObject b,JSONObject state,long used,long now,int renewal,ZoneId zone,boolean consuming,List<Notice> notices) {
        return evaluate(b,state,used,0,now,renewal,zone,consuming,notices);
    }
    static boolean sessionSteps(JSONObject b) {
        JSONArray steps=b.optJSONArray("steps");if(steps!=null)for(int i=0;i<steps.length();i++)if(steps.optJSONObject(i).optString("mode").equals("sessions"))return true;return false;
    }
    static Result evaluate(JSONObject b,JSONObject state,long used,long sessions,long now,int renewal,ZoneId zone,boolean consuming,List<Notice> notices) {
        String day=day(now,renewal,zone);long next=nextDay(now,renewal,zone);
        if(!state.optString("day").equals(day)) {
            JSONObject breaks=state.optJSONObject("breaks");JSONObject carried=new JSONObject();
            if(breaks!=null)for(Iterator<String> keys=breaks.keys();keys.hasNext();) {String key=keys.next();JSONObject s=breaks.optJSONObject(key);if(s!=null&&s.optLong("until")>now)set(carried,key,copy(s));}
            long grant=state.optLong("grantUntil");String pkg=state.optString("grantPackage");
            for(String key:new String[]{"expired","delivered","usedAllowance","grantUntil","grantPackage","breaks"})state.remove(key);
            set(state,"day",day);set(state,"breaks",carried);if(grant>now){set(state,"grantUntil",grant);set(state,"grantPackage",pkg);}
        }
        if(!active(b,day))return new Result(false,false,0,next,false);
        long limit=b.optBoolean("limit",true)?b.optLong("minutes",60)*60000:Long.MAX_VALUE;
        if(used<limit)state.remove("expired");
        if(used>=limit&&!state.has("expired")){set(state,"expired",now);notices.add(new Notice("budget_end:"+b.optString("id")+":"+day,b.optString("name"),"budget_end",true,"none",new JSONObject()));}
        boolean blocked=used>=limit&&(b.optBoolean("block",true)||limit==0),pause=false;long until=0;
        JSONArray delivered=state.optJSONArray("delivered");if(delivered==null){delivered=new JSONArray();set(state,"delivered",delivered);}
        JSONObject breaks=state.optJSONObject("breaks");if(breaks==null){breaks=new JSONObject();set(state,"breaks",breaks);}
        JSONArray steps=b.optJSONArray("steps");if(steps==null)steps=new JSONArray();
        for(int i=0;i<steps.length();i++) {
            JSONObject s=steps.optJSONObject(i);if(s==null)continue;String id=s.optString("id"),mode=s.optString("mode"),kind=s.optString("kind");
            boolean sessionMode=mode.equals("sessions");long measured=sessionMode?sessions:used;
            long threshold=sessionMode?s.optLong("sessions",5):s.optLong("minutes")*60000,at=0;
            if(mode.equals("clock"))at=clock(day,s.optInt("clock"),renewal,zone);
            if(mode.equals("relative")) {if(threshold<=0)threshold=Math.max(0,limit+threshold);else at=state.has("expired")?state.optLong("expired")+threshold:Long.MAX_VALUE;}
            boolean due=sessionMode?sessions>threshold:at!=0?now>=at:used>=threshold;
            if(kind.equals("break")) {
                JSONObject item=breaks.optJSONObject(id);String spec=s.toString();if(item==null||!item.optString("spec").isEmpty()&&!item.optString("spec").equals(spec)){item=new JSONObject();set(item,"next",threshold);set(breaks,id,item);}set(item,"spec",spec);
                long end=item.optLong("until");
                if(end>0&&now>=end){item.remove("until");set(item,"next",measured+threshold);end=0;}
                if(mode.equals("clock")) {
                    if(!day.equals(item.optString("clockDay"))&&due) {set(item,"clockDay",day);if(used<limit&&now<at+s.optLong("duration",5)*60000){end=at+s.optLong("duration",5)*60000;set(item,"until",end);}}
                } else if(end==0&&(sessionMode?sessions>item.optLong("next",threshold):used>=item.optLong("next",threshold))&&used<limit&&(sessionMode||item.optLong("next",threshold)<limit)) {end=now+s.optLong("duration",5)*60000;set(item,"until",end);}
                if(end>now){pause=true;until=Math.max(until,end);next=Math.min(next,end);if(item.optLong("announced")!=end){set(item,"announced",end);notices.add(new Notice("budget_break:"+b.optString("id")+":"+id+":"+end,b.optString("name"),"budget_break",s.optBoolean("sound",true),"none",new JSONObject()));}}
                else if(consuming&&!sessionMode&&!mode.equals("clock")&&item.optLong("next",threshold)>used)next=Math.min(next,now+item.optLong("next",threshold)-used);
            } else if(due&&kind.equals("block"))blocked=true;
            else if(due&&kind.equals("notify")&&!contains(delivered,id)) {delivered.put(id);notices.add(new Notice("budget:"+b.optString("id")+":"+day+":"+id,b.optString("name"),"budget",s.optBoolean("sound",true),"none",new JSONObject()));}
            if(at>now&&at<Long.MAX_VALUE)next=Math.min(next,at);
            else if(consuming&&!sessionMode&&at==0&&threshold>used)next=Math.min(next,now+threshold-used);
        }
        if(consuming&&limit>used&&limit<Long.MAX_VALUE)next=Math.min(next,now+limit-used);
        if(state.optLong("grantUntil")>now)next=Math.min(next,state.optLong("grantUntil"));
        return new Result(blocked||pause,!blocked&&pause,blocked?0:until,next,blocked&&limit!=0&&!state.optBoolean("usedAllowance")&&b.optInt("allowance")>0);
    }
}
