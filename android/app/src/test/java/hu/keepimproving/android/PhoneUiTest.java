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
    private void settle() throws Exception {CollectionJob.WORK.submit(()->{}).get(15,TimeUnit.SECONDS);Shadows.shadowOf(Looper.getMainLooper()).idle();}
    private TextView find(View root,String text) {
        if(root instanceof TextView view&&view.getText().toString().equals(text))return view;
        if(root instanceof ViewGroup group)for(int i=0;i<group.getChildCount();i++){TextView result=find(group.getChildAt(i),text);if(result!=null)return result;}
        return null;
    }
    private void capture(MainActivity activity,String name) throws Exception {
        View view=activity.getWindow().getDecorView();int width=activity.getResources().getDisplayMetrics().widthPixels,height=activity.getResources().getDisplayMetrics().heightPixels;
        view.measure(View.MeasureSpec.makeMeasureSpec(width,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(height,View.MeasureSpec.EXACTLY));view.layout(0,0,width,height);
        Bitmap bitmap=Bitmap.createBitmap(width,height,Bitmap.Config.ARGB_8888);view.draw(new Canvas(bitmap));
        File output=new File(System.getProperty("keepImprovingReports","build"),"ui/"+name+".png");output.getParentFile().mkdirs();try(var stream=new FileOutputStream(output)){assertTrue(bitmap.compress(Bitmap.CompressFormat.PNG,100,stream));}bitmap.recycle();
    }
    @Test public void permissionNavigationAndBothLanguages() throws Exception {
        Context context=RuntimeEnvironment.getApplication();
        for(String language:new String[]{"hu","en"}) {
            context.getSharedPreferences("ui",0).edit().putString("language",language).commit();
            try(var controller=Robolectric.buildActivity(MainActivity.class).setup()) {
                MainActivity activity=controller.get();settle();
                View root=activity.getWindow().getDecorView();
                assertNotNull(find(root,activity.getString(R.string.grant_access)));capture(activity,"permission-"+language);
                TextView nav=find(root,activity.getString(R.string.settings));assertNotNull(nav);nav.performClick();
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
                assertNotNull(find(root,activity.getString(R.string.sync_now)));capture(activity,"three-devices-"+language);
                // Scroll the actual content to the device cards for visual review.
                View sync=find(root,activity.getString(R.string.devices_sync));View parent=sync;while(parent.getParent() instanceof View&&!(parent instanceof android.widget.ScrollView))parent=(View)parent.getParent();
                if(parent instanceof android.widget.ScrollView scroll){android.graphics.Rect bounds=new android.graphics.Rect();sync.getDrawingRect(bounds);scroll.offsetDescendantRectToMyCoords(sync,bounds);scroll.scrollTo(0,Math.max(0,bounds.top-50));capture(activity,"device-cards-"+language);}
            }
        }
    }
}
