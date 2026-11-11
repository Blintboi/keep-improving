package hu.keepimproving.android;
import org.junit.Test;
import static org.junit.Assert.*;
import org.json.*;
import java.time.*;
import java.util.*;
public class PhoneFocusTest {
    final long base=1760000000000L;
    final ZoneId zone=ZoneId.of("Europe/Budapest");
    PhoneFocus.Time time(long minutes){return new PhoneFocus.Time(base+minutes*60000,1000+minutes*60000,2);}
    @Test public void completionAfterProcessDeathIsCountedOnceAndBreakContinues()throws Exception {var c=PhoneFocus.defaults();var s=PhoneFocus.state(c);PhoneFocus.command(s,c,"start",time(0));s=PhoneRules.copy(s);var done=new ArrayList<PhoneFocus.Completion>();var notes=new ArrayList<PhoneRules.Notice>();PhoneFocus.advance(s,c,time(27),0,zone,done,notes);assertEquals(1,done.size());assertEquals("short",s.getString("phase"));assertEquals(3*60000,s.getLong("remaining"));PhoneFocus.advance(s,c,time(28),0,zone,done,notes);assertEquals(1,done.size());PhoneFocus.advance(s,c,time(45),0,zone,done,notes);assertFalse(s.getBoolean("running"));assertEquals("work",s.getString("phase"));assertEquals(2,notes.size());assertEquals(1,done.size());}
    @Test public void clockChangeWhileBootedUsesMonotonicTime(){var c=PhoneFocus.defaults();var s=PhoneFocus.state(c);PhoneFocus.command(s,c,"start",time(0));assertEquals(24*60000,PhoneFocus.remaining(s,new PhoneFocus.Time(base-86400000,61000,2)));}
    @Test public void rebootUsesStoredWallDeadline(){var c=PhoneFocus.defaults();var s=PhoneFocus.state(c);PhoneFocus.command(s,c,"start",time(0));assertEquals(15*60000,PhoneFocus.remaining(s,new PhoneFocus.Time(base+600000,500,3)));}
    @Test public void pauseDoesNotLoseElapsedTime()throws Exception {var c=PhoneFocus.defaults();var s=PhoneFocus.state(c);PhoneFocus.command(s,c,"start",time(0));PhoneFocus.advance(s,c,time(10),0,zone,new ArrayList<>(),new ArrayList<>());PhoneFocus.command(s,c,"pause",time(10));assertEquals(15*60000,PhoneFocus.remaining(s,time(50)));PhoneFocus.command(s,c,"start",time(50));assertEquals(10*60000,PhoneFocus.remaining(s,time(55)));}
    @Test public void zeroBreakAndSingleTimerDoNotLoopForever()throws Exception {for(int cycles:new int[]{0,4}){var c=PhoneFocus.defaults().put("cycles",cycles).put("short",0);var s=PhoneFocus.state(c);PhoneFocus.command(s,c,"start",time(0));var done=new ArrayList<PhoneFocus.Completion>();PhoneFocus.advance(s,c,time(10000),0,zone,done,new ArrayList<>());assertFalse(s.getBoolean("running"));assertEquals(1,done.size());}}
    @Test public void fourthRoundSelectsLongBreak()throws Exception {var c=PhoneFocus.defaults();var s=PhoneFocus.state(c).put("round",3);PhoneFocus.command(s,c,"start",time(0));PhoneFocus.advance(s,c,time(25),0,zone,new ArrayList<>(),new ArrayList<>());assertEquals("long",s.getString("phase"));assertEquals(15*60000,s.getLong("remaining"));}
}
