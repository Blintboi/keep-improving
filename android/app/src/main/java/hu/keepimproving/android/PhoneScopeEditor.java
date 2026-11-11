package hu.keepimproving.android;

import android.app.*;
import android.widget.*;
import org.json.*;
import java.util.*;

/** Scope belongs to the edited rule, alongside its weekdays. */
final class PhoneScopeEditor {
    static Map<String,String> devices(MainActivity a){Map<String,String> result=new LinkedHashMap<>();try(PhoneStore s=new PhoneStore(a)){result.put(s.device(),s.name());}for(JSONObject d:a.devices)result.putIfAbsent(d.optString("device"),d.optString("name"));for(JSONObject d:RemoteScreens.pcs(a))result.putIfAbsent(d.optString("device"),d.optString("name"));return result;}
    static String label(MainActivity a,JSONObject scope,String fallback){
        if(scope==null)return devices(a).getOrDefault(fallback,a.t("This device","Ez az eszköz"));
        if(scope.optString("mode").equals("all"))return a.t("All linked devices","Minden kapcsolt eszköz");
        if(scope.optString("mode").equals("group")){try(PhoneStore s=new PhoneStore(a)){JSONObject g=PhoneShared.groups(s).optJSONObject(scope.optString("group"));return g==null?a.t("Unavailable group","Nem elérhető csoport"):g.optString("name");}}
        return devices(a).getOrDefault(scope.optString("device"),a.t("Unavailable device","Nem elérhető eszköz"));
    }
    static void add(PhoneEditor e,boolean budget,String owner){
        MainActivity a=e.a;a.heading(e.box,a.t("Devices","Eszközök"));Button choose=a.button("",()->{});Runnable refresh=()->choose.setText(label(a,e.value.optJSONObject("devices"),owner));refresh.run();e.box.addView(choose);
        choose.setOnClickListener(v->{List<String> names=new ArrayList<>();List<JSONObject> scopes=new ArrayList<>();String connection;try(PhoneStore s=new PhoneStore(a)){connection=PhoneShared.connection(s);for(var d:devices(a).entrySet()){JSONObject x=new JSONObject();PhoneRules.set(x,"mode","device");PhoneRules.set(x,"device",d.getKey());names.add(d.getValue());scopes.add(x);}if(!connection.isEmpty()){JSONObject all=new JSONObject();PhoneRules.set(all,"mode","all");names.add(a.t("All linked devices","Minden kapcsolt eszköz"));scopes.add(all);JSONObject groups=PhoneShared.groups(s);for(String id:PhoneShared.keys(groups)){JSONObject x=new JSONObject();PhoneRules.set(x,"mode","group");PhoneRules.set(x,"group",id);names.add(a.t("Group: ","Csoport: ")+groups.optJSONObject(id).optString("name"));scopes.add(x);}}}
            new AlertDialog.Builder(a).setTitle(a.t("Devices","Eszközök")).setItems(names.toArray(new String[0]),(d,i)->{JSONObject x=scopes.get(i);if(!connection.isEmpty())PhoneRules.set(x,"connection",connection);if(budget)PhoneRules.set(x,"accounting","shared");e.set("devices",x);refresh.run();}).setNegativeButton(R.string.cancel,null).show();});
        e.box.addView(a.button(a.t("Device groups…","Eszközcsoportok…"),()->groups(a,refresh)));
        e.hint(budget?"One shared allowance across the selected devices.":"This notification appears on the selected devices.",budget?"A kijelölt eszközök közös keretet fogyasztanak.":"Ez az értesítés a kijelölt eszközökön jelenik meg.");
        if(budget)try(PhoneStore s=new PhoneStore(a)){long at=Math.max(s.number("last_sync",0),s.number("shared_received_at",0));if(at>0)e.box.addView(a.text(a.t("Last received sync: ","Utolsó beérkezett szinkron: ")+java.text.DateFormat.getDateTimeInstance(java.text.DateFormat.SHORT,java.text.DateFormat.SHORT).format(new java.util.Date(at)),12,MainActivity.MUTED));}
    }
    static void groups(MainActivity a,Runnable refreshed){
        JSONObject groups;try(PhoneStore s=new PhoneStore(a)){if(PhoneShared.connection(s).isEmpty()){Toast.makeText(a,a.t("Connect your devices first.","Előbb kapcsold össze az eszközöket."),Toast.LENGTH_LONG).show();return;}groups=PhoneShared.groups(s);}
        List<String> ids=PhoneShared.keys(groups),names=new ArrayList<>();names.add(a.t("+ New group","+ Új csoport"));for(String id:ids)names.add(groups.optJSONObject(id).optString("name"));
        new AlertDialog.Builder(a).setTitle(a.t("Device groups","Eszközcsoportok")).setItems(names.toArray(new String[0]),(d,index)->{
            String id=index==0?PhoneRules.id():ids.get(index-1);JSONObject original=index==0?PhoneRules.object("{\"name\":\"\",\"devices\":[]}"):PhoneRules.copy(groups.optJSONObject(id));PhoneRules.set(original,"id",id);PhoneEditor e=new PhoneEditor(a,"remote:groups",original,a.t("Device group","Eszközcsoport"));e.text("name",a.t("Name","Név"),80,false);
            Set<String> selected=new LinkedHashSet<>();JSONArray old=e.value.optJSONArray("devices");if(old!=null)for(int i=0;i<old.length();i++)selected.add(old.optString(i));for(var item:devices(a).entrySet()){CheckBox c=new CheckBox(a);c.setText(item.getValue());c.setTextColor(MainActivity.TEXT);c.setMinHeight(a.dp(48));c.setChecked(selected.contains(item.getKey()));c.setOnCheckedChangeListener((b,on)->{if(on)selected.add(item.getKey());else selected.remove(item.getKey());e.set("devices",new JSONArray(selected));});e.box.addView(c);}
            if(index>0)e.box.addView(a.button(a.t("Delete group","Csoport törlése"),()->new AlertDialog.Builder(a).setTitle(a.t("Delete device group?","Törlöd az eszközcsoportot?")).setMessage(a.t("Rules using this group will become inactive. History will be kept.","Az ezt a csoportot használó szabályok inaktívvá válnak. Az előzmények megmaradnak.")).setNegativeButton(R.string.cancel,null).setPositiveButton(a.t("Delete","Törlés"),(confirm,w)->{a.edit(()->{try(PhoneStore s=new PhoneStore(a)){JSONObject records=PhoneShared.records(s);PhoneShared.update(s,records,id,"group",null);s.put("shared_records:"+PhoneShared.connection(s),records.toString());}});e.clear();e.dialog.dismiss();refreshed.run();}).show()));
            e.customSave=v->{String name=v.optString("name").trim();if(name.isEmpty()||name.length()>80)throw new IllegalArgumentException();a.edit(()->{try(PhoneStore s=new PhoneStore(a)){JSONObject value=new JSONObject();PhoneRules.set(value,"name",name);PhoneRules.set(value,"devices",v.optJSONArray("devices"));PhoneRules.set(value,"connection",PhoneShared.connection(s));JSONObject records=PhoneShared.records(s);PhoneShared.update(s,records,id,"group",value);s.put("shared_records:"+PhoneShared.connection(s),records.toString());}});e.clear();e.dialog.dismiss();refreshed.run();};e.dialog.show();
        }).setNegativeButton(R.string.cancel,null).show();
    }
}
