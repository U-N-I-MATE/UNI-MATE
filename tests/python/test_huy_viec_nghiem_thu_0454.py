"""0.454.0: cancel background jobs from chat; a job is judged on its work, a long report is shortened.

    python tests/run.py huy_viec_nghiem_thu_0454

Owner 16/11/2026 (approved 15:39):
1. "huỷ việc X" in chat did nothing: unimate_task had no cancel and its description sent the owner to the Tasks page
   (14/11 t_b00a871979f2, four duplicate QĐ 74 jobs, 15/11 two merge jobs, all cancelled by hand). Now op=cancel takes
   one or more ids, goes the same path as the Tasks page button (a running worker and its processes are stopped, a job
   left `running` by a restart is closed too), cancels waiting, running, asking or stuck jobs, reports each one with
   its state before, does NOT cancel the jobs waiting on it unless asked again with with_waiting, and only the owner's
   own chat may cancel.
2. The acceptance check failed finished jobs only because the closing report ran longer than "Tin báo ... không quá 3
   câu" (t_2d6ce500d9a5: video merged and on drive H, report 8-9 sentences; t_de73770197db: all voice lines, report 4
   sentences). Criteria about the report's form no longer decide; the job goes to Done and the chat gets a message cut
   to the cap, the full report stays in the job's result. The 3-sentence rule (QĐ 73) stays.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import importlib.util
from pathlib import Path

from task_store import TaskStore  # noqa: F401
import tasks as tasks_mod
from tasks import TasksDeps, TasksFeature

# The real criteria of the two jobs (read from the VPS, /kanban/task/show, 16/11/2026).
ACC_VIDEO = [
    "Đã đọc Tiendo.json trước khi ghép; nếu việc A chưa có bản quay Excel 150% đạt soát khung thì Tiendo.json ghi rõ "
    "trạng thái dừng kèm lý do và không có video ghép mới",
    "Nếu đủ điều kiện ghép: 137 câu giọng có sẵn không bị tạo lại hay ghi đè (dấu thời gian và dung lượng giữ "
    "nguyên), chỉ thêm câu thiếu và câu đổi lời, trong đó có 06_04 và các câu đoạn 05 việc A đã sửa",
    "Nếu đủ điều kiện ghép: bản video đạt đã có trên ổ H đúng đường dẫn ghi trong Giaoviec_QD78.md, dung lượng khớp",
    "Tin báo cuối không quá 3 câu và có đường dẫn video hoặc lý do dừng",
    "Không dùng tác tử con chạy nền",
]
ACC_GIONG = [
    "Mỗi câu lời trong kịch bản Bài 1.2 có đúng một tệp âm thanh giọng Breeze tại thư mục giao việc chỉ định, số tệp "
    "bằng số câu lời",
    "Văn bản dùng để tạo từng tệp giọng khớp nguyên văn câu lời trong kịch bản, không câu nào bị thiếu hay sửa chữ",
    "Tin báo kết quả không quá 3 câu",
]
REPORT_VIDEO = ("Đã ghép xong video Bài 1.1, dài 12 phút 52 giây. Bản ghép ở Quay_Thu/Bai_1.1/Bai_1.1_Chuan.mp4. "
                "Soát 4 phần đều đạt. Đã đẩy lên ổ H, dung lượng khớp. Tiendo.json đã ghi từng bước. "
                "Giọng giữ nguyên 137 câu cũ, thêm 6 câu mới. Không dùng tác tử con. Anh xem video giúp em. "
                "Chi tiết ở báo cáo.")


def _atomic(path, text):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


async def _workflow(*_args, **_kwargs):
    if False:
        yield {}


def _feature(tmp_path):
    brain = tmp_path / "Brain"
    brain.mkdir(exist_ok=True)
    sent = []

    async def report(chat_id, text, **kw):
        sent.append({"chat_id": chat_id, "text": text, **kw})
        return True

    deps = TasksDeps(
        brain_root=lambda value: str(brain), atomic_write_text=_atomic, execute_workflow=_workflow,
        workflows_dir=lambda b: brain / "workflows", build_system_prompt=lambda b: "system",
        aux_model=lambda: None, safe_tools=["Read", "Write"], state_dir=tmp_path / "state",
        scheduler_brains=lambda: [str(brain)], report=report,
    )
    return TasksFeature(deps), brain, sent


def _job(feature, brain, title, status="ready", deps=None, acceptance=None):
    root = feature._ensure(str(brain))
    tid = feature.store.enqueue(root, title, title, capability="files", status=status, chat_id="web:s1",
                                deps=deps or [])
    if acceptance:
        feature.store.update_metadata(tid, {"acceptance": acceptance}) if hasattr(feature.store, "update_metadata") \
            else feature.store._db.execute("UPDATE tasks SET metadata_json=? WHERE id=?",
                                           (__import__("json").dumps({"acceptance": acceptance}), tid))
        try:
            feature.store._db.commit()
        except Exception:
            pass
    return tid


def _plugin():
    spec = importlib.util.spec_from_file_location(
        "unimate_task_plugin_0454", ROOT / "system" / "plugins" / "unimate-task" / "plugin.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---------------------------------------------------------------- 1. cancel
def test_cancel_waiting_asking_stuck_and_review_jobs_reports_state_before(tmp_path):
    f, brain, _ = _feature(tmp_path)
    a = _job(f, brain, "Việc chờ chạy")
    b = _job(f, brain, "Việc đang hỏi")
    assert f.store.claim(b, "w") and f.store.ask(b, "w", "Gửi cho khách nào?")
    c = _job(f, brain, "Việc kẹt")
    assert f.store.claim(c, "w") and f.store.block(c, "w", "tool_error", "lỗi công cụ")
    r = asyncio.run(f.cancel(str(brain), [a, b, c]))
    assert r["ok"] and not r["failed"], r
    before = {d["id"]: d["before"] for d in r["cancelled"]}
    assert before == {a: "ready", b: "blocked", c: "blocked"}
    assert all(f.store.get_task(t)["status"] == "cancelled" for t in (a, b, c))
    again = asyncio.run(f.cancel(str(brain), [a]))
    assert not again["ok"] and again["failed"][0]["before"] == "cancelled"
    f.store.close()


def test_cancel_running_job_stops_its_worker_and_processes(tmp_path, monkeypatch):
    f, brain, _ = _feature(tmp_path)
    t = _job(f, brain, "Ghép video")
    killed = []
    monkeypatch.setattr(tasks_mod, "cancel_all", lambda tag: killed.append(tag) or 1)

    async def go():
        async def worker():
            await asyncio.sleep(30)
        f.store.claim(t, "w")
        f._workers[t] = asyncio.create_task(worker())
        r = await f.cancel(str(brain), [t])
        await asyncio.sleep(0)
        return r, f._workers[t].cancelled()

    r, was_cancelled = asyncio.run(go())
    assert r["cancelled"][0]["before"] == "running" and was_cancelled
    assert killed == [f"dispatch:{t}"]
    f.store.close()


def test_cancel_running_job_left_by_a_restart_is_closed_not_orphaned(tmp_path, monkeypatch):
    f, brain, _ = _feature(tmp_path)
    t = _job(f, brain, "Ghép video")
    monkeypatch.setattr(tasks_mod, "cancel_all", lambda tag: 0)
    f.store.claim(t, "w")                      # running in the store, no worker in this process
    r = asyncio.run(f.cancel(str(brain), [t]))
    assert r["ok"] and f.store.get_task(t)["status"] == "cancelled"
    f.store.close()


def test_jobs_waiting_on_a_cancelled_job_are_listed_then_cancelled_on_a_yes(tmp_path):
    f, brain, _ = _feature(tmp_path)
    a = _job(f, brain, "Quay video")
    b = _job(f, brain, "Ghép giọng", status="todo", deps=[a])
    c = _job(f, brain, "Đẩy ổ H", status="todo", deps=[b])
    r = asyncio.run(f.cancel(str(brain), [a]))
    assert [d["id"] for d in r["cancelled"]] == [a]
    assert [w["id"] for w in r["waiting"]] == [b, c], r["waiting"]
    assert f.store.get_task(b)["status"] == "todo" and f.store.get_task(c)["status"] == "todo"
    r2 = asyncio.run(f.cancel(str(brain), [a], with_waiting=True))
    assert {d["id"] for d in r2["cancelled"]} == {b, c} and not r2["waiting"]
    f.store.close()


def test_tasks_page_button_and_tool_share_one_path():
    src = (Path(SERVER) / "tasks.py").read_text(encoding="utf-8")
    route = src[src.index('@router.post("/kanban/task/cancel")'):src.index('@router.post("/kanban/stop")')]
    assert "self._cancel_one(task)" in route


def test_tool_op_cancel_owner_only_and_report(tmp_path, monkeypatch):
    import turn_context
    f, brain, _ = _feature(tmp_path)
    monkeypatch.setattr(tasks_mod, "current", lambda: f)
    m = _plugin()

    class Ctx:
        vault_root = str(brain)

    # The real case of 14/11: four duplicate jobs in one go, one of them waiting on another.
    ids = [_job(f, brain, f"QĐ 74 bài {n}") for n in ("4.6", "5A.8", "5B.8")]
    w = _job(f, brain, "QĐ 74 bài 5C.8", status="todo", deps=[ids[0]])
    tok = turn_context.bind(turn_context.make("dashboard", chat_id="s1", la_chu=True, session_id="s1"))
    try:
        out = asyncio.run(m._chay({"op": "cancel", "ids": ",".join(ids)}, Ctx()))
    finally:
        turn_context.reset(tok)
    assert out.startswith("Đã huỷ 3 việc:"), out
    assert "trước khi huỷ: đang chờ tới lượt chạy" in out
    assert w in out and "CHƯA HUỶ" in out and "with_waiting=true" in out
    assert f.store.get_task(w)["status"] == "todo"

    for turn, why in ((None, "không rõ ai"),
                      (turn_context.make("bot:shop", chat_id="c", la_chu=False), "không phải chủ"),
                      (turn_context.make("zalo", chat_id="g", chat_type="group", la_chu=True), "nhóm chat"),
                      (turn_context.make("kanban", la_chu=True, job="kanban:t_x"), "việc nền")):
        tok = turn_context.bind(turn)
        try:
            out = asyncio.run(m._chay({"op": "cancel", "ids": w}, Ctx()))
        finally:
            turn_context.reset(tok)
        assert out.startswith("ERROR: chỉ chủ") and why in out, (turn, out)
    assert f.store.get_task(w)["status"] == "todo"
    # A follow-up turn of the owner's chat (0.453.0) is still the owner.
    tok = turn_context.bind(turn_context.make("dashboard", chat_id="s1", la_chu=True, job="noitiep:abc"))
    try:
        out = asyncio.run(m._chay({"op": "cancel", "ids": [w]}, Ctx()))
    finally:
        turn_context.reset(tok)
    assert out.startswith("Đã huỷ 1 việc:"), out
    f.store.close()


def test_tool_description_and_prompt_say_cancel_works():
    src = (Path(ROOT) / "system/plugins/unimate-task/plugin.py").read_text(encoding="utf-8")
    assert '"enum": ["add", "list", "answer", "cancel"]' in src
    assert "huỷ việc và duyệt" not in src and "op=cancel: CHỦ bảo huỷ việc" in src
    md = (Path(ROOT) / "CLAUDE.md").read_text(encoding="utf-8")
    assert "`unimate_task` op=cancel" in md and "with_waiting=true" in md


# ---------------------------------------------------------------- 2. acceptance
def test_form_criteria_are_split_from_the_work():
    n, h = tasks_mod.tach_dieu_kien(ACC_VIDEO)
    assert h == ["Tin báo cuối không quá 3 câu và có đường dẫn video hoặc lý do dừng"] and len(n) == 4
    assert tasks_mod.tran_cau(h) == 3
    n2, h2 = tasks_mod.tach_dieu_kien(ACC_GIONG)
    assert h2 == ["Tin báo kết quả không quá 3 câu"] and len(n2) == 2
    # "137 câu giọng" is about the work, never a sentence cap.
    assert any("137 câu giọng" in c for c in n)


def test_checker_judges_only_the_work_and_writes_the_short_message(tmp_path):
    f, brain, _ = _feature(tmp_path)
    t = _job(f, brain, "Video Bài 1.1 - B", acceptance=ACC_VIDEO)
    task = f.store.get_task(t)
    seen = {}

    class FakeCli:
        disallowed_tools = []

    f._base_cli = lambda *a, **k: FakeCli()

    async def query(cli, prompt):
        seen["prompt"] = prompt
        return ('{"pass": true, "missing": "", "tin_ngan": "Đã ghép video Bài 1.1 dài 12 phút 52 giây và đẩy lên ổ H. '
                'Bản ghép ở Quay_Thu/Bai_1.1/Bai_1.1_Chuan.mp4. Anh xem giúp em."}', "", {})

    f._query = query
    passed, why, how = asyncio.run(f._check_acceptance(task, REPORT_VIDEO))
    assert passed and how == "ai"
    crit = seen["prompt"].split("ĐIỀU KIỆN HOÀN THÀNH:")[1].split("BÁO CÁO CỦA WORKER")[0]
    assert "không quá 3 câu" not in crit and "137 câu giọng" in crit
    assert "KHÔNG phải lý do để trượt" in seen["prompt"] and '"tin_ngan"' in seen["prompt"]
    short = f.tin_ngan(task, REPORT_VIDEO)
    assert short.startswith("Đã ghép video Bài 1.1") and tasks_mod.dem_cau(short) <= 3
    f.store.close()


def test_long_report_job_goes_to_done_and_the_chat_gets_three_sentences(tmp_path):
    f, brain, sent = _feature(tmp_path)
    t = _job(f, brain, "Video Bài 1.2 - B: giọng", acceptance=ACC_GIONG)

    async def check(task, result):          # the work is fine
        return True, "", "ai"

    async def execute(task):
        return ("Đã tạo đủ 160 câu giọng Breeze. Mỗi câu khớp nguyên văn kịch bản. Tiendo.json đã có thời lượng "
                "từng tệp. Không tạo video ghép ở bước này."), "", False, {"provider": "test"}

    f._check_acceptance = check
    f._execute = execute
    claimed = f.store.claim(t, "w")
    asyncio.run(f._run_worker(claimed, "w"))
    task = f.store.get_task(t)
    assert task["status"] == "done", task["status"]
    assert "160 câu giọng" in task["result"] and "Không tạo video ghép" in task["result"]   # full report kept
    msg = [s for s in sent if s.get("viec", {}).get("status") == "done"][-1]
    body = msg["web"]
    assert tasks_mod.dem_cau(body) <= 3 and "Không tạo video ghép" not in body, body
    f.store.close()


def test_short_report_is_sent_as_is(tmp_path):
    f, brain, _ = _feature(tmp_path)
    t = _job(f, brain, "Việc ngắn", acceptance=ACC_GIONG)
    task = f.store.get_task(t)
    assert f.tin_ngan(task, "Đã tạo đủ 160 câu giọng. Khớp kịch bản.") == ""
    f.store.close()


def test_work_that_is_not_done_still_fails():
    src = (Path(SERVER) / "tasks.py").read_text(encoding="utf-8")
    assert "if not passed:" in src and "Chưa đạt điều kiện hoàn thành" in src


if __name__ == "__main__":
    import sys
    try:
        import pytest
    except ImportError:
        print("bỏ qua: chưa cài pytest")
        sys.exit(0)
    sys.exit(pytest.main([__file__, "-q"]))
