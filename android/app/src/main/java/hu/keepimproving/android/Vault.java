package hu.keepimproving.android;

import android.content.Context;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.util.Base64;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

final class Vault {
    private static final String ALIAS="keep-improving-sync-v1";
    private static SecretKey key() throws Exception {
        KeyStore store=KeyStore.getInstance("AndroidKeyStore"); store.load(null);
        if (!store.containsAlias(ALIAS)) {
            KeyGenerator generator=KeyGenerator.getInstance("AES","AndroidKeyStore");
            generator.init(new KeyGenParameterSpec.Builder(ALIAS,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());
            generator.generateKey();
        }
        return (SecretKey)store.getKey(ALIAS,null);
    }
    static String read(Context context) throws Exception {
        String value=context.getSharedPreferences("vault",0).getString("connection","");
        if (value.isEmpty()) return "";
        String[] parts=value.split(":");
        if (parts.length!=2) throw new IllegalStateException("Unreadable connection");
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Base64.getDecoder().decode(parts[0])));
        return new String(cipher.doFinal(Base64.getDecoder().decode(parts[1])),StandardCharsets.UTF_8);
    }
    static void write(Context context,String code) throws Exception {
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding"); cipher.init(Cipher.ENCRYPT_MODE,key());
        String value=Base64.getEncoder().encodeToString(cipher.getIV())+":"+Base64.getEncoder().encodeToString(cipher.doFinal(code.getBytes(StandardCharsets.UTF_8)));
        if (!context.getSharedPreferences("vault",0).edit().putString("connection",value).commit()) throw new IllegalStateException("Storage unavailable");
    }
    @android.annotation.SuppressLint("ApplySharedPref") // Background worker; disconnect must be durable before cache removal.
    static void clear(Context context) {
        if(!context.getSharedPreferences("vault",0).edit().remove("connection").commit()) throw new IllegalStateException("Storage unavailable");
    }
}
