// Original RTSS V2 client; no SDK binaries or source embedded. Windows 11
// includes .NET Framework 4. CLR Interlocked provides the required atomic lock.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.MemoryMappedFiles;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;

unsafe sealed class RtssBridge {
    const uint Signature = 0x52545353;
    readonly string mappingName;
    string owner = "", identity = "", lastAck = "";
    uint? lastFrame;
    long confirmed;
    readonly JavaScriptSerializer json = new JavaScriptSerializer();
    public RtssBridge(string name) { mappingName = name; }
    static uint Read(byte* p, long offset) { return *(uint*)(p + offset); }
    static void Write(byte* p, long offset, uint value) { *(uint*)(p + offset) = value; }
    static string Text(byte* p, long offset, int length) {
        int size = 0; while (size < length && p[offset + size] != 0) size++;
        return Encoding.ASCII.GetString(p + offset, size);
    }
    static void Clear(byte* p, long offset, int size) { for (int i = 0; i < size; i++) p[offset + i] = 0; }
    static bool Ascii(string s) { foreach (char c in s) if (c == 0 || c > 127) return false; return true; }
    static void Put(byte* p, long offset, string text) { for (int i = 0; i < text.Length; i++) p[offset + i] = (byte)text[i]; }
    static long Range(uint offset, uint size, uint count, uint minimum, long capacity) {
        long end = offset + (long)size * count;
        if (offset < 40 || (offset & 3) != 0 || (size & 3) != 0 || size < minimum || count > 4096 || end > capacity)
            throw new InvalidDataException("Invalid RTSS array bounds");
        return end;
    }
    public Dictionary<string, object> Publish(string newOwner, string newIdentity, int pid, string text) {
        if (!newOwner.StartsWith("GameTimeMonitor:") || newOwner.Length > 255 || !Ascii(newOwner)
                || text.Length > 4095 || !Ascii(text) || newIdentity.Length > 200 || pid < 0)
            throw new InvalidDataException("Invalid RTSS request");
        owner = newOwner;
        if (newIdentity != identity) { identity = newIdentity; lastFrame = null; lastAck = ""; confirmed = 0; }
        using (var mapping = MemoryMappedFile.OpenExisting(mappingName, MemoryMappedFileRights.ReadWrite))
        using (var view = mapping.CreateViewAccessor(0, 0, MemoryMappedFileAccess.ReadWrite)) {
            long capacity = view.Capacity;
            if (capacity < 40 || capacity > 256L * 1024 * 1024) throw new InvalidDataException("Invalid RTSS mapping size");
            byte* pointer = null; view.SafeMemoryMappedViewHandle.AcquirePointer(ref pointer);
            byte* p = pointer + view.PointerOffset; bool acquired = false;
            try {
                uint version = Read(p, 4);
                if (Read(p, 0) != Signature || version >> 16 != 2 || version < 0x2000E)
                    throw new InvalidDataException("Unsupported RTSS shared memory");
                acquired = Interlocked.CompareExchange(ref *(int*)(p + 36), 1, 0) == 0;
                if (!acquired) return Reply(false, "RTSS is busy");
                if (Read(p, 0) != Signature || Read(p, 4) != version) throw new InvalidDataException("RTSS is restarting");
                uint appSize = Read(p, 8), appOffset = Read(p, 12), appCount = Read(p, 16);
                uint osdSize = Read(p, 20), osdOffset = Read(p, 24), osdCount = Read(p, 28);
                long appEnd = Range(appOffset, appSize, appCount, 336, capacity);
                long osdEnd = Range(osdOffset, osdSize, osdCount, 4608, capacity);
                if (Math.Max(appOffset, osdOffset) < Math.Min(appEnd, osdEnd)) throw new InvalidDataException("Overlapping RTSS arrays");
                bool hooked = false; uint renderWidth = 0, renderHeight = 0;
                for (uint i = 0; i < appCount && pid > 0; i++) {
                    long a = appOffset + (long)i * appSize;
                    if (Read(p, a) != pid || (Read(p, a + 264) & 0xFFFF) == 0) continue;
                    hooked = true; uint frame = Read(p, a + 332);
                    // SDK v2.20 reports the render resolution, which can differ
                    // from desktop resolution in exclusive fullscreen.
                    if (version >= 0x20014 && appSize >= 9232) {
                        uint width = Read(p, a + 9224), height = Read(p, a + 9228);
                        if (width > 0 && width <= 32768 && height > 0 && height <= 32768) {
                            renderWidth = width; renderHeight = height;
                        }
                    }
                    string ack = frame + ":" + Read(p, a + 268) + ":" + Read(p, a + 272) + ":" + Read(p, a + 276) + ":" + Read(p, a + 280);
                    if (lastFrame.HasValue && unchecked(frame - lastFrame.Value) < 0x80000000 && ack != lastAck) {
                        confirmed = Stopwatch.GetTimestamp(); lastAck = ack;
                    }
                    break;
                }
                long slot = -1, empty = -1;
                // Slot zero is reserved for primary OSD applications by the SDK.
                for (uint i = 1; i < osdCount; i++) {
                    long s = osdOffset + (long)i * osdSize; string current = Text(p, s + 256, 256);
                    if (current == owner) { slot = s; break; }
                    if (current.Length == 0 && empty < 0) empty = s;
                }
                if (slot < 0 && text.Length > 0) slot = empty;
                if (slot < 0) return Reply(false, text.Length > 0 ? "No free RTSS OSD slot" : "");
                Clear(p, slot, 4608);
                if (version >= 0x20014 && osdSize >= 299520) Clear(p, slot + 266752, 32768);
                if (text.Length > 0) { Put(p, slot + 256, owner); Put(p, slot + 512, text); }
                uint next = unchecked(Read(p, 32) + 1); Write(p, 32, next); lastFrame = next;
                bool healthy = text.Length > 0 && hooked && confirmed != 0 &&
                    (Stopwatch.GetTimestamp() - confirmed) / (double)Stopwatch.Frequency <= 2.5;
                var result = Reply(healthy, hooked ? "" : "RTSS is waiting for the game. Restart the game after saving.");
                result["width"] = renderWidth; result["height"] = renderHeight; return result;
            } finally {
                if (acquired) Interlocked.Exchange(ref *(int*)(p + 36), 0);
                view.SafeMemoryMappedViewHandle.ReleasePointer();
            }
        }
    }
    static Dictionary<string, object> Reply(bool healthy, string error) {
        return new Dictionary<string, object> { { "healthy", healthy }, { "error", error }, { "available", true } };
    }
    public void Run() {
        try {
            string line;
            while ((line = Console.ReadLine()) != null) {
                try {
                    if (line.Length > 16384) throw new InvalidDataException("Oversized request");
                    var request = json.Deserialize<Dictionary<string, object>>(line);
                    bool clear = request.ContainsKey("clear") && Convert.ToBoolean(request["clear"]);
                    var reply = Publish((string)request["owner"], clear ? "" : (string)request["identity"],
                                        clear ? 0 : Convert.ToInt32(request["pid"]), clear ? "" : (string)request["text"]);
                    Console.WriteLine(json.Serialize(reply));
                } catch (Exception ex) { confirmed = 0; var reply = Reply(false, ex.Message); reply["available"] = false; Console.WriteLine(json.Serialize(reply)); }
            }
        } finally {
            if (owner.Length > 0) try { Publish(owner, "", 0, ""); } catch { }
        }
    }
    static void Check(bool value, string label) { if (!value) throw new Exception("Self-test failed: " + label); }
    static int SelfTest() {
        string name = "GameTimeMonitor.RTSS.Test." + Guid.NewGuid().ToString("N");
        const int osd = 10240, slotSize = 4608, capacity = osd + 4 * slotSize;
        using (var map = MemoryMappedFile.CreateNew(name, capacity))
        using (var view = map.CreateViewAccessor()) {
            uint[] header = { Signature, 0x20014, 9232, 128, 1, slotSize, osd, 4, 0, 0 };
            for (int i = 0; i < header.Length; i++) view.Write(i * 4, header[i]);
            view.WriteArray(osd + 256, Encoding.ASCII.GetBytes("Primary"), 0, 7);
            view.WriteArray(osd + slotSize + 256, Encoding.ASCII.GetBytes("Foreign"), 0, 7);
            view.WriteArray(osd + slotSize + 512, Encoding.ASCII.GetBytes("keep"), 0, 4);
            var bridge = new RtssBridge(name); string owner = "GameTimeMonitor:selftest";
            Check(!(bool)bridge.Publish(owner, "77:123", 77, "00:20:00")["healthy"], "missing hook");
            byte[] foreign = new byte[slotSize]; view.ReadArray(osd + slotSize, foreign, 0, slotSize);
            Check(Encoding.ASCII.GetString(foreign, 512, 4) == "keep", "foreign slot preserved");
            Check(view.ReadByte(osd + 256) == (byte)'P', "slot zero preserved");
            view.Write(128, 77u); view.Write(128 + 264, 7u); view.Write(128 + 332, view.ReadUInt32(32));
            Check((bool)bridge.Publish(owner, "77:123", 77, "00:19:59")["healthy"], "renderer acknowledgement");
            view.Write(128 + 9224, 1280u); view.Write(128 + 9228, 720u);
            var resolution = bridge.Publish(owner, "77:123", 77, "00:19:59");
            Check(Convert.ToUInt32(resolution["width"]) == 1280 && Convert.ToUInt32(resolution["height"]) == 720, "game render resolution reported");
            bridge.Publish(owner, "", 0, "");
            Check(view.ReadByte(osd + 2 * slotSize + 256) == 0, "owned slot released");
            view.Write(36, 1); Check(!(bool)bridge.Publish(owner, "77:123", 77, "busy")["healthy"], "busy skipped");
            Check(view.ReadInt32(36) == 1, "foreign lock preserved"); view.Write(36, 0);
            view.Write(24, 129u); bool rejected = false;
            try { bridge.Publish(owner, "77:123", 77, "bad"); } catch (InvalidDataException) { rejected = true; }
            Check(rejected && view.ReadInt32(36) == 0, "malformed bounds rejected and lock released");
            view.Write(24, (uint)osd); view.Write(0, 0xDEADu); rejected = false;
            try { bridge.Publish(owner, "77:123", 77, "bad"); } catch (InvalidDataException) { rejected = true; }
            Check(rejected && view.ReadInt32(36) == 0, "dead mapping rejected");
        }
        Console.WriteLine("RTSS native shared-memory self-test passed (10 checks)"); return 0;
    }
    static int Main(string[] args) {
        Console.InputEncoding = new UTF8Encoding(false); Console.OutputEncoding = new UTF8Encoding(false);
        if (args.Length == 1 && args[0] == "--self-test") return SelfTest();
        new RtssBridge("RTSSSharedMemoryV2").Run(); return 0;
    }
}
