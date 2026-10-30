using System;
using System.Runtime.InteropServices;
using System.Windows.Forms;
// Disposable test window: no documents, network, children, or saved state.
class FixtureRestriction {
    [DllImport("winmm.dll", CharSet=CharSet.Unicode)]
    static extern bool PlaySound(string name, IntPtr module, uint flags);
    [STAThread] static void Main(string[] args) {
        var form = new Form { Text = "Keep Improving restriction test", Width = 640, Height = 420 };
        form.Controls.Add(new Label { Text = "Disposable restriction test window", Dock = DockStyle.Fill });
        if (args.Length > 0) PlaySound(args[0], IntPtr.Zero, 0x20009);
        if (args.Length > 1 && args[1] == "ignore-close") form.FormClosing += (s,e) => {e.Cancel = true;};
        Application.Run(form);
        PlaySound(null, IntPtr.Zero, 0);
    }
}
