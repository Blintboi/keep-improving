package hu.keepimproving.android;
import java.util.*;
final class RemoteLabels {
    private static final Map<String,String[]> LABELS=new HashMap<>();
    static {String source="""
warning_seconds|Early warning (seconds)|Előzetes jelzés (másodperc)
limit_seconds|Daily game allowance (seconds)|Napi játékkeret (másodperc)
budget_reset_minute|Daily reset (minute of day)|Napi megújulás (napon belüli perc)
budget_reset_overrides|Budget reset overrides|Keretek egyéni megújulása
hub_enabled|Open Hub at startup|Hub megnyitása induláskor
language|Language|Nyelv
check_updates|Check for updates|Frissítések keresése
overlay_enabled|Countdown overlay|Visszaszámláló megjelenítése
overlay_replace_warning|Countdown replaces early popup|Visszaszámláló a korai felugró jelzés helyett
limit_popup_enabled|Popup when limit reached|Felugró jelzés a keret végén
overlay_opacity|Countdown opacity (0–1)|Visszaszámláló átlátszatlansága (0–1)
overlay_font_size|Countdown text size|Visszaszámláló betűmérete
overlay_color_normal|Normal countdown color|Visszaszámláló normál színe
overlay_color_warning|Warning countdown color|Visszaszámláló figyelmeztető színe
overlay_x|Horizontal position (0–1)|Vízszintes helyzet (0–1)
overlay_y|Vertical position (0–1)|Függőleges helyzet (0–1)
overlay_rtss_auto|Use RTSS automatically|RTSS automatikus használata
overlay_rtss_details|RTSS details|RTSS részletek
restriction_enabled|Game restriction enabled|Játékkorlátozás bekapcsolva
restriction_seconds|Restriction starts (seconds)|Korlátozás kezdete (másodperc)
bedtime_enabled|Bedtime enabled|Alvásidő bekapcsolva
bedtime_warning_enabled|Bedtime reminder enabled|Alvásidő jelzése bekapcsolva
bedtime_warning_minute|Bedtime reminder (minute of day)|Alvásidő jelzése (napon belüli perc)
bedtime_minute|Bedtime starts (minute of day)|Alvásidő kezdete (napon belüli perc)
bedtime_resume_minute|Bedtime ends (minute of day)|Alvásidő vége (napon belüli perc)
bedtime_minimize|Minimize games at bedtime|Játékok kis méretre alvásidőkor
bedtime_caps_budget|Bedtime caps game allowance|Alvásidő rövidíti a játékkeretet
statistics_sync_enabled|Synchronization enabled|Szinkronizálás bekapcsolva
statistics_device_name|Computer name|Számítógép neve
notification_messages|Notification messages|Értesítések szövegei
removed_notifications|Removed preset notifications|Eltávolított alapértesítések
notification_sound|Notification sound|Értesítési hang
weekend_enabled|Separate weekend schedule|Külön hétvégi időrend
weekend_schedule|Weekend schedule|Hétvégi időrend
game_overlays|Game countdowns|Játékonkénti visszaszámlálók
counter_overlays|Budget countdowns|Keretek visszaszámlálói
activity_overlays|Activity countdowns|Tevékenységek visszaszámlálói
game_limits|Individual game allowances|Játékonkénti keretek
daily_schedules|Weekday schedules|Napokra szabott időrendek
computer_periods|Computer availability|Számítógép elérhetősége
restriction_plans|Restriction steps|Korlátozási lépések
budget_active_days|Active budget days|Keretek aktív napjai
budget_usage_limits|Daily caps|Napi korlátok
game_budget_enabled|Shared game budget enabled|Közös játékkeret bekapcsolva
budget_setup_completed|Initial budget setup complete|Kezdeti keretbeállítás kész
tracking|Measure application use|Alkalmazáshasználat mérése
work|Focus (minutes)|Fókusz (perc)
short_break|Short break (minutes)|Rövid szünet (perc)
long_break|Long break (minutes)|Hosszú szünet (perc)
rounds|Rounds before a long break|Körök a hosszú szünet előtt
block_apps|Apps blocked during focus|Fókusz alatt tiltott alkalmazások
block_sites|Websites blocked during focus|Fókusz alatt tiltott webhelyek
block_groups|Groups blocked during focus|Fókusz alatt tiltott csoportok
excluded_apps|Apps excluded from measurement|Mérésből kizárt alkalmazások
time|At a time of day|Adott időpontban
startup|When the PC app starts|A PC-s alkalmazás indításakor
pomodoros|After daily focus goal|Napi fókuszcél elérésekor
warning|Before the daily limit|A napi keret vége előtt
limit|Daily limit reached|Napi keret elérve
session|Playing again after the limit|Új játék a keret elérése után
bedtime|Bedtime reminder|Alvásidő jelzése
game|Game|Játék
app|Application|Alkalmazás
site|Website|Webhely
games|Games|Játékok
apps|Applications|Alkalmazások
sites|Websites|Webhelyek
members|Members|Tagok
plan|Restriction plan|Korlátozási terv
kind|Action|Művelet
value|Selection|Kiválasztás
id|Identifier|Azonosító
name|Name|Név
enabled|Enabled|Bekapcsolva
days|Active days|Aktív napok
steps|Steps|Lépések
mode|Timing|Időzítés
minutes|Minutes|Perc
seconds|Seconds|Másodperc
duration|Duration|Időtartam
minute|Time (minute of day)|Időpont (napon belüli perc)
clock|Time of day|Időpont
start|Start|Kezdet
end|End|Vége
sound|Sound|Hang
action|Action|Művelet
notify|Notify|Értesítés
break|Break|Szünet
cover|Cover|Eltakarás
minimize|Minimize|Kis méret
close|Close|Bezárás
enforce|Enforce restriction|Korlátozás érvényesítése
close_confirmed|Closing confirmed on PC|Bezárás jóváhagyva a PC-n
grace_seconds|Grace period (seconds)|Türelmi idő (másodperc)
allowance_minutes|Extension (minutes)|Hosszabbítás (perc)
focus|Focus settings|Fókuszbeállítások
notification|Notification|Értesítés
budget|Budget|Keret
""";for(String row:source.split("\n")){String[] p=row.split("\\|");if(p.length==3)LABELS.put(p[0],new String[]{p[1],p[2]});}}
    static String label(MainActivity a,String key){String[] found=LABELS.get(key);if(found!=null)return a.t(found[0],found[1]);if(key.isEmpty())return a.t("Settings","Beállítások");String readable=key.replace('_',' ');return Character.toUpperCase(readable.charAt(0))+readable.substring(1);}
}
