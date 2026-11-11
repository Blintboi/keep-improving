package hu.keepimproving.android;

import android.content.Context;
import android.os.Bundle;
import android.os.Looper;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.Config;
import org.robolectric.util.ReflectionHelpers;
import java.util.concurrent.TimeUnit;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=35)
public class PhoneNavigationTest {
    private TextView find(View root,String text){
        if(root instanceof TextView v&&v.getText().toString().equals(text))return v;
        if(root instanceof ViewGroup group)for(int i=0;i<group.getChildCount();i++){TextView found=find(group.getChildAt(i),text);if(found!=null)return found;}
        return null;
    }
    private void settle()throws Exception{CollectionJob.LOAD.submit(()->{}).get(20,TimeUnit.SECONDS);CollectionJob.WORK.submit(()->{}).get(15,TimeUnit.SECONDS);Shadows.shadowOf(Looper.getMainLooper()).idle();}
    @Test @Config(sdk={28,35}) public void settingsOnlyInMenuAndBackReturnsHome()throws Exception{
        try(var controller=Robolectric.buildActivity(MainActivity.class).setup()){
            MainActivity a=controller.get();settle();assertNotNull(a.state);
            assertNull(find(a.root,a.getString(R.string.settings)));
            a.showMenu(((ViewGroup)a.root.getChildAt(0)).getChildAt(0));
            find(a.navigationMenu.getContentView(),a.getString(R.string.settings)).performClick();
            assertEquals(5,(int)ReflectionHelpers.getField(a,"page"));
            a.onBackPressed();assertFalse(a.isFinishing());assertEquals(0,(int)ReflectionHelpers.getField(a,"page"));
            for(int page=1;page<=5;page++){a.showPage(page);a.onBackPressed();assertEquals(0,(int)ReflectionHelpers.getField(a,"page"));assertFalse(a.isFinishing());}
        }
    }
    @Test public void gestureBackWorksAfterRecreationAndLeavesRootToAndroid()throws Exception{
        try(var controller=Robolectric.buildActivity(MainActivity.class).setup()){
            MainActivity a=controller.get();settle();a.showPage(5);controller.recreate();a=controller.get();settle();
            android.window.OnBackInvokedCallback callback=ReflectionHelpers.getField(a,"pageBack");assertNotNull(callback);
            callback.onBackInvoked();assertEquals(0,(int)ReflectionHelpers.getField(a,"page"));assertFalse(a.isFinishing());assertNull(ReflectionHelpers.getField(a,"pageBack"));
        }
    }
    @Test public void upgradeRechecksOldDailyRefusalOnceAndPreservesData(){
        Context c=RuntimeEnvironment.getApplication();long now=System.currentTimeMillis();
        try(PhoneStore store=new PhoneStore(c)){
            store.put("sync_after",Long.toString(now+4*3600000));store.put("last_sync",Long.toString(now-3600000));store.put("enabled","true");String device=store.device();
            store.add(new UsageLedger.Slice("2026-11-04","example.app",9000),"Example",false);
            store.getWritableDatabase().setVersion(4);
            try(PhoneStore upgraded=new PhoneStore(c)){
                assertTrue(upgraded.number("sync_after",0)<=System.currentTimeMillis());assertEquals(device,upgraded.device());assertEquals("true",upgraded.get("enabled",""));
                assertEquals(1,upgraded.getReadableDatabase().compileStatement("SELECT COUNT(*) FROM usage").simpleQueryForLong());
                upgraded.put("sync_after",Long.toString(now+7200000));
            }
            try(PhoneStore reopened=new PhoneStore(c)){assertEquals(now+7200000,reopened.number("sync_after",0));}
        }
    }
    @Test public void upgradeKeepsRecentCooldown(){
        Context c=RuntimeEnvironment.getApplication();long now=System.currentTimeMillis();
        try(PhoneStore store=new PhoneStore(c)){store.put("sync_after",Long.toString(now+4*3600000));store.put("last_sync",Long.toString(now-5000));store.getWritableDatabase().setVersion(4);}
        try(PhoneStore store=new PhoneStore(c)){assertEquals(now+10000,store.number("sync_after",0));}
    }
}
