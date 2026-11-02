# ============================================================
#  UNI MATE - dua cua so UNI MATE dang mo len truoc (Windows).
#  "UNI MATE.bat" va "start-unimate.vbs /open" goi file nay TRUOC khi mo cua so moi:
#    exit 0 = da co cua so, da dua len truoc (mo lai neu dang thu nho) -> KHONG mo them
#    exit 1 = chua co cua so nao (hoac khong do duoc) -> mo cua so moi nhu cu
#  Chu repo 02/11/2026: "Khi da mo san 1 cua so thi du co bam lai vao bieu tuong tren
#  man hinh bao nhieu lan thi van se chi mo cua so dang bat thoi".
#
#  Chi khop cua so co tieu de DUNG "UNI MATE": cua so app (Edge/Chrome --app) hien tieu de
#  trang tran. Tab thuong cua trinh duyet co duoi " - Google Chrome" / " - Microsoft Edge",
#  nen tab dashboard VPS mo trong trinh duyet khong bi nham thanh ban tren may.
#  Moi loi deu tra exit 1: do khong duoc thi mo cua so moi, khong bao gio de nguoi dung
#  bam ma khong thay gi.
# ============================================================
param([string]$Title = "UNI MATE")

try {
    Add-Type -ErrorAction Stop @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class UniMateCuaSo {
    public delegate bool EnumProc(IntPtr h, IntPtr p);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc f, IntPtr p);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
    public static IntPtr Tim(string tieuDe) {
        IntPtr thay = IntPtr.Zero;
        EnumWindows(delegate (IntPtr h, IntPtr p) {
            if (!IsWindowVisible(h)) return true;
            StringBuilder sb = new StringBuilder(512);
            GetWindowText(h, sb, 512);
            if (sb.ToString() == tieuDe) { thay = h; return false; }
            return true;
        }, IntPtr.Zero);
        return thay;
    }
    public static void DuaLen(IntPtr h) {
        // 9 = SW_RESTORE: chi goi khi dang thu nho, de cua so phong to khong bi thu ve co cu.
        if (IsIconic(h)) ShowWindow(h, 9);
        // Windows chan SetForegroundWindow tu tien trinh nen; nhan-nha phim Alt mo khoa (cach pho bien).
        keybd_event(0x12, 0, 0, UIntPtr.Zero);
        keybd_event(0x12, 0, 2, UIntPtr.Zero);
        SetForegroundWindow(h);
    }
}
"@
    $h = [UniMateCuaSo]::Tim($Title)
    if ($h -eq $null -or $h -eq [IntPtr]::Zero) { exit 1 }
    [UniMateCuaSo]::DuaLen($h)
    exit 0
} catch {
    exit 1
}
