package hu.keepimproving.android;
import android.content.Context;
import android.content.res.Configuration;
import java.util.Locale;
final class PhoneLocale {
    static Context context(Context base) {
        String language=base.getSharedPreferences("ui",0).getString("language",Locale.getDefault().getLanguage().equals("hu")?"hu":"en");
        Configuration config=new Configuration(base.getResources().getConfiguration());config.setLocale(Locale.forLanguageTag(language));return base.createConfigurationContext(config);
    }
    static String text(Context context,String en,String hu){return context.getResources().getConfiguration().getLocales().get(0).getLanguage().equals("hu")?hu:en;}
    static String timer(long millis) {long seconds=Math.max(0,(millis+999)/1000);return seconds>=3600?String.format(Locale.ROOT,"%d:%02d:%02d",seconds/3600,seconds/60%60,seconds%60):String.format(Locale.ROOT,"%02d:%02d",seconds/60,seconds%60);}
}
