package hu.keepimproving.android;

import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;
import org.robolectric.Robolectric;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import org.robolectric.annotation.GraphicsMode;
import org.robolectric.annotation.Implements;
import org.robolectric.annotation.Implementation;
import org.robolectric.Shadows;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.os.Looper;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;
import java.io.File;
import java.io.FileOutputStream;
import java.util.concurrent.TimeUnit;
import org.json.*;
import java.nio.charset.StandardCharsets;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=35,qualifiers="w393dp-h851dp-port-xxhdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
public class PhoneUiTest {
    private void settle() throws Exception {CollectionJob.LOAD.submit(()->{}).get(20,TimeUnit.SECONDS);CollectionJob.WORK.submit(()->{}).get(15,TimeUnit.SECONDS);Shadows.shadowOf(Looper.getMainLooper()).idle();}
    private TextView find(View root,String text) {
        if(root instanceof TextView view&&view.getText().toString().equals(text))return view;
        if(root instanceof ViewGroup group)for(int i=0;i<group.getChildCount();i++){TextView result=find(group.getChildAt(i),text);if(result!=null)return result;}
        return null;
    }
    private void capture(MainActivity activity,String name) throws Exception {
        captureView(activity,activity.getWindow().getDecorView(),name);
    }
    @Test public void companionNavigationAndFormsInBothLanguages()throws Exception {
        Context c=RuntimeEnvironment.getApplication();JSONObject companion;
        try(PhoneStore s=new PhoneStore(c)){s.saveRule("budget",PhoneRules.budget().put("name","Phone games").put("category","games"));s.saveRule("reminder",PhoneRules.reminder().put("title","Phone reminder"));JSONObject snap=PhoneCompanionTest.snapshot(s);snap.getJSONObject("companion").getJSONArray("notifications").put(PhoneRules.object("{\"id\":\"pc-reminder\",\"title\":\"PC reminder\",\"text\":\"Take a break\",\"trigger\":\"time\",\"minute\":720,\"enabled\":true}"));PhoneCompanion.accept(s,snap);companion=PhoneCompanion.devices(s).get(0);}
        for(String language:new String[]{"hu","en"}){
            c.getSharedPreferences("ui",0).edit().putString("language",language).commit();RuntimeEnvironment.setQualifiers(language.equals("hu")?"w393dp-h851dp-port-xxhdpi":"w320dp-h640dp-port-xhdpi");
            try(var controller=Robolectric.buildActivity(MainActivity.class).setup()){
                MainActivity a=controller.get();settle();a.showPage(5);assertNull(find(a.getWindow().getDecorView(),a.getString(R.string.read_error)));assertNotNull(find(a.getWindow().getDecorView(),"Asztali PC"));capture(a,"linked-settings-"+language);
                a.showMenu(((ViewGroup)a.root.getChildAt(0)).getChildAt(0));assertTrue(a.navigationMenu.isShowing());assertNull(find(a.navigationMenu.getContentView(),a.getString(R.string.pc_devices)));captureView(a,a.navigationMenu.getContentView(),"hamburger-"+language);a.navigationMenu.dismiss();
                a.showPage(2);assertNotNull(find(a.root,"Asztali PC"));assertNotNull(find(a.root,"Phone games"));capture(a,"unified-budgets-"+language);a.showPage(3);assertNotNull(find(a.root,"PC reminder"));assertNotNull(find(a.root,"Phone reminder"));capture(a,"unified-notifications-"+language);
                a.showPage(1);assertNotNull(find(a.getWindow().getDecorView(),"Example game\nAsztali PC · "+a.t("Game","Játék")));capture(a,"all-activities-"+language);
                RemoteScreens.budget(a,companion,companion.getJSONArray("budgets").getJSONObject(0));android.app.AlertDialog editor=org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog();assertTrue(editor.isShowing());captureView(a,editor.getWindow().getDecorView(),"pc-budget-"+language);editor.dismiss();
                RemoteScreens.settings(a,companion);editor=org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog();captureView(a,editor.getWindow().getDecorView(),"pc-settings-"+language);editor.dismiss();
            }
        }
    }
    private void captureView(MainActivity activity,View view,String name) throws Exception {
        int width=activity.getResources().getDisplayMetrics().widthPixels,height=activity.getResources().getDisplayMetrics().heightPixels;
        view.measure(View.MeasureSpec.makeMeasureSpec(width,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(height,View.MeasureSpec.EXACTLY));view.layout(0,0,width,height);
        Bitmap bitmap=Bitmap.createBitmap(width,height,Bitmap.Config.ARGB_8888);view.draw(new Canvas(bitmap));
        File output=new File(System.getProperty("keepImprovingReports","build"),"ui/"+name+".png");output.getParentFile().mkdirs();try(var stream=new FileOutputStream(output)){assertTrue(bitmap.compress(Bitmap.CompressFormat.PNG,100,stream));}bitmap.recycle();
    }
    @Test public void completePhoneFlowsAndDraftsInBothLanguages()throws Exception {
        Context c=RuntimeEnvironment.getApplication();
        JSONObject budget=PhoneRules.budget().put("name","Játékok / Games").put("category","games");JSONObject reminder=PhoneRules.reminder().put("title","Ideje pihenni / Take a break").put("text","Állj fel, igyál vizet. / Stand up and drink some water.").put("clock",1439);
        try(PhoneStore s=new PhoneStore(c)){s.saveRule("budget",budget);s.saveRule("reminder",reminder);s.add(new UsageLedger.Slice(java.time.LocalDate.now().toString(),"com.example.game",900000),"Sample game",true);}
        for(String language:new String[]{"hu","en"}){
            c.getSharedPreferences("ui",0).edit().putString("language",language).commit();RuntimeEnvironment.setQualifiers(language.equals("hu")?"w393dp-h851dp-port-xxhdpi":"w320dp-h640dp-port-xhdpi");
            try(var controller=Robolectric.buildActivity(MainActivity.class).setup()){
                MainActivity a=controller.get();settle();assertNotNull(a.state);
                for(int page:new int[]{1,2,3,4,5}){a.showPage(page);assertNull(find(a.getWindow().getDecorView(),a.getString(R.string.read_error)));capture(a,"feature-"+page+"-"+language);}
                a.showPage(4);PhoneEditor.focus(a);android.app.AlertDialog focus=org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog();assertTrue(focus.isShowing());captureView(a,focus.getWindow().getDecorView(),"editor-focus-"+language);focus.dismiss();
                PhoneEditor.budget(a,budget);android.app.AlertDialog edit=org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog();captureView(a,edit.getWindow().getDecorView(),"editor-budget-"+language);edit.dismiss();
                PhoneEditor.reminder(a,reminder);edit=org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog();captureView(a,edit.getWindow().getDecorView(),"editor-reminder-"+language);edit.dismiss();
                PhoneEditor draft=new PhoneEditor(a,"budget",budget,"Draft");draft.set("name","Saved unfinished edit");draft.dialog.show();draft.dialog.dismiss();PhoneEditor restored=new PhoneEditor(a,"budget",budget,"Draft");assertEquals("Saved unfinished edit",restored.value.getString("name"));restored.clear();
            }
        }
    }
    @Test public void sessionLimitEditorInBothLanguages()throws Exception {
        Context c=RuntimeEnvironment.getApplication();
        for(String language:new String[]{"hu","en"}){
            c.getSharedPreferences("ui",0).edit().putString("language",language).commit();RuntimeEnvironment.setQualifiers(language.equals("hu")?"w393dp-h851dp-port-xxhdpi":"w320dp-h640dp-port-xhdpi");
            try(var controller=Robolectric.buildActivity(MainActivity.class).setup()){
                MainActivity a=controller.get();settle();JSONObject budget=PhoneRules.budget().put("name","Visits").put("category","apps").put("limit",false).put("steps",new JSONArray().put(PhoneRules.step().put("mode","sessions").put("sessions",5)));
                PhoneEditor parent=new PhoneEditor(a,"budget",budget,"Visits");PhoneEditor.step(parent,0,()->{});settle();
                android.app.AlertDialog dialog=org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog();assertNotNull(dialog);
                assertNotNull(find(dialog.getWindow().getDecorView(),a.t("Allowed sessions","Engedélyezett munkamenetek")+" (1–10000)"));
                captureView(a,dialog.getWindow().getDecorView(),"session-limit-"+language);
                dialog.getButton(android.app.AlertDialog.BUTTON_POSITIVE).performClick();assertFalse(dialog.isShowing());
                assertEquals(5,parent.value.getJSONArray("steps").getJSONObject(0).getInt("sessions"));parent.clear();
            }
        }
    }
    @Test public void protectionOverlayRendersAndExemptsSystemApps()throws Exception {
        Context c=RuntimeEnvironment.getApplication();c.getSharedPreferences("ui",0).edit().putString("language","hu").commit();
        var serviceController=Robolectric.buildService(ShieldService.class).create();
        try(var controller=Robolectric.buildActivity(MainActivity.class).setup()){
            MainActivity a=controller.get();settle();ShieldService service=serviceController.get();org.robolectric.util.ReflectionHelpers.setField(service,"foreground","com.example.game");
            java.lang.reflect.Method apply=ShieldService.class.getDeclaredMethod("apply",PhoneRuntime.Decision.class);apply.setAccessible(true);
            apply.invoke(service,new PhoneRuntime.Decision("com.example.game",true,false,false,"Játékok",0,5,java.util.List.of("group")));
            View overlay=org.robolectric.util.ReflectionHelpers.getField(service,"overlay");assertNotNull(overlay);captureView(a,overlay,"protection-hu");
            org.robolectric.util.ReflectionHelpers.setField(service,"foreground","com.android.settings");apply.invoke(service,new PhoneRuntime.Decision("com.android.settings",true,true,false,"",0,0,java.util.List.of()));assertNull(org.robolectric.util.ReflectionHelpers.getField(service,"overlay"));settle();
        }finally{serviceController.destroy();}
    }
    @Test public void permissionNavigationAndBothLanguages() throws Exception {
        Context context=RuntimeEnvironment.getApplication();
        for(String language:new String[]{"hu","en"}) {
            context.getSharedPreferences("ui",0).edit().putString("language",language).commit();
            try(var controller=Robolectric.buildActivity(MainActivity.class).setup()) {
                MainActivity activity=controller.get();settle();
                View root=activity.getWindow().getDecorView();
                assertNotNull(find(root,activity.getString(R.string.grant_access)));capture(activity,"permission-"+language);
                assertNull(find(root,activity.getString(R.string.settings)));activity.showMenu(((ViewGroup)activity.root.getChildAt(0)).getChildAt(0));TextView nav=find(activity.navigationMenu.getContentView(),activity.getString(R.string.settings));assertNotNull(nav);nav.performClick();
                assertNotNull(find(activity.getWindow().getDecorView(),activity.getString(R.string.tracking)));capture(activity,"settings-"+language);
            }
        }
    }
    @Test public void persistedPhoneHistoryAndDevicesRemainDistinct() throws Exception {
        Context context=RuntimeEnvironment.getApplication();String id;
        try(PhoneStore store=new PhoneStore(context)) {
            id=store.device();store.add(new UsageLedger.Slice(java.time.LocalDate.now().toString(),"com.android.settings",3600000),"Settings",false);
            assertEquals(3600,store.rows(false).getJSONArray(0).getDouble(4),.001);
        }
        try(PhoneStore reopened=new PhoneStore(context)) {assertEquals(id,reopened.device());assertEquals(1,reopened.rows(false).length());assertEquals(0,reopened.rows(true).length());}
        try(var controller=Robolectric.buildActivity(MainActivity.class).setup()) {settle();capture(controller.get(),"recorded-phone");}
    }
    @Implements(value=Vault.class,isInAndroidSdk=false)
    public static class MemoryVault {
        @Implementation protected static String read(Context context){return "11111111111111111111111111111111";}
    }
    @Test @Config(shadows=MemoryVault.class) public void threeDevicesAndSmallScreen() throws Exception {
        Context context=RuntimeEnvironment.getApplication();String code="11111111111111111111111111111111";
        JSONObject fixture;try(var stream=getClass().getResourceAsStream("/interop.json")){fixture=new JSONObject(new String(stream.readAllBytes(),StandardCharsets.UTF_8));}
        JSONObject desktop=SyncProtocol.decode(fixture.getJSONObject("entry"),code);
        try(PhoneStore store=new PhoneStore(context)) {
            store.put("sync_after",Long.toString(System.currentTimeMillis()+3600000));store.put("name","Telefon");
            store.add(new UsageLedger.Slice(java.time.LocalDate.now().toString(),"com.android.settings",3600000),"Settings",false);
            JSONArray entries=new JSONArray();
            for(String id:new String[]{"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}) {
                desktop.put("device",id).put("name",id.startsWith("a")?"Asztali PC":"Laptop");
                desktop.getJSONArray("rows").getJSONArray(0).put(0,java.time.LocalDate.now().toString());
                for(int i=0;i<desktop.getJSONArray("activity").length();i++)desktop.getJSONArray("activity").getJSONArray(i).put(0,java.time.LocalDate.now().toString());
                String revision=Long.toString(desktop.getLong("revision"));entries.put(new JSONObject().put("device",id).put("revision",revision).put("payload",SyncCrypto.seal(desktop.toString().getBytes(StandardCharsets.UTF_8),code,id,revision)));
            }
            store.accept(entries);assertEquals(2,store.remotes(code).length());
            // Reimport is idempotent and imported time never becomes a local upload.
            store.accept(entries);assertEquals(2,store.known().length());assertEquals(0,store.snapshot(code).getJSONArray("rows").length());assertEquals(1,store.snapshot(code).getJSONArray("activity").length());
            JSONObject phone=store.snapshot(code);String revision=Long.toString(phone.getLong("revision"));
            JSONObject exported=new JSONObject().put("code",code).put("entry",new JSONObject().put("device",phone.getString("device")).put("revision",revision).put("payload",SyncCrypto.seal(phone.toString().getBytes(StandardCharsets.UTF_8),code,phone.getString("device"),revision)));
            java.nio.file.Files.write(new File(System.getProperty("keepImprovingReports","build"),"phone-export.json").toPath(),exported.toString().getBytes(StandardCharsets.UTF_8));
        }
        for(String language:new String[]{"hu","en"}) {
            context.getSharedPreferences("ui",0).edit().putString("language",language).commit();
            RuntimeEnvironment.setQualifiers(language.equals("hu")?"w393dp-h851dp-port-xxhdpi":"w320dp-h640dp-port-xhdpi");
            try(var controller=Robolectric.buildActivity(MainActivity.class).setup()) {
                settle();MainActivity activity=controller.get();View root=activity.getWindow().getDecorView();
                assertNull(find(root,activity.getString(R.string.sync_now)));assertEquals(View.GONE,((TextView)org.robolectric.util.ReflectionHelpers.getField(activity,"status")).getVisibility());capture(activity,"three-devices-"+language);
                // Scroll the actual content to the device cards for visual review.
                View sync=find(root,activity.t("Time by device","Idő eszközönként"));View parent=sync;while(parent.getParent() instanceof View&&!(parent instanceof android.widget.ScrollView))parent=(View)parent.getParent();
                if(parent instanceof android.widget.ScrollView scroll){android.graphics.Rect bounds=new android.graphics.Rect();sync.getDrawingRect(bounds);scroll.offsetDescendantRectToMyCoords(sync,bounds);scroll.scrollTo(0,Math.max(0,bounds.top-50));capture(activity,"device-cards-"+language);}
                activity.showPage(5);assertNotNull(find(activity.root,activity.getString(R.string.sync_now)));assertEquals(View.VISIBLE,((TextView)org.robolectric.util.ReflectionHelpers.getField(activity,"status")).getVisibility());capture(activity,"sync-settings-"+language);
            }
        }
    }
}
