package hu.keepimproving.android;
import org.junit.Test;
import static org.junit.Assert.*;
import java.time.*;
import java.util.*;

public class UsageLedgerTest {
    private final ZoneId zone=ZoneId.of("Europe/Budapest");
    private long time(String value){return ZonedDateTime.parse(value).toInstant().toEpochMilli();}
    private UsageLedger.Event e(long time,int type,String pkg,String activity){return new UsageLedger.Event(time,type,pkg,activity);}
    private double total(UsageLedger.Result result){return result.slices().stream().mapToLong(UsageLedger.Slice::millis).sum();}
    @Test public void switchesAndLatePausesAreNotCountedTwice(){
        var result=UsageLedger.collect(new UsageLedger.State(0,"",""),List.of(e(1000,1,"one","A"),e(2000,1,"two","B"),e(2100,2,"one","A"),e(3000,2,"two","B")),4000,zone);
        assertEquals(2000,total(result),0);assertEquals("",result.state().pkg());
    }
    @Test public void sameApplicationActivityTransitionKeepsRunning(){
        var result=UsageLedger.collect(new UsageLedger.State(0,"",""),List.of(e(1000,1,"one","A"),e(2000,1,"one","B"),e(2100,2,"one","A")),3000,zone);
        assertEquals(2000,total(result),0);assertEquals("B",result.state().activity());
    }
    @Test public void lockAndShutdownCloseTheSession(){
        for(int type:new int[]{16,17,26}) {
            var result=UsageLedger.collect(new UsageLedger.State(0,"one","A"),List.of(e(1000,type,"","")),100000,zone);assertEquals(1000,total(result),0);
        }
    }
    @Test public void unexpectedRebootDoesNotCountOfflineTime(){
        var result=UsageLedger.collect(new UsageLedger.State(0,"one","A"),List.of(e(80000,27,"","")),100000,zone);
        assertEquals(0,total(result),0);
    }
    @Test public void midnightUsesLocalDays(){
        long start=time("2026-11-03T23:59:00+01:00[Europe/Budapest]");
        var result=UsageLedger.collect(new UsageLedger.State(start,"one","A"),List.of(),start+120000,zone);
        assertEquals(2,result.slices().size());assertEquals("2026-11-03",result.slices().get(0).day());assertEquals(60000,result.slices().get(1).millis());
    }
    @Test public void daylightSavingDayHasTwentyFiveHours(){
        long start=time("2026-10-25T00:00:00+02:00[Europe/Budapest]"),end=time("2026-10-26T00:00:00+01:00[Europe/Budapest]");
        var result=UsageLedger.collect(new UsageLedger.State(start,"one","A"),List.of(),end,zone);
        assertEquals(25*3600000L,total(result),0);assertEquals(1,result.slices().size());
    }
    @Test public void checkpointIncludesBoundaryEventExactlyOnce(){
        var events=List.of(e(0,1,"one","A"),e(1000,2,"one","A"));
        var first=UsageLedger.collect(new UsageLedger.State(0,"",""),events,1000,zone);
        var second=UsageLedger.collect(first.state(),events,2000,zone);
        assertEquals(1000,total(first)+total(second),0);assertEquals("",second.state().pkg());
    }
}
