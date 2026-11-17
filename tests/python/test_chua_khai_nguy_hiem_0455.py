"""0.455.0: an MCP tool nobody classified is danger, not read.

    python -m pytest tests/python/test_chua_khai_nguy_hiem_0455.py -q

Order (owner approved 17/11/2026): template declaration, then the MCP's own annotations
(destructiveHint true -> danger, readOnlyHint true -> read), then WRITE_HINTS, then danger.
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))
os.environ.setdefault("UNIMATE_STATE_DIR", tempfile.mkdtemp(prefix="unimate-0455-"))

import mcp_catalog as mc  # noqa: E402

KHUON = {"id": "x", "tool_meta": {"read": ["list_*"], "write": ["save_note"], "danger": ["wipe_*"]}}


def test_declaration_wins_over_hints():
    assert mc.classify_detail(KHUON, "list_items", {}, {"destructiveHint": True}) == ("read", "khai")
    assert mc.classify_detail(KHUON, "wipe_all", {}, {"readOnlyHint": True}) == ("danger", "khai")
    assert mc.classify_detail(KHUON, "save_note", {}, {"readOnlyHint": True}) == ("write", "khai")


def test_hints_come_before_name_rules():
    # A tool the MCP calls read-only is read even with a write word in its name, and the reverse.
    assert mc.classify_detail(KHUON, "create_preview", {}, {"readOnlyHint": True}) == ("read", "goi_y")
    assert mc.classify_detail(KHUON, "move_item", {}, {"readOnlyHint": False, "destructiveHint": True}) \
        == ("danger", "goi_y")
    # Contradictory hints stay on the safe side.
    assert mc.classify(KHUON, "odd", {}, {"readOnlyHint": True, "destructiveHint": True}) == "danger"


def test_only_explicit_true_counts():
    for hints in (None, {}, {"readOnlyHint": False}, {"readOnlyHint": "true"}, {"destructiveHint": False}, "x"):
        assert mc.classify_detail(KHUON, "run_report", {}, hints) == ("danger", "mac_dinh"), hints
    assert mc.classify_detail(KHUON, "update_row", {}, {"readOnlyHint": False}) == ("write", "ten")


def test_undeclared_without_hint_is_danger_also_for_custom():
    assert mc.classify(None, "list_domains") == "danger"
    assert mc.classify({}, "fetch_report", {}) == "danger"
    assert mc.classify(None, "list_domains", None, {"readOnlyHint": True}) == "read"


def test_allowed_names_the_real_reason():
    ok, why = mc.allowed(None, "readonly", "full", "fetch_report", {})
    assert not ok and "chưa khai" in why and "Toàn quyền" in why
    ok, why = mc.allowed(None, "safe", "full", "fetch_report", {})
    assert not ok and "chưa khai" in why
    assert mc.allowed(None, "full", "full", "fetch_report", {}) == (True, "")
    assert mc.allowed(None, "readonly", "full", "fetch_report", {}, {"readOnlyHint": True}) == (True, "")
    # A declared danger tool keeps the old wording.
    ok, why = mc.allowed(KHUON, "safe", "full", "wipe_all", {})
    assert not ok and "chưa khai" not in why and "NGUY HIỂM" in why
    # The mode cap still applies: a read-hinted tool passes suggest, an undeclared one does not.
    assert mc.allowed(None, "full", "suggest", "x_read", {}, {"readOnlyHint": True})[0]
    assert not mc.allowed(None, "full", "suggest", "x_read", {})[0]


def test_listing_hides_undeclared_tools_from_readonly_and_safe():
    # Hub listing uses classify(args=None): an undeclared tool is not offered below Full access.
    assert mc.classify(None, "list_domains", None) == "danger"
    assert mc.classify(None, "list_domains", None, {"readOnlyHint": True}) == "read"


def _con(cid):
    return mc.load()[cid]


def test_core_catalog_declares_the_tools_that_used_to_be_guessed_read():
    # Real tool lists, read from the latest releases on 17/11/2026 (tools/list), see CHANGELOG 0.455.0.
    reads = {
        "google-search-console": ["list_sites", "search_analytics", "enhanced_search_analytics", "detect_quick_wins",
                                  "index_inspect", "list_sitemaps", "get_sitemap"],
        "botcake": ["botcake_customers", "botcake_customer", "botcake_customer_fields_get", "botcake_custom_fields",
                    "botcake_tags", "botcake_tag_statistic", "botcake_flows", "botcake_flow_statistics",
                    "botcake_keywords", "botcake_sequences", "botcake_message_templates"],
        "google-sheets": ["get_sheet_data", "get_sheet_formulas", "list_sheets", "get_multiple_sheet_data",
                          "get_multiple_spreadsheet_summary", "get_spreadsheet_info", "list_spreadsheets",
                          "list_folders", "search_spreadsheets", "find_in_spreadsheet"],
        "google-workspace": ["download_chat_attachment", "get_gmail_attachment_content", "search_drive_files",
                             "get_doc_content", "read_sheet_values", "list_script_deployments"],
        "google-keep": ["download_media"],
        "notebooklm": ["chat_status", "source_list_play_books"],
        "gmail": ["get_message"],
        "google-calendar": ["search_events"],
    }
    for cid, tools in reads.items():
        con = _con(cid)
        for t in tools:
            assert mc.classify(con, t, {}) == "read", (cid, t)
            assert mc.allowed(con, "readonly", "full", t, {})[0], (cid, t)
    # Tools that slipped into read before 0.455.0 and are now where they belong.
    assert mc.classify(_con("google-workspace"), "insert_doc_elements", {}) == "write"
    assert mc.classify(_con("google-workspace"), "find_and_replace_doc", {}) == "write"
    assert mc.classify(_con("google-sheets"), "rename_sheet", {}) == "write"
    assert mc.classify(_con("google-keep"), "replace_list_items", {}) == "danger"
    assert mc.classify(_con("google-ads"), "labels_manage_labels", {}) == "danger"
    assert mc.classify(_con("botcake"), "botcake_send_flow", {}) == "danger"


def test_discover_resolved_keeps_the_annotations():
    import mcp_client

    class Pool:
        async def list_tools(self, spec):
            return [{"name": "peek", "annotations": {"readOnlyHint": True}},
                    {"name": "plain"}, {"name": "odd", "annotations": "not a dict"}]

        def dang_goi_tool(self, spec):
            return False

    conn = {"id": "c1", "connector_id": "custom", "namespace": "src", "label": "src", "perm": "readonly",
            "transport": "stdio", "command": "x", "args": [], "env": {}, "headers": {}}
    old_pool, old_spec = mcp_client.pool, mcp_client._conn_spec
    try:
        mcp_client.pool = Pool()
        mcp_client._conn_spec = lambda c: {"transport": "stdio", "command": "x", "args": [], "headers": {}, "env": {}}
        tools, route = asyncio.run(mcp_client.discover_resolved([conn]))
    finally:
        mcp_client.pool, mcp_client._conn_spec = old_pool, old_spec
    by_tool = {r["tool"]: r for r in route.values()}
    assert by_tool["peek"]["annotations"] == {"readOnlyHint": True}
    assert by_tool["plain"]["annotations"] is None
    assert by_tool["odd"]["annotations"] is None
