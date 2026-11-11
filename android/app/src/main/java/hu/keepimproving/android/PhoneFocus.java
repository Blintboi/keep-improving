package hu.keepimproving.android;

import org.json.*;
import java.time.ZoneId;
import java.util.*;

/** Monotonic while booted, durable across process death; one natural work completion per run. */
final class PhoneFocus {
    record Time(long wall,long elapsed,int boot) {}
    record Completion(String day,String token,int round,long at) {}
    static JSONObject defaults() {
        JSONObject c=new JSONObject();PhoneRules.set(c,"work",25);PhoneRules.set(c,"short",5);PhoneRules.set(c,"long",15);PhoneRules.set(c,"cycles",4);
        PhoneRules.set(c,"apps",new JSONArray());PhoneRules.set(c,"groups",new JSONArray());return c;
    }
    static void validate(JSONObject config) {PhoneRules.bounded(config,"work",1,240);PhoneRules.bounded(config,"short",0,60);PhoneRules.bounded(config,"long",0,180);PhoneRules.bounded(config,"cycles",0,12);}
    static JSONObject state(JSONObject config) {
        JSONObject s=new JSONObject();PhoneRules.set(s,"phase","work");PhoneRules.set(s,"remaining",config.optLong("work",25)*60000);
        PhoneRules.set(s,"round",0);PhoneRules.set(s,"running",false);PhoneRules.set(s,"token",PhoneRules.id());return s;
    }
    static long remaining(JSONObject s,Time now) {
        if(!s.optBoolean("running"))return s.optLong("remaining");
        long delta=now.boot==s.optInt("boot")&&now.elapsed>=s.optLong("elapsed")?now.elapsed-s.optLong("elapsed"):Math.max(0,now.wall-s.optLong("wall",now.wall));
        return Math.max(0,s.optLong("remaining")-delta);
    }
    static void anchor(JSONObject s,Time now){PhoneRules.set(s,"wall",now.wall);PhoneRules.set(s,"elapsed",now.elapsed);PhoneRules.set(s,"boot",now.boot);}
    static void advance(JSONObject s,JSONObject c,Time now,int renewal,ZoneId zone,List<Completion> completions,List<PhoneRules.Notice> notices) {
        if(!s.optBoolean("running"))return;
        long delta=now.boot==s.optInt("boot")&&now.elapsed>=s.optLong("elapsed")?now.elapsed-s.optLong("elapsed"):Math.max(0,now.wall-s.optLong("wall",now.wall));
        long cursor=now.wall-delta;
        while(s.optBoolean("running")&&delta>0) {
            long amount=Math.min(delta,s.optLong("remaining"));delta-=amount;cursor+=amount;PhoneRules.set(s,"remaining",s.optLong("remaining")-amount);
            if(s.optLong("remaining")>0)break;
            String kind;
            if(s.optString("phase").equals("work")) {
                int round=s.optInt("round")+1;PhoneRules.set(s,"round",round);
                completions.add(new Completion(PhoneRules.day(cursor,renewal,zone),s.optString("token"),round,cursor));
                if(c.optInt("cycles")==0){PhoneRules.set(s,"running",false);kind="focus_done";}
                else {
                    String phase=round%c.optInt("cycles")==0?"long":"short";PhoneRules.set(s,"phase",phase);PhoneRules.set(s,"remaining",c.optLong(phase)*60000);kind="focus_break";
                    if(s.optLong("remaining")==0){PhoneRules.set(s,"phase","work");PhoneRules.set(s,"remaining",c.optLong("work")*60000);PhoneRules.set(s,"running",false);kind="focus_done";}
                }
            } else {PhoneRules.set(s,"phase","work");PhoneRules.set(s,"remaining",c.optLong("work")*60000);PhoneRules.set(s,"running",false);kind="break_done";}
            notices.add(new PhoneRules.Notice(kind+":"+s.optString("token")+":"+s.optInt("round"),"",kind,true,"none",new JSONObject()));
        }
        anchor(s,now);
    }
    static void command(JSONObject s,JSONObject c,String action,Time now) {
        if(!Set.of("start","pause","stop").contains(action))throw new IllegalArgumentException("action");
        if(action.equals("start")&&s.optBoolean("running"))return;
        if(action.equals("stop")||action.equals("start")&&s.optLong("remaining")==0) {PhoneRules.set(s,"phase","work");PhoneRules.set(s,"remaining",c.optLong("work",25)*60000);PhoneRules.set(s,"round",0);}
        PhoneRules.set(s,"running",action.equals("start"));PhoneRules.set(s,"token",PhoneRules.id());anchor(s,now);
    }
}
