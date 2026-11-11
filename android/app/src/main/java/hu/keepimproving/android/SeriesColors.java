package hu.keepimproving.android;
import android.content.Context;
import android.graphics.Color;
import java.util.*;
/** Desktop palette, stable assignments across filters, languages and app restarts. */
final class SeriesColors {
    static final String[] PALETTE={"#73c7ff","#f0ba68","#b9a1ff","#7de5bf","#f58fa7","#74d8db","#d7dc7a","#f4a67c","#9faef4","#e4a1e0","#a1d99b","#dcc6a1"};
    static String identity(String kind,String key){
        if(kind.equals("game")){
            if(key.startsWith("app:")){String value=key.substring(4).replace('\\','/');return "app:"+value.substring(value.lastIndexOf('/')+1).toLowerCase(Locale.ROOT);}
            if(key.startsWith("site:")){String value=key.substring(5).toLowerCase(Locale.ROOT);return "site:"+(value.startsWith("www.")?value.substring(4):value);}
        }
        return key;
    }
    static int get(Context c,String kind,String key){
        var p=c.getSharedPreferences("series_colors",0);String id=kind+":"+identity(kind,key);
        if(p.contains(id))return p.getInt(id,0);
        // Retain an existing assignment when upgrading old path-based colors.
        // The sorted choice is independent of the first selected day/filter.
        Map<String,?> saved=new TreeMap<>(p.getAll());
        for(var entry:saved.entrySet())if(entry.getValue() instanceof Integer color&&entry.getKey().startsWith(kind+":")&&
                (kind+":"+identity(kind,entry.getKey().substring(kind.length()+1))).equals(id)){
            p.edit().putInt(id,color).apply();return color;
        }
        Set<Integer> used=new HashSet<>();for(var e:saved.entrySet())if(e.getKey().startsWith(kind+":")&&e.getValue() instanceof Integer color)used.add(color);
        int best=0;double score=-1;int start=Math.floorMod(id.hashCode(),PALETTE.length);
        for(int i=0;i<PALETTE.length;i++){int color=Color.parseColor(PALETTE[(i+start)%PALETTE.length]);if(used.contains(color))continue;double distance=Double.MAX_VALUE;for(int old:used){double r=Color.red(color)-Color.red(old),g=Color.green(color)-Color.green(old),b=Color.blue(color)-Color.blue(old);distance=Math.min(distance,r*r+g*g+b*b);}if(distance>score){score=distance;best=color;}}
        if(score<0)best=Color.HSVToColor(new float[]{Math.floorMod(id.hashCode(),360),.45f,.95f});p.edit().putInt(id,best).apply();return best;
    }
}
