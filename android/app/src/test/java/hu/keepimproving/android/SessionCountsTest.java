package hu.keepimproving.android;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.*;
import org.robolectric.util.ReflectionHelpers;
import android.os.Looper;
import android.view.*;
import android.widget.*;
import android.graphics.*;
import java.util.*;
import java.time.*;
import java.io.*;
import java.util.concurrent.TimeUnit;
import org.json.*;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class) @Config(sdk=35) @GraphicsMode(GraphicsMode.Mode.NATIVE)
public class SessionCountsTest {
    @Test public void batchesMidnightAndReplayRemainOneSession()throws Exception{
        var c=RuntimeEnvironment.getApplication();try(var store=new PhoneStore(c)){
            long start=LocalDate.now().minusDays(1).atTime(23,59,58).atZone(ZoneId.systemDefault()).toInstant().toEpochMilli();store.put("sessions_since",Long.toString(start-1000));
            String day=PhoneRules.day(start,0,ZoneId.systemDefault());store.add(new UsageLedger.Slice(day,"example.app",10000),"Example",false);
            var db=store.getWritableDatabase();db.beginTransaction();try{SessionCounts.record(store,"example.app",start,start+2000);SessionCounts.record(store,"example.app",start+4000,start+10000);SessionCounts.record(store,"example.app",start+2000,start+4000);SessionCounts.record(store,"example.app",start,start+10000);db.setTransactionSuccessful();}finally{db.endTransaction();}
            JSONObject data=SessionCounts.snapshot(store);assertEquals(1,data.getJSONArray("rows").length());assertEquals(1,data.getJSONArray("rows").getJSONArray(0).getLong(3));assertEquals(day,data.getJSONArray("rows").getJSONArray(0).getString(0));
            SessionCounts.record(store,"example.app",start+12000,start+13000);
            store.add(new UsageLedger.Slice(PhoneRules.day(start+12000,0,ZoneId.systemDefault()),"example.app",1000),"Example",false);
            assertEquals(2,SessionCounts.snapshot(store).getJSONArray("rows").length());
            String code="1".repeat(32);JSONObject snapshot=store.snapshot(code);String device=snapshot.getString("device"),revision=Long.toString(snapshot.getLong("revision"));
            JSONObject fixture=new JSONObject().put("code",code).put("entry",new JSONObject().put("device",device).put("revision",revision).put("payload",SyncCrypto.seal(snapshot.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8),code,device,revision)));
            java.nio.file.Files.write(new File(System.getProperty("keepImprovingReports","build"),"sessions-phone-export.json").toPath(),fixture.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
        }
    }
    @Test public void visiblePartsSplitCoveredTimeAndUpgradeKeepsUnknownHistory()throws Exception{
        var parts=CoverageLedger.parts(List.of(new CoverageLedger.Interval(12,16),new CoverageLedger.Interval(14,18)),10,20);
        assertEquals(List.of(new CoverageLedger.Interval(10,12),new CoverageLedger.Interval(18,20)),parts);
        assertEquals(4,CoverageLedger.visible(List.of(new CoverageLedger.Interval(12,16),new CoverageLedger.Interval(14,18)),10,20));
        var c=RuntimeEnvironment.getApplication();String day=LocalDate.now().minusDays(1).toString();
        try(var store=new PhoneStore(c)){store.add(new UsageLedger.Slice(day,"old.app",60000),"Old",false);store.put("excluded","[\"private.app\"]");store.getWritableDatabase().execSQL("DROP TABLE sessions");store.getWritableDatabase().delete("meta","key='sessions_since'",null);store.getWritableDatabase().setVersion(5);}
        try(var store=new PhoneStore(c)) {assertEquals(6,store.getReadableDatabase().getVersion());assertEquals("[\"private.app\"]",store.get("excluded",""));assertEquals(60000,store.rows(false).getJSONArray(0).getDouble(4)*1000,.001);assertEquals(0,SessionCounts.snapshot(store).getJSONArray("rows").length());SessionCounts.record(store,"old.app",1,100);assertEquals(0,SessionCounts.snapshot(store).getJSONArray("rows").length());}
    }
    @Test public void importedCountsUseMatchingCategoriesAndRejectInvalidData()throws Exception{
        JSONObject data=new JSONObject().put("device","a").put("rows",new JSONArray()).put("activity",new JSONArray().put(new JSONArray().put("2026-11-03").put("app").put("chrome.exe").put("Chrome").put(60)).put(new JSONArray().put("2026-11-03").put("site").put("example.test").put("example.test").put(50))).put("sessions",new JSONObject().put("since","2026-11-02").put("rows",new JSONArray().put(new JSONArray().put("2026-11-03").put("app").put("chrome.exe").put(1)).put(new JSONArray().put("2026-11-03").put("site").put("example.test").put(3)).put(new JSONArray().put("2026-11-03").put("browser").put("other").put(2))));
        SessionCounts.validate(data.getJSONObject("sessions"));assertEquals(5,Statistics.rows(data,"all").stream().mapToLong(Statistics.Row::sessions).sum());assertEquals(1,Statistics.rows(data,"apps").get(0).sessions());assertEquals(3,Statistics.rows(data,"websites").get(0).sessions());
        data.getJSONObject("sessions").getJSONArray("rows").getJSONArray(0).put(3,1.5);assertThrows(Exception.class,()->SessionCounts.validate(data.getJSONObject("sessions")));
        data.remove("sessions");assertTrue(SessionCounts.partial(Statistics.rows(data,"apps").get(0),"2026-11-03"));
    }
    static String labels(View v){StringBuilder b=new StringBuilder();if(v instanceof TextView t)b.append(t.getText()).append('\n');if(v instanceof ViewGroup group)for(int i=0;i<group.getChildCount();i++)b.append(labels(group.getChildAt(i)));return b.toString();}
    @Test public void onlyActualUntrackedUsageMakesCountsPartial() {
        assertFalse(SessionCounts.partial(new Statistics.Row("2026-11-03","app","New","app",60,"pc",2,"2026-11-02"),"2026-10-01"));
        assertTrue(SessionCounts.partial(new Statistics.Row("2026-11-02","app","Old","app",60,"pc",2,"2026-11-02"),"2026-10-01"));
    }
    @Test public void chartChoiceIsRememberedAndKeepsCategory()throws Exception {
        var c=RuntimeEnvironment.getApplication();c.getSharedPreferences("ui",0).edit().putBoolean("statistics_chart_sessions",false).commit();
        try(var controller=Robolectric.buildActivity(MainActivity.class).setup()){
            MainActivity a=controller.get();a.content.removeAllViews();ReflectionHelpers.callInstanceMethod(a,"filters",ReflectionHelpers.ClassParameter.from(boolean.class,false));
            Spinner choice=a.content.findViewWithTag("statistics-measure");assertNotNull(choice);assertEquals(8,choice.getCount());choice.setSelection(6);Shadows.shadowOf(Looper.getMainLooper()).idle();
            assertTrue(c.getSharedPreferences("ui",0).getBoolean("statistics_chart_sessions",false));assertEquals(2,(int)ReflectionHelpers.getField(a,"categoryIndex"));
        }
        try(var controller=Robolectric.buildActivity(MainActivity.class).setup()){assertTrue((boolean)ReflectionHelpers.callInstanceMethod(controller.get(),"chartSessions"));}
    }
    @Test public void rankingShowsMeasuredCountsAndSortsZeroesInBothLanguages()throws Exception{
        var c=RuntimeEnvironment.getApplication();String day=LocalDate.now().toString(),since=LocalDate.now().minusDays(2).toString();
        for(String language:new String[]{"hu","en"}){
            c.getSharedPreferences("ui",0).edit().putString("language",language).commit();RuntimeEnvironment.setQualifiers(language.equals("hu")?"w393dp-h851dp-port-xxhdpi":"w320dp-h640dp-port-xhdpi");
            try(var controller=Robolectric.buildActivity(MainActivity.class).setup()){
                MainActivity a=controller.get();CollectionJob.LOAD.submit(()->{}).get(20,TimeUnit.SECONDS);CollectionJob.WORK.submit(()->{}).get(15,TimeUnit.SECONDS);Shadows.shadowOf(Looper.getMainLooper()).idle();
                List<Statistics.Row> rows=List.of(new Statistics.Row(day,"editor.exe","Editor","app",100,"pc",1,since),new Statistics.Row(day,"discord.exe","Discord","app",80,"pc",12,since),new Statistics.Row(day,"legacy.exe","Legacy","app",120,"older"));
                for(boolean sessions:new boolean[]{false,true}){
                c.getSharedPreferences("ui",0).edit().putBoolean("statistics_chart_sessions",sessions).commit();
                a.content.removeAllViews();ReflectionHelpers.callInstanceMethod(a,"chart",ReflectionHelpers.ClassParameter.from(List.class,rows));
                View chart=((ViewGroup)a.content.getChildAt(0)).getChildAt(2);assertTrue(chart.getContentDescription().toString().contains("13"));assertFalse(chart.getContentDescription().toString().contains("≥"));
                TreeMap<String,Map<String,Double>> values=ReflectionHelpers.getField(chart,"values");assertEquals(sessions?13:300,values.get(day).values().stream().mapToDouble(Double::doubleValue).sum(),.001);
                int cw=a.getResources().getDisplayMetrics().widthPixels,ch=a.getResources().getDisplayMetrics().heightPixels;a.root.measure(View.MeasureSpec.makeMeasureSpec(cw,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(ch,View.MeasureSpec.EXACTLY));a.root.layout(0,0,cw,ch);
                Bitmap chartImage=Bitmap.createBitmap(cw,ch,Bitmap.Config.ARGB_8888);a.root.draw(new Canvas(chartImage));File chartFile=new File(System.getProperty("keepImprovingReports","build"),"ui/chart-"+(sessions?"sessions":"time")+"-"+language+".png");chartFile.getParentFile().mkdirs();try(var out=new FileOutputStream(chartFile)){assertTrue(chartImage.compress(Bitmap.CompressFormat.PNG,100,out));}chartImage.recycle();
                }
                for(int order:new int[]{3,2}){c.getSharedPreferences("ui",0).edit().putInt("statistics_sort",order).commit();a.content.removeAllViews();ReflectionHelpers.callInstanceMethod(a,"ranking",ReflectionHelpers.ClassParameter.from(List.class,rows));String text=labels(a.content);assertTrue(text.contains("13"));assertFalse(text.contains("≥"));assertTrue(order==2?text.indexOf("Legacy")>text.indexOf("Editor"):text.indexOf("Legacy")<text.indexOf("Editor"));assertTrue(order==2?text.indexOf("Discord")<text.indexOf("Editor"):text.indexOf("Editor")<text.indexOf("Discord"));}
                int width=a.getResources().getDisplayMetrics().widthPixels,height=a.getResources().getDisplayMetrics().heightPixels;a.root.measure(View.MeasureSpec.makeMeasureSpec(width,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(height,View.MeasureSpec.EXACTLY));a.root.layout(0,0,width,height);
                Bitmap image=Bitmap.createBitmap(width,height,Bitmap.Config.ARGB_8888);a.root.draw(new Canvas(image));File file=new File(System.getProperty("keepImprovingReports","build"),"ui/sessions-"+language+".png");file.getParentFile().mkdirs();try(var out=new FileOutputStream(file)){assertTrue(image.compress(Bitmap.CompressFormat.PNG,100,out));}image.recycle();
            }
        }
    }
}
