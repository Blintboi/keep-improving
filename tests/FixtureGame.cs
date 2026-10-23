// A synthetic foreground-window test fixture, not an actual Steam/Epic game.
using System;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Windows.Forms;

class FixtureGame : Form {
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] static extern bool AllowSetForegroundWindow(int processId);
    readonly string stop;
    readonly DateTime started = DateTime.UtcNow;
    FixtureGame(string stopFile, int previewOwner) {
        stop = stopFile;
        Text = "Jatekido tesztablak";
        BackColor = Color.FromArgb(25, 28, 35);
        if (previewOwner > 0) {
            BackColor = Color.FromArgb(35, 105, 150);
            Activated += (sender, args) => AllowSetForegroundWindow(previewOwner);
        }
        ForeColor = Color.White;
        Size = new Size(560, 280);
        StartPosition = FormStartPosition.CenterScreen;
        Controls.Add(new Label { Text = "Automatikus tesztablak\nNincs billentyuzet- vagy egermuvelet.",
            Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleCenter,
            Font = new Font("Segoe UI", 15) });
        var timer = new Timer { Interval = 100 };
        timer.Tick += (sender, args) => {
            if (previewOwner > 0 && File.Exists(stop + ".yield")) {
                File.Delete(stop + ".yield");
                WindowState = FormWindowState.Minimized;
            }
            if (File.Exists(stop) || (DateTime.UtcNow - started).TotalSeconds > 45) Close();
        };
        Shown += (sender, args) => {
            TopMost = true;
            Activate();
            SetForegroundWindow(Handle);
            TopMost = false;
            timer.Start();
        };
    }
    [STAThread] static void Main(string[] args) {
        Application.EnableVisualStyles();
        Application.Run(new FixtureGame(args[0], args.Length > 1 ? Int32.Parse(args[1]) : 0));
    }
}
