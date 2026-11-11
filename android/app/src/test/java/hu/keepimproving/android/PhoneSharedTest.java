package hu.keepimproving.android;
import org.junit.*;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;
import org.robolectric.*;
import org.robolectric.annotation.*;
import android.app.*;
import android.content.*;
import org.json.*;
import java.time.*;
import java.util.*;
import java.nio.file.*;

@RunWith(RobolectricTestRunner.class) @Config(sdk=35)
public class PhoneSharedTest {
    static final String CODE="a1".repeat(16),PC="b".repeat(32),RULE="c".repeat(32),GROUP="d".repeat(32);
    Context context;
    @Before public void setup(){context=RuntimeEnvironment.getApplication();Shadows.shadowOf((Application)context).grantPermissions(android.Manifest.permission.POST_NOTIFICATIONS);}
    static JSONObject scope(String mode,String value)throws Exception{JSONObject s=new JSONObject().put("mode",mode).put("connection",PhoneShared.connection(CODE)).put("accounting","shared");if(!mode.equals("all"))s.put(mode,value);return s;}
    static JSONObject budget(JSONObject scope)throws Exception{return new JSONObject().put("name","Shared games").put("seconds",3600).put("enabled",true).put("enforce",true).put("usage_limit",true).put("reset_minute",0).put("days",new JSONArray("[0,1,2,3,4,5,6]")).put("devices",scope).put("members",new JSONArray("[{\"kind\":\"category\",\"value\":\"games\"}]"));}
    static JSONObject record(String kind,Object v,long clock)throws Exception{return new JSONObject().put("kind",kind).put("value",v).put("clock",clock).put("device",PC);}
    static JSONObject incoming(PhoneStore s,JSONObject records,JSONArray usage)throws Exception{return s.snapshot(CODE).put("device",PC).put("name","PC").put("scoped_rules",new JSONObject().put("records",records).put("usage",usage));}
    @Test public void sharedConsumptionIsLocalPlusRemoteAndExportDoesNotEcho()throws Exception{
        try(PhoneStore s=new PhoneStore(context)){
            String day=LocalDate.now().toString();s.add(new UsageLedger.Slice(day,"com.game.test",300000),"Game",true);
            JSONObject group=new JSONObject().put("name","PC + phone").put("devices",new JSONArray().put(PC).put(s.device())).put("connection",PhoneShared.connection(CODE));
            JSONObject records=new JSONObject().put(GROUP,record("group",group,1)).put(RULE,record("budget",budget(scope("group",GROUP)),2));
            JSONObject snapshot=incoming(s,records,new JSONArray().put(new JSONArray().put(RULE).put(day).put(0).put(900)));
            PhoneShared.merge(s,snapshot,CODE);PhoneShared.merge(s,snapshot,CODE);assertEquals(1,s.rules("budget").length());JSONObject rule=s.rules("budget").getJSONObject(0);
            assertEquals(1200000,PhoneShared.used(s,rule,System.currentTimeMillis()));JSONObject export=s.snapshot(CODE);assertEquals(300,export.getJSONObject("scoped_rules").getJSONArray("usage").getJSONArray(0).getDouble(3),0);
            String id=export.getString("device"),revision=Long.toString(export.getLong("revision"));JSONObject fixture=new JSONObject().put("code",CODE).put("entry",new JSONObject().put("device",id).put("revision",revision).put("payload",SyncCrypto.seal(export.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8),CODE,id,revision)));
            Files.write(Path.of(System.getProperty("keepImprovingReports"),"shared-phone-export.json"),fixture.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
        }
    }
    @Test public void groupMembershipFiltersBothEnforcementAndRemoteUsage()throws Exception{
        try(PhoneStore s=new PhoneStore(context)){
            JSONObject group=new JSONObject().put("name","Only phone").put("devices",new JSONArray().put(s.device())).put("connection",PhoneShared.connection(CODE));JSONObject records=new JSONObject().put(GROUP,record("group",group,1)).put(RULE,record("budget",budget(scope("group",GROUP)),2));
            PhoneShared.merge(s,incoming(s,records,new JSONArray().put(new JSONArray().put(RULE).put(LocalDate.now().toString()).put(0).put(900))),CODE);
            JSONObject rule=s.rules("budget").getJSONObject(0);assertTrue(PhoneShared.applies(s,rule.getJSONObject("devices")));assertEquals(0,PhoneShared.used(s,rule,System.currentTimeMillis()));
            group.put("devices",new JSONArray().put(PC));records.put(GROUP,record("group",group,3));PhoneShared.merge(s,incoming(s,records,new JSONArray()),CODE);assertFalse(PhoneShared.applies(s,rule.getJSONObject("devices")));
        }
    }
    @Test public void remoteEditsProtectOpenDraftAndTombstoneDoesNotResurrect()throws Exception{
        try(PhoneStore s=new PhoneStore(context)){
            JSONObject records=new JSONObject().put(RULE,record("budget",budget(scope("all","")),1));PhoneShared.merge(s,incoming(s,records,new JSONArray()),CODE);JSONObject draft=PhoneRules.copy(s.rules("budget").getJSONObject(0));
            records.put(RULE,record("budget",budget(scope("all","")).put("seconds",1800),2));PhoneShared.merge(s,incoming(s,records,new JSONArray()),CODE);draft.put("minutes",10);
            assertThrows(IllegalStateException.class,()->s.saveRule("budget",draft));assertEquals(30,s.rules("budget").getJSONObject(0).getInt("minutes"));
            records.put(RULE,record("budget",JSONObject.NULL,3));PhoneShared.merge(s,incoming(s,records,new JSONArray()),CODE);assertEquals(0,s.rules("budget").length());assertTrue(s.snapshot(CODE).getJSONObject("scoped_rules").getJSONObject("records").getJSONObject(RULE).isNull("value"));
        }
    }
    @Test public void independentRenewalSplitsVisibleIntervalsAndExcludesCoveredTime()throws Exception{
        try(PhoneStore s=new PhoneStore(context)){
            JSONObject records=new JSONObject().put(RULE,record("budget",budget(scope("all","")).put("reset_minute",720),1));PhoneShared.merge(s,incoming(s,records,new JSONArray()),CODE);ZoneId zone=ZoneId.systemDefault();long start=LocalDate.now().atTime(11,59).atZone(zone).toInstant().toEpochMilli();
            s.getWritableDatabase().execSQL("INSERT INTO coverage VALUES ('cover','com.game.test',?,?)",new Object[]{start+30000,start+90000});PhoneShared.credit(s,new UsageLedger.Slice(LocalDate.now().toString(),"com.game.test",120000,start),true);
            JSONObject rule=s.rules("budget").getJSONObject(0);assertEquals(30000,PhoneShared.localUsed(s,rule,start+120000));assertEquals(30000,PhoneShared.localUsed(s,rule,start));
        }
    }
    @Test public void malformedSharedPayloadRollsBackEnvelopeImport()throws Exception{
        try(PhoneStore s=new PhoneStore(context)){
            JSONObject payload=new JSONObject().put(RULE,record("budget",budget(scope("all","")).put("seconds",-1),1));JSONObject incoming=incoming(s,payload,new JSONArray());
            assertThrows(Exception.class,()->s.accept(PhoneCompanionTest.envelope(incoming),CODE));assertEquals(0,s.rules("budget").length());assertEquals(0,s.known().length());
        }
    }
    @Implements(value=ShieldService.class,isInAndroidSdk=false) public static class Shield { @Implementation protected static boolean connected(){return true;} @Implementation protected static String coveredPackage(){return "";} }
    @Implements(value=PhoneUsage.class,isInAndroidSdk=false) public static class Usage { @Implementation protected static boolean allowed(Context c){return true;} }
    @Test @Config(shadows={Shield.class,Usage.class}) public void ongoingCounterRunsPausesAndUsesOneNotification()throws Exception{
        try(PhoneStore s=new PhoneStore(context)){
            s.put("enabled","true");JSONObject rule=PhoneRules.budget().put("name","Games").put("category","games");long now=System.currentTimeMillis();var view=new PhoneRuntime.BudgetView(rule,600000,new PhoneRules.Result(false,false,0,now+3000000,false));
            var state=new PhoneRuntime.State(new JSONObject(),new JSONObject(),List.of(view),new JSONArray(),0,now+3000000,PhoneRuntime.Decision.clear("com.game.test"));
            PhoneNotifications.budget(context,s,state,"com.game.test",true,now);var manager=Shadows.shadowOf(context.getSystemService(NotificationManager.class));Notification first=manager.getNotification(101);assertNotNull(first);assertTrue((first.flags&Notification.FLAG_ONGOING_EVENT)!=0);assertTrue(first.extras.getBoolean(Notification.EXTRA_SHOW_CHRONOMETER));assertTrue(first.extras.getBoolean(Notification.EXTRA_CHRONOMETER_COUNT_DOWN));assertEquals(now+3000000,first.when);
            PhoneNotifications.budget(context,s,state,"",false,now+10000);Notification paused=manager.getNotification(101);assertFalse(paused.extras.getBoolean(Notification.EXTRA_SHOW_CHRONOMETER));assertTrue(paused.extras.getString(Notification.EXTRA_TEXT).contains("0:50:00"));assertEquals(1,manager.size());
            s.put("budget_counter","false");PhoneNotifications.budget(context,s,state,"",false,now);assertNull(manager.getNotification(101));
        }
    }
}
