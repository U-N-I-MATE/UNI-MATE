#!/usr/bin/env python3
"""Xuất logo + favicon + icon PWA của UNI MATE từ dashboard/logo.svg.

    python tools/gen_logo.py

Logo là linh vật D2 "mắt long lanh" của UNI TECH (chủ dự án chốt 01/11/2026): thân Tím công nghệ
#5B2DA0, chấm vàng #C9A24B, má hồng, mắt tròng trắng nhìn thẳng, không có miệng. Hình gốc nằm ở
dashboard/logo.svg, thân là ĐÚNG đường SHAPES.uni trong dashboard/pet.js; sửa hình thì sửa cả hai
chỗ (tests/js/test_logo_linh_vat.js canh sự trùng khớp).

Ghi ra (PNG nền trong suốt):
  dashboard/logo.png      - logo chính 512px, cũng là nguồn của /brand-logo
  dashboard/icon-192.png  - icon PWA (manifest.json)
  dashboard/icon-512.png
  dashboard/favicon.png   - 64px cho tab trình duyệt (/brand-logo?nho=1, /favicon.ico): BỎ má hồng
                            (nhóm id="ma" trong logo.svg) vì ở cỡ 16-32px má chỉ là vệt nhoè.

Cần Playwright cho Python (pip install playwright, rồi playwright install chromium).
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

DASH = Path(__file__).resolve().parent.parent / "dashboard"


def _xuat(trang, svg: str, ra: Path, canh: int) -> None:
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    trang.set_viewport_size({"width": canh, "height": canh})
    trang.set_content(
        '<html><body style="margin:0;background:transparent">'
        f'<img src="data:image/svg+xml;base64,{b64}" style="width:{canh}px;height:{canh}px;display:block">'
        "</body></html>")
    trang.wait_for_timeout(150)
    trang.screenshot(path=str(ra), omit_background=True)


def main() -> None:
    svg = (DASH / "logo.svg").read_text(encoding="utf-8")
    khong_ma = re.sub(r'<g id="ma">.*?</g>', "", svg, flags=re.S)
    with sync_playwright() as p:
        trinh = p.chromium.launch()
        trang = trinh.new_page()
        for ten, nguon, canh in [("logo.png", svg, 512), ("icon-512.png", svg, 512),
                                 ("icon-192.png", svg, 192), ("favicon.png", khong_ma, 64)]:
            _xuat(trang, nguon, DASH / ten, canh)
            print("ghi", DASH / ten)
        trinh.close()


if __name__ == "__main__":
    main()
