package hu.keepimproving.android;

import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.Shadows;
import org.robolectric.annotation.Config;
import org.robolectric.shadows.ShadowUsageStatsManager.EventBuilder;
import android.app.AppOpsManager;
import android.app.usage.UsageEvents;
import android.app.usage.UsageStatsManager;
import android.content.Context;
import android.os.Process;
import android.os.UserManager;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=35)
public class PhoneUsageTest {
    private void allow(Context c,int mode) {Shadows.shadowOf(c.getSystemService(AppOpsManager.class)).setMode(AppOpsManager.OPSTR_GET_USAGE_STATS,Process.myUid(),c.getPackageName(),mode);}
    private void event(Context c,long time,int type) {Shadows.shadowOf(c.getSystemService(UsageStatsManager.class)).addEvent(EventBuilder.buildEvent().setPackage("com.example.game").setClass("Game").setTimeStamp(time).setEventType(type).build());}
    @Test public void permissionCollectionReopenAndRevocation() throws Exception {
        Context c=RuntimeEnvironment.getApplication();long now=System.currentTimeMillis();allow(c,AppOpsManager.MODE_ALLOWED);Shadows.shadowOf(c.getSystemService(UserManager.class)).setUserUnlocked(true);
        event(c,now-10000,UsageEvents.Event.ACTIVITY_RESUMED);event(c,now-5000,UsageEvents.Event.SCREEN_NON_INTERACTIVE);
        try(PhoneStore store=new PhoneStore(c)) {
            store.put("enabled","true");store.resetCursor(now-20000);PhoneUsage.collect(c,store);
            assertEquals(5,store.rows(false).getJSONArray(0).getDouble(4),.001);
            PhoneUsage.collect(c,store);assertEquals(5,store.rows(false).getJSONArray(0).getDouble(4),.001);
        }
        try(PhoneStore reopened=new PhoneStore(c)) {
            assertEquals(5,reopened.rows(false).getJSONArray(0).getDouble(4),.001);
            allow(c,AppOpsManager.MODE_IGNORED);PhoneUsage.collect(c,reopened);assertEquals("true",reopened.get("access_missing",""));
            allow(c,AppOpsManager.MODE_ALLOWED);PhoneUsage.collect(c,reopened);assertEquals("false",reopened.get("access_missing",""));
            assertEquals(5,reopened.rows(false).getJSONArray(0).getDouble(4),.001);
        }
    }
    @Test public void pausedAndLockedMeasurementPreserveCursor() {
        Context c=RuntimeEnvironment.getApplication();allow(c,AppOpsManager.MODE_ALLOWED);
        try(PhoneStore store=new PhoneStore(c)) {
            store.resetCursor(42);PhoneUsage.collect(c,store);assertEquals(42,store.number("cursor",0));
            store.put("enabled","true");Shadows.shadowOf(c.getSystemService(UserManager.class)).setUserUnlocked(false);PhoneUsage.collect(c,store);assertEquals(42,store.number("cursor",0));
        }
    }
}
