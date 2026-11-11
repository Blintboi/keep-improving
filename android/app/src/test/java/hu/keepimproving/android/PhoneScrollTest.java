package hu.keepimproving.android;

import android.os.Bundle;
import android.os.Looper;
import android.view.View;
import android.widget.TextView;
import android.widget.Spinner;
import android.view.ViewGroup;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.Robolectric;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.Shadows;
import org.robolectric.annotation.Config;
import org.robolectric.annotation.GraphicsMode;
import java.time.LocalDate;
import java.util.concurrent.TimeUnit;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=35,qualifiers="w393dp-h851dp-port-xxhdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
public class PhoneScrollTest {
    void settle()throws Exception{CollectionJob.LOAD.submit(()->{}).get(20,TimeUnit.SECONDS);CollectionJob.WORK.submit(()->{}).get(15,TimeUnit.SECONDS);Shadows.shadowOf(Looper.getMainLooper()).idle();}
    void layout(MainActivity a){a.root.measure(View.MeasureSpec.makeMeasureSpec(a.dp(393),View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(a.dp(780),View.MeasureSpec.EXACTLY));a.root.layout(0,0,a.dp(393),a.dp(780));a.pageScroll.getViewTreeObserver().dispatchOnPreDraw();}
    Spinner chartChoice(View view){if(view instanceof Spinner s&&s.getCount()==2&&s.getItemAtPosition(0).toString().contains("Colors"))return s;if(view instanceof ViewGroup g)for(int i=0;i<g.getChildCount();i++){Spinner s=chartChoice(g.getChildAt(i));if(s!=null)return s;}return null;}
    int chartTop(MainActivity a){Spinner choice=chartChoice(a.root);assertNotNull(choice);android.graphics.Rect bounds=new android.graphics.Rect();choice.getDrawingRect(bounds);a.content.offsetDescendantRectToMyCoords(choice,bounds);return bounds.top;}
    @Test public void syncedFocusCardAppearingAndDisappearingKeepsChartAtTheSameScreenPosition()throws Exception{
        try(var controller=Robolectric.buildActivity(MainActivity.class).setup()){
            MainActivity a=controller.get();settle();layout(a);a.pageScroll.scrollTo(0,chartTop(a)-a.dp(60));int offset=chartTop(a)-a.pageScroll.getScrollY();
            var timer=new org.json.JSONObject().put("active",true).put("running",false).put("remaining",900).put("at",System.currentTimeMillis());
            var pc=new org.json.JSONObject().put("device","fixture-pc").put("name","PC").put("rows",new org.json.JSONArray()).put("companion",new org.json.JSONObject().put("focus_state",timer));
            a.devices.add(pc);a.render();layout(a);assertEquals(offset,chartTop(a)-a.pageScroll.getScrollY());
            timer.put("active",false);a.render();layout(a);assertEquals(offset,chartTop(a)-a.pageScroll.getScrollY());
        }
    }
    @Test public void scrollingMomentumContinuesAcrossAnOverviewRefresh()throws Exception{
        try(var controller=Robolectric.buildActivity(MainActivity.class).setup()){
            MainActivity a=controller.get();settle();layout(a);a.pageScroll.scrollTo(0,a.dp(150));a.pageScroll.fling(a.dp(1500));
            Shadows.shadowOf(Looper.getMainLooper()).idleFor(java.time.Duration.ofMillis(40));a.pageScroll.computeScroll();int before=a.pageScroll.getScrollY();
            a.render();layout(a);
            Shadows.shadowOf(Looper.getMainLooper()).idleFor(java.time.Duration.ofMillis(40));a.pageScroll.computeScroll();
            assertTrue("Refreshing the statistics must not cancel an ongoing scroll",a.pageScroll.getScrollY()>before);
        }
    }
    @Test public void choosingChartColorsKeepsTheChartInView()throws Exception{
        try(var controller=Robolectric.buildActivity(MainActivity.class).setup()){
            MainActivity a=controller.get();settle();layout(a);Spinner choice=chartChoice(a.root);assertNotNull(choice);
            android.graphics.Rect bounds=new android.graphics.Rect();choice.getDrawingRect(bounds);a.content.offsetDescendantRectToMyCoords(choice,bounds);
            a.pageScroll.scrollTo(0,bounds.top-a.dp(60));int offset=a.pageScroll.getScrollY();assertTrue(offset>0);
            choice.setSelection(1);choice.getOnItemSelectedListener().onItemSelected(choice,null,1,1);layout(a);
            assertEquals(offset,a.pageScroll.getScrollY());assertEquals(1,chartChoice(a.root).getSelectedItemPosition());
        }
    }
    @Test public void refreshNavigationAndRecreationKeepTheVisibleSection()throws Exception{
        Bundle saved=new Bundle();int offset;
        try(var controller=Robolectric.buildActivity(MainActivity.class).setup()){
            MainActivity a=controller.get();settle();a.showPage(5);layout(a);a.pageScroll.scrollTo(0,a.dp(450));offset=a.pageScroll.getScrollY();assertTrue(offset>0);
            a.render();a.render();layout(a);assertEquals(offset,a.pageScroll.getScrollY());
            a.showPage(0);layout(a);assertEquals(0,a.pageScroll.getScrollY());a.showPage(5);layout(a);assertEquals(offset,a.pageScroll.getScrollY());
            a.budgetDevice="saved-device";a.reminderLimit=80;a.activityQuery="test search";a.activityDevice="phone";a.activityCategory=2;controller.saveInstanceState(saved);
        }
        try(var controller=Robolectric.buildActivity(MainActivity.class).create(saved).start().resume()){
            MainActivity a=controller.get();settle();layout(a);assertEquals(offset,a.pageScroll.getScrollY());assertEquals("test search",a.activityQuery);assertEquals("phone",a.activityDevice);assertEquals(2,a.activityCategory);assertEquals("saved-device",a.budgetDevice);assertEquals(80,a.reminderLimit);
        }
    }
    @Test public void freshLocalUsageUpdatesVisibleTotalWithoutMovingPage()throws Exception{
        try(var controller=Robolectric.buildActivity(MainActivity.class).setup()){
            MainActivity a=controller.get();settle();layout(a);a.pageScroll.scrollTo(0,a.dp(300));int offset=a.pageScroll.getScrollY();assertTrue(offset>0);
            try(PhoneStore store=new PhoneStore(a)){store.add(new UsageLedger.Slice(LocalDate.now().toString(),"com.example.fixture",60000),"Fixture",false);}
            a.refreshVisibleStats();settle();layout(a);
            assertEquals(a.duration(60),((TextView)a.root.findViewWithTag("phone-today")).getText().toString());assertEquals(offset,a.pageScroll.getScrollY());
            controller.pause();try(PhoneStore store=new PhoneStore(a)){store.add(new UsageLedger.Slice(LocalDate.now().toString(),"com.example.fixture",60000),"Fixture",false);}
            a.refreshVisibleStats();settle();assertEquals(a.duration(60),((TextView)a.root.findViewWithTag("phone-today")).getText().toString());
        }
    }
}
