package hu.keepimproving.android;

import android.content.Context;
import android.graphics.*;
import android.graphics.drawable.*;
import android.util.Base64;
import android.util.LruCache;
import org.json.*;
import java.util.Locale;

/** Bounded images from the authenticated encrypted snapshot; no phone downloads. */
final class RemoteIcons {
    private static final LruCache<String,Bitmap> cache=new LruCache<>(64);
    static String key(String kind,String value){
        if(kind.equals("app"))value=value.substring(Math.max(value.lastIndexOf('\\'),value.lastIndexOf('/'))+1).toLowerCase(Locale.ROOT);
        if(kind.equals("site")){value=value.toLowerCase(Locale.ROOT);if(value.startsWith("www."))value=value.substring(4);}
        return kind+":"+value;
    }
    static Drawable from(Context c,JSONObject companion,String kind,String value){
        if(companion==null)return null;JSONObject icons=companion.optJSONObject("icons");if(icons==null)return null;
        String encoded=icons.optString(key(kind,value));
        if(encoded.isEmpty()||encoded.length()>11000)return null;
        try{
            Bitmap image=cache.get(encoded);
            if(image==null){byte[] bytes=Base64.decode(encoded,Base64.DEFAULT);BitmapFactory.Options size=new BitmapFactory.Options();size.inJustDecodeBounds=true;BitmapFactory.decodeByteArray(bytes,0,bytes.length,size);
                if(size.outWidth<1||size.outHeight<1||size.outWidth>64||size.outHeight>64)return null;
                image=BitmapFactory.decodeByteArray(bytes,0,bytes.length);if(image==null)return null;cache.put(encoded,image);
            }
            return new BitmapDrawable(c.getResources(),image);
        }catch(IllegalArgumentException ignored){return null;}
    }
    static Drawable row(MainActivity a,Statistics.Row row){
        if(row.key().startsWith("android:"))try{return a.getPackageManager().getApplicationIcon(row.key().substring(8));}catch(Exception ignored){}
        for(JSONObject device:a.devices)if(device.optString("device").equals(row.device())){
            Drawable image=from(a,device.optJSONObject("companion"),row.kind(),row.key());if(image!=null)return image;
        }
        for(JSONObject device:a.devices){Drawable image=from(a,device.optJSONObject("companion"),row.kind(),row.key());if(image!=null)return image;}
        return new PhoneIcons(row.kind().equals("app")?"apps":row.kind(),SeriesColors.get(a,row.kind(),row.key()));
    }
}
