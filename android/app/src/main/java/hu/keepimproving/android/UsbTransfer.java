package hu.keepimproving.android;
import android.content.Intent;
import android.util.AtomicFile;
import android.widget.Toast;
import java.io.*;
import java.nio.charset.StandardCharsets;
import org.json.*;

/** Optional USB transport for the same authenticated ciphertext, without using cloud quota. */
final class UsbTransfer {
    static final String ACTION="hu.keepimproving.android.USB_SYNC";
    static boolean receive(MainActivity a,Intent intent){
        if(!ACTION.equals(intent.getAction()))return false;
        String extra=intent.getStringExtra("payload");a.setIntent(new Intent(a,MainActivity.class));
        if(extra!=null&&extra.length()>512*1024)return true;
        CollectionJob.LOAD.execute(()->{
            boolean success=false;
            try(PhoneStore store=new PhoneStore(a)){
                String raw=extra;
                if(raw==null){File dir=a.getExternalFilesDir("usb");if(dir==null)throw new IOException();File request=new File(dir,"request.json");if(request.length()>512*1024||request.length()<1)throw new IOException();try(FileInputStream stream=new FileInputStream(request)){byte[] bytes=new byte[(int)request.length()];int offset=0,count;while(offset<bytes.length&&(count=stream.read(bytes,offset,bytes.length-offset))>0)offset+=count;if(offset!=bytes.length)throw new IOException();raw=new String(bytes,StandardCharsets.UTF_8);}request.delete();}
                String code=Vault.read(a);if(code.isEmpty())throw new IllegalArgumentException();
                JSONArray entries=SyncProtocol.response(new JSONObject(raw),code,store.device());
                store.accept(entries,code);CollectionJob.WORK.submit(()->PhoneRuntime.refresh(a,false)).get();
                JSONObject snapshot=store.snapshot(code);String revision=Long.toString(snapshot.getLong("revision"));
                JSONObject reply=new JSONObject().put("device",store.device()).put("revision",revision).put("payload",SyncCrypto.seal(snapshot.toString().getBytes(StandardCharsets.UTF_8),code,store.device(),revision));
                File dir=a.getExternalFilesDir("usb");if(dir==null)throw new IOException();AtomicFile file=new AtomicFile(new File(dir,"response.json"));FileOutputStream out=null;try{out=file.startWrite();out.write(reply.toString().getBytes(StandardCharsets.UTF_8));file.finishWrite(out);}catch(Exception error){if(out!=null)file.failWrite(out);throw error;}
                store.put("last_sync",Long.toString(System.currentTimeMillis()));store.put("last_local_sync",Long.toString(System.currentTimeMillis()));success=true;
            }catch(Exception ignored){/* An invalid or replayed cross-group file never changes local rules. */}
            boolean done=success;a.runOnUiThread(()->{Toast.makeText(a,done?a.t("Encrypted USB sync complete.","A titkosított USB-szinkron elkészült."):a.t("USB sync could not be verified. Keep the existing pairing code on both devices.","Az USB-szinkron nem ellenőrizhető. Mindkét eszközön ugyanaz a kapcsolódási kód szükséges."),Toast.LENGTH_LONG).show();a.load(false,null);});
        });return true;
    }
}
