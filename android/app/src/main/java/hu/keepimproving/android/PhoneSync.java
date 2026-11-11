package hu.keepimproving.android;

import android.content.Context;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import javax.net.ssl.HttpsURLConnection;
import org.json.JSONObject;

final class PhoneSync {
    static final String ENDPOINT="https://jtvdbqwmejrckjejjrdl.supabase.co/functions/v1/statistics-sync";
    enum Result { DONE, NOT_CONNECTED, WAIT, UNAVAILABLE, INVALID_CODE, LIMIT, INVALID_DATA }
    static void dirty(PhoneStore store){store.put("cloud_changes",Long.toString(store.number("cloud_changes",0)+1));}
    static Result run(Context context,PhoneStore store) {
        HttpsURLConnection connection=null;
        try {
            String code=Vault.read(context);
            if(code.isEmpty()) return Result.NOT_CONNECTED;
            long now=System.currentTimeMillis();
            if(now<store.number("sync_after",0)) return Result.WAIT;
            // Persistent across restarts and code changes; also bounds failing/manual attempts.
            store.put("sync_after",Long.toString(now+15000));
            long changes=store.number("cloud_changes",0);
            boolean upload=store.number("cloud_revision",0)==0||changes!=store.number("cloud_published_changes",-1)||now-store.number("cloud_uploaded_at",0)>=900000;
            String device=store.device(),revision=store.get("cloud_revision","1");
            JSONObject snapshot=upload?SyncProtocol.validate(store.snapshot(code),code):null;
            if(snapshot!=null)revision=Long.toString(snapshot.getLong("revision"));
            JSONObject body=new JSONObject().put("format",SyncProtocol.CLOUD).put("device",device).put("revision",revision).put("known",store.known())
                .put("payload",upload?SyncCrypto.seal(snapshot.toString().getBytes(StandardCharsets.UTF_8),code,device,revision):JSONObject.NULL);
            for(int attempt=0;attempt<2;attempt++){
            connection=(HttpsURLConnection)new URL(ENDPOINT).openConnection();
            connection.setInstanceFollowRedirects(false); connection.setConnectTimeout(12000); connection.setReadTimeout(12000);
            connection.setRequestMethod("POST"); connection.setDoOutput(true);
            connection.setRequestProperty("Authorization","Bearer "+SyncCrypto.authorization(code));
            connection.setRequestProperty("Content-Type","application/json"); connection.setRequestProperty("Accept","application/json");
            connection.setRequestProperty("X-GameTime-Sync","event-driven-v2"); connection.setRequestProperty("User-Agent","KeepImprovingAndroid/0.4.5");
            byte[] request=body.toString().getBytes(StandardCharsets.UTF_8); connection.setFixedLengthStreamingMode(request.length);
            try(var stream=connection.getOutputStream()) { stream.write(request); }
            int status=connection.getResponseCode();
            if(status!=200) {
                String retry=connection.getHeaderField("Retry-After");
                if(retry!=null&&retry.matches("[0-9]{1,8}")) store.put("sync_after",Long.toString(now+Math.max(15,Math.min(86400,Long.parseLong(retry)))*1000));
                if(status==401||status==403) return Result.INVALID_CODE;
                if(status==429||status==507) return Result.LIMIT;
                return Result.UNAVAILABLE;
            }
            if(connection.getContentLengthLong()>2*1024*1024) return Result.INVALID_DATA;
            ByteArrayOutputStream response=new ByteArrayOutputStream(); long deadline=android.os.SystemClock.elapsedRealtime()+20000;
            try(InputStream stream=connection.getInputStream()) {
                byte[] buf=new byte[8192]; int count;
                while((count=stream.read(buf))!=-1) {
                    if(response.size()+count>2*1024*1024||android.os.SystemClock.elapsedRealtime()>deadline) return Result.INVALID_DATA;
                    response.write(buf,0,count);
                }
            }
            JSONObject result=new JSONObject(response.toString(StandardCharsets.UTF_8.name()));
            if(result.optBoolean("need_upload")&&!upload&&attempt==0){
                connection.disconnect();connection=null;upload=true;
                snapshot=SyncProtocol.validate(store.snapshot(code),code);revision=Long.toString(snapshot.getLong("revision"));
                body.put("revision",revision).put("payload",SyncCrypto.seal(snapshot.toString().getBytes(StandardCharsets.UTF_8),code,device,revision));continue;
            }
            var entries=SyncProtocol.response(result,code,device);
            store.accept(entries,code); store.put("last_sync",Long.toString(System.currentTimeMillis()));
            if(upload){store.put("cloud_revision",revision);store.put("cloud_uploaded_at",Long.toString(now));store.put("cloud_published_changes",Long.toString(changes));}
            return Result.DONE;
            }
            return Result.INVALID_DATA;
        } catch(java.io.IOException e) { store.put("sync_after",Long.toString(System.currentTimeMillis()+60000));return Result.UNAVAILABLE; }
          catch(Exception e) { return Result.INVALID_DATA; }
        finally { if(connection!=null) connection.disconnect(); }
    }
}
