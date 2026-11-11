package hu.keepimproving.android;

import android.graphics.Color;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import org.robolectric.annotation.GraphicsMode;
import org.robolectric.Robolectric;
import org.robolectric.Shadows;
import org.robolectric.util.ReflectionHelpers;
import android.view.View;
import android.view.ViewGroup;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.os.Looper;
import java.util.*;
import java.time.LocalDate;
import java.util.concurrent.TimeUnit;
import java.io.File;
import java.io.FileOutputStream;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class) @Config(sdk=35) @GraphicsMode(GraphicsMode.Mode.NATIVE)
public class SeriesColorsTest {
    @Test public void dailyChartGroupsUpdatedPathsIntoOneColoredSeries()throws Exception{
        var c=RuntimeEnvironment.getApplication();
        for(String language:new String[]{"hu","en"}){
            c.getSharedPreferences("ui",0).edit().putString("language",language).commit();
            RuntimeEnvironment.setQualifiers(language.equals("hu")?"w393dp-h851dp-port-xxhdpi":"w320dp-h640dp-port-xhdpi");
            try(var controller=Robolectric.buildActivity(MainActivity.class).setup()){
                MainActivity a=controller.get();CollectionJob.LOAD.submit(()->{}).get(20,TimeUnit.SECONDS);CollectionJob.WORK.submit(()->{}).get(15,TimeUnit.SECONDS);Shadows.shadowOf(Looper.getMainLooper()).idle();
                String today=LocalDate.now().toString(),yesterday=LocalDate.now().minusDays(1).toString();
                List<Statistics.Row> rows=List.of(new Statistics.Row(yesterday,"C:\\Discord\\app-1.0\\discord.exe","Discord","app",600,"pc"),new Statistics.Row(today,"D:\\Discord\\app-2.0\\DISCORD.EXE","Discord","app",300,"pc"),new Statistics.Row(today,"editor.exe","Editor","app",180,"pc"));
                a.content.removeAllViews();ReflectionHelpers.callInstanceMethod(a,"chart",ReflectionHelpers.ClassParameter.from(List.class,rows));
                ViewGroup card=(ViewGroup)a.content.getChildAt(0);View chart=null;for(int i=0;i<card.getChildCount();i++)if(card.getChildAt(i).getClass().getSimpleName().equals("Chart"))chart=card.getChildAt(i);assertNotNull(chart);
                Map<String,Integer> colors=ReflectionHelpers.getField(chart,"colors");Map<String,Map<String,Double>> values=ReflectionHelpers.getField(chart,"values");
                assertEquals(2,colors.size());assertTrue(colors.containsKey("app:discord.exe"));assertEquals(600,values.get(yesterday).get("app:discord.exe"),.001);assertEquals(300,values.get(today).get("app:discord.exe"),.001);
                int width=a.getResources().getDisplayMetrics().widthPixels,height=a.getResources().getDisplayMetrics().heightPixels;
                a.root.measure(View.MeasureSpec.makeMeasureSpec(width,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(height,View.MeasureSpec.EXACTLY));a.root.layout(0,0,width,height);
                Bitmap image=Bitmap.createBitmap(width,height,Bitmap.Config.ARGB_8888);a.root.draw(new Canvas(image));File file=new File(System.getProperty("keepImprovingReports","build"),"ui/stable-colors-"+language+".png");file.getParentFile().mkdirs();try(var out=new FileOutputStream(file)){assertTrue(image.compress(Bitmap.CompressFormat.PNG,100,out));}image.recycle();
            }
        }
    }
    @Test public void updatesAndImportedBasenamesShareOnePersistentColor(){
        var c=RuntimeEnvironment.getApplication();var saved=c.getSharedPreferences("series_colors",0);saved.edit().clear().commit();
        int before=SeriesColors.get(c,"game","app:C:\\Users\\Fixture\\Discord\\app-1.0\\Discord.exe");
        int other=SeriesColors.get(c,"game","app:editor.exe");
        assertEquals(before,SeriesColors.get(c,"game","app:D:/Apps/Discord/app-2.0/DISCORD.EXE"));
        assertEquals(before,SeriesColors.get(c,"game","app:discord.exe"));
        assertEquals(before,saved.getInt("game:app:discord.exe",0));assertNotEquals(before,other);
        assertNotEquals(before,SeriesColors.get(c,"game","site:discord.exe"));
        assertEquals(SeriesColors.get(c,"game","site:www.example.com"),SeriesColors.get(c,"game","site:example.com"));
    }
    @Test public void migrationChoosesExistingColorIndependentOfSelectedDay(){
        var c=RuntimeEnvironment.getApplication();var saved=c.getSharedPreferences("series_colors",0);
        String old="app:C:\\Discord\\app-1.0\\discord.exe",next="app:C:\\Discord\\app-2.0\\discord.exe";
        for(String selected:new String[]{old,next}){
            saved.edit().clear().putInt("game:"+old,Color.CYAN).putInt("game:"+next,Color.MAGENTA).commit();
            assertEquals(Color.CYAN,SeriesColors.get(c,"game",selected));
            assertEquals(Color.CYAN,SeriesColors.get(c,"game",selected.equals(old)?next:old));
            assertEquals(Color.MAGENTA,saved.getInt("game:"+next,0));
        }
    }
}
