package hu.keepimproving.android;

import android.app.AlertDialog;
import android.content.Intent;
import android.os.Looper;
import android.view.*;
import android.widget.TextView;
import org.json.*;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.Config;
import org.robolectric.shadows.ShadowAlertDialog;
import java.util.*;
import java.util.concurrent.TimeUnit;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class) @Config(sdk=35)
public class UnifiedRulesTest {
    void settle()throws Exception{CollectionJob.LOAD.submit(()->{}).get(20,TimeUnit.SECONDS);CollectionJob.WORK.submit(()->{}).get(15,TimeUnit.SECONDS);Shadows.shadowOf(Looper.getMainLooper()).idle();}
    TextView find(View view,String text){if(view instanceof TextView t&&t.getText().toString().equals(text))return t;if(view instanceof ViewGroup g)for(int i=0;i<g.getChildCount();i++){TextView t=find(g.getChildAt(i),text);if(t!=null)return t;}return null;}
    @Test public void unifiedListEditsThePcWithoutCreatingAPhoneCopy()throws Exception{
        try(PhoneStore s=new PhoneStore(RuntimeEnvironment.getApplication())){s.saveRule("budget",PhoneRules.budget().put("name","Phone games").put("category","games"));PhoneCompanion.accept(s,PhoneCompanionTest.snapshot(s));}
        try(var controller=Robolectric.buildActivity(MainActivity.class).setup()){
            MainActivity a=controller.get();settle();a.showPage(2);
            assertNotNull(find(a.root,"Phone games"));assertNotNull(find(a.root,"Asztali PC"));
            View row=a.root.findViewWithTag("rule:pc:"+PhoneCompanionTest.DEVICE+":shared-games");assertNotNull(row);
            find(row,a.t("Edit budget","Keret szerkesztése")).performClick();settle();AlertDialog editor=ShadowAlertDialog.getLatestAlertDialog();assertTrue(editor.isShowing());
            editor.getButton(AlertDialog.BUTTON_POSITIVE).performClick();settle();settle();
            try(PhoneStore s=new PhoneStore(a)){assertEquals(1,s.rules("budget").length());JSONObject command=PhoneCompanion.commands(s).getJSONObject(0);assertEquals(PhoneCompanionTest.DEVICE,command.getString("target"));assertEquals("shared-games",command.getString("key"));assertEquals("budget",command.getString("kind"));}
            UnifiedRules.create(a,"notification",RemoteScreens.pcs(a));AlertDialog picker=ShadowAlertDialog.getLatestAlertDialog();assertEquals(2,picker.getListView().getCount());picker.getListView().performItemClick(null,1,1);
            AlertDialog remote=ShadowAlertDialog.getLatestAlertDialog();assertNotSame(picker,remote);assertTrue(remote.isShowing());remote.dismiss();
        }
    }
    @Test public void sharedIdentitiesCollapseButIndependentPcRulesRemainSeparate()throws Exception{
        String shared,notice,local;
        try(PhoneStore s=new PhoneStore(RuntimeEnvironment.getApplication())){
            local=s.device();s.put("shared_connection",PhoneShared.connection(PhoneCompanionTest.CODE));JSONObject scope=new JSONObject().put("mode","all").put("connection",PhoneShared.connection(s));
            s.saveRule("budget",PhoneRules.budget().put("name","Shared").put("category","games").put("devices",scope));shared=s.rules("budget").getJSONObject(0).getString("_shared");
            s.saveRule("budget",PhoneRules.budget().put("name","Shared").put("category","games"));
            s.saveRule("reminder",PhoneRules.reminder().put("title","Shared reminder").put("devices",scope));notice=s.rules("reminder").getJSONObject(0).getString("_shared");
        }
        try(var controller=Robolectric.buildActivity(MainActivity.class).setup()){
            MainActivity a=controller.get();settle();List<JSONObject> pcs=new ArrayList<>();
            for(String device:List.of("a".repeat(32),"b".repeat(32))){JSONObject pc=PhoneCompanionTest.companion().put("device",device);pc.getJSONArray("budgets").put(PhoneRules.copy(pc.getJSONArray("budgets").getJSONObject(0)).put("id","independent"));pc.put("shared_ids",new JSONObject().put("budget:shared-games",shared).put("notification:reminder",notice));pc.getJSONArray("notifications").put(new JSONObject().put("id","reminder").put("title","Shared reminder"));pcs.add(pc);}
            List<UnifiedRules.Row> rows=UnifiedRules.rows(a,"budget",pcs);assertEquals(4,rows.size());assertEquals(1,rows.stream().filter(r->r.key().equals("shared:"+shared)).count());assertEquals(1,UnifiedRules.rows(a,"notification",pcs).size());
            try(PhoneStore s=new PhoneStore(a)){assertEquals(2,rows.stream().filter(r->UnifiedRules.matches(s,r,pcs.get(0).optString("device"))).count());assertEquals(2,rows.stream().filter(r->UnifiedRules.matches(s,r,local)).count());s.deleteRule("budget",PhoneShared.nativeId(s,shared));}
            a.state=PhoneRuntime.refresh(a,false);assertEquals(3,UnifiedRules.rows(a,"budget",pcs).size());
        }
    }
    @Test public void syncLivesInSettingsAndOldComputersLinksStillWork()throws Exception{
        Intent intent=new Intent(RuntimeEnvironment.getApplication(),MainActivity.class).putExtra("page",6);
        try(var controller=Robolectric.buildActivity(MainActivity.class,intent).setup()){
            MainActivity a=controller.get();settle();assertNotNull(a.root.findViewWithTag("synchronization"));
            a.showMenu(((ViewGroup)a.root.getChildAt(0)).getChildAt(0));assertNull(find(a.navigationMenu.getContentView(),a.getString(R.string.pc_devices)));assertNotNull(find(a.navigationMenu.getContentView(),a.getString(R.string.settings)));a.navigationMenu.dismiss();
            a.showPage(0);assertNull(a.root.findViewWithTag("synchronization"));assertNull(find(a.root,a.getString(R.string.connect)));assertNull(find(a.root,a.getString(R.string.sync_now)));
            a.showPage(5);assertNotNull(a.root.findViewWithTag("synchronization"));assertNotNull(find(a.root,a.getString(R.string.connect)));
        }
    }
    @Test public void detailedSettingsOpenOneLevelAtATimeAndKeepAllItemsReachable()throws Exception{
        JSONObject pc=PhoneCompanionTest.companion();JSONArray plans=new JSONArray();
        for(int i=1;i<=45;i++)plans.put(new JSONObject().put("name","Plan "+i).put("seconds",i*60));
        pc.getJSONObject("settings").put("restriction_plans",plans);
        try(var controller=Robolectric.buildActivity(MainActivity.class).setup()){
            MainActivity a=controller.get();settle();RemoteScreens.settings(a,pc);
            AlertDialog settings=ShadowAlertDialog.getLatestAlertDialog();
            find(settings.getWindow().getDecorView(),RemoteLabels.label(a,"restriction_plans")+"\n"+RemoteScreens.summary(a,plans)).performClick();
            AlertDialog list=ShadowAlertDialog.getLatestAlertDialog();View rows=list.getWindow().getDecorView();
            String last="Plan 45\n"+RemoteScreens.summary(a,plans.getJSONObject(44));
            assertNull(find(rows,last));assertNull(find(rows,RemoteLabels.label(a,"seconds")+": 2700"));
            find(rows,a.getString(R.string.show_more)).performClick();find(rows,last).performClick();
            AlertDialog detail=ShadowAlertDialog.getLatestAlertDialog();assertNotNull(find(detail.getWindow().getDecorView(),RemoteLabels.label(a,"seconds")+": 2700"));
            detail.getButton(AlertDialog.BUTTON_POSITIVE).performClick();assertTrue(list.isShowing());assertNotNull(find(rows,last));
            list.dismiss();settings.dismiss();
        }
    }
}
