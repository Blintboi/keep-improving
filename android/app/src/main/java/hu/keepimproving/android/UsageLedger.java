package hu.keepimproving.android;

import java.time.Instant;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;

/** One foreground application at a time; no double counting during activity switches. */
public final class UsageLedger {
    public record Event(long time, int type, String pkg, String activity) {}
    public record Slice(String day, String pkg, long millis,long start) {public Slice(String day,String pkg,long millis){this(day,pkg,millis,0);}}
    public record State(long cursor, String pkg, String activity) {}
    public record Result(State state, List<Slice> slices) {}
    public static Result collect(State previous, List<Event> events, long end, ZoneId zone) {
        return collect(previous,events,end,zone,0);
    }
    public static Result collect(State previous, List<Event> events, long end, ZoneId zone,int renewal) {
        long cursor = previous.cursor();
        String pkg = previous.pkg(), activity = previous.activity();
        List<Slice> slices = new ArrayList<>();
        for (Event e : events) {
            if (e.time < cursor || e.time >= end) continue;
            // A startup without a closing event has an unknown shutdown time.
            // Do not charge the offline interval to the last foreground app.
            if (e.type != 27) split(slices, pkg, cursor, e.time, zone,renewal);
            cursor = e.time;
            if (e.type == 1) { pkg = e.pkg; activity = e.activity; }
            else if (e.type == 2 && e.pkg.equals(pkg) && e.activity.equals(activity)) {
                pkg = ""; activity = "";
            } else if (e.type == 16 || e.type == 17 || e.type == 26 || e.type == 27) {
                // Screen off, keyguard, shutdown and startup end any open session.
                pkg = ""; activity = "";
            }
        }
        split(slices, pkg, cursor, end, zone,renewal);
        return new Result(new State(Math.max(cursor, end), pkg, activity), slices);
    }
    private static void split(List<Slice> out, String pkg, long start, long end, ZoneId zone,int renewal) {
        if (pkg.isEmpty()) return;
        while (start < end) {
            var day = java.time.LocalDate.parse(PhoneRules.day(start,renewal,zone));
            long next = Math.min(end,PhoneRules.nextDay(start,renewal,zone));
            if (next <= start) break;
            out.add(new Slice(day.toString(), pkg, next - start,start));
            start = next;
        }
    }
}
