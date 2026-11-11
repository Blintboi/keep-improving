package hu.keepimproving.android;
import android.os.SystemClock;
import android.view.Gravity;
import android.widget.*;
import org.json.*;

/** The remote timer is a display, never a second local focus session. */
final class RemoteFocus {
    static long remaining(JSONObject state,long now){long value=Math.max(0,state.optLong("remaining")*1000);return state.optBoolean("running")?Math.max(0,value-Math.max(0,now-state.optLong("at",now))):value;}
    static void show(MainActivity a){
        for(JSONObject device:a.devices){JSONObject companion=device.optJSONObject("companion");JSONObject state=companion==null?null:companion.optJSONObject("focus_state");if(state==null||!state.optBoolean("active"))continue;
            LinearLayout box=a.card();box.setTag("remote-focus:"+device.optString("device"));a.heading(box,device.optString("name"));
            String phase=switch(state.optString("phase")){case "short_break"->a.t("Short break","Rövid szünet");case "long_break"->a.t("Long break","Hosszú szünet");default->a.getString(R.string.focus);};
            box.addView(a.text(phase+(state.optBoolean("running")?"":a.t(" · Paused"," · Szüneteltetve")),16,MainActivity.TEXT));long left=remaining(state,System.currentTimeMillis());
            if(state.optBoolean("running")&&left>0){Chronometer timer=new Chronometer(a);timer.setTextColor(MainActivity.ACCENT);timer.setTextSize(36);timer.setGravity(Gravity.CENTER);timer.setCountDown(true);timer.setBase(SystemClock.elapsedRealtime()+left);timer.setOnChronometerTickListener(v->{if(SystemClock.elapsedRealtime()>=v.getBase()){v.stop();v.setText("0:00");}});box.addView(timer);if(a.hasWindowFocus())timer.start();box.addOnAttachStateChangeListener(new android.view.View.OnAttachStateChangeListener(){public void onViewAttachedToWindow(android.view.View v){timer.start();}public void onViewDetachedFromWindow(android.view.View v){timer.stop();}});}
            else box.addView(a.text(PhoneLocale.timer(left),36,MainActivity.ACCENT));
            if(System.currentTimeMillis()-state.optLong("at")>120000)box.addView(a.text(a.t("Based on the last sync","A legutóbbi szinkron alapján"),13,MainActivity.MUTED));
        }
    }
}
