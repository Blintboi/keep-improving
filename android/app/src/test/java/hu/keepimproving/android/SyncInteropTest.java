package hu.keepimproving.android;
import org.junit.Test;
import org.json.*;
import static org.junit.Assert.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

public class SyncInteropTest {
    private JSONObject fixture() throws Exception {try(var stream=getClass().getResourceAsStream("/interop.json")){return new JSONObject(new String(stream.readAllBytes(),StandardCharsets.UTF_8));}}
    @Test public void decryptsDesktopAndExportsAndroidSnapshot() throws Exception {
        JSONObject fixture=fixture();String code=fixture.getString("code");JSONObject entry=fixture.getJSONObject("entry");
        assertEquals(fixture.getString("authorization"),SyncCrypto.authorization(code));
        JSONObject snapshot=SyncProtocol.decode(entry,code);
        assertEquals("Kísérleti számítógép",snapshot.getString("name"));
        snapshot.put("name","Android próba");
        String payload=SyncCrypto.seal(snapshot.toString().getBytes(StandardCharsets.UTF_8),code,entry.getString("device"),entry.getString("revision"));
        Path output=Paths.get(System.getProperty("keepImprovingReports","build"),"interop-export.json");Files.createDirectories(output.getParent());
        Files.write(output,new JSONObject().put("code",code).put("entry",new JSONObject(entry.toString()).put("payload",payload)).toString().getBytes(StandardCharsets.UTF_8));
    }
    @Test public void rejectsWrongCodeChangedDeviceAndChangedRevision() throws Exception {
        JSONObject fixture=fixture(),entry=fixture.getJSONObject("entry");String code=fixture.getString("code");
        assertThrows(Exception.class,()->SyncProtocol.decode(entry,"22222222222222222222222222222222"));
        for(String field:List.of("device","revision")) {
            JSONObject bad=new JSONObject(entry.toString()).put(field,field.equals("device")?"33333333333333333333333333333333":"2");
            assertThrows(Exception.class,()->SyncProtocol.decode(bad,code));
        }
    }
    @Test public void rejectsDuplicateDevicesAndLocalEcho() throws Exception {
        JSONObject fixture=fixture(),entry=fixture.getJSONObject("entry");String code=fixture.getString("code");
        JSONObject response=new JSONObject().put("format",SyncProtocol.CLOUD).put("need_upload",false).put("snapshots",new JSONArray().put(entry).put(entry));
        assertThrows(Exception.class,()->SyncProtocol.response(response,code,"00000000000000000000000000000000"));
        response.put("snapshots",new JSONArray().put(entry));assertThrows(Exception.class,()->SyncProtocol.response(response,code,entry.getString("device")));
    }
    @Test public void rejectsInvalidRowsBeforeImport() throws Exception {
        JSONObject fixture=fixture();String code=fixture.getString("code");JSONObject base=SyncProtocol.decode(fixture.getJSONObject("entry"),code);
        for(Object seconds:List.of(-1,172801,"60")) {
            JSONObject bad=new JSONObject(base.toString());bad.getJSONArray("rows").getJSONArray(0).put(4,seconds);
            assertThrows(Exception.class,()->SyncProtocol.validate(bad,code));
        }
        base.getJSONArray("rows").put(base.getJSONArray("rows").getJSONArray(0));assertThrows(Exception.class,()->SyncProtocol.validate(base,code));
    }
    @Test public void browserWebsitesDoNotDoubleCount() throws Exception {
        JSONObject fixture=fixture();JSONObject snapshot=SyncProtocol.decode(fixture.getJSONObject("entry"),fixture.getString("code"));
        assertEquals(1800,Statistics.rows(snapshot,"all").stream().mapToDouble(Statistics.Row::seconds).sum(),.001);
        assertEquals(1200,Statistics.rows(snapshot,"apps").stream().mapToDouble(Statistics.Row::seconds).sum(),.001);
        assertEquals(1500,Statistics.rows(snapshot,"websites").stream().mapToDouble(Statistics.Row::seconds).sum(),.001);
        assertEquals(600,Statistics.rows(snapshot,"games").stream().mapToDouble(Statistics.Row::seconds).sum(),.001);
    }
    @Test public void rejectsOversizedEncryptedEnvelopes() {
        assertThrows(Exception.class,()->SyncCrypto.open("A".repeat(SyncCrypto.MAX_SEALED*2),"11111111111111111111111111111111","11111111111111111111111111111111","1"));
    }
}
