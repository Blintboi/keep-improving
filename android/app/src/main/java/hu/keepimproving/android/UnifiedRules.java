package hu.keepimproving.android;

import android.app.AlertDialog;
import android.widget.*;
import org.json.*;
import java.util.*;

/** One list per feature. Shared identities collapse copies, never similarly named rules. */
final class UnifiedRules {
    record Row(String key,JSONObject value,JSONObject pc,PhoneRuntime.BudgetView budget) {}

    static List<Row> rows(MainActivity a,String kind,List<JSONObject> pcs) {
        Map<String,Row> rows=new LinkedHashMap<>();
        try(PhoneStore store=new PhoneStore(a)) {
            String nativeKind=kind.equals("budget")?"budget":"reminder";
            Map<String,String> sharedIds=new HashMap<>();JSONObject aliases=PhoneShared.aliases(store),records=PhoneShared.records(store);
            for(String id:PhoneShared.keys(aliases)) {
                JSONObject alias=aliases.optJSONObject(id);
                if(nativeKind.equals(alias.optString("kind")))sharedIds.put(alias.optString("native"),id);
            }
            if(a.state!=null) {
                if(kind.equals("budget"))for(var item:a.state.budgets())addLocal(rows,sharedIds,item.rule(),item);
                else for(int i=0;i<a.state.reminders().length();i++)addLocal(rows,sharedIds,a.state.reminders().optJSONObject(i),null);
            }
            for(JSONObject pc:pcs) {
                JSONArray values=pc.optJSONArray(kind.equals("budget")?"budgets":"notifications");JSONObject ids=pc.optJSONObject("shared_ids");
                if(values==null)continue;
                for(int i=0;i<values.length();i++) {
                    JSONObject value=values.optJSONObject(i);if(value==null)continue;
                    String id=value.optString("id"),shared=ids==null?"":ids.optString(kind+":"+id);
                    JSONObject record=records.optJSONObject(shared);
                    if(record!=null&&record.isNull("value"))continue; // A stale PC copy must not resurrect a deleted rule.
                    String key=shared.isEmpty()?"pc:"+pc.optString("device")+":"+id:"shared:"+shared;
                    rows.putIfAbsent(key,new Row(key,value,pc,null));
                }
            }
        }
        List<Row> result=new ArrayList<>(rows.values());result.sort(Comparator.comparing(row->title(a,kind,row).toLowerCase(Locale.ROOT)));return result;
    }
    private static void addLocal(Map<String,Row> rows,Map<String,String> ids,JSONObject value,PhoneRuntime.BudgetView budget) {
        if(value==null)return;String id=value.optString("id"),shared=value.optString("_shared",ids.getOrDefault(id,""));
        String key=shared.isEmpty()?"phone:"+id:"shared:"+shared;rows.putIfAbsent(key,new Row(key,value,null,budget));
    }
    static String title(MainActivity a,String kind,Row row) {
        if(row.pc()!=null)return RemoteScreens.name(a,row.value(),kind);
        String name=row.value().optString(kind.equals("budget")?"name":"title");return name.isBlank()?RemoteLabels.label(a,row.value().optString("trigger")):name;
    }
    static final class Labels {
        final String local;final JSONObject groups;final Map<String,String> names;final Set<String> computers=new HashSet<>();
        Labels(MainActivity a,List<JSONObject> pcs){try(PhoneStore s=new PhoneStore(a)){local=s.device();groups=PhoneShared.groups(s);}names=PhoneScopeEditor.devices(a);for(JSONObject pc:pcs){String id=pc.optString("device");names.put(id,pc.optString("name"));computers.add(id);}}
        void badge(MainActivity a,LinearLayout box,JSONObject value,String owner) {
        JSONObject scope=value.optJSONObject("devices");String text,glyph;
        if(scope!=null&&!scope.optString("mode").equals("device")) {
            JSONObject group=groups.optJSONObject(scope.optString("group"));
            text=scope.optString("mode").equals("group")?a.t("Group · ","Csoport · ")+(group==null?a.t("Unavailable group","Nem elérhető csoport"):group.optString("name")):a.t("All linked devices","Minden kapcsolt eszköz");glyph="computer";
        } else {
            String device=scope==null?owner:scope.optString("device");boolean phone=device.equals(local);
            text=names.getOrDefault(device,a.t("Unavailable device","Nem elérhető eszköz"));glyph=phone?"phone":"computer";
        }
        TextView label=a.text(text,14,MainActivity.ACCENT);a.icon(label,glyph,MainActivity.ACCENT);box.addView(label);
        }
    }
    static boolean matches(PhoneStore store,Row row,String selected) {
        if(selected.isEmpty())return true;JSONObject scope=row.value().optJSONObject("devices");
        return scope==null?selected.equals(row.pc()==null?store.device():row.pc().optString("device")):PhoneShared.applies(store,scope,selected);
    }
    static void show(MainActivity a,String kind) {
        boolean budget=kind.equals("budget");List<JSONObject> pcs=RemoteScreens.pcs(a);List<Row> all=rows(a,kind,pcs);
        a.content.addView(a.button(budget?a.t("+ New budget","+ Új keret"):a.t("+ New notification","+ Új értesítés"),()->create(a,kind,pcs)));
        Labels labels=new Labels(a,pcs);Map<String,String> devices=labels.names;String selected=budget?a.budgetDevice:a.reminderDevice;
        if(!devices.containsKey(selected))selected="";
        String[] ids=new String[devices.size()+1],names=new String[devices.size()+1];ids[0]="";names[0]=a.t("All devices","Minden eszköz");int index=0,n=1;
        for(var device:devices.entrySet()){ids[n]=device.getKey();names[n]=device.getValue();if(selected.equals(ids[n]))index=n;n++;}
        if(devices.size()>1){LinearLayout filter=a.card();a.heading(filter,a.t("Devices","Eszközök"));filter.addView(a.spinner(names,index,i->{if(budget){a.budgetDevice=ids[i];a.budgetLimit=40;}else{a.reminderDevice=ids[i];a.reminderLimit=40;}a.render();}));}
        int limit=budget?a.budgetLimit:a.reminderLimit,count=0;try(PhoneStore s=new PhoneStore(a)) {
            for(Row row:all) {
                if(!matches(s,row,selected))continue;if(count++>=limit)continue;
                if(row.pc()==null) {
                    if(budget)PhoneScreens.budgetCard(a,row.budget(),labels);else PhoneScreens.reminderCard(a,row.value(),labels);
                } else {
                    LinearLayout box=a.card();box.setTag("rule:"+row.key());a.heading(box,title(a,kind,row));labels.badge(a,box,row.value(),row.pc().optString("device"));
                    box.addView(a.text(row.value().optBoolean("enabled")?a.t("Enabled","Bekapcsolva"):a.t("Disabled","Kikapcsolva"),14,MainActivity.MUTED));
                    if(budget)box.addView(a.text(row.value().optBoolean("usage_limit",true)?a.t("Daily allowance: ","Napi keret: ")+a.duration(row.value().optDouble("seconds")):a.t("No daily cap","Napi korlát nélkül"),22,MainActivity.TEXT));
                    else {box.addView(a.text(row.value().optString("text"),15,MainActivity.MUTED));box.addView(a.text(RemoteLabels.label(a,row.value().optString("trigger")),14,MainActivity.MUTED));}
                    box.addView(a.button(budget?a.t("Edit budget","Keret szerkesztése"):a.t("Edit notification","Értesítés szerkesztése"),()->{if(budget)RemoteScreens.budget(a,row.pc(),row.value());else RemoteScreens.notification(a,row.pc(),row.value());}));
                }
            }
        }
        if(count==0){LinearLayout empty=a.card();PhoneScreens.note(a,empty,all.isEmpty()?"No rules yet.":"No rules for this device.",all.isEmpty()?"Még nincs szabály.":"Ehhez az eszközhöz nincs szabály.");}
        if(count>limit)a.content.addView(a.button(R.string.show_more,()->{if(budget)a.budgetLimit+=40;else a.reminderLimit+=40;a.render();}));
        if(!pcs.isEmpty()){LinearLayout info=a.card();PhoneScreens.note(a,info,"PC changes take effect after sync.","A PC-s módosítások szinkronizálás után lépnek életbe.");}
        PhoneScreens.readiness(a);
    }
    static void create(MainActivity a,String kind,List<JSONObject> pcs) {
        if(pcs.isEmpty()){createOn(a,kind,null);return;}
        List<String> names=new ArrayList<>();try(PhoneStore s=new PhoneStore(a)){names.add(s.name());}for(JSONObject pc:pcs)names.add(pc.optString("name"));
        new AlertDialog.Builder(a).setTitle(a.t("Which device?","Melyik eszközön?"))
            .setItems(names.toArray(new String[0]),(d,i)->createOn(a,kind,i==0?null:pcs.get(i-1))).setNegativeButton(R.string.cancel,null).show();
    }
    static void createOn(MainActivity a,String kind,JSONObject pc) {
        if(pc==null){if(kind.equals("budget"))PhoneEditor.budget(a,PhoneRules.budget());else PhoneEditor.reminder(a,PhoneRules.reminder());}
        else RemoteScreens.createRule(a,pc,kind);
    }
}
