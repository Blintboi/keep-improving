package hu.keepimproving.android;
import org.junit.*;
import static org.junit.Assert.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.Config;
import android.app.*;
import android.content.*;
import android.database.sqlite.*;
import org.json.*;

@RunWith(RobolectricTestRunner.class) @Config(sdk=35)
public class PhoneFeaturesTest {
    Context c;
    @Before public void setup(){c=RuntimeEnvironment.getApplication();Shadows.shadowOf((android.app.Application)c).grantPermissions(android.Manifest.permission.POST_NOTIFICATIONS);}
    @Test public void migrationPreservesV1ProfileAndRemotePayload()throws Exception {
        c.deleteDatabase("usage.sqlite3");try(var helper=new SQLiteOpenHelper(c,"usage.sqlite3",null,1){public void onCreate(SQLiteDatabase db){db.execSQL("CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)");db.execSQL("CREATE TABLE usage(day TEXT,package TEXT,name TEXT,game INTEGER,millis INTEGER,PRIMARY KEY(day,package))");db.execSQL("CREATE TABLE remote(device TEXT PRIMARY KEY,revision TEXT,payload TEXT)");}public void onUpgrade(SQLiteDatabase db,int old,int current){}}){var db=helper.getWritableDatabase();db.execSQL("INSERT INTO meta VALUES('device','preserved-device'),('name','My phone'),('enabled','false'),('excluded','[\"com.example.app\"]')");db.execSQL("INSERT INTO usage VALUES('2026-11-03','com.example.app','App',0,123000)");db.execSQL("INSERT INTO remote VALUES('pc','100','encrypted-payload')");}
        try(PhoneStore s=new PhoneStore(c)){assertEquals(6,s.getReadableDatabase().getVersion());assertEquals("preserved-device",s.device());assertEquals("My phone",s.name());assertTrue(s.get("excluded","").contains("com.example.app"));assertEquals(123,s.rows(false).getJSONArray(0).getDouble(4),0);try(var row=s.getReadableDatabase().rawQuery("SELECT payload FROM remote",null)){assertTrue(row.moveToFirst());assertEquals("encrypted-payload",row.getString(0));}assertEquals(0,s.rules("budget").length());s.saveRule("budget",PhoneRules.budget().put("name","Apps").put("category","all"));assertEquals(1,s.rules("budget").length());}
    }
    @Test public void aSharedBudgetSumsEachPackageOnlyOnce()throws Exception {try(PhoneStore s=new PhoneStore(c)){s.add(new UsageLedger.Slice("2026-11-04","com.example.game",120000),"Game",true);var rule=PhoneRules.budget().put("category","games").put("apps",new JSONArray().put("com.example.game"));assertEquals(120000,s.used(rule,"2026-11-04"));}}
    @Test public void repeatedRefreshDoesNotDuplicateReminderAndStartDismissesIt()throws Exception {
        var r=PhoneRules.reminder().put("title","Focus now").put("trigger","startup").put("action","focus");String day;
        try(PhoneStore s=new PhoneStore(c)){s.saveRule("reminder",r);day=PhoneRuntime.day(s,System.currentTimeMillis());}
        PhoneRuntime.refresh(c,true);PhoneRuntime.refresh(c,true);String id="reminder:"+r.getString("id")+":"+day;
        NotificationManager manager=c.getSystemService(NotificationManager.class);assertNotNull(Shadows.shadowOf(manager).getNotification(PhoneNotifications.identifier(id)));
        try(PhoneStore s=new PhoneStore(c);var row=s.getReadableDatabase().rawQuery("SELECT COUNT(*) FROM notices",null)){row.moveToFirst();assertEquals(1,row.getInt(0));}
        assertTrue(PhoneRuntime.startNotice(c,id));assertNull(Shadows.shadowOf(manager).getNotification(PhoneNotifications.identifier(id)));assertFalse(PhoneRuntime.startNotice(c,id));PhoneRuntime.refresh(c,true);assertNull(Shadows.shadowOf(manager).getNotification(PhoneNotifications.identifier(id)));
    }
    @Test public void staleTimerNotificationCannotPauseANewerSession(){var state=PhoneRuntime.refresh(c,false);String old=state.focus().optString("token");assertTrue(PhoneRuntime.command(c,"start",old));assertFalse(PhoneRuntime.command(c,"pause",old));assertTrue(PhoneRuntime.refresh(c,false).focus().optBoolean("running"));}
    @Test public void systemAndOwnAppAlwaysExempt(){for(String pkg:new String[]{c.getPackageName(),"android","com.android.systemui","com.android.settings","com.android.phone","com.google.android.permissioncontroller"})assertTrue(AppCatalog.safe(c,pkg));assertFalse(AppCatalog.safe(c,"com.example.game"));}
    @Test public void noExactAlarmPermissionFallsBackWithoutCrashing(){PhoneAlarms.invalidate(c);PhoneAlarms.schedule(c,System.currentTimeMillis()+60000);assertNotNull(c.getSharedPreferences("alarms",0).getString("scheduled",null));PhoneAlarms.schedule(c,Long.MAX_VALUE);}
    @Test public void networkWaitDoesNotBlockTheTimerWorker()throws Exception {var started=new java.util.concurrent.CountDownLatch(1);var finish=new java.util.concurrent.CountDownLatch(1);CollectionJob.LOAD.execute(()->{started.countDown();try{finish.await(10,java.util.concurrent.TimeUnit.SECONDS);}catch(InterruptedException e){Thread.currentThread().interrupt();}});try{assertTrue(started.await(2,java.util.concurrent.TimeUnit.SECONDS));assertEquals("responsive",CollectionJob.WORK.submit(()->"responsive").get(2,java.util.concurrent.TimeUnit.SECONDS));}finally{finish.countDown();CollectionJob.LOAD.submit(()->{}).get(2,java.util.concurrent.TimeUnit.SECONDS);}}
}
