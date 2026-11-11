package hu.keepimproving.android;

import android.os.Bundle;
import android.view.View;
import android.view.ViewGroup;
import android.view.ViewTreeObserver;
import android.widget.ScrollView;

/** Keep the visible section in place across a layout or content replacement. */
final class ScrollPosition {
    final int y,index,offset;final String anchor;
    ScrollPosition(int y,int index,int offset){this(y,index,offset,null);}
    ScrollPosition(int y,int index,int offset,String anchor){this.y=y;this.index=index;this.offset=offset;this.anchor=anchor;}
    static ScrollView parent(View view){while(view!=null){if(view instanceof ScrollView s)return s;view=view.getParent() instanceof View v?v:null;}return null;}
    static ScrollPosition capture(ScrollView scroll){
        int y=scroll.getScrollY(),index=-1,offset=0;String anchor=null;
        if(scroll.getChildCount()>0&&scroll.getChildAt(0) instanceof ViewGroup content)
            for(int i=0;i<content.getChildCount();i++){View v=content.getChildAt(i);if(v.getVisibility()!=View.GONE&&v.getBottom()>y){index=i;offset=v.getTop()-y;if(v.getTag() instanceof String tag)anchor=tag;break;}}
        return new ScrollPosition(y,index,offset,anchor);
    }
    Bundle save(){Bundle b=new Bundle();b.putInt("y",y);b.putInt("index",index);b.putInt("offset",offset);b.putString("anchor",anchor);return b;}
    static ScrollPosition read(Bundle b){return new ScrollPosition(b.getInt("y"),b.getInt("index",-1),b.getInt("offset"),b.getString("anchor"));}
    void restore(ScrollView scroll,Runnable restored){
        scroll.getViewTreeObserver().addOnPreDrawListener(new ViewTreeObserver.OnPreDrawListener(){
            public boolean onPreDraw(){
                scroll.getViewTreeObserver().removeOnPreDrawListener(this);
                int target=y;
                if(scroll.getChildCount()>0&&scroll.getChildAt(0) instanceof ViewGroup content){
                    View section=anchor!=null?content.findViewWithTag(anchor):index>=0&&index<content.getChildCount()?content.getChildAt(index):null;
                    if(section!=null&&section.getVisibility()!=View.GONE)target=section.getTop()-offset;
                }
                scroll.scrollTo(0,Math.max(0,target));restored.run();return true;
            }
        });scroll.requestLayout();scroll.invalidate();
    }
    static void change(View source,Runnable action){
        ScrollView scroll=parent(source);ScrollPosition before=scroll!=null&&scroll.isLaidOut()?capture(scroll):null;
        View content=scroll!=null&&scroll.getChildCount()>0?scroll.getChildAt(0):null;
        action.run();if(before!=null&&scroll.isAttachedToWindow()&&scroll.getChildCount()>0&&scroll.getChildAt(0)==content)before.restore(scroll,()->{});
    }
}
