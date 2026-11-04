package hu.keepimproving.android;

import org.json.JSONArray;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Set;

public final class Statistics {
    public record Row(String day,String key,String name,String kind,double seconds,String device) {}
    private static final Set<String> BROWSERS=new java.util.HashSet<>(java.util.Arrays.asList("brave.exe","chrome.exe","msedge.exe","firefox.exe","opera.exe","vivaldi.exe","browser.exe","iexplore.exe"));
    public static List<Row> rows(JSONObject snapshot,String category) throws Exception {
        ArrayList<Row> result=new ArrayList<>(); String device=snapshot.getString("device");
        if(category.equals("all")||category.equals("games")) {
            JSONArray games=snapshot.getJSONArray("rows");
            for(int i=0;i<games.length();i++) { JSONArray r=games.getJSONArray(i); result.add(new Row(r.getString(0),r.getString(1),r.getString(2),"game",r.getDouble(4),device)); }
        }
        JSONArray activity=snapshot.optJSONArray("activity"); if(activity==null) return result;
        HashMap<String,Double> browsers=new HashMap<>(),sites=new HashMap<>();
        for(int i=0;i<activity.length();i++) {
            JSONArray r=activity.getJSONArray(i); String day=r.getString(0),kind=r.getString(1),key=r.getString(2); double seconds=r.getDouble(4);
            String basename=key.substring(Math.max(key.lastIndexOf('\\'),key.lastIndexOf('/'))+1).toLowerCase(java.util.Locale.ROOT);
            boolean browser=kind.equals("app")&&BROWSERS.contains(basename);
            if(browser) browsers.merge(day,seconds,Double::sum);
            if(kind.equals("site")) sites.merge(day,seconds,Double::sum);
            if(category.equals("apps")&&kind.equals("app")||category.equals("websites")&&kind.equals("site")||category.equals("all")&&kind.equals("app")&&!browser)
                result.add(new Row(day,key,r.getString(3),kind,seconds,device));
        }
        if(category.equals("all")) {
            for(int i=0;i<activity.length();i++) {
                JSONArray r=activity.getJSONArray(i); if(!r.getString(1).equals("site")) continue;
                String day=r.getString(0); double scale=Math.min(1,browsers.getOrDefault(day,0.0)/sites.get(day));
                if(scale>0) result.add(new Row(day,r.getString(2),r.getString(3),"site",r.getDouble(4)*scale,device));
            }
            for(var entry:browsers.entrySet()) {
                double remaining=Math.max(0,entry.getValue()-sites.getOrDefault(entry.getKey(),0.0));
                if(remaining>0) result.add(new Row(entry.getKey(),"browser:other","","browser",remaining,device));
            }
        }
        return result;
    }
}
