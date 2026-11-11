package hu.keepimproving.android;
import java.util.*;
/** Subtract the union of covering intervals, never charge the obscured application. */
final class CoverageLedger {
    record Interval(long start,long end){}
    static List<Interval> parts(List<Interval> covers,long start,long end){List<Interval> result=new ArrayList<>(),sorted=new ArrayList<>(covers);sorted.sort(Comparator.comparingLong(Interval::start));long cursor=start;for(var cover:sorted){if(cover.end()<=cursor)continue;if(cover.start()>=end)break;if(cover.start()>cursor)result.add(new Interval(cursor,Math.min(end,cover.start())));cursor=Math.max(cursor,cover.end());if(cursor>=end)break;}if(cursor<end)result.add(new Interval(cursor,end));return result;}
    static long visible(List<Interval> covers,long start,long end){long hidden=0,cursor=start;List<Interval> sorted=new ArrayList<>(covers);sorted.sort(Comparator.comparingLong(Interval::start));for(var cover:sorted){long from=Math.max(cursor,cover.start()),to=Math.min(end,cover.end());if(to>from){hidden+=to-from;cursor=to;}}return Math.max(0,end-start-hidden);}
}
