package hu.keepimproving.android;

import org.json.JSONArray;
import org.json.JSONObject;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.charset.CodingErrorAction;
import java.time.LocalDate;
import java.util.HashSet;

public final class SyncProtocol {
    public static final String STATISTICS="GameTimeMonitor.statistics.v1", CLOUD="GameTimeMonitor.sync.v2";
    static void text(String value,int max) {
        if(value.isEmpty()||value.length()>max) throw new IllegalArgumentException("Invalid text");
    }
    static void date(String day) { if(!LocalDate.parse(day).toString().equals(day)) throw new IllegalArgumentException("Invalid date"); }
    public static JSONObject validate(JSONObject value,String code) throws Exception {
        if(!value.getString("format").equals(STATISTICS)||!value.getString("group").equals(code)||!value.getString("device").matches("[0-9a-f]{32}"))
            throw new IllegalArgumentException("Invalid snapshot");
        Object revision=value.get("revision");
        if(!(revision instanceof Long || revision instanceof Integer)||((Number)revision).longValue()<=0) throw new IllegalArgumentException("Invalid revision");
        text(value.getString("name"),80); date(value.getString("started"));
        validateRows(value.getJSONArray("rows"),false);
        if(value.has("activity")) { date(value.getString("activity_started")); validateRows(value.getJSONArray("activity"),true); }
        return value;
    }
    private static void validateRows(JSONArray rows,boolean activity) throws Exception {
        if(rows.length()>100000) throw new IllegalArgumentException("Too many rows");
        HashSet<String> seen=new HashSet<>();
        for(int i=0;i<rows.length();i++) {
            JSONArray row=rows.getJSONArray(i);
            if(row.length()!=5) throw new IllegalArgumentException("Invalid row");
            String day=row.getString(0); date(day);
            String a=row.getString(1),b=row.getString(2),c=row.getString(3);
            if(activity) {
                if(!a.equals("app")&&!a.equals("site")) throw new IllegalArgumentException("Invalid activity");
                text(b,512); text(c,512);
            } else { text(a,512); text(b,512); if(c.length()>80) throw new IllegalArgumentException("Invalid source"); }
            Object number=row.get(4);
            if(!(number instanceof Number)) throw new IllegalArgumentException("Invalid time");
            double seconds=((Number)number).doubleValue();
            if(!Double.isFinite(seconds)||seconds<=0||seconds>172800) throw new IllegalArgumentException("Invalid time");
            // Length-prefixed keys avoid ambiguity in arbitrary activity identifiers.
            String key=day+":"+a.length()+":"+a+(activity?":"+b:"");
            if(!seen.add(key)) throw new IllegalArgumentException("Duplicate activity");
        }
    }
    public static JSONObject decode(JSONObject entry,String code) throws Exception {
        String device=entry.getString("device"),revision=entry.getString("revision");
        byte[] raw=SyncCrypto.open(entry.getString("payload"),code,device,revision);
        String json=StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(raw)).toString();
        JSONObject value=validate(new JSONObject(json),code);
        if(!value.getString("device").equals(device)||value.getLong("revision")!=Long.parseLong(revision)) throw new IllegalArgumentException("Mismatched snapshot");
        return value;
    }
    public static JSONArray response(JSONObject result,String code,String local) throws Exception {
        if(!result.getString("format").equals(CLOUD)||result.get("need_upload")!=Boolean.FALSE) throw new IllegalArgumentException("Invalid response");
        JSONArray entries=result.getJSONArray("snapshots");
        if(entries.length()>20) throw new IllegalArgumentException("Too many devices");
        HashSet<String> seen=new HashSet<>();
        for(int i=0;i<entries.length();i++) {
            JSONObject value=decode(entries.getJSONObject(i),code); String device=value.getString("device");
            if(device.equals(local)||!seen.add(device)) throw new IllegalArgumentException("Duplicate device");
        }
        return entries;
    }
}
