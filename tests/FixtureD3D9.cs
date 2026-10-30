// Synthetic Direct3D9 fixture for the local overlay smoke test. No real game is touched.
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using System.Drawing;
using System.Drawing.Imaging;

static class Fixture {
    [DllImport("d3d9.dll")] static extern IntPtr Direct3DCreate9(uint version);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr window);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [StructLayout(LayoutKind.Sequential)] struct Presentation {
        public uint Width,Height,Format,Count,MultiSample,Quality,SwapEffect;
        public IntPtr Window;
        public int Windowed,AutoDepth;
        public uint DepthFormat,Flags,Refresh,Interval;
    }
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int CreateDevice(IntPtr self,uint adapter,uint type,IntPtr window,uint behavior,ref Presentation presentation,out IntPtr device);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int Present(IntPtr self,IntPtr a,IntPtr b,IntPtr c,IntPtr d);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int Clear(IntPtr self,uint count,IntPtr rects,uint flags,uint color,float z,uint stencil);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int Scene(IntPtr self);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int SetFVF(IntPtr self,uint value);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int DrawUP(IntPtr self,uint type,uint count,IntPtr data,uint stride);
    [StructLayout(LayoutKind.Sequential)] struct Vertex {public float X,Y,Z,Rhw; public uint Color;}
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate uint Release(IntPtr self);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int GetBackBuffer(IntPtr self,uint swap,uint index,uint type,out IntPtr surface);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int CreateSurface(IntPtr self,uint width,uint height,uint format,uint pool,out IntPtr surface,IntPtr shared);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int GetTargetData(IntPtr self,IntPtr render,IntPtr destination);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int GetFrontData(IntPtr self,uint swap,IntPtr destination);
    [StructLayout(LayoutKind.Sequential)] struct Locked {public int Pitch; public IntPtr Bits;}
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int LockSurface(IntPtr self,out Locked rect,IntPtr area,uint flags);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int UnlockSurface(IntPtr self);
    static void Capture(IntPtr device,int width,int height,string file,bool front) {
        IntPtr back=IntPtr.Zero,copy=IntPtr.Zero;
        try {
            int hr=Method<GetBackBuffer>(device,18)(device,0,0,0,out back); if(hr<0) throw new Exception("GetBackBuffer "+hr.ToString("X8"));
            hr=Method<CreateSurface>(device,36)(device,(uint)width,(uint)height,front?21u:22u,2,out copy,IntPtr.Zero); if(hr<0) throw new Exception("CreateSurface "+hr.ToString("X8"));
            hr=front?Method<GetFrontData>(device,33)(device,0,copy):Method<GetTargetData>(device,32)(device,back,copy); if(hr<0) throw new Exception("Capture frame "+hr.ToString("X8"));
            Locked source; hr=Method<LockSurface>(copy,13)(copy,out source,IntPtr.Zero,0x10); if(hr<0) throw new Exception("LockRect "+hr.ToString("X8"));
            try {
                using(var bitmap=new Bitmap(width,height,PixelFormat.Format32bppRgb)) {
                    var target=bitmap.LockBits(new Rectangle(0,0,width,height),ImageLockMode.WriteOnly,PixelFormat.Format32bppRgb);
                    try { byte[] row=new byte[width*4]; for(int y=0;y<height;y++) {Marshal.Copy(IntPtr.Add(source.Bits,y*source.Pitch),row,0,row.Length); Marshal.Copy(row,0,IntPtr.Add(target.Scan0,y*target.Stride),row.Length);} }
                    finally {bitmap.UnlockBits(target);} bitmap.Save(file,ImageFormat.Png);
                }
            } finally {Method<UnlockSurface>(copy,14)(copy);}
        } finally {if(copy!=IntPtr.Zero) Method<Release>(copy,2)(copy); if(back!=IntPtr.Zero) Method<Release>(back,2)(back);}
    }
    static T Method<T>(IntPtr obj,int index) where T:class {
        IntPtr vtable=Marshal.ReadIntPtr(obj); IntPtr ptr=Marshal.ReadIntPtr(vtable,index*IntPtr.Size);
        return Marshal.GetDelegateForFunctionPointer(ptr,typeof(T)) as T;
    }
    [STAThread] static int Main(string[] args) {
        string folder=args[0]; bool fullscreen=args.Length>1 && args[1]=="fullscreen";
        var form=new Form(); form.Text="Synthetic Direct3D notification fixture";
        form.StartPosition=FormStartPosition.Manual; form.FormBorderStyle=fullscreen?FormBorderStyle.None:FormBorderStyle.FixedSingle;
        form.Bounds=fullscreen?Screen.PrimaryScreen.Bounds:new Rectangle(40,40,900,650);
        form.TopMost=true; form.ShowInTaskbar=true;
        IntPtr direct=IntPtr.Zero, device=IntPtr.Zero; int width=0,height=0; var timer=new Timer(); timer.Interval=33;
        form.Shown+=(sender,e)=> {
            try {
                direct=Direct3DCreate9(32); if(direct==IntPtr.Zero) throw new Exception("Direct3DCreate9 failed");
                var size=fullscreen?Screen.PrimaryScreen.Bounds.Size:form.ClientSize; width=size.Width; height=size.Height;
                var pp=new Presentation {Width=(uint)size.Width,Height=(uint)size.Height,Format=22,Count=1,SwapEffect=fullscreen?1u:3u,Window=form.Handle,Windowed=fullscreen?0:1,Interval=1};
                int hr=Method<CreateDevice>(direct,16)(direct,0,1,form.Handle,0x20,ref pp,out device);
                if(hr<0 || device==IntPtr.Zero) throw new Exception("CreateDevice failed: "+hr.ToString("X8"));
                form.Activate(); SetForegroundWindow(form.Handle);
                File.WriteAllText(Path.Combine(folder,"ready"),form.Handle.ToInt64().ToString()); timer.Start();
            } catch(Exception ex) {File.WriteAllText(Path.Combine(folder,"error"),ex.ToString()); form.Close();}
        };
        timer.Tick+=(sender,e)=> {
            if(File.Exists(Path.Combine(folder,"stop"))) {form.Close(); return;}
            Method<Clear>(device,43)(device,0,IntPtr.Zero,1,0xFF234563,1,0);
            Method<Scene>(device,41)(device);
            Method<SetFVF>(device,89)(device,0x44);
            var verts=new Vertex[] {new Vertex{X=20,Y=height-90,Z=.5f,Rhw=1,Color=0xffffd050},new Vertex{X=110,Y=height-90,Z=.5f,Rhw=1,Color=0xffffd050},new Vertex{X=20,Y=height-20,Z=.5f,Rhw=1,Color=0xffffd050}};
            var size=Marshal.SizeOf(typeof(Vertex)); var buffer=Marshal.AllocHGlobal(size*verts.Length);
            try {for(int i=0;i<verts.Length;i++) Marshal.StructureToPtr(verts[i],IntPtr.Add(buffer,i*size),false); Method<DrawUP>(device,83)(device,4,1,buffer,(uint)size);} finally {Marshal.FreeHGlobal(buffer);}
            Method<Scene>(device,42)(device);
            string request=Path.Combine(folder,"capture");
            if(File.Exists(request)) {
                try {File.Delete(request); Capture(device,width,height,Path.Combine(folder,"capture.png"),false);}
                catch(Exception ex) {File.WriteAllText(Path.Combine(folder,"capture-error"),ex.ToString());}
            }
            Method<Present>(device,17)(device,IntPtr.Zero,IntPtr.Zero,IntPtr.Zero,IntPtr.Zero);
        };
        form.FormClosed+=(sender,e)=> {timer.Stop(); if(device!=IntPtr.Zero) Method<Release>(device,2)(device); if(direct!=IntPtr.Zero) Method<Release>(direct,2)(direct);};
        Application.Run(form); return File.Exists(Path.Combine(folder,"error"))?1:0;
    }
}
