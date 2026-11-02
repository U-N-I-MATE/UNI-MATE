"""Dọn tàn dư của khung trình duyệt đã gỡ (0.430.2).

Khung trình duyệt (0.430.0, 0.430.1) chạy một Chromium ẩn với hồ sơ riêng `<STATE_DIR>/browser-profile`. Chủ repo gỡ tính
năng ngày 02/11/2026 ("vì k dùng được ở google"). Gỡ mã thôi thì trên máy đã dùng còn lại hai thứ:

- Chromium mồ côi vẫn chạy ngầm (nó cố ý sống qua lần khởi động lại server để nối lại), ăn RAM tới khi tắt máy;
- hồ sơ chứa cookie và phiên đăng nhập THẬT (Gmail, Google...) nằm trên đĩa mà không còn giao diện nào để xoá.

Nên lúc server khởi động, nếu thấy dấu vết đó thì ở một luồng nền: đóng Chromium qua cổng DevTools nội bộ của nó, rồi xoá hồ
sơ và tệp nhật ký đi kèm. Không có dấu vết thì không làm gì. Thư mục `downloads/` trong brain là dữ liệu của người dùng, để yên.
"""
from __future__ import annotations

import asyncio
import json
import shutil
import sys
import threading
import time

import config as cfgmod


def _dong_chromium(ho_so) -> None:
    try:
        dong = (ho_so / "DevToolsActivePort").read_text(encoding="utf-8").split()
        port, duong = int(dong[0]), dong[1]
    except (OSError, ValueError, IndexError):
        return

    async def dong_lai():
        import websockets
        async with websockets.connect(f"ws://127.0.0.1:{port}{duong}", open_timeout=3) as ws:
            await ws.send(json.dumps({"id": 1, "method": "Browser.close"}))
            try:
                await asyncio.wait_for(ws.recv(), 3)
            except Exception:
                pass

    try:
        asyncio.run(dong_lai())
        time.sleep(2)   # chờ Chromium nhả tệp trong hồ sơ trước khi xoá
    except Exception:
        pass


def don() -> None:
    goc = cfgmod.STATE_DIR
    ho_so = goc / "browser-profile"
    _dong_chromium(ho_so)
    shutil.rmtree(ho_so, ignore_errors=True)
    try:
        (goc / "browser-pane.log").unlink(missing_ok=True)
    except OSError:
        pass
    print("[browser-cleanup] đã dọn hồ sơ của khung trình duyệt đã gỡ", file=sys.stderr)


def chay_nen() -> None:
    """Gọi một lần lúc server khởi động. Không có dấu vết thì không bật luồng nào."""
    goc = cfgmod.STATE_DIR
    if (goc / "browser-profile").exists() or (goc / "browser-pane.log").exists():
        threading.Thread(target=don, daemon=True, name="don-trinh-duyet-cu").start()
