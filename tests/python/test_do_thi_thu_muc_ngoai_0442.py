"""0.442.0: trang Đồ thị không hiện một thư mục ngoài trùng với bộ não đã kết nối.

    python tests/run.py do_thi_thu_muc_ngoai_0442      (KHÔNG mạng)

Chủ dự án gặp 04/11/2026: menu chọn não hiện "Bonao_AI · 1136" (não) và thêm nhóm "Thư mục ngoài" có Bonao_AI. Trên máy
anh, `brains/Bonao_AI` là LỐI TẮT tới `D:/9. AI/01. BRAIN PROJECT/Bonao_AI`, còn thư mục ngoài trỏ thẳng tới đó, nên dashboard
so hai chuỗi đường dẫn thì không khớp. Máy chủ giờ trả thêm đường dẫn thật (`real`, đã đi theo lối tắt) ở GET /brains và
GET /path/exists để dashboard so đúng thư mục. Phần dashboard (gỡ trùng, nút Gỡ, nhãn nhóm) ở tests/js/test_brains_ui.mjs.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import sys
import tempfile
from pathlib import Path

_STATE = tempfile.mkdtemp(prefix="unimate-0442-")
os.environ["UNIMATE_STATE_DIR"] = _STATE
os.environ["BRAINS_DIR"] = str(Path(_STATE) / "brains")
os.environ["UNIMATE_ALLOWED_HOSTS"] = "testserver"
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them)[:300] + "]") if not cond else ""))
    if not cond:
        _fails.append(name)


import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

cl = TestClient(main.app)
brains = Path(os.environ["BRAINS_DIR"])
brains.mkdir(parents=True, exist_ok=True)
that = Path(tempfile.mkdtemp(prefix="unimate-0442-vault-")) / "Bonao_AI"
that.mkdir()
(that / "ghi-chu.md").write_text("# x\n", encoding="utf-8")
(brains / "Bonao_AI").symlink_to(that, target_is_directory=True)
(brains / "Rieng").mkdir()

ds = {b["name"]: b for b in cl.get("/brains").json()["brains"]}
check("GET /brains: não là lối tắt vẫn được liệt kê", "Bonao_AI" in ds, list(ds))
b = ds.get("Bonao_AI") or {}
check("GET /brains: `path` giữ địa chỉ trong thư mục brains (không đổi)", b.get("path") == str(brains / "Bonao_AI"), b)
check("GET /brains: `real` là thư mục thật sau lối tắt", b.get("real") == str(that.resolve()), b)
check("GET /brains: não thường có `real`", (ds.get("Rieng") or {}).get("real") == str((brains / "Rieng").resolve()))

r = cl.get("/path/exists", params={"path": str(that)}).json()
check("GET /path/exists: thư mục thật trả `real` khớp `real` của não", r.get("is_dir") is True and r.get("real") == b.get("real"), r)
r = cl.get("/path/exists", params={"path": str(brains / "Bonao_AI")}).json()
check("GET /path/exists: đi qua lối tắt cũng ra cùng `real`", r.get("real") == b.get("real"), r)
r = cl.get("/path/exists", params={"path": str(that / "khong-co")}).json()
check("GET /path/exists: thư mục không có thì không trả `real`, giữ đúng câu trả lời cũ",
      r.get("exists") is False and r.get("is_dir") is False and "real" not in r, r)

print()
if _fails:
    print(f"FAIL {len(_fails)}: {_fails}")
    sys.exit(1)
print("OK - test_do_thi_thu_muc_ngoai_0442: all pass")
