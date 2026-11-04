package hu.keepimproving.android;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.SecureRandom;
import java.util.Arrays;
import java.util.Base64;
import java.util.zip.Deflater;
import java.util.zip.Inflater;
import javax.crypto.Cipher;
import javax.crypto.Mac;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;

/** Byte-for-byte compatible with gametime/statistics_cloud.py. */
public final class SyncCrypto {
    public static final int MAX_RAW = 16 * 1024 * 1024, MAX_SEALED = 512 * 1024;
    public static String normalize(String code) {
        String result = code.replace("-", "").replace(" ", "").trim().toLowerCase(java.util.Locale.ROOT);
        if (!result.matches("[0-9a-f]{32}")) throw new IllegalArgumentException("Invalid connection code");
        return result;
    }
    private static byte[] key(String code, String label) throws GeneralSecurityException {
        code = normalize(code);
        byte[] secret = new byte[16];
        for (int i=0; i<16; i++) secret[i]=(byte)Integer.parseInt(code.substring(i*2,i*2+2),16);
        Mac hmac = Mac.getInstance("HmacSHA256");
        hmac.init(new SecretKeySpec(secret,"HmacSHA256"));
        return hmac.doFinal(("GameTimeMonitor/"+label+"/v1").getBytes(StandardCharsets.US_ASCII));
    }
    public static String authorization(String code) throws GeneralSecurityException {
        StringBuilder value = new StringBuilder();
        for (byte b : key(code,"authorization")) value.append(String.format(java.util.Locale.ROOT,"%02x",b & 255));
        return value.toString();
    }
    private static byte[] aad(String device, String revision) {
        if (!device.matches("[0-9a-f]{32}") || !revision.matches("[1-9][0-9]{0,18}") || Long.parseLong(revision)<=0)
            throw new IllegalArgumentException("Invalid snapshot identity");
        return ("GameTimeMonitor.sync.v1:"+device+":"+revision).getBytes(StandardCharsets.US_ASCII);
    }
    public static String seal(byte[] raw, String code, String device, String revision) throws Exception {
        if (raw.length>MAX_RAW) throw new IllegalArgumentException("History too large");
        Deflater deflater = new Deflater();
        ByteArrayOutputStream compressed = new ByteArrayOutputStream();
        try {
            deflater.setInput(raw); deflater.finish(); byte[] buf = new byte[8192];
            while (!deflater.finished()) compressed.write(buf,0,deflater.deflate(buf));
        } finally { deflater.end(); }
        byte[] nonce=new byte[12]; new SecureRandom().nextBytes(nonce);
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE,new SecretKeySpec(key(code,"encryption"),"AES"),new GCMParameterSpec(128,nonce));
        cipher.updateAAD(aad(device,revision));
        ByteArrayOutputStream envelope=new ByteArrayOutputStream();
        envelope.write(new byte[]{'G','T','M','1'}); envelope.write(nonce); envelope.write(cipher.doFinal(compressed.toByteArray()));
        if (envelope.size()>MAX_SEALED) throw new IllegalArgumentException("History too large");
        return Base64.getEncoder().encodeToString(envelope.toByteArray());
    }
    public static byte[] open(String payload, String code, String device, String revision) throws Exception {
        if (payload.length()>4*((MAX_SEALED+2)/3)) throw new IllegalArgumentException("Invalid snapshot");
        byte[] value=Base64.getDecoder().decode(payload);
        if (value.length<32 || value.length>MAX_SEALED || value[0]!='G'||value[1]!='T'||value[2]!='M'||value[3]!='1')
            throw new IllegalArgumentException("Invalid snapshot");
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE,new SecretKeySpec(key(code,"encryption"),"AES"),new GCMParameterSpec(128,Arrays.copyOfRange(value,4,16)));
        cipher.updateAAD(aad(device,revision));
        Inflater inflater=new Inflater(); ByteArrayOutputStream result=new ByteArrayOutputStream();
        try {
            inflater.setInput(cipher.doFinal(Arrays.copyOfRange(value,16,value.length))); byte[] buf=new byte[8192];
            while (!inflater.finished()) {
                int count=inflater.inflate(buf);
                if (count==0 || result.size()+count>MAX_RAW) throw new IllegalArgumentException("Invalid compressed snapshot");
                result.write(buf,0,count);
            }
            if (inflater.getRemaining()!=0) throw new IllegalArgumentException("Trailing data");
            return result.toByteArray();
        } finally { inflater.end(); }
    }
}
