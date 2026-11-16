/* may-chay-lich.js - Settings block "Schedule machine" (0.452.0).
   The owner runs UNI MATE on a home PC and on a VPS over the same brains. Only one of them runs reminders, loops
   and the bots that answer customers (server/may_chay_lich.py). This block shows this machine, lets the owner pick
   the machine that runs schedules, and links the home PC to the VPS with a code made on the VPS (shown once).
   Also exposes window.UniMateMayChay.get() for the banner on the Tasks page. Vanilla DOM, same family as
   remote-access.js. */
(function () {
  "use strict";

  var _st = null;      // last GET /may-chay-lich
  var _code = "";      // a link code just made here (shown once)
  var _msg = "", _msgErr = false, _busy = false;
  var _waiters = [];

  function $(id) { return document.getElementById(id); }
  function t(k, v) {
    var s = typeof window.t === "function" ? window.t(k, v) : k;
    if (v) s = String(s).replace(/\{(\w+)\}/g, function (m, x) { return Object.prototype.hasOwnProperty.call(v, x) ? String(v[x]) : m; });
    return s;
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function kindName(k) { return t(k === "vps" ? "mcl.kind_vps" : "mcl.kind_home"); }

  function injectCss() {
    if ($("mclCss")) return;
    var s = document.createElement("style");
    s.id = "mclCss";
    s.textContent =
      ".mcl{display:flex;flex-direction:column;gap:10px;margin-top:8px;font-size:16px;line-height:1.5}" +
      ".mcl-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}" +
      ".mcl-modes{display:flex;gap:6px}.mcl-modes .gcard-btn{flex:1 1 0;width:auto;font-size:16px}" +
      ".mcl-modes .gcard-btn[aria-pressed=false]{background:var(--surface-2);color:var(--text2);border:1px solid var(--border)}" +
      ".mcl-modes .gcard-btn[aria-pressed=true]{background:var(--accent);color:#fff;border:1px solid var(--accent);font-weight:600}" +
      ".mcl-hint{color:var(--text3)}.mcl-err{color:var(--red)}.mcl-ok{color:var(--green)}" +
      ".mcl-warn{color:var(--warn-ink);background:var(--warn-wash);border:1px solid var(--warn-line);border-radius:8px;padding:8px 10px}" +
      ".mcl input{width:100%;box-sizing:border-box;background:var(--field-bg);border:1px solid var(--border);color:var(--text);" +
      "border-radius:7px;padding:9px 10px;font-size:16px}.mcl input:focus{outline:none;border-color:var(--accent)}" +
      ".mcl code{background:var(--info-wash);padding:3px 7px;border-radius:5px;font-size:14px;overflow-wrap:anywhere;display:block}" +
      ".mcl-lbl{font-weight:600}" +
      ".mcl-actions{display:flex;gap:6px;flex-wrap:wrap}.mcl-actions .gcard-btn{flex:1 1 auto;width:auto;font-size:16px}" +
      "@media(max-width:600px){.mcl-actions{flex-direction:column}.mcl-actions .gcard-btn{width:100%}}";
    document.head.appendChild(s);
  }

  async function getJSON(url) {
    try { var r = await fetch(url, { cache: "no-store" }); return await r.json(); } catch (e) { return null; }
  }
  async function postJSON(url, body) {
    try {
      var r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
      return await r.json();
    } catch (e) { return { ok: false, error: String(e) }; }
  }

  async function load() {
    var d = await getJSON("/may-chay-lich");
    if (d && d.machine) _st = d;
    var w = _waiters; _waiters = [];
    w.forEach(function (fn) { try { fn(_st); } catch (e) {} });
    render();
    return _st;
  }

  /** Status for the Tasks page banner: null until loaded once. */
  function get() { return _st; }

  /** One line the Tasks page shows when this machine does not run schedules ("" when it does). */
  function bannerText(st) {
    st = st || _st;
    if (!st || st.is_runner) return "";
    return t("mcl.banner", { kind: kindName(st.runner), label: st.runner_label || kindName(st.runner) });
  }

  function render() {
    var box = $("mclBox");
    if (!box) return;
    injectCss();
    var st = _st;
    if (!st) { box.innerHTML = '<div class="mcl-hint">' + esc(t("mcl.loading")) + "</div>"; return; }
    var me = st.machine || {};
    var h = "";
    h += '<div><span class="mcl-lbl">' + esc(t("mcl.this")) + ":</span> " + esc(me.label || "") + " (" + esc(kindName(me.kind)) + ")</div>";
    h += '<div class="mcl-lbl">' + esc(t("mcl.runner")) + "</div>";
    h += '<div class="mcl-modes" role="group" aria-label="' + esc(t("mcl.runner")) + '">';
    ["vps", "home"].forEach(function (k) {
      h += '<button type="button" class="gcard-btn" data-mcl="runner" data-v="' + k + '" aria-pressed="' + (st.runner === k) + '"'
        + (_busy ? " disabled" : "") + ">" + esc(kindName(k)) + "</button>";
    });
    h += "</div>";
    h += '<div class="' + (st.is_runner ? "mcl-ok" : "mcl-hint") + '">'
      + esc(st.is_runner ? t("mcl.is_runner") : bannerText(st)) + "</div>";

    if (me.kind === "vps") {
      h += '<div class="mcl-lbl">' + esc(t("mcl.pair_title")) + "</div>";
      h += '<div class="mcl-hint">' + esc(t("mcl.pair_sub")) + "</div>";
      if (_code) {
        h += "<code>" + esc(_code) + "</code>";
        h += '<div class="mcl-warn">' + esc(t("mcl.code_once")) + "</div>";
      }
      h += '<div class="mcl-actions"><button type="button" class="gcard-btn" data-mcl="code"' + (_busy ? " disabled" : "") + ">" + esc(t("mcl.make_code")) + "</button>";
      if (_code) h += '<button type="button" class="gcard-btn" data-mcl="copy">' + esc(t("mcl.copy")) + "</button>";
      if (st.pair_codes) h += '<button type="button" class="gcard-btn" data-mcl="revoke"' + (_busy ? " disabled" : "") + ">" + esc(t("mcl.revoke", { n: st.pair_codes })) + "</button>";
      h += "</div>";
    } else if (st.linked) {
      h += '<div><span class="mcl-lbl">' + esc(t("mcl.linked")) + ":</span> " + esc(st.link_url) + "</div>";
      h += '<div class="' + (st.link_ok ? "mcl-ok" : "mcl-err") + '">' + esc(st.link_ok ? t("mcl.link_ok") : t("mcl.link_bad", { e: st.link_error || "" })) + "</div>";
      if (st.pending) h += '<div class="mcl-hint">' + esc(t("mcl.pending", { n: st.pending })) + "</div>";
      h += '<div class="mcl-actions"><button type="button" class="gcard-btn" data-mcl="unlink"' + (_busy ? " disabled" : "") + ">" + esc(t("mcl.unlink")) + "</button></div>";
    } else {
      h += '<label class="mcl-lbl" for="mclCode">' + esc(t("mcl.paste")) + "</label>";
      h += '<input id="mclCode" type="password" autocomplete="off" spellcheck="false" placeholder="' + esc(t("mcl.paste_ph")) + '">';
      h += '<div class="mcl-hint">' + esc(t("mcl.paste_sub")) + "</div>";
      h += '<div class="mcl-actions"><button type="button" class="gcard-btn" data-mcl="link"' + (_busy ? " disabled" : "") + ">" + esc(t("mcl.link")) + "</button></div>";
    }
    if (st.peers && st.peers.length) {
      h += '<div class="mcl-hint">' + esc(t("mcl.peers")) + ": " + st.peers.map(function (p) { return esc(p.label || p.id) + " (" + esc(kindName(p.kind)) + ")"; }).join(", ") + "</div>";
    }
    if (_msg) h += '<div class="' + (_msgErr ? "mcl-err" : "mcl-ok") + '" role="status">' + esc(_msg) + "</div>";
    box.innerHTML = h;
  }

  async function act(fn) {
    if (_busy) return;
    _busy = true; _msg = ""; render();
    try { await fn(); } finally { _busy = false; await load(); }
  }

  function onClick(e) {
    var b = e.target.closest && e.target.closest("[data-mcl]");
    if (!b || !$("mclBox") || !$("mclBox").contains(b)) return;
    var k = b.dataset.mcl;
    if (k === "runner") {
      return act(async function () {
        var r = await postJSON("/may-chay-lich/runner", { runner: b.dataset.v });
        _msgErr = !(r && r.ok); _msg = _msgErr ? ((r && r.error) || t("mcl.fail")) : t("mcl.saved");
      });
    }
    if (k === "code") {
      return act(async function () {
        var r = await postJSON("/may-chay-lich/pair-code", {});
        if (r && r.ok) { _code = r.code; _msgErr = !r.https; _msg = r.https ? "" : t("mcl.not_https"); }
        else { _msgErr = true; _msg = (r && r.error) || t("mcl.fail"); }
      });
    }
    if (k === "copy") {
      try { navigator.clipboard.writeText(_code); _msgErr = false; _msg = t("mcl.copied"); } catch (er) { _msgErr = true; _msg = t("mcl.fail"); }
      return render();
    }
    if (k === "revoke") {
      return act(async function () {
        var r = await postJSON("/may-chay-lich/pair-revoke", {});
        _code = ""; _msgErr = !(r && r.ok); _msg = _msgErr ? t("mcl.fail") : t("mcl.revoked");
      });
    }
    if (k === "link") {
      var inp = $("mclCode"), code = inp ? inp.value.trim() : "";
      if (!code) { _msgErr = true; _msg = t("mcl.paste_empty"); return render(); }
      return act(async function () {
        var r = await postJSON("/may-chay-lich/link", { code: code });
        _msgErr = !(r && r.ok); _msg = _msgErr ? ((r && r.error) || t("mcl.fail")) : t("mcl.linked_ok");
      });
    }
    if (k === "unlink") {
      return act(async function () {
        var r = await postJSON("/may-chay-lich/unlink", {});
        _msgErr = !(r && r.ok); _msg = _msgErr ? t("mcl.fail") : t("mcl.unlinked");
      });
    }
  }

  window.UniMateMayChay = { load: load, get: get, bannerText: bannerText, kindName: kindName,
    whenLoaded: function (fn) { if (_st) fn(_st); else _waiters.push(fn); } };
  if (typeof module !== "undefined" && module.exports) module.exports = window.UniMateMayChay;

  if (typeof document !== "undefined" && document.addEventListener) {
    document.addEventListener("click", onClick);
    var start = function () { if ($("mclBox")) load(); };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
    // The Settings page opens later: draw (or refresh) when the block becomes visible.
    document.addEventListener("click", function (e) {
      if (e.target && e.target.closest && e.target.closest("#settingsBtn")) setTimeout(load, 50);
    });
  }
})();
