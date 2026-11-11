package hu.keepimproving.android;
import android.graphics.*;
import android.graphics.drawable.Drawable;
/** Small native vector icons; no image downloads or background work. */
final class PhoneIcons extends Drawable {
    final String kind;final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);int color;
    PhoneIcons(String kind,int color){this.kind=kind;this.color=color;setBounds(0,0,24,24);}
    void path(Canvas c,float... xy){Path p=new Path();p.moveTo(xy[0],xy[1]);for(int i=2;i<xy.length;i+=2)p.lineTo(xy[i],xy[i+1]);c.drawPath(p,paint);}
    @Override public void draw(Canvas canvas){int save=canvas.save();Rect b=getBounds();canvas.translate(b.left,b.top);canvas.scale(b.width()/24f,b.height()/24f);paint.setColor(color);paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(1.8f);paint.setStrokeCap(Paint.Cap.ROUND);paint.setStrokeJoin(Paint.Join.ROUND);
        switch(kind){
            case "menu"->{path(canvas,4,6,20,6);path(canvas,4,12,20,12);path(canvas,4,18,20,18);}
            case "chart"->{path(canvas,3,3,3,21,22,21);path(canvas,7,17,7,12);path(canvas,12,17,12,6);path(canvas,17,17,17,9);}
            case "apps"->{for(int x:new int[]{3,14})for(int y:new int[]{3,14})canvas.drawRoundRect(x,y,x+7,y+7,1.5f,1.5f,paint);}
            case "budget","clock"->{canvas.drawCircle(12,12,9,paint);path(canvas,12,6,12,12,16,14);}
            case "focus"->{canvas.drawCircle(12,13,8,paint);canvas.drawCircle(12,13,3,paint);path(canvas,9,2,15,2);path(canvas,12,2,12,5);}
            case "bell"->{Path p=new Path();p.moveTo(5,17);p.lineTo(7,14);p.lineTo(7,9);p.cubicTo(7,2,17,2,17,9);p.lineTo(17,14);p.lineTo(19,17);p.close();canvas.drawPath(p,paint);canvas.drawArc(10,18,14,22,0,180,false,paint);}
            case "settings"->{canvas.drawCircle(12,12,7,paint);canvas.drawCircle(12,12,2.5f,paint);for(int i=0;i<8;i++){double t=Math.PI*i/4;path(canvas,(float)(12+Math.cos(t)*7),(float)(12+Math.sin(t)*7),(float)(12+Math.cos(t)*10),(float)(12+Math.sin(t)*10));}}
            case "game"->{canvas.drawRoundRect(2,6,22,18,4,4,paint);path(canvas,6,12,10,12);path(canvas,8,10,8,14);canvas.drawCircle(16,11,.6f,paint);canvas.drawCircle(19,14,.6f,paint);}
            case "site","browser"->{canvas.drawCircle(12,12,9,paint);canvas.drawOval(8,3,16,21,paint);path(canvas,3,12,21,12);}
            case "computer"->{canvas.drawRoundRect(2,3,22,17,2,2,paint);path(canvas,12,17,12,21);path(canvas,7,21,17,21);}
            case "phone"->{canvas.drawRoundRect(6,2,18,22,2,2,paint);path(canvas,10,18,14,18);}
            case "plus"->{path(canvas,12,4,12,20);path(canvas,4,12,20,12);}
            case "edit"->{path(canvas,4,16,4,21,9,20,21,8,16,3,4,16);path(canvas,14,5,19,10);}
            case "trash"->{path(canvas,4,6,20,6);path(canvas,9,6,9,3,15,3,15,6);path(canvas,6,6,7,21,17,21,18,6);path(canvas,10,10,10,17);path(canvas,14,10,14,17);}
            case "play"->path(canvas,7,3,21,12,7,21,7,3);
            case "pause"->{path(canvas,7,4,7,20);path(canvas,17,4,17,20);}
            case "stop"->canvas.drawRoundRect(5,5,19,19,2,2,paint);
            case "sync"->{canvas.drawArc(3,3,21,21,35,145,false,paint);canvas.drawArc(3,3,21,21,215,145,false,paint);path(canvas,3,14,3,20,9,20);path(canvas,15,4,21,4,21,10);}
            case "shield"->{path(canvas,12,2,21,6,20,15,17,19,12,22,7,19,4,15,3,6,12,2);path(canvas,8,12,11,15,16,9);}
            case "check"->path(canvas,4,12,10,18,21,5);
            case "export"->{path(canvas,4,14,4,21,20,21,20,14);path(canvas,12,3,12,16);path(canvas,7,11,12,16,17,11);}
            default->{canvas.drawCircle(12,12,9,paint);paint.setStyle(Paint.Style.FILL);canvas.drawCircle(12,12,2,paint);}
        }canvas.restoreToCount(save);
    }
    @Override public void setAlpha(int value){paint.setAlpha(value);}@Override public void setColorFilter(ColorFilter filter){paint.setColorFilter(filter);}@Override public int getOpacity(){return PixelFormat.TRANSLUCENT;}
}
