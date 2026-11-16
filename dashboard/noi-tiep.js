/* noi-tiep.js - Settings switch "Continue when background work ends" (0.453.0).
   Background work given from a chat (shell job, Kanban job, team job, workflow run) opens a follow-up turn in that chat
   once it has ended, so UNI MATE reads the results and does the next step (server/noi_tiep_nen.py). On by default; this
   block lets the owner turn it off and shows the caps. Vanilla DOM, same family as may-chay-lich.js. */
(function () {
  "use strict";

  function $(id) { return document.getElementById(id); }
  function t(k, v) {
    var s = typeof window.t === "function" ? window.t(k, v) : k;
    if (v) s = String(s).replace(/\{(\w+)\}/g, function (m, x) { return Object.prototype.hasOwnProperty.call(v, x) ? String(v[x]) : m; });
    return s;
  }

  var _st = null, _msg = "", _err = false;

  function draw() {
    var box = $("ntBox");
    if (!box || !_st) return;
    box.innerHTML =
      '<label class="loop-row" style="padding:0"><span>' + t("nt.on") + '</span>' +
      '<label class="toggle"><input type="checkbox" id="ntOn"' + (_st.enabled ? " checked" : "") + '><span></span></label></label>' +
      '<div class="opt-sub">' + t("nt.caps", { chuoi: _st.tran_chuoi, gio: _st.tran_gio }) + '</div>' +
      (_msg ? '<div class="opt-sub" style="color:var(' + (_err ? "--red" : "--green") + ')">' + _msg + '</div>' : "");
  }

  async function load() {
    try {
      var r = await fetch("/noi-tiep", { cache: "no-store" });
      _st = await r.json();
    } catch (e) { _st = null; }
    draw();
    return _st;
  }

  async function save(on) {
    var f = new FormData();
    f.append("enabled", on ? "1" : "0");
    try {
      var r = await fetch("/noi-tiep", { method: "POST", body: f });
      var d = await r.json();
      _err = !(d && d.ok);
      if (!_err) _st.enabled = !!d.enabled;
    } catch (e) { _err = true; }
    _msg = t(_err ? "nt.err" : "nt.saved");
    draw();
  }

  function init() {
    var box = $("ntBox");
    if (!box) return;
    box.addEventListener("change", function (ev) {
      if (ev.target && ev.target.id === "ntOn") save(ev.target.checked);
    });
    load();
  }

  window.UniMateNoiTiep = { load: load };
  if (typeof module !== "undefined" && module.exports) module.exports = { load: load, save: save };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
