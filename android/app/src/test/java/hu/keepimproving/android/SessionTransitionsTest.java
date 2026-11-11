package hu.keepimproving.android;

import java.time.*;
import java.util.*;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.Config;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class) @Config(sdk=35)
public class SessionTransitionsTest {
    final String pkg="example.habits";
    long start=LocalDate.now().atStartOfDay(ZoneId.systemDefault()).toInstant().toEpochMilli()+1000;
    UsageLedger.Event event(long at,int type,String app,String activity){return new UsageLedger.Event(start+at,type,app,activity);}
    long count(PhoneStore store){try(var c=store.getReadableDatabase().rawQuery("SELECT COUNT(*) FROM sessions WHERE package=?",new String[]{pkg})){c.moveToFirst();return c.getLong(0);}}
    void record(PhoneStore store,long from,long to){SessionCounts.record(store,pkg,start+from,start+to);}
    @Test public void repairsSixtyTwoInternalScreensWithoutChangingUsageOrRealReturns()throws Exception {
        try(var store=new PhoneStore(RuntimeEnvironment.getApplication())) {
            store.put("sessions_since",Long.toString(start));List<UsageLedger.Event> events=new ArrayList<>();
            for(int i=0;i<62;i++) {
                long at=i*1010L;record(store,at,at+1000);
                if(i<61){events.add(event(at+1000,2,pkg,i%2==0?"List":"Detail"));events.add(event(at+1010,1,pkg,i%2==0?"Detail":"List"));}
            }
            String day=LocalDate.now().toString();store.add(new UsageLedger.Slice(day,pkg,62000),"Habits",false);
            assertEquals(62,count(store));SessionTransitions.reconcile(store,events,start+63000,true);assertEquals(1,count(store));
            SessionTransitions.reconcile(store,events,start+63000,true);assertEquals(1,count(store));
            try(var c=store.getReadableDatabase().rawQuery("SELECT COUNT(*) FROM sessions_activity_backup",null)){c.moveToFirst();assertEquals(62,c.getLong(0));}
            assertEquals(62,store.rows(false).getJSONArray(0).getDouble(4),0);
            record(store,70000,71000);SessionTransitions.reconcile(store,List.of(event(62610,2,pkg,"List"),event(62700,1,"launcher","Home"),event(70000,1,pkg,"List")),start+72000,false);
            assertEquals(2,count(store));assertEquals(2,SessionCounts.snapshot(store).getJSONArray("rows").getJSONArray(0).getLong(3));
        }
    }
    @Test public void transitionAcrossCollectionAndRestartKeepsOneSession() {
        var context=RuntimeEnvironment.getApplication();
        try(var store=new PhoneStore(context)) {store.put("sessions_since",Long.toString(start));record(store,0,1000);SessionTransitions.reconcile(store,List.of(event(1000,2,pkg,"List")),start+1005,false);}
        try(var store=new PhoneStore(context)) {record(store,1010,2000);SessionTransitions.reconcile(store,List.of(event(1010,1,pkg,"Detail")),start+2000,false);assertEquals(1,count(store));}
    }
    @Test public void realSwitchLockLongAbsenceAndCoverageRemainSeparate() {
        for(int boundary:new int[]{1,16,17,26,27,0,99})try(var store=new PhoneStore(RuntimeEnvironment.getApplication())) {
            store.getWritableDatabase().delete("sessions",null,null);store.getWritableDatabase().delete("coverage",null,null);store.put("sessions_since",Long.toString(start));
            record(store,0,1000);long resume=boundary==0?3000:1010;record(store,resume,4000);
            List<UsageLedger.Event> events=new ArrayList<>(List.of(event(1000,2,pkg,"List")));
            if(boundary!=0&&boundary!=99)events.add(event(1001,boundary,boundary==1?"other.app":"","Other"));
            if(boundary==99)store.getWritableDatabase().execSQL("INSERT INTO coverage VALUES ('fixture',?,?,?)",new Object[]{pkg,start+1001,start+1009});
            events.add(event(resume,1,pkg,"Detail"));SessionTransitions.reconcile(store,events,start+4000,true);assertEquals(2,count(store));
        }
    }
}
