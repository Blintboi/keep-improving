package hu.keepimproving.android;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.Config;
import org.json.*;
import java.time.*;
import java.util.*;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class) @Config(sdk=35)
public class PhoneSessionLimitTest {
    final ZoneId zone=ZoneId.of("Europe/Budapest");
    final long now=ZonedDateTime.of(2026,11,10,12,0,0,0,zone).toInstant().toEpochMilli();
    JSONObject rule(String kind)throws Exception{return PhoneRules.budget().put("name","Visits").put("category","apps").put("limit",false).put("steps",new JSONArray().put(PhoneRules.step().put("kind",kind).put("mode","sessions").put("sessions",5).put("duration",1)));}
    PhoneRules.Result run(JSONObject rule,JSONObject state,long count,long at,List<PhoneRules.Notice> notices){return PhoneRules.evaluate(rule,state,1234,count,at,240,zone,true,notices);}
    @Test public void fiveAllowedSixthBlockedAcrossRestartAndRenewal()throws Exception{
        var rule=rule("block");PhoneRules.validate(rule,false);var state=new JSONObject();var notices=new ArrayList<PhoneRules.Notice>();
        for(int n=0;n<=5;n++)assertFalse(run(rule,state,n,now,notices).blocked());
        assertTrue(run(rule,state,6,now,notices).blocked());assertTrue(run(rule,PhoneRules.copy(state),6,now+5000,notices).blocked());
        assertFalse(run(rule,state,0,PhoneRules.nextDay(now,240,zone),notices).blocked());
    }
    @Test public void warningIsOnceAndSessionsDoNotStartMillisecondPolling()throws Exception{
        var rule=rule("notify");var state=new JSONObject();var notices=new ArrayList<PhoneRules.Notice>();
        assertEquals(PhoneRules.nextDay(now,240,zone),run(rule,state,5,now,notices).next());assertEquals(0,notices.size());
        run(rule,state,6,now,notices);run(rule,PhoneRules.copy(state),7,now,notices);assertEquals(1,notices.size());
    }
    @Test public void repeatBreakNeedsFiveNewVisitsAndTimeLimitWins()throws Exception{
        var rule=rule("break");var state=new JSONObject();var notices=new ArrayList<PhoneRules.Notice>();
        assertTrue(run(rule,state,6,now,notices).pause());assertFalse(run(rule,state,6,now+60000,notices).blocked());
        assertFalse(run(rule,state,11,now+70000,notices).blocked());assertTrue(run(rule,state,12,now+80000,notices).pause());
        rule.put("limit",true).put("minutes",0);var end=run(rule,state,12,now+80000,notices);assertTrue(end.blocked());assertFalse(end.pause());
    }
    @Test public void integerValidation()throws Exception{
        for(Object bad:List.of(0,-1,1.5,true,10001)){var rule=rule("block");rule.getJSONArray("steps").getJSONObject(0).put("sessions",bad);assertThrows(IllegalArgumentException.class,()->PhoneRules.validate(rule,false));}
    }
    @Test public void measuredLedgerUsesCustomRenewalAndDeduplicatesSelectors()throws Exception{
        try(var store=new PhoneStore(RuntimeEnvironment.getApplication())){
            var rule=rule("block").put("apps",new JSONArray().put("example.app"));String day=PhoneRules.day(now,240,zone);
            long boundary=PhoneRules.clock(day,240,240,ZoneId.systemDefault());store.put("sessions_since",Long.toString(boundary-10000));
            store.add(new UsageLedger.Slice(day,"example.app",10000),"Example",false);
            SessionCounts.record(store,"example.app",boundary-1000,boundary+1000);
            SessionCounts.record(store,"example.app",boundary+2000,boundary+3000);
            SessionCounts.record(store,"example.app",boundary+3000,boundary+4000);
            assertEquals(1,SessionCounts.budget(store,rule,day,240));
            assertEquals(1,SessionCounts.budget(store,rule,LocalDate.parse(day).minusDays(1).toString(),240));
        }
    }
}
