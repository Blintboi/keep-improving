package hu.keepimproving.android;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.content.res.Configuration;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.content.res.ColorStateList;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.text.InputFilter;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.*;
import java.time.LocalDate;
import java.util.*;
import org.json.JSONArray;
import org.json.JSONObject;

public final class MainActivity extends Activity {
    static final int BG=Color.rgb(15,23,26),CARD=Color.rgb(25,35,40),TEXT=Color.rgb(237,244,242),MUTED=Color.rgb(154,175,180),ACCENT=Color.rgb(125,229,191);
    LinearLayout root,content; private TextView status;
    String activityDevice="all",activityQuery="";int activityCategory=0,activityLimit=40;
    String budgetDevice="",reminderDevice="";int budgetLimit=40,reminderLimit=40;
    ScrollView pageScroll;private int renderedPage=-1;private boolean restoringScroll;
    private final Map<Integer,ScrollPosition> scrollPositions=new HashMap<>();
    PhoneRuntime.State state; List<AppCatalog.Item> apps=List.of(); TextView countdown; private boolean visible;
    private final android.os.Handler handler=new android.os.Handler(android.os.Looper.getMainLooper());
    private final Runnable syncVisible=new Runnable(){public void run(){if(!visible)return;if(connected&&!busy&&System.currentTimeMillis()>=syncAfter)load(true,null);handler.postDelayed(this,30000);}};
    private boolean syncPending;
    private final Runnable syncChanges=()->{if(!isDestroyed())load(true,null);};
    void syncChanged(){try(PhoneStore s=new PhoneStore(this)){PhoneSync.dirty(s);SyncJob.soon(this,Math.max(1000,s.number("sync_after",0)-System.currentTimeMillis()));}syncPending=true;handler.removeCallbacks(syncChanges);handler.post(syncChanges);}
    private boolean refreshingLocal;private LocalDate renderedDate=LocalDate.now();
    private final Runnable refreshVisible=new Runnable(){public void run(){if(!visible)return;refreshVisibleStats();handler.postDelayed(this,15000);}};
    private final Runnable tick=new Runnable(){public void run(){if(!visible)return;if(countdown!=null&&state!=null){long left=PhoneFocus.remaining(state.focus(),PhoneRuntime.now(MainActivity.this));countdown.setText(PhoneLocale.timer(left));if(left==0&&state.focus().optBoolean("running"))load(false,null);}handler.postDelayed(this,1000);}};
    private final android.content.BroadcastReceiver changes=new android.content.BroadcastReceiver(){public void onReceive(Context c,Intent i){if(visible)load(false,null);}};
    private int page=0,days=7,deviceIndex=0,categoryIndex=0,rowLimit=50;
    private String rangeStart="",rangeEnd="";
    private boolean chartDevices; PopupWindow navigationMenu;
    private android.window.OnBackInvokedCallback pageBack;
    private boolean busy=false,opened=false,connected=false,tracking=false,gap=false,syncMessage=false;
    private long lastSync=0,syncAfter=0; private String message="",localId="",deviceName="";
    final ArrayList<JSONObject> devices=new ArrayList<>();
    @Override protected void attachBaseContext(Context base) {
        String language=base.getSharedPreferences("ui",0).getString("language",Locale.getDefault().getLanguage().equals("hu")?"hu":"en");
        Configuration config=new Configuration(base.getResources().getConfiguration()); config.setLocale(Locale.forLanguageTag(language));
        super.attachBaseContext(base.createConfigurationContext(config));
    }
    @Override public void onCreate(Bundle saved) { super.onCreate(saved); if(saved!=null) { page=Math.max(0,Math.min(5,saved.getInt("page")));budgetDevice=saved.getString("budgetDevice","");reminderDevice=saved.getString("reminderDevice","");budgetLimit=saved.getInt("budgetLimit",40);reminderLimit=saved.getInt("reminderLimit",40); days=saved.getInt("days",7);rangeStart=saved.getString("rangeStart","");rangeEnd=saved.getString("rangeEnd","");activityDevice=saved.getString("activityDevice","all");activityQuery=saved.getString("activityQuery","");activityCategory=saved.getInt("activityCategory");activityLimit=saved.getInt("activityLimit",40);deviceIndex=saved.getInt("deviceIndex");categoryIndex=saved.getInt("categoryIndex");chartDevices=saved.getBoolean("chartDevices");rowLimit=saved.getInt("rowLimit",50);for(int i=0;i<6;i++){Bundle position=saved.getBundle("scroll:"+i);if(position!=null)scrollPositions.put(i,ScrollPosition.read(position));} }else page=Math.max(0,Math.min(5,getIntent().getIntExtra("page",0))); render(); }
    @Override protected void onSaveInstanceState(Bundle state) { super.onSaveInstanceState(state);rememberScroll();state.putInt("page",page);state.putString("budgetDevice",budgetDevice);state.putString("reminderDevice",reminderDevice);state.putInt("budgetLimit",budgetLimit);state.putInt("reminderLimit",reminderLimit);state.putInt("days",days);state.putString("rangeStart",rangeStart);state.putString("rangeEnd",rangeEnd);state.putString("activityDevice",activityDevice);state.putString("activityQuery",activityQuery);state.putInt("activityCategory",activityCategory);state.putInt("activityLimit",activityLimit);state.putInt("deviceIndex",deviceIndex);state.putInt("categoryIndex",categoryIndex);state.putBoolean("chartDevices",chartDevices);state.putInt("rowLimit",rowLimit);for(var entry:scrollPositions.entrySet())state.putBundle("scroll:"+entry.getKey(),entry.getValue().save()); }
    @Override protected void onResume() { super.onResume();visible=true; boolean sync=!opened; if(!UsbTransfer.receive(this,getIntent()))load(sync,null);opened=true;handler.post(tick);handler.postDelayed(refreshVisible,15000);handler.postDelayed(syncVisible,30000); }
    @Override protected void onPause(){visible=false;handler.removeCallbacks(tick);handler.removeCallbacks(refreshVisible);handler.removeCallbacks(syncVisible);super.onPause();}
    @Override protected void onStart(){super.onStart();registerReceiver(changes,new android.content.IntentFilter(PhoneRuntime.CHANGED),getPackageName()+".INTERNAL",null,android.os.Build.VERSION.SDK_INT>=33?Context.RECEIVER_NOT_EXPORTED:0);}
    @Override protected void onStop(){unregisterReceiver(changes);super.onStop();}
    @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);if(UsbTransfer.receive(this,intent))return;showPage(intent.getIntExtra("page",0));}
    void showPage(int value){page=Math.max(0,Math.min(5,value));rowLimit=50;render();}
    // Legacy button navigation; API 33+ gestures use pageBack below.
    @android.annotation.SuppressLint("GestureBackNavigation")
    @Override public void onBackPressed(){if(!backToOverview())super.onBackPressed();}
    private boolean backToOverview(){
        if(navigationMenu!=null&&navigationMenu.isShowing()){navigationMenu.dismiss();return true;}
        if(page==0)return false;
        showPage(0);return true;
    }
    private void updateBackNavigation(){
        if(android.os.Build.VERSION.SDK_INT<33)return;
        if(page!=0&&pageBack==null){pageBack=this::backToOverview;getOnBackInvokedDispatcher().registerOnBackInvokedCallback(android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT,pageBack);}
        else if(page==0&&pageBack!=null){getOnBackInvokedDispatcher().unregisterOnBackInvokedCallback(pageBack);pageBack=null;}
    }
    @Override protected void onDestroy(){if(android.os.Build.VERSION.SDK_INT>=33&&pageBack!=null){getOnBackInvokedDispatcher().unregisterOnBackInvokedCallback(pageBack);pageBack=null;}super.onDestroy();}
    String t(String en,String hu){return PhoneLocale.text(this,en,hu);}
    String localDeviceName(){return deviceName.isEmpty()?android.os.Build.MODEL:deviceName;}
    int dp(float value) { return Math.round(value*getResources().getDisplayMetrics().density); }
    TextView text(String value,int size,int color) {
        TextView view=new TextView(this); view.setText(value); view.setTextSize(size); view.setTextColor(color); view.setPadding(0,dp(4),0,dp(4)); return view;
    }
    GradientDrawable background(int color) {
        GradientDrawable drawable=new GradientDrawable(); drawable.setColor(color); drawable.setCornerRadius(dp(16)); drawable.setStroke(dp(1),Color.rgb(43,62,68)); return drawable;
    }
    LinearLayout column() { LinearLayout view=new LinearLayout(this); view.setOrientation(LinearLayout.VERTICAL); return view; }
    LinearLayout card() {
        LinearLayout view=column(); view.setPadding(dp(18),dp(14),dp(18),dp(14)); view.setBackground(background(CARD));
        LinearLayout.LayoutParams params=new LinearLayout.LayoutParams(-1,-2); params.bottomMargin=dp(14); content.addView(view,params); return view;
    }
    Button button(String label,Runnable action){Button b=button(R.string.save,action);b.setCompoundDrawablesRelative(null,null,null,null);b.setText(label);String s=label.toLowerCase(Locale.ROOT),kind=label.startsWith("+")?"plus":s.equals("delete")||s.equals("törlés")?"trash":s.startsWith("edit ")||s.contains("szerkesztése")?"edit":s.contains("export")?"export":s.startsWith("start")||s.startsWith("indítás")?"play":s.equals("pause")||s.equals("szüneteltetés")?"pause":s.startsWith("stop")||s.startsWith("leállítás")?"stop":"";if(!kind.isEmpty())icon(b,kind,ACCENT);return b;}
    Button button(int label,Runnable action) {
        Button view=new Button(this); view.setText(label); view.setAllCaps(false); view.setTextColor(ACCENT); view.setMinHeight(dp(48));
        view.setBackground(new RippleDrawable(ColorStateList.valueOf(Color.argb(50,125,229,191)),background(Color.rgb(32,48,54)),null));
        view.setPadding(dp(12),dp(8),dp(12),dp(8));LinearLayout.LayoutParams layout=new LinearLayout.LayoutParams(-1,-2);layout.topMargin=dp(4);layout.bottomMargin=dp(4);view.setLayoutParams(layout);view.setOnClickListener(v->ScrollPosition.change(view,action));String kind=label==R.string.notifications?"bell":label==R.string.settings?"settings":label==R.string.focus?"focus":label==R.string.budgets?"budget":label==R.string.activities?"apps":label==R.string.sync_now||label==R.string.refresh||label==R.string.connect?"sync":label==R.string.grant_access?"shield":"";if(!kind.isEmpty())icon(view,kind,ACCENT); return view;
    }
    void heading(LinearLayout parent,String label) { TextView title=text(label,18,TEXT); title.setTypeface(null,Typeface.BOLD); parent.addView(title); }
    void heading(LinearLayout parent,int label) {heading(parent,getString(label));}
    String duration(double seconds) {
        long value=Math.max(0,(long)seconds);
        return value>=3600?getString(R.string.hours_minutes,value/3600,(value%3600)/60):value>=60?getString(R.string.minutes,value/60):getString(R.string.seconds,value);
    }
    void rememberScroll(){if(pageScroll!=null&&pageScroll.isLaidOut()&&!restoringScroll)scrollPositions.put(renderedPage,ScrollPosition.capture(pageScroll));}
    void render() {
        updateBackNavigation();
        boolean pageChanged=renderedPage!=page;
        rememberScroll();ScrollPosition position=scrollPositions.get(page);renderedPage=page;restoringScroll=true;
        renderedDate=LocalDate.now();
        countdown=null;
        if(root==null){
        root=column(); root.setBackgroundColor(BG);
        root.setOnApplyWindowInsetsListener((view,insets)->{ view.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom()); return insets; });
        setContentView(root);
        LinearLayout header=new LinearLayout(this); header.setGravity(Gravity.CENTER_VERTICAL); header.setPadding(dp(20),dp(16),dp(20),dp(8));
        ImageButton menu=new ImageButton(this);menu.setImageDrawable(new PhoneIcons("menu",ACCENT));menu.setContentDescription(t("Navigation menu","Navigációs menü"));menu.setBackground(background(BG));menu.setPadding(dp(10),dp(10),dp(10),dp(10));menu.setOnClickListener(v->showMenu(menu));header.addView(menu,new LinearLayout.LayoutParams(dp(48),dp(48)));
        TextView brand=text("Keep Improving",20,TEXT); brand.setTypeface(null,Typeface.BOLD);brand.setGravity(Gravity.CENTER_VERTICAL);brand.setIncludeFontPadding(false);brand.setMaxLines(1);brand.setAutoSizeTextTypeUniformWithConfiguration(14,20,1,android.util.TypedValue.COMPLEX_UNIT_SP); brand.setPadding(dp(12),0,0,0); header.addView(brand,new LinearLayout.LayoutParams(0,dp(48),1));ImageView logo=new ImageView(this);logo.setImageResource(R.drawable.ic_launcher);logo.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);header.addView(logo,new LinearLayout.LayoutParams(dp(32),dp(32)));root.addView(header);
        pageScroll=new ScrollView(this);pageScroll.setFocusableInTouchMode(true);pageScroll.setDescendantFocusability(android.view.ViewGroup.FOCUS_BEFORE_DESCENDANTS);root.addView(pageScroll,new LinearLayout.LayoutParams(-1,0,1));
        }
        ScrollView scroll=pageScroll;content=column();content.setPadding(dp(20),dp(8),dp(20),dp(16));scroll.removeAllViews();scroll.addView(content);
        int[] titles={R.string.overview,R.string.activities,R.string.budgets,R.string.notifications,R.string.focus,R.string.settings};
        TextView title=text(getString(titles[page]),28,TEXT);title.setTag("page-title"); title.setTypeface(null,Typeface.BOLD); content.addView(title);
        status=text(busy?getString(R.string.loading):message,14,ACCENT);status.setTag("page-status");status.setVisibility(!busy&&(message.isEmpty()||syncMessage&&page!=5)?View.GONE:View.VISIBLE); status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE); content.addView(status);
        try { if(page==0) {PhoneScreens.overview(this);statistics();} else if(page==1) RemoteScreens.activities(this); else if(page==2) PhoneScreens.budgets(this);else if(page==3)PhoneScreens.reminders(this);else if(page==4)PhoneScreens.focus(this);else {synchronization();settings();RemoteScreens.linkedSettings(this);PhoneScreens.settings(this);PhoneScreens.permissions(this);} }
        catch(Exception e) { content.addView(text(getString(R.string.read_error),15,MUTED)); }
        root.requestApplyInsets();
        if(pageChanged)scroll.requestFocus();
        (position==null?new ScrollPosition(0,-1,0):position).restore(scroll,()->{if(pageScroll==scroll)restoringScroll=false;});
    }
    void showMenu(View anchor){LinearLayout box=column();box.setPadding(dp(12),dp(10),dp(12),dp(10));box.setBackground(background(CARD));ScrollView scroll=new ScrollView(this);scroll.addView(box);navigationMenu=new PopupWindow(scroll,Math.min(dp(320),getResources().getDisplayMetrics().widthPixels-dp(32)),ViewGroup.LayoutParams.WRAP_CONTENT,true);navigationMenu.setBackgroundDrawable(background(CARD));navigationMenu.setOutsideTouchable(true);navigationMenu.setElevation(dp(16));int[] titles={R.string.overview,R.string.activities,R.string.budgets,R.string.notifications,R.string.focus,R.string.settings};String[] icons={"chart","apps","budget","bell","focus","settings"};for(int i=0;i<titles.length;i++){int next=i;Button b=button(titles[i],()->{navigationMenu.dismiss();showPage(next);});b.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);icon(b,icons[i],ACCENT);b.setSelected(page==i);if(page==i)b.setBackground(background(Color.rgb(30,60,51)));box.addView(b);}navigationMenu.showAsDropDown(anchor,0,dp(4));}
    void icon(TextView view,String kind,int color){PhoneIcons icon=new PhoneIcons(kind,color);icon.setBounds(0,0,dp(24),dp(24));view.setCompoundDrawablesRelative(icon,null,null,null);view.setCompoundDrawablePadding(dp(10));}
    void edit(Runnable action){CollectionJob.WORK.execute(()->{try{action.run();PhoneRuntime.refresh(this,false);PhoneRuntime.changed(this);runOnUiThread(()->{load(false,null);syncChanged();});}catch(Exception e){runOnUiThread(()->Toast.makeText(this,t("Could not save changes. Please try again.","Nem sikerült menteni. Próbáld újra."),Toast.LENGTH_LONG).show());}});}
    void export(){startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("text/csv").putExtra(Intent.EXTRA_TITLE,"Keep-Improving-"+LocalDate.now()+".csv"),301);}
    static String csv(String value){if(value.matches("^[=+@\\-\\t\\r].*"))value="'"+value;return "\""+value.replace("\"","\"\"")+"\"";}
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request!=301||result!=RESULT_OK||data==null||data.getData()==null)return;Uri target=data.getData();CollectionJob.WORK.execute(()->{try(PhoneStore store=new PhoneStore(this)){
        PhoneUsage.collect(this,store);String code=Vault.read(this);JSONArray all=store.remotes(code);all.put(store.snapshot(code.isEmpty()?"00000000000000000000000000000000":code));StringBuilder out=new StringBuilder("\ufeffdate,device,category,name,activity,seconds\r\n");
        for(int i=0;i<all.length();i++){JSONObject device=all.getJSONObject(i);for(var row:Statistics.rows(device,"all"))out.append(csv(row.day())).append(',').append(csv(device.optString("name"))).append(',').append(csv(row.kind())).append(',').append(csv(row.name())).append(',').append(csv(row.key())).append(',').append(row.seconds()).append("\r\n");}
        try(var stream=getContentResolver().openOutputStream(target,"wt")){if(stream==null)throw new java.io.IOException();stream.write(out.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));}runOnUiThread(()->Toast.makeText(this,t("Statistics exported.","Statisztikák exportálva."),Toast.LENGTH_LONG).show());
    }catch(Exception e){runOnUiThread(()->Toast.makeText(this,t("Could not export this file.","Nem sikerült exportálni a fájlt."),Toast.LENGTH_LONG).show());}});}
    private String since(){return rangeStart.isEmpty()?LocalDate.now().minusDays(days-1).toString():rangeStart;}
    private String until(){return rangeEnd.isEmpty()?LocalDate.now().toString():rangeEnd;}
    private void dateRange(){LocalDate now=LocalDate.now();new android.app.DatePickerDialog(this,(picker,y,m,d)->{LocalDate start=LocalDate.of(y,m+1,d);new android.app.DatePickerDialog(this,(p,ey,em,ed)->{LocalDate end=LocalDate.of(ey,em+1,ed);if(end.isBefore(start)||java.time.temporal.ChronoUnit.DAYS.between(start,end)>365){Toast.makeText(this,t("Choose an ordered range of at most 366 days.","Legfeljebb 366 napos, helyes sorrendű időszakot válassz."),Toast.LENGTH_LONG).show();return;}rangeStart=start.toString();rangeEnd=end.toString();render();},now.getYear(),now.getMonthValue()-1,now.getDayOfMonth()).show();},now.getYear(),now.getMonthValue()-1,now.getDayOfMonth()).show();}
    private void permissionCard() {
        if(tracking&&PhoneUsage.allowed(this)) return;
        LinearLayout card=card();card.setTag("usage-permission"); heading(card,R.string.permission_title); card.addView(text(getString(R.string.permission_detail),14,MUTED)); card.addView(button(R.string.grant_access,this::grant));
    }
    private void grant() {
        edit(()->{try(PhoneStore store=new PhoneStore(this)) { if(!store.get("enabled","false").equals("true")) { store.put("enabled","true"); store.resetCursor(System.currentTimeMillis()); } }});
        if(PhoneUsage.allowed(this)) return;
        try { startActivity(new Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS,Uri.parse("package:"+getPackageName()))); }
        catch(android.content.ActivityNotFoundException e) { startActivity(new Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS)); }
    }
    private List<Statistics.Row> selected(boolean phoneOnly) throws Exception {
        String[] categories={"all","games","apps","websites"}; List<Statistics.Row> rows=new ArrayList<>();
        String since=since(),until=until();
        for(int i=0;i<devices.size();i++) {
            if(phoneOnly&&i!=0||!phoneOnly&&deviceIndex>0&&i!=deviceIndex-1) continue;
            for(var row:Statistics.rows(devices.get(i),categories[categoryIndex])) if(row.day().compareTo(since)>=0&&row.day().compareTo(until)<=0) rows.add(row);
        }
        return rows;
    }
    Spinner spinner(String[] labels,int current,java.util.function.IntConsumer select) {
        Spinner spinner=new Spinner(this); ArrayAdapter<String> adapter=new ArrayAdapter<>(this,android.R.layout.simple_spinner_item,labels); adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item); spinner.setAdapter(adapter); spinner.setSelection(current);
        spinner.setMinimumHeight(dp(48)); spinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            int last=current;
            public void onItemSelected(AdapterView<?> parent,View view,int position,long id) { if(position!=last) {last=position;ScrollPosition.change(spinner,()->select.accept(position));} }
            public void onNothingSelected(AdapterView<?> parent) {}
        }); return spinner;
    }
    private void filters(boolean phoneOnly) throws Exception {
        LinearLayout box=card();box.setTag("statistics-filters");
        if(!phoneOnly) {
            String[] names=new String[devices.size()+1]; names[0]=getString(R.string.all_devices);
            for(int i=0;i<devices.size();i++) names[i+1]=devices.get(i).getString("name")+(i==0?" · "+getString(R.string.this_phone):"");
            deviceIndex=Math.min(deviceIndex,names.length-1); box.addView(spinner(names,deviceIndex,i->{deviceIndex=i;render();}));
        }
        box.addView(spinner(new String[]{getString(R.string.today),getString(R.string.week),getString(R.string.month),t("Custom range","Egyéni időszak")},!rangeStart.isEmpty()?3:days==1?0:days==7?1:2,i->{if(i==3){dateRange();return;}rangeStart="";rangeEnd="";days=new int[]{1,7,30}[i];render();}));
        if(!rangeStart.isEmpty())box.addView(button(rangeStart+" – "+rangeEnd,this::dateRange));
        String[] categories={getString(R.string.everything),getString(R.string.games),getString(R.string.apps),getString(R.string.websites)};
        if(phoneOnly)box.addView(spinner(categories,categoryIndex,i->{categoryIndex=i;render();}));
        else {
            String[] choices=new String[8];for(int i=0;i<8;i++)choices[i]=categories[i%4]+" · "+(i<4?t("Time","Idő"):t("Sessions","Munkamenetek"));
            box.addView(text(t("Show activity","Mit szeretnél látni?"),13,MUTED));
            Spinner measure=spinner(choices,categoryIndex+(chartSessions()?4:0),i->{categoryIndex=i%4;getSharedPreferences("ui",0).edit().putBoolean("statistics_chart_sessions",i>=4).apply();render();});
            measure.setTag("statistics-measure");measure.setContentDescription(t("Show activity","Mit szeretnél látni?"));box.addView(measure);
        }
    }
    private void statistics() throws Exception {
        permissionCard();
        double today=0; if(!devices.isEmpty()) for(var row:Statistics.rows(devices.get(0),"all")) if(row.day().equals(LocalDate.now().toString())) today+=row.seconds();
        LinearLayout total=card();total.setTag("statistics-today"); total.addView(text(getString(R.string.phone_today),14,MUTED)); TextView value=text(duration(today),36,ACCENT);value.setTag("phone-today"); value.setTypeface(null,Typeface.BOLD); total.addView(value);
        total.addView(text(t("App use · updates every 15 seconds","Alkalmazáshasználat · 15 mp-enként frissül"),13,MUTED));
        filters(false); List<Statistics.Row> rows=selected(false); chart(rows);
        LinearLayout sync=card();sync.setTag("statistics-devices"); heading(sync,t("Time by device","Idő eszközönként"));
        for(int i=0;i<devices.size();i++) {
            JSONObject device=devices.get(i); double seconds=0;
            String since=since(),until=until();
            for(var row:Statistics.rows(device,new String[]{"all","games","apps","websites"}[categoryIndex])) if(row.day().compareTo(since)>=0&&row.day().compareTo(until)<=0) seconds+=row.seconds();
            int color=SeriesColors.get(this,"computer",device.optString("device"));TextView deviceLabel=text(device.getString("name")+"\n"+duration(seconds),15,color);icon(deviceLabel,i==0?"phone":"computer",color);sync.addView(deviceLabel);
        }
        ranking(rows);
    }
    private boolean chartSessions(){return getSharedPreferences("ui",0).getBoolean("statistics_chart_sessions",false);}
    private double chartValue(Statistics.Row row){return chartSessions()?row.sessions():row.seconds();}
    private void chart(List<Statistics.Row> rows) {
        LinearLayout box=card();box.setTag("statistics-chart"); heading(box,chartSessions()?t("Sessions by day","Munkamenetek naponta"):getString(R.string.time_chart));box.addView(spinner(new String[]{t("Colors by activity","Színek tevékenységenként"),t("Colors by device","Színek eszközönként")},chartDevices?1:0,i->{chartDevices=i==1;render();}));
        Map<String,Double> totals=new HashMap<>();Map<String,String> names=new HashMap<>(),kinds=new HashMap<>();for(var row:rows){String key=chartDevices?row.device():SeriesColors.identity("game",row.kind()+":"+row.key());totals.merge(key,chartValue(row),Double::sum);names.put(key,row.name().isEmpty()?getString(R.string.other_browser):row.name());kinds.put(key,row.kind());}if(chartDevices)for(JSONObject device:devices){names.put(device.optString("device"),device.optString("name"));kinds.put(device.optString("device"),device.optString("device").equals(localId)?"phone":"computer");}
        List<String> order=new ArrayList<>(totals.keySet());order.sort((x,y)->{int value=Double.compare(totals.get(y),totals.get(x));return value!=0?value:x.compareTo(y);});Set<String> selected=new HashSet<>(order.subList(0,Math.min(6,order.size())));LinkedHashMap<String,Integer> colors=new LinkedHashMap<>();for(String key:order.subList(0,Math.min(6,order.size())))colors.put(key,SeriesColors.get(this,chartDevices?"computer":"game",key));if(order.size()>6){colors.put("other",Color.rgb(107,132,144));names.put("other",t("Other","Egyéb"));kinds.put("other","apps");}
        TreeMap<String,Map<String,Double>> values=new TreeMap<>();for(LocalDate date=LocalDate.parse(since());!date.isAfter(LocalDate.parse(until()));date=date.plusDays(1))values.put(date.toString(),new HashMap<>());Map<String,Double> visibleTotals=new HashMap<>();for(var row:rows){String key=chartDevices?row.device():SeriesColors.identity("game",row.kind()+":"+row.key());if(!selected.contains(key))key="other";values.get(row.day()).merge(key,chartValue(row),Double::sum);visibleTotals.merge(key,chartValue(row),Double::sum);}
        Map<String,SessionCounts.Total> dailyCounts=new HashMap<>(),legendCounts=new HashMap<>();Map<String,Map<String,SessionCounts.Total>> segmentCounts=new HashMap<>();
        for(var row:rows){String key=chartDevices?row.device():SeriesColors.identity("game",row.kind()+":"+row.key());if(!selected.contains(key))key="other";
            dailyCounts.computeIfAbsent(row.day(),k->new SessionCounts.Total()).add(row,row.day());
            segmentCounts.computeIfAbsent(row.day(),k->new HashMap<>()).computeIfAbsent(key,k->new SessionCounts.Total()).add(row,row.day());
            legendCounts.computeIfAbsent(key,k->new SessionCounts.Total()).add(row,since());}
        box.addView(new Chart(this,values,colors,dailyCounts,segmentCounts),new LinearLayout.LayoutParams(-1,dp(220)));
        box.addView(text(chartSessions()?t("Column height shows sessions, counted on their starting day.","Az oszlopmagasság a kezdőnapjukon számolt munkamenetek számát mutatja."):t("Column height shows recorded time.","Az oszlopmagasság a mért időt mutatja."),13,MUTED));
        for(var entry:colors.entrySet()){String amount=chartSessions()?legendCounts.getOrDefault(entry.getKey(),new SessionCounts.Total()).text()+t(" sessions"," munkamenet"):duration(visibleTotals.getOrDefault(entry.getKey(),0.0));TextView label=text(names.get(entry.getKey())+" · "+amount,13,entry.getValue());icon(label,kinds.getOrDefault(entry.getKey(),"apps"),entry.getValue());box.addView(label);}
    }
    private void activities() throws Exception { permissionCard(); filters(true); ranking(selected(true)); content.addView(button(R.string.refresh,()->load(false,null))); }
    private void ranking(List<Statistics.Row> rows) {
        LinearLayout box=card();box.setTag("statistics-ranking"); heading(box,t("Activities","Tevékenységek"));
        Map<String,Double> totals=new HashMap<>(); Map<String,Statistics.Row> info=new HashMap<>();
        Map<String,Long> sessions=new HashMap<>();Map<String,Boolean> partial=new HashMap<>();long totalSessions=0;boolean incomplete=false;String start=since();
        for(var row:rows) { String key=SeriesColors.identity("game",row.kind()+":"+row.key()); totals.merge(key,row.seconds(),Double::sum); info.put(key,row);sessions.merge(key,row.sessions(),Long::sum);boolean missing=SessionCounts.partial(row,start);partial.merge(key,missing,(a,b)->a||b);totalSessions+=row.sessions();incomplete|=missing; }
        TextView sessionTotal=text(t("Total sessions","Összes munkamenet")+": "+SessionCounts.display(totalSessions,incomplete),20,ACCENT);sessionTotal.setTag("total-sessions");box.addView(sessionTotal);
        PhoneScreens.details(this,box,t("How are sessions counted?","Hogyan számoljuk a munkameneteket?"),"A session is continuous foreground use, counted on its starting day.","Egy munkamenet összefüggő előtérbeli használat, a kezdőnapján számolva.");
        int order=Math.max(0,Math.min(3,getSharedPreferences("ui",0).getInt("statistics_sort",0)));
        Spinner sort=spinner(new String[]{t("Time: most first","Idő: csökkenő"),t("Time: least first","Idő: növekvő"),t("Sessions: most first","Munkamenetek: csökkenő"),t("Sessions: least first","Munkamenetek: növekvő")},order,i->{getSharedPreferences("ui",0).edit().putInt("statistics_sort",i).apply();render();});sort.setTag("statistics-sort");sort.setContentDescription(t("Sort by","Rendezés"));box.addView(sort);
        if(totals.isEmpty()) { box.addView(text(getString(R.string.empty),14,MUTED)); return; }
        ArrayList<String> keys=new ArrayList<>(totals.keySet()); keys.sort((a,b)->{int result=(order%2==0?-1:1)*(order>=2?Long.compare(sessions.get(a),sessions.get(b)):Double.compare(totals.get(a),totals.get(b)));if(result==0)result=info.get(a).name().compareToIgnoreCase(info.get(b).name());return result==0?a.compareTo(b):result;});
        for(String key:keys.subList(0,Math.min(rowLimit,keys.size()))) {
            var row=info.get(key); LinearLayout line=new LinearLayout(this); line.setGravity(Gravity.CENTER_VERTICAL); line.setPadding(0,dp(8),0,dp(8));
            ImageView icon=new ImageView(this); icon.setImageDrawable(RemoteIcons.row(this,row));
            icon.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO); line.addView(icon,new LinearLayout.LayoutParams(dp(36),dp(36)));
            TextView label=text(row.name().isEmpty()?getString(R.string.other_browser):row.name(),15,TEXT); label.setPadding(dp(12),0,dp(8),0); line.addView(label,new LinearLayout.LayoutParams(0,-2,1));TextView amount=text(duration(totals.get(key))+"\n"+SessionCounts.display(sessions.get(key),partial.get(key))+t(" sessions"," munkamenet"),14,SeriesColors.get(this,"game",key));amount.setGravity(Gravity.END);line.addView(amount); box.addView(line);
        }
        if(keys.size()>rowLimit)box.addView(button(R.string.show_more,()->{rowLimit+=50;render();}));
    }
    private void synchronization() {
        LinearLayout sync=card();sync.setTag("synchronization");heading(sync,R.string.devices_sync);
        sync.addView(text(lastSync==0?getString(R.string.never_synced):getString(R.string.last_sync,java.text.DateFormat.getDateTimeInstance(java.text.DateFormat.SHORT,java.text.DateFormat.SHORT,getResources().getConfiguration().getLocales().get(0)).format(new Date(lastSync))),13,MUTED));
        Button connect=button(connected?R.string.sync_now:R.string.connect,()->{if(connected) syncChanged();else connectDialog();}); connect.setEnabled(!busy); sync.addView(connect);
        if(connected) { sync.addView(button(R.string.disconnect,this::disconnect)); }
        else sync.addView(text(getString(R.string.sync_explainer),13,MUTED));
        sync.addView(button(t("Device groups…","Eszközcsoportok…"),()->PhoneScopeEditor.groups(this,this::render)));
        PhoneScreens.details(this,sync,t("Details","Részletek"),"Changes appear after both devices sync. Sync can be delayed; local measurement continues. Keep Improving must be running on the PC to receive changes.","A módosítások mindkét eszköz szinkronizálása után jelennek meg. A szinkron késhet, a helyi mérés közben folytatódik. Az átvételhez a PC-n futnia kell a Keep Improvingnak.");
    }
    private void settings() {
        LinearLayout measurement=card(); Switch enabled=new Switch(this); enabled.setText(R.string.tracking); enabled.setTextColor(TEXT); enabled.setMinHeight(dp(48)); enabled.setChecked(tracking);
        enabled.setOnCheckedChangeListener((button,on)->{ if(on) grant(); else edit(()->{try(PhoneStore store=new PhoneStore(this)) {PhoneUsage.collect(this,store);store.put("enabled","false");store.resetCursor(System.currentTimeMillis());} CollectionJob.schedule(this);}); });
        measurement.addView(enabled);
        PhoneScreens.details(this,measurement,t("What is measured?","Mit mérünk?"),"Time spent using apps. Keep Improving, the home screen and system screens are excluded. Browsers count as apps; website details come from linked computers.","Az alkalmazások használati idejét. A Keep Improving, a kezdőképernyő és a rendszerfelületek kimaradnak. A böngészők alkalmazásként számítanak; webhelyenkénti adatok a kapcsolt PC-kről érkeznek.");
        if(tracking&&!PhoneUsage.allowed(this)) {measurement.addView(text(getString(R.string.access_missing),14,MUTED));measurement.addView(button(R.string.grant_access,this::grant));}
        LinearLayout name=card(); heading(name,R.string.device_name); name.addView(text(deviceName,16,TEXT)); name.addView(button(R.string.device_name,this::nameDialog));
        LinearLayout language=card(); heading(language,R.string.language); boolean hu=getResources().getConfiguration().getLocales().get(0).getLanguage().equals("hu");
        language.addView(spinner(new String[]{"Magyar","English"},hu?0:1,i->{getSharedPreferences("ui",0).edit().putString("language",i==0?"hu":"en").apply();recreate();}));
        if(gap) content.addView(text(getString(R.string.history_gap),14,MUTED));
    }
    private void nameDialog() {
        EditText input=new EditText(this); input.setText(deviceName); input.setSingleLine(true); input.setFilters(new InputFilter[]{new InputFilter.LengthFilter(80)});
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle(R.string.device_name).setView(input).setNegativeButton(R.string.cancel,null).setPositiveButton(R.string.save,null).create();
        dialog.setOnShowListener(d->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{ String name=input.getText().toString().trim(); if(name.isEmpty()) return; try(PhoneStore store=new PhoneStore(this)){store.put("name",name);} dialog.dismiss();load(false,null); })); dialog.show();
    }
    private void connectDialog() {
        LinearLayout box=column();box.setPadding(dp(20),0,dp(20),0);box.addView(text(getString(R.string.code_help),15,MUTED));
        EditText input=new EditText(this);input.setHint(R.string.connection_code);input.setSingleLine(true);input.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);input.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);input.setFilters(new InputFilter[]{new InputFilter.LengthFilter(48)});box.addView(input);
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle(R.string.connect).setView(box).setNegativeButton(R.string.cancel,null).setPositiveButton(R.string.connect_action,null).create();
        dialog.setOnShowListener(d->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{try {String code=SyncCrypto.normalize(input.getText().toString());dialog.dismiss();load(true,code);}catch(IllegalArgumentException e){input.setError(getString(R.string.invalid_code));}}));dialog.show();
    }
    private void disconnect() {
        new AlertDialog.Builder(this).setTitle(R.string.disconnect).setMessage(R.string.disconnect_detail).setNegativeButton(R.string.cancel,null).setPositiveButton(R.string.disconnect,(d,w)->{
            if(busy)return; CollectionJob.WORK.execute(()->{ try(PhoneStore store=new PhoneStore(this)){Vault.clear(this);PhoneCompanion.clear(store);store.put("last_sync","0");}catch(RuntimeException e){runOnUiThread(()->{message=getString(R.string.read_error);render();});return;}runOnUiThread(()->{deviceIndex=0;load(false,null);}); });
        }).show();
    }
    void refreshVisibleStats(){
        if(!visible||busy||refreshingLocal||devices.isEmpty()||page!=0&&page!=1&&page!=2)return;
        refreshingLocal=true;
        CollectionJob.WORK.execute(()->{
            JSONObject snapshot=null;PhoneRuntime.State latest=null;
            try(PhoneStore store=new PhoneStore(this)){
                latest=PhoneRuntime.refresh(this,false);String code=Vault.read(this);
                snapshot=store.snapshot(code.isEmpty()?"00000000000000000000000000000000":code);
            }catch(Exception ignored){/* Keep the last good view; later visible events retry. */}
            final JSONObject fresh=snapshot;final PhoneRuntime.State runtime=latest;
            runOnUiThread(()->{refreshingLocal=false;if(!visible||isDestroyed()||busy||fresh==null||devices.isEmpty())return;
                JSONObject before=devices.get(0);boolean changed=!Objects.toString(before.optJSONArray("activity")).equals(Objects.toString(fresh.optJSONArray("activity")))||!Objects.toString(before.optJSONArray("rows")).equals(Objects.toString(fresh.optJSONArray("rows")))||state==null||state.rounds()!=runtime.rounds()||!renderedDate.equals(LocalDate.now());
                devices.set(0,fresh);state=runtime;if(changed&&(page==0||page==1||page==2))render();
            });
        });
    }
    void load(boolean sync,String newCode) {
        if(busy){if(sync){syncPending=true;handler.removeCallbacks(syncChanges);handler.postDelayed(syncChanges,500);}return;}if(sync)syncPending=false;busy=true; message="";
        // Keep the current screen usable while a background refresh is pending.
        if(devices.isEmpty()||page==5)render();
        final boolean startup=!opened;CollectionJob.LOAD.execute(()->{
            ArrayList<JSONObject> loaded=new ArrayList<>();String result="",id="",name="";boolean paired=false,enabled=false,missing=false,syncNotice=false;long last=0,after=0;
            PhoneRuntime.State runtime=null;List<AppCatalog.Item> catalog=List.of();
            try(PhoneStore store=new PhoneStore(this)) {
                runtime=CollectionJob.WORK.submit(()->PhoneRuntime.refresh(this,startup)).get();CollectionJob.schedule(this);
                if(newCode!=null&&!newCode.equals(Vault.read(this))) {PhoneCompanion.clear(store);store.put("last_sync","0");Vault.write(this,newCode);}
                String code=Vault.read(this); paired=!code.isEmpty();SyncJob.schedule(this);
                if(sync) {
                    PhoneSync.Result outcome=PhoneSync.run(this,store);
                    int resource=switch(outcome){case DONE->R.string.synced;case UNAVAILABLE->R.string.sync_unavailable;case INVALID_CODE->R.string.sync_code_error;case LIMIT->R.string.sync_limit;case INVALID_DATA->R.string.sync_invalid;default->0;};
                    if(resource!=0) result=getString(resource);syncNotice=resource!=0||outcome==PhoneSync.Result.WAIT;
                    if(outcome==PhoneSync.Result.WAIT) {syncPending=true;long seconds=Math.max(1,(store.number("sync_after",0)-System.currentTimeMillis()+999)/1000);result=t("Next sync in ","Következő szinkron: ")+duration(seconds)+t(""," múlva");}
                }
                if(sync)runtime=CollectionJob.WORK.submit(()->PhoneRuntime.refresh(this,false)).get();catalog=AppCatalog.list(this,store);
                loaded.add(store.snapshot(code.isEmpty()?"00000000000000000000000000000000":code)); JSONArray remote=store.remotes(code);
                for(int i=0;i<remote.length();i++)loaded.add(remote.getJSONObject(i));
                id=store.device();name=store.name();enabled=store.get("enabled","false").equals("true");missing=store.get("history_gap","false").equals("true");last=store.number("last_sync",0);after=store.number("sync_after",0);
            } catch(Exception e) {result=getString(R.string.read_error);syncNotice=false;}
            final String text=result,identity=id,label=name;final boolean isConnected=paired,isEnabled=enabled,hasGap=missing,isSyncNotice=syncNotice;final long syncTime=last,next=after;
            final PhoneRuntime.State loadedState=runtime;final List<AppCatalog.Item> loadedApps=catalog;
            runOnUiThread(()->{if(isDestroyed())return;state=loadedState;apps=loadedApps;devices.clear();devices.addAll(loaded);localId=identity;deviceName=label;connected=isConnected;tracking=isEnabled;gap=hasGap;lastSync=syncTime;syncAfter=next;message=text;syncMessage=isSyncNotice;busy=false;render();if(syncPending){handler.removeCallbacks(syncChanges);handler.postDelayed(syncChanges,Math.max(1,syncAfter-System.currentTimeMillis()));}});
        });
    }
    private final class Chart extends View {
        private final TreeMap<String,Map<String,Double>> values;private final LinkedHashMap<String,Integer> colors;private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Map<String,SessionCounts.Total> dailyCounts;private final Map<String,Map<String,SessionCounts.Total>> segmentCounts;
        private final boolean sessions=chartSessions();
        Chart(Context context,TreeMap<String,Map<String,Double>> values,LinkedHashMap<String,Integer> colors,Map<String,SessionCounts.Total> dailyCounts,Map<String,Map<String,SessionCounts.Total>> segmentCounts){
            super(context);this.values=values;this.colors=colors;this.dailyCounts=dailyCounts;this.segmentCounts=segmentCounts;
            StringBuilder description=new StringBuilder(sessions?t("Sessions by day","Munkamenetek naponta"):getString(R.string.time_chart));
            for(var entry:values.entrySet()){description.append(". ").append(entry.getKey()).append(": ");if(!sessions)description.append(duration(entry.getValue().values().stream().mapToDouble(Double::doubleValue).sum())).append(" · ");description.append(t("Sessions","Munkamenetek")).append(": ").append(dailyCounts.getOrDefault(entry.getKey(),new SessionCounts.Total()).text());}
            setContentDescription(description);setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_YES);
        }
        @Override protected void onDraw(Canvas canvas){
            super.onDraw(canvas);double max=1;for(var day:values.values())max=Math.max(max,day.values().stream().mapToDouble(Double::doubleValue).sum());
            float width=getWidth()/(float)values.size(),bottom=getHeight()-dp(28),top=dp(30);int i=0;paint.setTextSize(dp(10));paint.setTextAlign(Paint.Align.CENTER);
            for(var entry:values.entrySet()){
                float x=width*i+width/2,y=bottom;double total=0;
                for(var series:colors.entrySet()){
                    double value=entry.getValue().getOrDefault(series.getKey(),0.0);total+=value;float bar=(float)(value/max)*(bottom-top);paint.setColor(series.getValue());canvas.drawRect(x-width*.30f,y-bar,x+width*.30f,y,paint);
                    var count=segmentCounts.getOrDefault(entry.getKey(),Map.of()).get(series.getKey());if(sessions&&count!=null&&bar>=dp(20)&&paint.measureText(count.text())+dp(4)<width*.6f){paint.setColor(BG);canvas.drawText(count.text(),x,y-bar/2+dp(3),paint);}y-=bar;
                }
                paint.setColor(MUTED);if(values.size()<=7||i==0||i==values.size()-1)canvas.drawText(entry.getKey().substring(5),x,bottom+dp(20),paint);
                if(values.size()<=7&&(sessions||total>0)){paint.setColor(TEXT);canvas.drawText(sessions?dailyCounts.getOrDefault(entry.getKey(),new SessionCounts.Total()).text():duration(total),x,y-dp(6),paint);}i++;
            }
        }
    }
}
