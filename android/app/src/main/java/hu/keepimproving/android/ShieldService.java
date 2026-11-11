package hu.keepimproving.android;

import android.accessibilityservice.*;
import android.content.*;
import android.graphics.*;
import android.graphics.drawable.GradientDrawable;
import android.os.*;
import android.view.*;
import android.view.accessibility.AccessibilityEvent;
import android.widget.*;
import java.lang.ref.WeakReference;

/** Uses package/window-change events only. Never retrieves window nodes or reads text. */
public final class ShieldService extends AccessibilityService {
    private static WeakReference<ShieldService> current=new WeakReference<>(null);
    private final Handler handler=new Handler(Looper.getMainLooper());private View overlay;private volatile String foreground="",covered="";private String signature="",coverId="";private int serial;
    private final Runnable refresh=this::queue;
    private final BroadcastReceiver screen=new BroadcastReceiver(){@Override public void onReceive(Context c,Intent i){if(Intent.ACTION_SCREEN_OFF.equals(i.getAction())){foreground="";hide();}queue();}};
    static String foregroundPackage(){ShieldService s=current.get();return s==null?"":s.foreground;}
    static String coveredPackage(){ShieldService s=current.get();return s==null?"":s.covered;}
    static boolean connected(){return current.get()!=null;}
    static void refreshSoon(){ShieldService s=current.get();if(s!=null)s.handler.post(s::queue);}
    @Override protected void onServiceConnected(){current=new WeakReference<>(this);IntentFilter filter=new IntentFilter(Intent.ACTION_SCREEN_OFF);filter.addAction(Intent.ACTION_USER_PRESENT);filter.addAction(Intent.ACTION_SCREEN_ON);if(Build.VERSION.SDK_INT>=33)registerReceiver(screen,filter,Context.RECEIVER_NOT_EXPORTED);else registerReceiver(screen,filter);queue();}
    @Override public void onAccessibilityEvent(AccessibilityEvent event) {
        if(event.getEventType()!=AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED||event.getPackageName()==null)return;
        String pkg=event.getPackageName().toString();
        if(pkg.equals(getPackageName())&&overlay!=null)return;
        if(!pkg.equals(foreground)){foreground=pkg;handler.removeCallbacks(refresh);handler.postDelayed(refresh,150);}
    }
    private void queue() {
        final int request=++serial;handler.removeCallbacks(refresh);
        CollectionJob.WORK.execute(()->{try {PhoneRuntime.State state=PhoneRuntime.refresh(this,false);handler.post(()->{if(current.get()!=this||request!=serial)return;apply(state.decision());if(state.next()<Long.MAX_VALUE)handler.postDelayed(refresh,Math.max(500,state.next()-System.currentTimeMillis()));});}catch(RuntimeException e){handler.post(()->{hide();handler.postDelayed(refresh,10000);});}});
    }
    private int dp(int value){return Math.round(value*getResources().getDisplayMetrics().density);}
    private TextView text(Context c,String value,int size,int color){TextView v=new TextView(c);v.setText(value);v.setTextSize(size);v.setTextColor(color);v.setGravity(Gravity.CENTER);v.setPadding(0,dp(12),0,dp(12));return v;}
    private void apply(PhoneRuntime.Decision decision) {
        if(!decision.blocked()||!decision.pkg().equals(foreground)||AppCatalog.safe(this,foreground)||!getSystemService(PowerManager.class).isInteractive()){hide();return;}
        String next=decision.pkg()+":"+decision.focus()+":"+decision.pause()+":"+decision.until()+":"+decision.allowance()+":"+decision.title();if(next.equals(signature)&&overlay!=null)return;
        hide();Context c=new ContextThemeWrapper(PhoneLocale.context(this),R.style.AppTheme);LinearLayout box=new LinearLayout(c);box.setOrientation(LinearLayout.VERTICAL);box.setGravity(Gravity.CENTER);box.setPadding(dp(28),dp(36),dp(28),dp(36));box.setBackgroundColor(Color.rgb(15,23,26));
        ImageView icon=new ImageView(c);icon.setImageResource(R.drawable.ic_launcher);box.addView(icon,new LinearLayout.LayoutParams(dp(64),dp(64)));
        box.addView(text(c,PhoneLocale.text(c,"Keep Improving","Keep Improving"),20,Color.rgb(125,229,191)));
        String title=decision.focus()?PhoneLocale.text(c,"Stay focused","Most a fókuszé az idő"):decision.pause()?PhoneLocale.text(c,"Time for a break","Ideje szünetet tartani"):PhoneLocale.text(c,"Budget reached","Elérted a keretet");
        box.addView(text(c,title,28,Color.WHITE));if(!decision.title().isEmpty())box.addView(text(c,decision.title(),18,Color.LTGRAY));
        if(decision.until()>System.currentTimeMillis()){Chronometer timer=new Chronometer(c);timer.setBase(SystemClock.elapsedRealtime()+decision.until()-System.currentTimeMillis());timer.setCountDown(true);timer.setTextSize(40);timer.setTextColor(Color.rgb(125,229,191));timer.setGravity(Gravity.CENTER);timer.start();box.addView(timer);}
        Button home=new Button(c);home.setText(PhoneLocale.text(c,"Go to home screen","Vissza a kezdőképernyőre"));home.setAllCaps(false);home.setOnClickListener(v->{performGlobalAction(GLOBAL_ACTION_HOME);foreground="";hide();queue();});box.addView(home,new LinearLayout.LayoutParams(-1,dp(56)));
        if(decision.allowance()>0){Button allow=new Button(c);allow.setAllCaps(false);allow.setText(PhoneLocale.text(c,"One-time allowance: ","Egyszeri hosszabbítás: ")+decision.allowance()+PhoneLocale.text(c," min"," perc"));allow.setOnClickListener(v->{allow.setEnabled(false);CollectionJob.WORK.execute(()->{try{PhoneRuntime.allowance(this,decision.pkg());}finally{handler.post(this::queue);}});});box.addView(allow,new LinearLayout.LayoutParams(-1,dp(56)));}
        Button open=new Button(c);open.setAllCaps(false);open.setText(PhoneLocale.text(c,"Open Keep Improving","Keep Improving megnyitása"));open.setOnClickListener(v->{startActivity(new Intent(this,MainActivity.class).putExtra("page",decision.focus()?4:2).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TOP));foreground=getPackageName();hide();queue();});box.addView(open,new LinearLayout.LayoutParams(-1,dp(56)));
        for(int i=0;i<box.getChildCount();i++)if(box.getChildAt(i) instanceof Button b){GradientDrawable background=new GradientDrawable();background.setColor(Color.rgb(32,48,54));background.setCornerRadius(dp(16));background.setStroke(dp(1),Color.rgb(43,62,68));b.setBackground(new android.graphics.drawable.RippleDrawable(android.content.res.ColorStateList.valueOf(Color.argb(50,125,229,191)),background,null));b.setTextColor(Color.rgb(125,229,191));b.setMinHeight(dp(56));b.setPadding(dp(12),dp(10),dp(12),dp(10));LinearLayout.LayoutParams layout=new LinearLayout.LayoutParams(-1,-2);layout.topMargin=dp(6);b.setLayoutParams(layout);}
        WindowManager.LayoutParams params=new WindowManager.LayoutParams(-1,-1,WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,PixelFormat.OPAQUE);
        params.gravity=Gravity.CENTER;params.setTitle("Keep Improving");
        box.setOnKeyListener((v,key,event)->{if(key==android.view.KeyEvent.KEYCODE_BACK){if(event.getAction()==android.view.KeyEvent.ACTION_UP)performGlobalAction(GLOBAL_ACTION_HOME);return true;}return false;});
        ScrollView scroll=new ScrollView(c);scroll.setFillViewport(true);scroll.addView(box);scroll.setBackgroundColor(Color.rgb(15,23,26));
        try{getSystemService(WindowManager.class).addView(scroll,params);overlay=scroll;covered=decision.pkg();signature=next;coverId=PhoneRules.id();String id=coverId,pkg=covered;long start=System.currentTimeMillis();CollectionJob.WORK.execute(()->{try(PhoneStore store=new PhoneStore(this)){store.getWritableDatabase().execSQL("INSERT INTO coverage VALUES (?,?,?,0)",new Object[]{id,pkg,start});}});}catch(RuntimeException ignored){hide();}
    }
    private void hide(){if(!coverId.isEmpty()){String id=coverId;long end=System.currentTimeMillis();coverId="";CollectionJob.WORK.execute(()->{try(PhoneStore store=new PhoneStore(this)){store.getWritableDatabase().execSQL("UPDATE coverage SET finish=? WHERE id=?",new Object[]{end,id});}});}if(overlay!=null){try{getSystemService(WindowManager.class).removeView(overlay);}catch(RuntimeException ignored){}overlay=null;}covered="";signature="";}
    @Override public void onInterrupt(){hide();}
    @Override public void onDestroy(){if(current.get()==this)current.clear();handler.removeCallbacksAndMessages(null);hide();try{unregisterReceiver(screen);}catch(IllegalArgumentException ignored){}super.onDestroy();}
}
