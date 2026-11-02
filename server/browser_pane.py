"""Khung trình duyệt cạnh khung chat (0.430.0).

Chủ repo 02/11/2026 gửi ảnh khung "Duyệt web với Claude" và chốt: "Anh muốn phát triển tính năng bổ
sung cửa sổ trình duyệt web như này vào trong phần mềm". Hướng đã duyệt: trình duyệt chạy BÊN TRONG
UNI MATE, khung trên dashboard chiếu hình trực tiếp và gửi ngược thao tác của người dùng; AI và người
dùng dùng CHUNG một trình duyệt, chung phiên đăng nhập; chạy giống nhau trên máy nhà và VPS.

Vì sao không nhúng trang web thẳng vào dashboard (iframe): Gmail, Google, ngân hàng, Facebook đều
chặn bị nhúng (X-Frame-Options / CSP frame-ancestors), khung sẽ trắng. Và trên VPS thì trang phải
mở TỪ VPS mới đăng nhập hộ được việc nền.

Cách làm:
- Một Chromium chạy ẩn (headless) với hồ sơ riêng `<STATE_DIR>/browser-profile`, nên đăng nhập một
  lần là nhớ và cập nhật phần mềm không mất. File chạy lấy từ `optional_tools.duong_dan_chrome()`,
  cùng nguồn sự thật với trang Công cụ (máy nhà dùng Chrome/Edge có sẵn, VPS dùng bản đã tải).
- Nói chuyện với nó qua Chrome DevTools Protocol trên 127.0.0.1 (cổng ngẫu nhiên, đọc từ
  `DevToolsActivePort`). Cổng cố ý chỉ nghe nội bộ: hồ sơ chứa phiên đăng nhập thật.
- Hình: `Page.startScreencast` của tab đang xem, mỗi khung JPEG đẩy thẳng ra websocket dạng nhị phân.
  Chỉ giữ khung MỚI NHẤT cho mỗi người xem, mạng chậm thì bỏ khung cũ chứ không dồn hàng.
- Thao tác: chuột, cuộn, phím, chữ (kể cả tiếng Việt gõ bằng bộ gõ) đi qua `Input.*`.
- Tab: theo dõi `Target.*`. Trang tự mở cửa sổ mới (target=_blank, window.open) thành tab mới và
  được chọn ngay, giống trình duyệt thật.
- Tải tệp: `Browser.setDownloadBehavior` lưu vào `<brain>/downloads/` của brain người xem đang chọn,
  để AI đọc được bằng công cụ vault.

Vòng đời: bật lười khi có người mở khung lần đầu, tự tắt sau `NGHI_TAT_GIAY` không ai xem (hồ sơ vẫn
giữ). Server chết đột ngột để lại Chromium mồ côi thì lần sau NỐI LẠI chính nó qua `DevToolsActivePort`
thay vì bật bản thứ hai giành khoá hồ sơ.

Tắt hẳn tính năng: biến môi trường UNIMATE_BROWSER_PANE=0.
"""
from __future__ import annotations

import asyncio
import atexit
import base64
import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus

import config as cfgmod
import winproc

PROFILE_DIR = cfgmod.STATE_DIR / "browser-profile"
NGHI_TAT_GIAY = 30 * 60          # không ai xem 30 phút thì tắt trình duyệt (hồ sơ vẫn giữ)
CHO_KHOI_DONG_GIAY = 25.0
VIEW_MAC_DINH = (1280, 800)
VIEW_MIN = (320, 240)
VIEW_MAX = (3840, 2400)
JPEG_CHAT_LUONG = 70
# Địa chỉ của một tab "chưa có gì" (Chromium hồ sơ mới mở trang tab mới của nó, chạy ẩn thì là trang trắng).
TRANG_TRANG = ("", "about:blank", "chrome://newtab/", "chrome://new-tab-page/")


def bat() -> bool:
    """Tính năng có đang bật trên máy này không (UNIMATE_BROWSER_PANE=0 thì tắt)."""
    return str(os.getenv("UNIMATE_BROWSER_PANE", "1")).strip().lower() not in ("0", "false", "no", "off")


def _log(msg: str) -> None:
    print(f"[browser-pane] {msg}", file=sys.stderr)


# ─────────────────────────── địa chỉ người dùng gõ ───────────────────────────

_CO_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
_GIONG_DIA_CHI = re.compile(r"^(localhost|\[[0-9a-fA-F:]+\]|[^\s/]+\.[^\s/]+|\d{1,3}(\.\d{1,3}){3})(:\d+)?(/.*)?$")
_SCHEME_CHO_PHEP = ("http:", "https:", "about:", "data:", "view-source:", "file:")


def chuan_hoa_dia_chi(text: str) -> str:
    """Chữ gõ ở ô địa chỉ -> URL mở được. Trông như địa chỉ thì thêm https://, không thì tìm Google.

    Chặn `javascript:` (gõ vào ô địa chỉ là chạy mã trên trang đang mở) và `chrome:` (trang nội bộ
    của trình duyệt), thay bằng tìm kiếm chữ đó, đúng như ô địa chỉ của trình duyệt thật xử lý.
    """
    s = (text or "").strip()
    if not s:
        return "about:blank"
    if _CO_SCHEME.match(s) and not re.match(r"^[^\s:/]+\.[^\s:/]+:\d+", s) and not s.lower().startswith("localhost:"):
        if s.lower().startswith(_SCHEME_CHO_PHEP):
            return s
        return "https://www.google.com/search?q=" + quote_plus(s)
    if " " not in s and _GIONG_DIA_CHI.match(s):
        dau = "http://" if re.match(r"^(localhost|127\.|\[::1\])", s) else "https://"
        return dau + s
    return "https://www.google.com/search?q=" + quote_plus(s)


# ─────────────────────────── kết nối CDP ───────────────────────────

class CdpError(RuntimeError):
    pass


class Cdp:
    """Một kết nối Chrome DevTools Protocol tới cả trình duyệt, chế độ session phẳng (flatten)."""

    def __init__(self, ws):
        self.ws = ws
        self._id = 0
        self._cho: dict[int, asyncio.Future] = {}
        self._nghe = []
        self.dong = False
        self._doc = asyncio.create_task(self._vong_doc())

    def on(self, cb) -> None:
        self._nghe.append(cb)

    async def call(self, method: str, params: dict | None = None, session: str | None = None,
                   timeout: float = 20.0) -> dict:
        if self.dong:
            raise CdpError("trình duyệt đã đóng")
        self._id += 1
        mid = self._id
        msg = {"id": mid, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        fut = asyncio.get_running_loop().create_future()
        self._cho[mid] = fut
        try:
            await self.ws.send(json.dumps(msg))
            return await asyncio.wait_for(fut, timeout)
        finally:
            self._cho.pop(mid, None)

    def gui_khong_cho(self, method: str, params: dict | None = None, session: str | None = None) -> None:
        """Gửi mà không chờ trả lời (ack khung hình, thao tác chuột dồn dập). Lỗi thì bỏ qua."""
        async def _go():
            try:
                await self.call(method, params, session, timeout=10.0)
            except Exception:
                pass
        if not self.dong:
            asyncio.create_task(_go())

    async def _vong_doc(self):
        try:
            async for raw in self.ws:
                try:
                    m = json.loads(raw)
                except Exception:
                    continue
                if "id" in m:
                    fut = self._cho.get(m["id"])
                    if fut and not fut.done():
                        if "error" in m:
                            fut.set_exception(CdpError(str((m.get("error") or {}).get("message") or m["error"])))
                        else:
                            fut.set_result(m.get("result") or {})
                    continue
                for cb in list(self._nghe):
                    try:
                        cb(m.get("method", ""), m.get("params") or {}, m.get("sessionId"))
                    except Exception as e:  # noqa: BLE001
                        _log(f"lỗi xử lý sự kiện {m.get('method')}: {type(e).__name__}: {e}")
        except Exception:
            pass
        finally:
            self.dong = True
            for fut in self._cho.values():
                if not fut.done():
                    fut.set_exception(CdpError("mất kết nối tới trình duyệt"))
            for cb in list(self._nghe):
                try:
                    cb("__closed__", {"cdp": self}, None)
                except Exception:
                    pass

    async def close(self):
        self.dong = True
        try:
            await self.ws.close()
        except Exception:
            pass


# ─────────────────────────── người xem (một khung trên dashboard) ───────────────────────────

class NguoiXem:
    """Một websocket đang mở khung. Tin trạng thái xếp hàng; khung hình chỉ giữ cái MỚI NHẤT."""

    def __init__(self, send_text, send_bytes):
        self._send_text = send_text
        self._send_bytes = send_bytes
        self._tin: list[str] = []
        self._khung: bytes | None = None
        self._co = asyncio.Event()
        self._task = asyncio.create_task(self._vong_gui())

    def tin(self, obj: dict) -> None:
        self._tin.append(json.dumps(obj, ensure_ascii=False))
        self._co.set()

    def khung(self, data: bytes) -> None:
        self._khung = data
        self._co.set()

    async def _vong_gui(self):
        try:
            while True:
                await self._co.wait()
                self._co.clear()
                while self._tin:
                    await self._send_text(self._tin.pop(0))
                if self._khung is not None:
                    k, self._khung = self._khung, None
                    await self._send_bytes(k)
        except asyncio.CancelledError:
            raise
        except Exception:
            pass

    def huy(self):
        self._task.cancel()


# ─────────────────────────── trình duyệt dùng chung ───────────────────────────

class Tab:
    __slots__ = ("id", "session", "url", "title", "loading", "opener", "tao_luc")

    def __init__(self, tid: str, url: str = "", title: str = "", opener: str = ""):
        self.id = tid
        self.session = ""
        self.url = url
        self.title = title
        self.loading = False
        self.opener = opener
        self.tao_luc = time.time()

    def dict(self) -> dict:
        return {"id": self.id, "url": self.url, "title": self.title, "loading": self.loading}


class TrinhDuyet:
    """Chromium dùng chung cho cả máy. Một bản duy nhất: `TRINH_DUYET`."""

    def __init__(self):
        self.proc: subprocess.Popen | None = None
        self.cdp: Cdp | None = None
        self.tabs: dict[str, Tab] = {}
        self.thu_tu: list[str] = []
        self.dang_xem = ""
        self.cho_chon: set[str] = set()      # tab mình vừa mở, chọn ngay khi nó hiện ra
        self.nguoi_xem: set[NguoiXem] = set()
        self.view = VIEW_MAC_DINH
        self.thu_muc_tai = ""
        self.tai_ve: dict[str, str] = {}     # guid -> tên tệp
        self.da_tai: list[tuple[float, str]] = []   # (lúc xong, tên tệp) gần đây, để AI biết tệp vừa tải
        self.hop_thoai: dict[str, dict] = {}  # session -> hộp thoại đang chờ
        self.lan_cuoi_dung = time.time()
        self._khoa = asyncio.Lock()
        self._lan_hoi_tab = 0.0
        self._canh: asyncio.Task | None = None

    # ---------- bật / tắt ----------

    def dang_chay(self) -> bool:
        return bool(self.cdp and not self.cdp.dong)

    @staticmethod
    def file_chay() -> str:
        try:
            import optional_tools
            return optional_tools.duong_dan_chrome()
        except Exception as e:  # noqa: BLE001
            _log(f"dò trình duyệt lỗi: {type(e).__name__}: {e}")
            return ""

    async def bat_dau(self) -> None:
        async with self._khoa:
            if self.dang_chay():
                return
            await self._noi_hoac_bat()
            if self._canh is None or self._canh.done():
                self._canh = asyncio.create_task(self._canh_nghi())

    async def _noi_ws(self, port: int, path: str) -> bool:
        import websockets
        try:
            ws = await websockets.connect(f"ws://127.0.0.1:{port}{path}", max_size=None,
                                          ping_interval=None, open_timeout=5)
        except Exception:
            return False
        self.cdp = Cdp(ws)
        self.cdp.on(self._su_kien)
        return True

    @staticmethod
    def _doc_cong() -> tuple[int, str] | None:
        f = PROFILE_DIR / "DevToolsActivePort"
        try:
            dong = f.read_text(encoding="utf-8").split()
            if len(dong) >= 2 and dong[0].isdigit():
                return int(dong[0]), dong[1]
        except OSError:
            pass
        return None

    async def _noi_hoac_bat(self) -> None:
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        # Chromium mồ côi từ lần chạy trước (server chết đột ngột): nối lại chính nó.
        cu = self._doc_cong()
        if cu and await self._noi_ws(*cu):
            _log(f"nối lại trình duyệt đang chạy ở cổng {cu[0]}")
            await self._khoi_tao()
            return
        try:
            (PROFILE_DIR / "DevToolsActivePort").unlink()
        except OSError:
            pass
        exe = self.file_chay()
        if not exe:
            raise RuntimeError("no-browser")
        w, h = self.view
        args = [exe, "--headless=new", "--remote-debugging-port=0", f"--user-data-dir={PROFILE_DIR}",
                "--no-first-run", "--no-default-browser-check", "--disable-dev-shm-usage",
                "--mute-audio", "--disable-features=Translate,MediaRouter", "--lang=vi-VN",
                f"--window-size={w},{h}"]
        if platform.system().lower() == "linux":
            # Như Playwright mặc định (chromiumSandbox=false): container chạy user thường thiếu
            # user namespace, sandbox bật là Chromium chết ngay lúc mở.
            args.insert(1, "--no-sandbox")
        # Lời Chromium tự kể (vì sao nó thoát) ghi đè vào một tệp nhỏ, để soi được khi khung báo trình duyệt đã đóng.
        try:
            nhat_ky = open(cfgmod.STATE_DIR / "browser-pane.log", "wb")
        except OSError:
            nhat_ky = subprocess.DEVNULL
        self.proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=nhat_ky,
                                     stderr=nhat_ky, creationflags=winproc.no_window())
        if nhat_ky is not subprocess.DEVNULL:
            nhat_ky.close()
        het = time.time() + CHO_KHOI_DONG_GIAY
        while time.time() < het:
            if self.proc.poll() is not None:
                raise RuntimeError(f"browser-exited:{self.proc.returncode}")
            cong = self._doc_cong()
            if cong and await self._noi_ws(*cong):
                await self._khoi_tao()
                _log(f"đã bật {Path(exe).name} (cổng {cong[0]})")
                return
            await asyncio.sleep(0.2)
        self._giet()
        raise RuntimeError("browser-timeout")

    async def _khoi_tao(self) -> None:
        self.tabs.clear()
        self.thu_tu.clear()
        self.dang_xem = ""
        await self.cdp.call("Target.setDiscoverTargets", {"discover": True})
        await self._dat_thu_muc_tai()
        # Chromium vừa bật có thể chưa kịp dựng tab đầu (hoặc đang khôi phục các tab của lần trước nếu lần trước bị tắt
        # đột ngột): chờ một chút cho các tab hiện ra rồi mới quyết định, không thì mỗi lần bật lại mọc thêm một tab trắng.
        het = time.time() + 2.0
        while True:
            res = await self.cdp.call("Target.getTargets")
            trang = [ti for ti in (res.get("targetInfos") or []) if ti.get("type") == "page"]
            if trang or time.time() > het:
                break
            await asyncio.sleep(0.2)
        for ti in trang:
            if ti["targetId"] not in self.tabs:
                self._them_tab(ti)
                await self._gan(ti["targetId"])
        trang_trang = [t for t in self.thu_tu if self.tabs[t].url in TRANG_TRANG]
        if trang_trang and len(trang_trang) < len(self.thu_tu):
            # Có tab thật được khôi phục thì bỏ các tab trắng Chromium tự mở kèm.
            for tid in trang_trang:
                try:
                    await self.cdp.call("Target.closeTarget", {"targetId": tid})
                except CdpError:
                    pass
        if not self.tabs:
            await self.cdp.call("Target.createTarget", {"url": "about:blank"})
        elif not self.dang_xem or self.dang_xem in trang_trang:
            con = [t for t in self.thu_tu if t not in trang_trang] or self.thu_tu
            await self.chon_tab(con[-1])

    def _giet(self):
        p = self.proc
        self.proc = None
        if p and p.poll() is None:
            try:
                p.terminate()
                p.wait(timeout=5)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass

    async def tat(self) -> None:
        if self.cdp and not self.cdp.dong:
            try:
                await self.cdp.call("Browser.close", timeout=5)
            except Exception:
                pass
            await self.cdp.close()
        self._giet()
        self.cdp = None
        self.tabs.clear()
        self.thu_tu.clear()
        self.dang_xem = ""

    async def _canh_nghi(self):
        """Không ai xem đủ lâu thì tắt trình duyệt. Hồ sơ (đăng nhập) vẫn nằm trên đĩa."""
        while self.dang_chay():
            await asyncio.sleep(60)
            if not self.nguoi_xem and time.time() - self.lan_cuoi_dung > NGHI_TAT_GIAY:
                _log("không ai dùng, tắt trình duyệt")
                await self.tat()
                return

    def cham(self):
        self.lan_cuoi_dung = time.time()

    # ---------- người xem ----------

    def them_nguoi_xem(self, nx: NguoiXem):
        self.nguoi_xem.add(nx)
        self.cham()
        nx.tin(self.trang_thai())
        hd = self.hop_thoai.get(self._session_dang_xem())
        if hd:
            nx.tin(hd)
        asyncio.create_task(self._chup_lai())

    def bo_nguoi_xem(self, nx: NguoiXem):
        self.nguoi_xem.discard(nx)
        nx.huy()
        self.cham()

    def _phat(self, obj: dict):
        for nx in list(self.nguoi_xem):
            nx.tin(obj)

    def _phat_tabs(self):
        self._phat({"type": "tabs", "tabs": [self.tabs[t].dict() for t in self.thu_tu if t in self.tabs],
                    "active": self.dang_xem})

    def trang_thai(self) -> dict:
        return {"type": "tabs", "tabs": [self.tabs[t].dict() for t in self.thu_tu if t in self.tabs],
                "active": self.dang_xem, "view": list(self.view)}

    # ---------- tab ----------

    def _them_tab(self, ti: dict) -> Tab:
        tab = Tab(ti["targetId"], ti.get("url", ""), ti.get("title", ""), ti.get("openerId", "") or "")
        self.tabs[tab.id] = tab
        self.thu_tu.append(tab.id)
        return tab

    def _session_dang_xem(self) -> str:
        t = self.tabs.get(self.dang_xem)
        return t.session if t else ""

    async def _gan(self, tid: str) -> None:
        tab = self.tabs.get(tid)
        if not tab or tab.session:
            return
        try:
            res = await self.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})
        except CdpError:
            return
        tab.session = res.get("sessionId", "")
        s = tab.session
        try:
            await self.cdp.call("Page.enable", session=s)
        except CdpError:
            pass
        if tid in self.cho_chon or tab.opener or not self.dang_xem:
            self.cho_chon.discard(tid)
            await self.chon_tab(tid)
        self._phat_tabs()

    async def _dat_kich_thuoc(self, session: str):
        w, h = self.view
        await self.cdp.call("Emulation.setDeviceMetricsOverride",
                            {"width": w, "height": h, "deviceScaleFactor": 1, "mobile": False}, session=session)

    async def chon_tab(self, tid: str) -> None:
        tab = self.tabs.get(tid)
        if not tab or not tab.session:
            return
        cu = self.tabs.get(self.dang_xem)
        if cu and cu.session and cu.id != tid:
            self.cdp.gui_khong_cho("Page.stopScreencast", session=cu.session)
        self.dang_xem = tid
        try:
            await self.cdp.call("Target.activateTarget", {"targetId": tid})
            # Đặt cỡ màn hình CHỈ cho tab đang xem, đúng lúc nó được chọn. Đặt cho tab nền là Chromium chạy ẩn sập
            # hẳn (SIGSEGV, thấy thật với Chromium 153 khi khôi phục 3 tab rồi đổi cỡ khung, 02/11/2026).
            await self._dat_kich_thuoc(tab.session)
        except CdpError:
            pass
        await self._bat_chieu(tab.session)
        self._phat_tabs()
        hd = self.hop_thoai.get(tab.session)
        if hd:
            self._phat(hd)

    async def _bat_chieu(self, session: str):
        w, h = self.view
        try:
            await self.cdp.call("Page.startScreencast", {"format": "jpeg", "quality": JPEG_CHAT_LUONG,
                                                         "maxWidth": w, "maxHeight": h, "everyNthFrame": 1},
                                session=session)
        except CdpError:
            pass
        # Không chờ: trang đang treo hộp thoại thì chụp ảnh treo tới hết hạn, kéo theo cả việc chuyển tab.
        asyncio.create_task(self._chup_lai())

    async def _chup_lai(self):
        """Trang đứng yên thì screencast không có khung nào để gửi: chụp một tấm cho người mới vào."""
        s = self._session_dang_xem()
        if not s or not self.dang_chay():
            return
        try:
            res = await self.cdp.call("Page.captureScreenshot", {"format": "jpeg", "quality": JPEG_CHAT_LUONG},
                                      session=s, timeout=10)
            data = base64.b64decode(res.get("data") or "")
            if data and s == self._session_dang_xem():
                for nx in list(self.nguoi_xem):
                    nx.khung(data)
        except Exception:
            pass

    async def mo_tab(self, url: str = "") -> str:
        res = await self.cdp.call("Target.createTarget", {"url": "about:blank"})
        tid = res.get("targetId", "")
        if tid:
            self.cho_chon.add(tid)
            if tid in self.tabs and self.tabs[tid].session:
                self.cho_chon.discard(tid)
                await self.chon_tab(tid)
            if url:
                await self._cho_session(tid)
                tab = self.tabs.get(tid)
                if tab and tab.session:
                    await self.cdp.call("Page.navigate", {"url": chuan_hoa_dia_chi(url)}, session=tab.session)
        return tid

    async def _cho_session(self, tid: str, giay: float = 5.0):
        het = time.time() + giay
        while time.time() < het:
            t = self.tabs.get(tid)
            if t and t.session:
                return
            await asyncio.sleep(0.05)

    async def dong_tab(self, tid: str) -> None:
        if tid not in self.tabs:
            return
        if len(self.tabs) == 1:
            # Đóng tab cuối thì mở sẵn một tab trắng, khung không bao giờ rỗng.
            await self.mo_tab("")
        try:
            await self.cdp.call("Target.closeTarget", {"targetId": tid})
        except CdpError:
            pass

    # ---------- tải tệp ----------

    async def _dat_thu_muc_tai(self):
        if not self.thu_muc_tai or not self.dang_chay():
            return
        # KHÔNG tạo sẵn thư mục ở đây: mở khung mà chưa tải gì thì brain không mọc thêm thư mục rỗng.
        # Thư mục được tạo đúng lúc có tệp đầu tiên (Browser.downloadWillBegin).
        try:
            await self.cdp.call("Browser.setDownloadBehavior",
                                {"behavior": "allow", "downloadPath": self.thu_muc_tai, "eventsEnabled": True})
        except Exception as e:  # noqa: BLE001
            _log(f"không đặt được thư mục tải về: {type(e).__name__}: {e}")

    async def dat_thu_muc_tai(self, duong: str):
        self.thu_muc_tai = duong
        await self._dat_thu_muc_tai()

    # ---------- sự kiện từ trình duyệt ----------

    def _su_kien(self, method: str, p: dict, session: str | None):
        if method == "Page.screencastFrame":
            if session:
                self.cdp.gui_khong_cho("Page.screencastFrameAck", {"sessionId": p.get("sessionId")}, session)
            if session and session == self._session_dang_xem():
                data = base64.b64decode(p.get("data") or "")
                for nx in list(self.nguoi_xem):
                    nx.khung(data)
                # Trang đang vẽ lại là lúc tiêu đề có thể đã đổi: hỏi lại, thưa thôi (tối đa 2 giây một lần).
                if time.time() - self._lan_hoi_tab > 2.0:
                    self._lan_hoi_tab = time.time()
                    asyncio.create_task(self.lam_moi_tabs())
            return
        if method == "Target.targetCreated":
            ti = p.get("targetInfo") or {}
            if ti.get("type") == "page" and ti.get("targetId") not in self.tabs:
                self._them_tab(ti)
                asyncio.create_task(self._gan(ti["targetId"]))
            return
        if method == "Target.targetInfoChanged":
            ti = p.get("targetInfo") or {}
            tab = self.tabs.get(ti.get("targetId"))
            if tab:
                tab.url = ti.get("url", tab.url)
                tab.title = ti.get("title", tab.title)
                self._phat_tabs()
            return
        if method == "Target.targetDestroyed":
            tid = p.get("targetId")
            tab = self.tabs.pop(tid, None)
            if tab:
                if tid in self.thu_tu:
                    self.thu_tu.remove(tid)
                self.hop_thoai.pop(tab.session, None)
                if self.dang_xem == tid:
                    self.dang_xem = ""
                    con = [t for t in self.thu_tu if self.tabs.get(t) and self.tabs[t].session]
                    ke = (tab.opener if tab.opener in con else (con[-1] if con else ""))
                    if ke:
                        asyncio.create_task(self.chon_tab(ke))
                self._phat_tabs()
            return
        if method in ("Page.frameStartedLoading", "Page.frameStoppedLoading"):
            tab = self._tab_theo_session(session)
            if tab and p.get("frameId") == tab.id:
                tab.loading = method.endswith("StartedLoading")
                self._phat_tabs()
                if not tab.loading:
                    # Target.targetInfoChanged không phải lúc nào cũng báo tiêu đề mới sau khi trang tải xong
                    # (thấy thật với Chromium 1243: tab mang tên là địa chỉ mãi), nên hỏi lại một lần.
                    asyncio.create_task(self._hoi_tieu_de(tab.id))
            return
        if method == "Page.javascriptDialogOpening":
            if session:
                hd = {"type": "dialog", "kind": p.get("type", "alert"), "message": p.get("message", ""),
                      "default": p.get("defaultPrompt", "")}
                self.hop_thoai[session] = hd
                if session == self._session_dang_xem():
                    self._phat(hd)
            return
        if method == "Page.javascriptDialogClosed":
            if session:
                self.hop_thoai.pop(session, None)
                if session == self._session_dang_xem():
                    self._phat({"type": "dialog_closed"})
            return
        if method == "Browser.downloadWillBegin":
            ten = os.path.basename(str(p.get("suggestedFilename") or "download"))
            self.tai_ve[p.get("guid", "")] = ten
            try:
                if self.thu_muc_tai:
                    Path(self.thu_muc_tai).mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
            self._phat({"type": "download", "state": "begin", "name": ten})
            return
        if method == "Browser.downloadProgress":
            st = p.get("state")
            if st in ("completed", "canceled"):
                ten = self.tai_ve.pop(p.get("guid", ""), "")
                if st == "completed" and ten:
                    self.da_tai = (self.da_tai + [(time.time(), ten)])[-20:]
                self._phat({"type": "download", "state": st, "name": ten, "folder": "downloads"})
            return
        if method == "__closed__":
            # Chỉ khi chính kết nối ĐANG DÙNG đóng. Một kết nối cũ (Chromium trước đó đã chết, hay lần nối lại hụt) đóng
            # muộn mà xoá luôn kết nối mới là khung đứng hình với lỗi "'NoneType' object has no attribute 'call'".
            if p.get("cdp") is not self.cdp:
                return
            self.cdp = None
            self.tabs.clear()
            self.thu_tu.clear()
            self.dang_xem = ""
            self._phat({"type": "closed"})

    async def lam_moi_tabs(self):
        """Hỏi lại tiêu đề + địa chỉ mọi tab. Trang tự đổi tiêu đề bằng mã (Gmail đếm thư chưa đọc, trang gửi form)
        thì Chromium không phải lúc nào cũng báo qua Target.targetInfoChanged."""
        self._lan_hoi_tab = time.time()
        try:
            res = await self.cdp.call("Target.getTargets", timeout=5)
        except Exception:
            return
        doi = False
        for ti in res.get("targetInfos") or []:
            tab = self.tabs.get(ti.get("targetId"))
            if tab and (ti.get("title") != tab.title or ti.get("url") != tab.url):
                tab.title, tab.url, doi = ti.get("title", tab.title), ti.get("url", tab.url), True
        if doi:
            self._phat_tabs()

    async def _hoi_tieu_de(self, tid: str):
        try:
            res = await self.cdp.call("Target.getTargetInfo", {"targetId": tid}, timeout=5)
        except Exception:
            return
        ti = res.get("targetInfo") or {}
        tab = self.tabs.get(tid)
        if tab and (ti.get("title") != tab.title or ti.get("url") != tab.url):
            tab.title = ti.get("title", tab.title)
            tab.url = ti.get("url", tab.url)
            self._phat_tabs()

    def _tab_theo_session(self, session: str | None) -> Tab | None:
        if not session:
            return None
        for t in self.tabs.values():
            if t.session == session:
                return t
        return None

    # ---------- thao tác của người dùng ----------

    async def doi_kich_thuoc(self, w, h):
        try:
            w = max(VIEW_MIN[0], min(VIEW_MAX[0], int(w)))
            h = max(VIEW_MIN[1], min(VIEW_MAX[1], int(h)))
        except (TypeError, ValueError):
            return
        if (w, h) == self.view:
            return
        self.view = (w, h)
        # Chỉ tab đang xem (xem chon_tab): tab nền nhận cỡ mới lúc được chọn.
        s = self._session_dang_xem()
        if s:
            try:
                await self._dat_kich_thuoc(s)
            except CdpError:
                pass
            await self._bat_chieu(s)
        self._phat({"type": "view", "view": [w, h]})

    NHANH = ("mouse", "wheel", "key", "text")

    async def xu_ly(self, m: dict) -> None:
        """Một tin từ khung trên dashboard. Loại trong NHANH không chờ trình duyệt trả lời (gửi rồi đi tiếp)."""
        if not self.dang_chay():
            return
        self.cham()
        t = m.get("type")
        s = self._session_dang_xem()
        if t == "mouse" and s:
            loai = {"down": "mousePressed", "up": "mouseReleased", "move": "mouseMoved"}.get(m.get("ev"))
            if not loai:
                return
            nut = m.get("button") if m.get("button") in ("left", "right", "middle", "none") else "none"
            self.cdp.gui_khong_cho("Input.dispatchMouseEvent", {
                "type": loai, "x": float(m.get("x") or 0), "y": float(m.get("y") or 0),
                "button": nut if loai != "mouseMoved" else (nut if m.get("held") else "none"),
                "buttons": int(m.get("buttons") or 0),
                "clickCount": int(m.get("clicks") or (1 if loai != "mouseMoved" else 0)),
                "modifiers": int(m.get("mods") or 0)}, s)
        elif t == "wheel" and s:
            self.cdp.gui_khong_cho("Input.dispatchMouseEvent", {
                "type": "mouseWheel", "x": float(m.get("x") or 0), "y": float(m.get("y") or 0),
                "deltaX": float(m.get("dx") or 0), "deltaY": float(m.get("dy") or 0),
                "modifiers": int(m.get("mods") or 0)}, s)
        elif t == "key" and s:
            ev = m.get("ev")
            text = str(m.get("text") or "")
            p = {"key": str(m.get("key") or ""), "code": str(m.get("code") or ""),
                 "windowsVirtualKeyCode": int(m.get("keyCode") or 0),
                 "nativeVirtualKeyCode": int(m.get("keyCode") or 0),
                 "modifiers": int(m.get("mods") or 0)}
            if ev == "down":
                p["type"] = "keyDown" if text else "rawKeyDown"
                if text:
                    p["text"] = text
                    p["unmodifiedText"] = text
            elif ev == "up":
                p["type"] = "keyUp"
            else:
                return
            self.cdp.gui_khong_cho("Input.dispatchKeyEvent", p, s)
        elif t == "text" and s:
            chu = str(m.get("text") or "")
            if chu:
                # Không chờ, như phím: chữ và phím đi đúng thứ tự gửi, và không nghẽn sau một việc chậm.
                self.cdp.gui_khong_cho("Input.insertText", {"text": chu[:20000]}, s)
        elif t in ("nav", "back", "forward", "reload") and s and s in self.hop_thoai:
            # Trang đang treo một hộp thoại (alert/confirm) thì Chromium không điều hướng được: đóng nó trước.
            try:
                await self.cdp.call("Page.handleJavaScriptDialog", {"accept": False}, session=s, timeout=5)
            except CdpError:
                pass
            self.hop_thoai.pop(s, None)
            self._phat({"type": "dialog_closed"})
            await self.xu_ly(m)
            return
        elif t == "nav" and s:
            await self.cdp.call("Page.navigate", {"url": chuan_hoa_dia_chi(str(m.get("url") or ""))}, session=s)
        elif t in ("back", "forward") and s:
            res = await self.cdp.call("Page.getNavigationHistory", session=s)
            i = int(res.get("currentIndex", 0)) + (-1 if t == "back" else 1)
            ds = res.get("entries") or []
            if 0 <= i < len(ds):
                await self.cdp.call("Page.navigateToHistoryEntry", {"entryId": ds[i]["id"]}, session=s)
        elif t == "reload" and s:
            await self.cdp.call("Page.reload", session=s)
        elif t == "stop" and s:
            await self.cdp.call("Page.stopLoading", session=s)
        elif t == "tab_new":
            await self.mo_tab(str(m.get("url") or ""))
        elif t == "tab_close":
            await self.dong_tab(str(m.get("id") or ""))
        elif t == "tab_select":
            await self.chon_tab(str(m.get("id") or ""))
        elif t == "resize":
            await self.doi_kich_thuoc(m.get("w"), m.get("h"))
        elif t == "dialog" and s:
            p = {"accept": bool(m.get("accept"))}
            if m.get("text") is not None:
                p["promptText"] = str(m.get("text"))
            try:
                await self.cdp.call("Page.handleJavaScriptDialog", p, session=s)
            except CdpError:
                self.hop_thoai.pop(s, None)
                self._phat({"type": "dialog_closed"})
        elif t == "refresh_frame":
            await self._chup_lai()


TRINH_DUYET = TrinhDuyet()


@atexit.register
def _tat_khi_thoat():
    # Server tắt êm thì tắt luôn Chromium; tắt đột ngột thì lần sau nối lại (xem _noi_hoac_bat).
    TRINH_DUYET._giet()
