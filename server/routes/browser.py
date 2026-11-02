"""Khung trình duyệt: `GET /browser/status` và luồng `WS /ws/browser` (0.430.0).

Toàn bộ việc lái Chromium nằm ở `browser_pane.py`; file này chỉ nối websocket của dashboard vào đó.

`ws_browser` TỰ kiểm đăng nhập ở đầu hàm, như `/ws/terminal` và `/ws/graph`: middleware `_auth_guard`
của main chỉ thấy request HTTP, không thấy scope websocket, mà trình duyệt này giữ phiên đăng nhập
thật của chủ máy (Gmail công ty, ngân hàng...). Bỏ dòng đó là mở toang các phiên ấy cho bất kỳ ai gõ
được địa chỉ VPS.
"""
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

import browser_pane
import config as cfgmod
import localefmt


@dataclass
class BrowserDeps:
    """Thứ duy nhất module này cần từ main: gốc thư mục của một brain (để đặt nơi lưu tệp tải về)."""
    brain_root: Callable[[str], str]


_DEPS: BrowserDeps = None


def _cau_loi(ma: str) -> str:
    if ma == "no-browser":
        return localefmt.chu("Máy này chưa có trình duyệt UNI MATE lái được. Vào Công cụ, cài Trình duyệt (Chromium) rồi mở lại khung.",
                             "This machine has no browser UNI MATE can drive. Open Tools, install the Browser (Chromium), then reopen the pane.")
    if ma == "disabled":
        return localefmt.chu("Khung trình duyệt đang tắt trên máy này (biến môi trường UNIMATE_BROWSER_PANE=0).",
                             "The browser pane is turned off on this machine (environment variable UNIMATE_BROWSER_PANE=0).")
    return localefmt.chu(f"Không mở được trình duyệt: {ma}", f"Could not start the browser: {ma}")


def _make_router() -> APIRouter:
    router = APIRouter()

    @router.get("/browser/status")
    async def browser_status():
        tb = browser_pane.TRINH_DUYET
        return {"enabled": browser_pane.bat(), "available": bool(tb.file_chay()),
                "running": tb.dang_chay(), "tabs": len(tb.tabs)}

    @router.websocket("/ws/browser")
    async def ws_browser(ws: WebSocket, brain: str = Query("brain"), w: int = Query(1280), h: int = Query(800)):
        if cfgmod.gate_active() and not cfgmod.valid_session(ws.cookies.get("unimate_session", "")):
            await ws.close(code=1008)
            return
        await ws.accept()

        async def bao_loi(ma: str):
            try:
                await ws.send_text(json.dumps({"type": "error", "code": ma, "error": _cau_loi(ma)}, ensure_ascii=False))
            except Exception:
                pass
            await ws.close()

        if not browser_pane.bat():
            await bao_loi("disabled")
            return
        tb = browser_pane.TRINH_DUYET
        tb.view = (max(browser_pane.VIEW_MIN[0], min(browser_pane.VIEW_MAX[0], int(w or 1280))),
                   max(browser_pane.VIEW_MIN[1], min(browser_pane.VIEW_MAX[1], int(h or 800)))) \
            if not tb.dang_chay() else tb.view
        try:
            await tb.bat_dau()
        except RuntimeError as e:
            await bao_loi(str(e))
            return
        except Exception as e:  # noqa: BLE001
            await bao_loi(f"{type(e).__name__}: {e}")
            return
        try:
            await tb.dat_thu_muc_tai(str(Path(_DEPS.brain_root(brain)) / "downloads"))
        except Exception:
            pass

        nx = browser_pane.NguoiXem(ws.send_text, ws.send_bytes)
        tb.them_nguoi_xem(nx)
        # Hai làn: chuột/phím/chữ xử lý ngay (chỉ gửi, không chờ), còn việc phải chờ trình duyệt trả lời (điều hướng,
        # mở/đóng tab, đổi cỡ) xếp vào một hàng riêng. Gộp chung một làn thì một trang tải chậm làm cả khung đơ:
        # bấm, cuộn, gõ đều đứng chờ sau nó.
        hang: asyncio.Queue = asyncio.Queue()

        async def lam_viec_cham():
            while True:
                m = await hang.get()
                try:
                    if not tb.dang_chay():
                        # Trình duyệt chết giữa chừng (tắt vì nghỉ lâu, hay sập): bật lại khi người dùng còn đang
                        # thao tác, thay vì bắt họ đóng mở khung.
                        await tb.bat_dau()
                        if nx not in tb.nguoi_xem:
                            tb.them_nguoi_xem(nx)
                    await tb.xu_ly(m)
                except Exception as e:  # noqa: BLE001
                    browser_pane._log(f"{m.get('type')}: {type(e).__name__}: {e}")
                    nx.tin({"type": "notice", "error": f"{type(e).__name__}: {e}"})

        tho = asyncio.create_task(lam_viec_cham())
        try:
            hang.put_nowait({"type": "resize", "w": w, "h": h})
            while True:
                raw = await ws.receive_text()
                try:
                    m = json.loads(raw)
                except Exception:
                    continue
                if not isinstance(m, dict):
                    continue
                if m.get("type") in browser_pane.TrinhDuyet.NHANH and tb.dang_chay():
                    try:
                        await tb.xu_ly(m)
                    except Exception:
                        pass
                else:
                    hang.put_nowait(m)
        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            tho.cancel()
            tb.bo_nguoi_xem(nx)

    return router


def register(app, deps: BrowserDeps):
    """Gắn router vào app."""
    global _DEPS
    _DEPS = deps
    router = _make_router()
    app.include_router(router)
    return router


__all__ = ["register", "BrowserDeps"]
