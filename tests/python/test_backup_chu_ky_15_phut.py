"""Chu kỳ đồng bộ brain với GitHub nhận số lẻ, ngắn nhất 15 phút (chủ dự án, 01/11/2026).

Máy nhà và VPS cùng nối một kho GitHub riêng tư; chu kỳ cũ thấp nhất 1 giờ (ô nhập chỉ nhận giờ chẵn) nên
hai bên lệch nhau lâu. Giờ 0.25 = 15 phút; dưới 15 phút thì kéo về 15 vì mỗi lượt là một lần kéo + đẩy git.
"""
from _paths import ROOT, SERVER  # noqa: F401
import os
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

state = tempfile.mkdtemp(prefix="unimate-bk-interval-")
os.environ["UNIMATE_STATE_DIR"] = state
os.environ["BRAINS_DIR"] = str(Path(state) / "brains")
os.environ["UNIMATE_SESSIONS_DB"] = str(Path(state) / "sessions.db")

import main  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


f = main.backup_interval_hours
check("0.25 giờ là 15 phút", f("0.25") == 0.25)
check("0.5 giờ giữ nguyên", f(0.5) == 0.5)
check("dưới 15 phút kéo về 15 phút", f("0.05") == 0.25 and f(0) == 0.25 and f(-3) == 0.25)
check("giờ chẵn cũ vẫn như trước", f(6) == 6.0 and f("1") == 1.0)
for bad in ("abc", "nan", "inf"):
    try:
        f(bad)
        check(f"giá trị hỏng bị từ chối: {bad}", False)
    except ValueError:
        check(f"giá trị hỏng bị từ chối: {bad}", True)

app = FastAPI()
app.post("/backup/config")(main.backup_config)
c = TestClient(app)
check("lưu 0,25 (dấu phẩy) qua API", c.post("/backup/config", data={"interval_hours": "0,25"}).json().get("ok")
      and main.cfgmod.read_settings()["backup"]["interval_hours"] == 0.25)
c.post("/backup/config", data={"interval_hours": "xyz"})
check("giá trị hỏng không ghi đè chu kỳ đã lưu", main.cfgmod.read_settings()["backup"]["interval_hours"] == 0.25)

src = (SERVER / "main.py").read_text(encoding="utf-8")
check("vòng nền tính chu kỳ bằng cùng hàm (không ép giờ chẵn)",
      'interval = backup_interval_hours(bcfg.get("interval_hours", 6)) * 3600' in src
      and 'max(1, int(bcfg.get("interval_hours", 6)))' not in src)
check("dòng trạng thái đồng bộ ghi giờ theo múi giờ người dùng, không theo giờ máy chủ (VPS chạy UTC)",
      '_dt_bk.datetime.now(localefmt.tz()).strftime("%H:%M %d/%m")' in src
      and '"✓ Đồng bộ 2 chiều " + time.strftime(' not in src)
js = (ROOT / "dashboard" / "console.js").read_text(encoding="utf-8")
check("ô nhập cho số lẻ, bước 15 phút", 'id="bkInterval" min="0.25" step="0.25"' in js)

if fails:
    print(f"\n{len(fails)} FAILED")
    sys.exit(1)
print("\nOK - backup interval 15 minutes")
