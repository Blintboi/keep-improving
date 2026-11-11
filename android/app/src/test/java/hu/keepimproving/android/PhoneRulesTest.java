package hu.keepimproving.android;
import org.junit.Test;
import static org.junit.Assert.*;
import org.json.*;
import java.time.*;
import java.util.*;

public class PhoneRulesTest {
    final ZoneId zone=ZoneId.of("Europe/Budapest");
    long time(String text){return ZonedDateTime.parse(text+"[Europe/Budapest]").toInstant().toEpochMilli();}
    final long now=time("2026-11-04T12:00:00+01:00");
    JSONObject budget()throws Exception{return PhoneRules.budget().put("name","Games").put("category","games");}
    PhoneRules.Result run(JSONObject b,JSONObject s,long used,long at,List<PhoneRules.Notice> out){return PhoneRules.evaluate(b,s,used,at,0,zone,true,out);}
    @Test public void zeroBudgetBlocksAndNeverOffersAllowance()throws Exception {var b=budget().put("minutes",0).put("block",false);var state=new JSONObject();var notices=new ArrayList<PhoneRules.Notice>();assertTrue(run(b,state,0,now,notices).blocked());assertFalse(run(b,state,0,now,notices).allowance());assertEquals(1,notices.size());}
    @Test public void sharedSelectorMatchesWithoutMultiplyingUse()throws Exception {var b=budget().put("apps",new JSONArray().put("com.example.game"));assertTrue(PhoneRules.matches(b,"com.example.game",true));assertFalse(PhoneRules.matches(b,"com.example.other",false));}
    @Test public void warningIsOnceAcrossRehydration()throws Exception {var b=budget().put("steps",new JSONArray().put(PhoneRules.step()));var notices=new ArrayList<PhoneRules.Notice>();JSONObject state=new JSONObject();run(b,state,30*60000,now,notices);state=PhoneRules.copy(state);run(b,state,31*60000,now+60000,notices);assertEquals(1,notices.size());}
    @Test public void repeatedBreakNeedsNewActiveTimeAndSurvivesRestart()throws Exception {var b=budget().put("minutes",120).put("steps",new JSONArray().put(PhoneRules.step().put("kind","break").put("minutes",20).put("duration",5)));var state=new JSONObject();var notices=new ArrayList<PhoneRules.Notice>();var first=run(b,state,20*60000,now,notices);assertTrue(first.pause());assertEquals(now+300000,first.until());state=PhoneRules.copy(state);assertTrue(run(b,state,20*60000,now+10000,notices).pause());assertEquals(1,notices.size());assertFalse(run(b,state,20*60000,now+300000,notices).blocked());assertTrue(run(b,state,40*60000,now+1500000,notices).pause());assertEquals(2,notices.size());}
    @Test public void terminalLimitWinsOverRepeatingBreak()throws Exception {var b=budget().put("minutes",20).put("steps",new JSONArray().put(PhoneRules.step().put("kind","break").put("minutes",20)));var r=run(b,new JSONObject(),20*60000,now,new ArrayList<>());assertTrue(r.blocked());assertFalse(r.pause());}
    @Test public void relativeBeforeAndAfterExpiryAreDistinct()throws Exception {var before=PhoneRules.step().put("mode","relative").put("minutes",-5);var after=PhoneRules.step().put("mode","relative").put("minutes",5).put("kind","block");var b=budget().put("block",false).put("steps",new JSONArray().put(before).put(after));var s=new JSONObject();var out=new ArrayList<PhoneRules.Notice>();assertFalse(run(b,s,55*60000,now,out).blocked());assertEquals(1,out.size());assertFalse(run(b,s,60*60000,now+300000,out).blocked());assertTrue(run(b,s,60*60000,now+600000,out).blocked());}
    @Test public void allowanceResetsAtBusinessDayBoundaryButActiveGrantCarries()throws Exception {var s=new JSONObject().put("day","2026-11-03").put("usedAllowance",true).put("grantUntil",now+60000).put("grantPackage","com.example.game");run(budget(),s,60*60000,now,new ArrayList<>());assertFalse(s.optBoolean("usedAllowance"));assertEquals(now+60000,s.getLong("grantUntil"));}
    @Test public void disabledDaysDoNotEmitWarnings()throws Exception {var b=budget().put("days",0);var out=new ArrayList<PhoneRules.Notice>();assertFalse(run(b,new JSONObject(),99999999,now,out).blocked());assertTrue(out.isEmpty());}
    @Test public void renewalAndDstUseCalendarTime(){long start=time("2026-10-25T01:00:00+02:00");long end=PhoneRules.nextDay(start,60,zone);assertEquals(25*3600000L,end-start);assertEquals("2026-11-03",PhoneRules.day(time("2026-11-04T03:59:00+01:00"),240,zone));}
    @Test public void usageSplitsAtCustomRenewal(){long start=time("2026-11-04T03:59:00+01:00");var r=UsageLedger.collect(new UsageLedger.State(start,"com.test","A"),List.of(),start+120000,zone,240);assertEquals("2026-11-03",r.slices().get(0).day());assertEquals(60000,r.slices().get(0).millis());assertEquals("2026-11-04",r.slices().get(1).day());}
    @Test public void ambiguousRenewalDoesNotRollBackTheBusinessDay(){assertEquals("2026-10-25",PhoneRules.day(time("2026-10-25T02:10:00+01:00"),150,zone));assertEquals("2026-10-24",PhoneRules.day(time("2026-10-25T02:10:00+02:00"),150,zone));assertEquals("2026-03-28",PhoneRules.day(time("2026-03-29T03:10:00+02:00"),150,zone));}
    @Test public void coverageSubtractsUnionOnlyWithinSlice(){assertEquals(200,CoverageLedger.visible(List.of(new CoverageLedger.Interval(0,300),new CoverageLedger.Interval(200,400),new CoverageLedger.Interval(600,1200)),100,1000));assertEquals(900,CoverageLedger.visible(List.of(),100,1000));}
    @Test public void rejectsImpossibleRuleCombinations()throws Exception {var b=budget().put("steps",new JSONArray().put(PhoneRules.step().put("kind","break").put("mode","relative")));assertThrows(IllegalArgumentException.class,()->PhoneRules.validate(b,false));}
    @Test public void coveredOrInactiveUsageDoesNotScheduleFastPoll()throws Exception {var b=budget();var r=PhoneRules.evaluate(b,new JSONObject(),3599999,now,0,zone,false,new ArrayList<>());assertEquals(PhoneRules.nextDay(now,0,zone),r.next());}
}
