package hu.keepimproving.android;
import android.graphics.*;
import android.graphics.drawable.BitmapDrawable;
import org.junit.*;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;
import org.robolectric.*;
import org.robolectric.annotation.*;
import org.json.*;
import java.io.ByteArrayOutputStream;

@RunWith(RobolectricTestRunner.class) @Config(sdk=35) @GraphicsMode(GraphicsMode.Mode.NATIVE)
public class RemoteDisplayTest {
    private String png(int width){Bitmap bitmap=Bitmap.createBitmap(width,width,Bitmap.Config.ARGB_8888);bitmap.eraseColor(Color.GREEN);ByteArrayOutputStream out=new ByteArrayOutputStream();bitmap.compress(Bitmap.CompressFormat.PNG,100,out);bitmap.recycle();return android.util.Base64.encodeToString(out.toByteArray(),android.util.Base64.NO_WRAP);}
    @Test public void remoteAppAndWebsiteIconsUseCanonicalKeysAndRejectOversizedImages()throws Exception{
        var c=RuntimeEnvironment.getApplication();String encoded=png(48);JSONObject companion=new JSONObject().put("icons",new JSONObject().put("app:editor.exe",encoded).put("site:example.com",encoded));
        assertTrue(RemoteIcons.from(c,companion,"app","C:\\Apps\\Editor.exe") instanceof BitmapDrawable);
        assertTrue(RemoteIcons.from(c,companion,"site","www.example.com") instanceof BitmapDrawable);
        companion.getJSONObject("icons").put("app:bad.exe",png(256));assertNull(RemoteIcons.from(c,companion,"app","bad.exe"));
        companion.getJSONObject("icons").put("app:bad.exe","invalid");assertNull(RemoteIcons.from(c,companion,"app","bad.exe"));
    }
    @Test public void remoteFocusUsesElapsedTimeAndPausedValueWithoutGoingNegative()throws Exception{
        JSONObject state=new JSONObject().put("running",true).put("remaining",60).put("at",100000);
        assertEquals(45000,RemoteFocus.remaining(state,115000));assertEquals(0,RemoteFocus.remaining(state,200000));
        state.put("running",false);assertEquals(60000,RemoteFocus.remaining(state,200000));
    }
}
