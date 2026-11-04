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
import android.widget.*;
import java.time.LocalDate;
import java.util.*;
import org.json.JSONArray;
import org.json.JSONObject;

public final class MainActivity extends Activity {
    private static final int BG=Color.rgb(15,23,26),CARD=Color.rgb(25,35,40),TEXT=Color.rgb(237,244,242),MUTED=Color.rgb(154,175,180),ACCENT=Color.rgb(125,229,191);
    private LinearLayout root,content; private TextView status;
    private int page=0,days=7,deviceIndex=0,categoryIndex=0,rowLimit=50;
    private boolean busy=false,opened=false,connected=false,tracking=false,gap=false;
    private long lastSync=0,syncAfter=0; private String message="",localId="",deviceName="";
    private final ArrayList<JSONObject> devices=new ArrayList<>();
    @Override protected void attachBaseContext(Context base) {
        String language=base.getSharedPreferences("ui",0).getString("language",Locale.getDefault().getLanguage().equals("hu")?"hu":"en");
        Configuration config=new Configuration(base.getResources().getConfiguration()); config.setLocale(Locale.forLanguageTag(language));
        super.attachBaseContext(base.createConfigurationContext(config));
    }
    @Override public void onCreate(Bundle state) { super.onCreate(state); if(state!=null) { page=state.getInt("page"); days=state.getInt("days",7); } render(); }
    @Override protected void onSaveInstanceState(Bundle state) { super.onSaveInstanceState(state); state.putInt("page",page); state.putInt("days",days); }
    @Override protected void onResume() { super.onResume(); boolean sync=!opened; opened=true; load(sync,null); }
    private int dp(float value) { return Math.round(value*getResources().getDisplayMetrics().density); }
    private TextView text(String value,int size,int color) {
        TextView view=new TextView(this); view.setText(value); view.setTextSize(size); view.setTextColor(color); view.setPadding(0,dp(4),0,dp(4)); return view;
    }
    private GradientDrawable background(int color) {
        GradientDrawable drawable=new GradientDrawable(); drawable.setColor(color); drawable.setCornerRadius(dp(16)); drawable.setStroke(dp(1),Color.rgb(43,62,68)); return drawable;
    }
    private LinearLayout column() { LinearLayout view=new LinearLayout(this); view.setOrientation(LinearLayout.VERTICAL); return view; }
    private LinearLayout card() {
        LinearLayout view=column(); view.setPadding(dp(18),dp(14),dp(18),dp(14)); view.setBackground(background(CARD));
        LinearLayout.LayoutParams params=new LinearLayout.LayoutParams(-1,-2); params.bottomMargin=dp(14); content.addView(view,params); return view;
    }
    private Button button(int label,Runnable action) {
        Button view=new Button(this); view.setText(label); view.setAllCaps(false); view.setTextColor(ACCENT); view.setMinHeight(dp(48));
        view.setBackground(new RippleDrawable(ColorStateList.valueOf(Color.argb(50,125,229,191)),background(Color.rgb(32,48,54)),null));
        view.setPadding(dp(12),dp(8),dp(12),dp(8)); view.setOnClickListener(v->action.run()); return view;
    }
    private void heading(LinearLayout parent,int label) { TextView title=text(getString(label),18,TEXT); title.setTypeface(null,Typeface.BOLD); parent.addView(title); }
    private String duration(double seconds) {
        long value=Math.max(0,(long)seconds);
        return value>=3600?getString(R.string.hours_minutes,value/3600,(value%3600)/60):value>=60?getString(R.string.minutes,value/60):getString(R.string.seconds,value);
    }
    private void render() {
        root=column(); root.setBackgroundColor(BG);
        root.setOnApplyWindowInsetsListener((view,insets)->{ view.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom()); return insets; });
        setContentView(root);
        LinearLayout header=new LinearLayout(this); header.setGravity(Gravity.CENTER_VERTICAL); header.setPadding(dp(20),dp(16),dp(20),dp(8));
        ImageView logo=new ImageView(this); logo.setImageResource(R.drawable.ic_launcher); logo.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO); header.addView(logo,new LinearLayout.LayoutParams(dp(34),dp(34)));
        TextView brand=text("Keep Improving",20,TEXT); brand.setTypeface(null,Typeface.BOLD); brand.setPadding(dp(12),0,0,0); header.addView(brand); root.addView(header);
        ScrollView scroll=new ScrollView(this); content=column(); content.setPadding(dp(20),dp(8),dp(20),dp(16)); scroll.addView(content); root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        int[] titles={R.string.statistics,R.string.activities,R.string.settings};
        TextView title=text(getString(titles[page]),28,TEXT); title.setTypeface(null,Typeface.BOLD); content.addView(title);
        status=text(busy?getString(R.string.loading):message,14,ACCENT); status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE); content.addView(status);
        try { if(page==0) statistics(); else if(page==1) activities(); else settings(); }
        catch(Exception e) { content.addView(text(getString(R.string.read_error),15,MUTED)); }
        LinearLayout nav=new LinearLayout(this); nav.setBackgroundColor(Color.rgb(11,18,21)); nav.setPadding(dp(6),dp(5),dp(6),dp(5));
        for(int i=0;i<titles.length;i++) { final int next=i; Button item=button(titles[i],()->{page=next;rowLimit=50;render();}); item.setTextSize(12); item.setBackground(background(i==page?Color.rgb(30,60,51):Color.rgb(11,18,21))); nav.addView(item,new LinearLayout.LayoutParams(0,dp(56),1)); }
        root.addView(nav); root.requestApplyInsets();
    }
    private void permissionCard() {
        if(tracking&&PhoneUsage.allowed(this)) return;
        LinearLayout card=card(); heading(card,R.string.permission_title); card.addView(text(getString(R.string.permission_detail),14,MUTED)); card.addView(button(R.string.grant_access,this::grant));
    }
    private void grant() {
        try(PhoneStore store=new PhoneStore(this)) { if(!store.get("enabled","false").equals("true")) { store.put("enabled","true"); store.resetCursor(System.currentTimeMillis()); } }
        if(PhoneUsage.allowed(this)) { load(false,null); return; }
        try { startActivity(new Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS,Uri.parse("package:"+getPackageName()))); }
        catch(android.content.ActivityNotFoundException e) { startActivity(new Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS)); }
    }
    private List<Statistics.Row> selected(boolean phoneOnly) throws Exception {
        String[] categories={"all","games","apps","websites"}; List<Statistics.Row> rows=new ArrayList<>();
        String since=LocalDate.now().minusDays(days-1).toString(),until=LocalDate.now().toString();
        for(int i=0;i<devices.size();i++) {
            if(phoneOnly&&i!=0||!phoneOnly&&deviceIndex>0&&i!=deviceIndex-1) continue;
            for(var row:Statistics.rows(devices.get(i),categories[categoryIndex])) if(row.day().compareTo(since)>=0&&row.day().compareTo(until)<=0) rows.add(row);
        }
        return rows;
    }
    private Spinner spinner(String[] labels,int current,java.util.function.IntConsumer select) {
        Spinner spinner=new Spinner(this); ArrayAdapter<String> adapter=new ArrayAdapter<>(this,android.R.layout.simple_spinner_item,labels); adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item); spinner.setAdapter(adapter); spinner.setSelection(current);
        spinner.setMinimumHeight(dp(48)); spinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            int last=current;
            public void onItemSelected(AdapterView<?> parent,View view,int position,long id) { if(position!=last) {last=position;select.accept(position);} }
            public void onNothingSelected(AdapterView<?> parent) {}
        }); return spinner;
    }
    private void filters(boolean phoneOnly) throws Exception {
        LinearLayout box=card();
        if(!phoneOnly) {
            String[] names=new String[devices.size()+1]; names[0]=getString(R.string.all_devices);
            for(int i=0;i<devices.size();i++) names[i+1]=devices.get(i).getString("name")+(i==0?" · "+getString(R.string.this_phone):"");
            deviceIndex=Math.min(deviceIndex,names.length-1); box.addView(spinner(names,deviceIndex,i->{deviceIndex=i;render();}));
        }
        box.addView(spinner(new String[]{getString(R.string.today),getString(R.string.week),getString(R.string.month)},days==1?0:days==7?1:2,i->{days=new int[]{1,7,30}[i];render();}));
        box.addView(spinner(new String[]{getString(R.string.everything),getString(R.string.games),getString(R.string.apps),getString(R.string.websites)},categoryIndex,i->{categoryIndex=i;render();}));
    }
    private void statistics() throws Exception {
        permissionCard();
        double today=0; if(!devices.isEmpty()) for(var row:Statistics.rows(devices.get(0),"all")) if(row.day().equals(LocalDate.now().toString())) today+=row.seconds();
        LinearLayout total=card(); total.addView(text(getString(R.string.phone_today),14,MUTED)); TextView value=text(duration(today),36,ACCENT); value.setTypeface(null,Typeface.BOLD); total.addView(value);
        filters(false); List<Statistics.Row> rows=selected(false); chart(rows);
        LinearLayout sync=card(); heading(sync,R.string.devices_sync);
        for(int i=0;i<devices.size();i++) {
            JSONObject device=devices.get(i); double seconds=0;
            String since=LocalDate.now().minusDays(days-1).toString(),until=LocalDate.now().toString();
            for(var row:Statistics.rows(device,new String[]{"all","games","apps","websites"}[categoryIndex])) if(row.day().compareTo(since)>=0&&row.day().compareTo(until)<=0) seconds+=row.seconds();
            sync.addView(text(device.getString("name")+(i==0?" · "+getString(R.string.this_phone):"")+"\n"+duration(seconds),15,TEXT));
        }
        sync.addView(text(lastSync==0?getString(R.string.never_synced):getString(R.string.last_sync,java.text.DateFormat.getDateTimeInstance(java.text.DateFormat.SHORT,java.text.DateFormat.SHORT,getResources().getConfiguration().getLocales().get(0)).format(new Date(lastSync))),13,MUTED));
        Button connect=button(connected?R.string.sync_now:R.string.connect,()->{if(connected) load(true,null);else connectDialog();}); connect.setEnabled(!busy); sync.addView(connect);
        if(connected) { sync.addView(button(R.string.disconnect,this::disconnect)); }
        else sync.addView(text(getString(R.string.sync_explainer),13,MUTED));
        ranking(rows);
    }
    private void chart(List<Statistics.Row> rows) {
        LinearLayout box=card(); heading(box,R.string.time_chart); TreeMap<String,Double> values=new TreeMap<>();
        for(int i=days-1;i>=0;i--) values.put(LocalDate.now().minusDays(i).toString(),0.0);
        for(var row:rows) values.merge(row.day(),row.seconds(),Double::sum);
        box.addView(new Chart(this,values),new LinearLayout.LayoutParams(-1,dp(170)));
    }
    private void activities() throws Exception { permissionCard(); filters(true); ranking(selected(true)); content.addView(button(R.string.refresh,()->load(false,null))); }
    private void ranking(List<Statistics.Row> rows) {
        LinearLayout box=card(); heading(box,R.string.top_activity);
        Map<String,Double> totals=new HashMap<>(); Map<String,Statistics.Row> info=new HashMap<>();
        for(var row:rows) { String key=row.kind()+":"+row.key(); totals.merge(key,row.seconds(),Double::sum); info.put(key,row); }
        if(totals.isEmpty()) { box.addView(text(getString(R.string.empty),14,MUTED)); return; }
        ArrayList<String> keys=new ArrayList<>(totals.keySet()); keys.sort((a,b)->Double.compare(totals.get(b),totals.get(a)));
        for(String key:keys.subList(0,Math.min(rowLimit,keys.size()))) {
            var row=info.get(key); LinearLayout line=new LinearLayout(this); line.setGravity(Gravity.CENTER_VERTICAL); line.setPadding(0,dp(8),0,dp(8));
            ImageView icon=new ImageView(this); boolean loaded=false;
            if(row.device().equals(localId)&&row.key().startsWith("android:")) try { icon.setImageDrawable(getPackageManager().getApplicationIcon(row.key().substring(8))); loaded=true; } catch(android.content.pm.PackageManager.NameNotFoundException ignored) {}
            if(!loaded) icon.setImageResource(R.drawable.ic_launcher);
            icon.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO); line.addView(icon,new LinearLayout.LayoutParams(dp(36),dp(36)));
            TextView label=text(row.name().isEmpty()?getString(R.string.other_browser):row.name(),15,TEXT); label.setPadding(dp(12),0,dp(8),0); line.addView(label,new LinearLayout.LayoutParams(0,-2,1)); line.addView(text(duration(totals.get(key)),14,ACCENT)); box.addView(line);
        }
        if(keys.size()>rowLimit)box.addView(button(R.string.show_more,()->{rowLimit+=50;render();}));
    }
    private void settings() {
        LinearLayout measurement=card(); Switch enabled=new Switch(this); enabled.setText(R.string.tracking); enabled.setTextColor(TEXT); enabled.setMinHeight(dp(48)); enabled.setChecked(tracking);
        enabled.setOnCheckedChangeListener((button,on)->{ if(on) grant(); else { try(PhoneStore store=new PhoneStore(this)) {store.put("enabled","false");store.resetCursor(System.currentTimeMillis());} CollectionJob.schedule(this);load(false,null); } });
        measurement.addView(enabled); measurement.addView(text(getString(R.string.tracking_help),14,MUTED));
        if(tracking&&!PhoneUsage.allowed(this)) {measurement.addView(text(getString(R.string.access_missing),14,MUTED));measurement.addView(button(R.string.grant_access,this::grant));}
        LinearLayout name=card(); heading(name,R.string.device_name); name.addView(text(deviceName,16,TEXT)); name.addView(button(R.string.device_name,this::nameDialog));
        LinearLayout language=card(); heading(language,R.string.language); boolean hu=getResources().getConfiguration().getLocales().get(0).getLanguage().equals("hu");
        language.addView(spinner(new String[]{"Magyar","English"},hu?0:1,i->{getSharedPreferences("ui",0).edit().putString("language",i==0?"hu":"en").apply();recreate();}));
        if(gap) content.addView(text(getString(R.string.history_gap),14,MUTED));
        content.addView(text(getString(R.string.sync_schedule),14,MUTED)); content.addView(text(getString(R.string.preview_scope),13,MUTED));
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
            if(busy)return; CollectionJob.WORK.execute(()->{ try(PhoneStore store=new PhoneStore(this)){Vault.clear(this);store.getWritableDatabase().delete("remote",null,null);store.put("last_sync","0");}catch(RuntimeException e){runOnUiThread(()->{message=getString(R.string.read_error);render();});return;}runOnUiThread(()->{deviceIndex=0;load(false,null);}); });
        }).show();
    }
    private void load(boolean sync,String newCode) {
        if(busy)return; busy=true; message=""; render();
        CollectionJob.WORK.execute(()->{
            ArrayList<JSONObject> loaded=new ArrayList<>();String result="",id="",name="";boolean paired=false,enabled=false,missing=false;long last=0,after=0;
            try(PhoneStore store=new PhoneStore(this)) {
                PhoneUsage.collect(this,store); CollectionJob.schedule(this);
                if(newCode!=null&&!newCode.equals(Vault.read(this))) {store.getWritableDatabase().delete("remote",null,null);store.put("last_sync","0");Vault.write(this,newCode);}
                String code=Vault.read(this); paired=!code.isEmpty();
                if(sync) {
                    PhoneSync.Result outcome=PhoneSync.run(this,store);
                    int resource=switch(outcome){case DONE->R.string.synced;case UNAVAILABLE->R.string.sync_unavailable;case INVALID_CODE->R.string.sync_code_error;case LIMIT->R.string.sync_limit;case INVALID_DATA->R.string.sync_invalid;default->0;};
                    if(resource!=0) result=getString(resource);
                    if(outcome==PhoneSync.Result.WAIT) {int minutes=(int)Math.max(1,(store.number("sync_after",0)-System.currentTimeMillis()+59999)/60000);result=getResources().getQuantityString(R.plurals.sync_wait,minutes,minutes);}
                }
                loaded.add(store.snapshot(code.isEmpty()?"00000000000000000000000000000000":code)); JSONArray remote=store.remotes(code);
                for(int i=0;i<remote.length();i++)loaded.add(remote.getJSONObject(i));
                id=store.device();name=store.name();enabled=store.get("enabled","false").equals("true");missing=store.get("history_gap","false").equals("true");last=store.number("last_sync",0);after=store.number("sync_after",0);
            } catch(Exception e) {result=getString(R.string.read_error);}
            final String text=result,identity=id,label=name;final boolean isConnected=paired,isEnabled=enabled,hasGap=missing;final long syncTime=last,next=after;
            runOnUiThread(()->{if(isDestroyed())return;devices.clear();devices.addAll(loaded);localId=identity;deviceName=label;connected=isConnected;tracking=isEnabled;gap=hasGap;lastSync=syncTime;syncAfter=next;message=text;busy=false;render();});
        });
    }
    private final class Chart extends View {
        private final TreeMap<String,Double> values;private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
        Chart(Context context,TreeMap<String,Double> values){super(context);this.values=values;StringBuilder description=new StringBuilder(getString(R.string.time_chart));for(var entry:values.entrySet())description.append(". ").append(entry.getKey()).append(": ").append(duration(entry.getValue()));setContentDescription(description);setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_YES);}
        @Override protected void onDraw(Canvas canvas){super.onDraw(canvas);double max=Math.max(1,Collections.max(values.values()));float width=getWidth()/(float)values.size(),bottom=getHeight()-dp(26),top=dp(30);int i=0;paint.setTextSize(dp(10));paint.setTextAlign(Paint.Align.CENTER);
            for(var entry:values.entrySet()){float x=width*i+width/2,bar=(float)(entry.getValue()/max)*(bottom-top);paint.setColor(ACCENT);canvas.drawRoundRect(x-width*.28f,bottom-bar,x+width*.28f,bottom,dp(3),dp(3),paint);paint.setColor(MUTED);if(values.size()<=7||i==0||i==values.size()-1)canvas.drawText(entry.getKey().substring(5),x,bottom+dp(20),paint);if(values.size()<=7&&entry.getValue()>0)canvas.drawText(duration(entry.getValue()),x,bottom-bar-dp(6),paint);i++;}
        }
    }
}
