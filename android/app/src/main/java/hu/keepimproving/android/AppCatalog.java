package hu.keepimproving.android;
import android.content.*;
import android.content.pm.*;
import android.database.Cursor;
import java.util.*;

final class AppCatalog {
    record Item(String pkg,String name,boolean game,boolean excluded) {}
    private static final Set<String> SYSTEM=Set.of("android","com.android.systemui","com.android.settings","com.android.phone","com.android.server.telecom","com.android.permissioncontroller","com.google.android.permissioncontroller","com.android.packageinstaller","com.google.android.packageinstaller","com.android.emergency");
    static boolean safe(Context context,String pkg) {
        if(pkg.isEmpty()||pkg.equals(context.getPackageName())||SYSTEM.contains(pkg))return true;
        PackageManager pm=context.getPackageManager();
        android.telecom.TelecomManager telecom=context.getSystemService(android.telecom.TelecomManager.class);if(telecom!=null&&pkg.equals(telecom.getDefaultDialerPackage()))return true;
        for(Intent intent:new Intent[]{new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME),new Intent(Intent.ACTION_DIAL),new Intent(android.provider.Settings.ACTION_SETTINGS)}) {
            ResolveInfo info=pm.resolveActivity(intent,PackageManager.MATCH_DEFAULT_ONLY);if(info!=null&&info.activityInfo!=null&&pkg.equals(info.activityInfo.packageName))return true;
        }
        return false;
    }
    static List<Item> list(Context context,PhoneStore store) {
        Map<String,Item> result=new HashMap<>();var excluded=PhoneRules.array(store.get("excluded","[]"));var games=PhoneRules.array(store.get("game_apps","[]"));
        PackageManager pm=context.getPackageManager();
        for(ResolveInfo info:pm.queryIntentActivities(new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER),0)) {
            String pkg=info.activityInfo.packageName;if(pkg.equals(context.getPackageName()))continue;
            result.put(pkg,new Item(pkg,info.loadLabel(pm).toString(),info.activityInfo.applicationInfo.category==ApplicationInfo.CATEGORY_GAME||PhoneRules.contains(games,pkg),PhoneRules.contains(excluded,pkg)));
        }
        try(Cursor c=store.getReadableDatabase().rawQuery("SELECT package,MAX(name),MAX(game) FROM usage GROUP BY package",null)) {
            while(c.moveToNext()){String pkg=c.getString(0);result.putIfAbsent(pkg,new Item(pkg,c.getString(1),c.getInt(2)!=0||PhoneRules.contains(games,pkg),PhoneRules.contains(excluded,pkg)));}
        }
        var nongames=PhoneRules.array(store.get("nongame_apps","[]"));result.replaceAll((pkg,item)->new Item(pkg,item.name(),item.game()&&!PhoneRules.contains(nongames,pkg),item.excluded()));
        List<Item> sorted=new ArrayList<>(result.values());sorted.sort(Comparator.comparing(Item::name,String.CASE_INSENSITIVE_ORDER));return sorted;
    }
}
