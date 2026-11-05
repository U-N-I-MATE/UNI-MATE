/* Facebook Page comments card on the Connections page (0.448.0).
 *
 * Owner's decision 05/11/2026: comments under the Pages' posts go to the inbox, read only. The owner makes a Facebook
 * app once (App ID, App Secret), then connects Pages with the Facebook login; logging in again adds more Pages and
 * leaves the ones already connected as they are. Same frame as the Messenger card (messenger-connect.js): a card in the
 * "Available" grid, the forms in the page's shared dialog (window.UniMateConnModal), the connected Pages as one card in
 * the "Connected" list. The server (server/fb_pages.py) never sends a token or the App Secret back.
 *
 * Render helpers are pure and exported for tests/js/test_fb_pages_0448.js. */
(function () {
  "use strict";

  function tw(key, vars) {
    var s = (typeof window !== "undefined" && window.t) ? window.t(key, vars) : key;
    if (vars) {
      s = String(s).replace(/\{(\w+)\}/g, function (m, name) {
        return Object.prototype.hasOwnProperty.call(vars, name) ? String(vars[name]) : m;
      });
    }
    return s;
  }
  function esc(t) {
    return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function icon(name) { return (typeof window !== "undefined" && typeof window.ic === "function") ? window.ic(name) : ""; }
  function infoBtn() { var J = typeof window !== "undefined" && window.UniMateInfo; return J ? J.btn(tw("info.more")) : ""; }
  function infoBody(html) {
    var J = typeof window !== "undefined" && window.UniMateInfo;
    return J ? J.body(html) : '<div class="info-body">' + html + "</div>";
  }
  function logo(size) {
    var I = typeof window !== "undefined" && window.Icons;
    return I && I.kenh ? I.kenh("facebook", { size: size }) : icon("message-square");
  }
  function when(ts) {
    if (!ts) return tw("fbp.never");
    try {
      var d = new Date(ts * 1000);
      return d.toLocaleString(undefined, { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" });
    } catch (e) { return ""; }
  }

  // One Page's state in a few words: what the owner needs to know first.
  function statusOf(p, now) {
    now = now || Date.now() / 1000;
    if (!p.token_ok) return { cls: "bad", text: tw("fbp.st_relogin") };
    if (p.error) return { cls: "warn", text: p.error };
    if (!p.watch) return { cls: "off", text: tw("fbp.st_paused") };
    if (p.relogin_soon) return { cls: "warn", text: tw("fbp.st_relogin_soon") };
    if (p.slowed_until && p.slowed_until > now) return { cls: "warn", text: tw("fbp.st_slowed") };
    return { cls: "ok", text: tw("fbp.st_reading") };
  }

  function pageHtml(p, now) {
    var st = statusOf(p, now);
    var fol = (p.followed || []).map(function (f) {
      return '<div class="fbp-fol" data-post="' + esc(f.post_id) + '"><a href="' + esc(f.url) + '" target="_blank" rel="noopener">'
        + esc(f.url || f.post_id) + '</a><button class="s-btn-ghost" type="button" data-act="unfollow">' + esc(tw("fbp.unfollow"))
        + "</button></div>";
    }).join("");
    return '<div class="lv-card fbp-page" data-id="' + esc(p.page_id) + '">'
      + '<div class="lv-top"><div class="lv-name"><span class="lv-ic">' + logo("18px") + "</span><b>" + esc(p.name) + "</b></div>"
      + '<span class="fbp-st ' + st.cls + '">' + esc(st.text) + "</span></div>"
      + '<div class="lv-meta">' + esc(tw("fbp.meta", { at: when(p.last_at), n: p.comments || 0 }))
      + (p.names ? "" : " · " + esc(tw("fbp.no_names")) + infoBtn()) + "</div>"
      + (p.names ? "" : infoBody(esc(tw("fbp.no_names_how"))))
      + '<div class="lv-actions">'
      + '<button class="s-btn-ghost" type="button" data-act="read">' + esc(tw("fbp.read_now")) + "</button>"
      + '<button class="s-btn-ghost" type="button" data-act="watch">' + esc(tw(p.watch ? "fbp.pause" : "fbp.resume")) + "</button>"
      + '<button class="s-btn-ghost" type="button" data-act="disconnect">' + esc(tw("fbp.disconnect")) + "</button></div>"
      + '<div class="fbp-fols"><div class="fbp-fol-head">' + esc(tw("fbp.followed")) + infoBtn() + "</div>"
      + infoBody(esc(tw("fbp.followed_how")))
      + fol
      + '<div class="fbp-fol-add"><input class="js-input" type="url" data-f="url" placeholder="' + esc(tw("fbp.follow_ph")) + '">'
      + '<button class="s-btn-ghost" type="button" data-act="follow">' + esc(tw("fbp.follow")) + "</button></div></div>"
      + '<div class="lv-msg" role="status"></div></div>';
  }

  function setupHtml(s) {
    s = s || {};
    var months = [];
    for (var m = 1; m <= 24; m++) {
      months.push('<option value="' + m + '"' + (m === (s.retention_months || 12) ? " selected" : "") + ">"
        + esc(tw("fbp.months", { n: m })) + "</option>");
    }
    var ready = !!(s.app_id && s.app_secret_set && s.https);
    return '<div class="fbp-form">'
      + (s.https ? "" : '<div class="msc-warn">' + esc(tw("fbp.need_https")) + "</div>")
      + '<div class="fbp-sec"><b>' + esc(tw("fbp.app_head")) + "</b>" + infoBtn() + "</div>"
      + infoBody(esc(tw("fbp.app_how")))
      + '<div class="msc-grid">'
      + '<div class="si-field msc-field"><label>App ID</label><input class="js-input" data-f="app_id" type="text"'
      + ' autocomplete="off" spellcheck="false" value="' + esc(s.app_id || "") + '"></div>'
      + '<div class="si-field msc-field"><label>App Secret</label><input class="js-input" data-f="app_secret" type="password"'
      + ' autocomplete="off" placeholder="' + esc(s.app_secret_set ? tw("fbp.secret_saved") : "") + '"></div>'
      + '<div class="si-field msc-field"><label>' + esc(tw("fbp.config_id")) + infoBtn() + "</label>"
      + infoBody(esc(tw("fbp.config_id_how")))
      + '<input class="js-input" data-f="config_id" type="text" autocomplete="off" value="' + esc(s.config_id || "") + '"></div>'
      + "</div>"
      + '<div class="si-field msc-field"><label>' + esc(tw("fbp.redirect")) + infoBtn() + "</label>"
      + infoBody(esc(tw("fbp.redirect_how")))
      + '<div class="fbp-copy"><input class="js-input" data-f="redirect" type="text" readonly value="' + esc(s.redirect_uri || "") + '">'
      + '<button class="s-btn-ghost" type="button" data-f="copy">' + esc(tw("fbp.copy")) + "</button></div></div>"
      + '<div class="si-field msc-field"><label>' + esc(tw("fbp.retention")) + infoBtn() + "</label>"
      + infoBody(esc(tw("fbp.retention_how")))
      + '<select class="js-input" data-f="months">' + months.join("") + "</select></div>"
      + '<div class="lv-form-act"><button class="s-btn-ghost" type="button" data-f="save">' + esc(tw("fbp.save")) + "</button>"
      + '<button class="s-btn" type="button" data-f="login"' + (ready ? "" : " disabled") + ">" + esc(tw("fbp.login")) + "</button>"
      + infoBtn() + '<span class="lv-msg" role="status"></span></div>'
      + infoBody(esc(tw("fbp.login_how")))
      + "</div>";
  }

  function catCard(category) {
    return '<div class="cat-card fbp-cat" data-cat="' + esc(category || "") + '">'
      + '<div class="cat-ico">' + logo("28px") + "</div>"
      + '<div class="cat-name">' + esc(tw("fbp.head")) + ' <span class="prov-kind">' + esc(tw("fbp.badge")) + "</span>"
      + infoBtn() + "</div>"
      + '<div class="cat-desc j-clamp2">' + esc(tw("fbp.card_desc")) + "</div>"
      + infoBody(esc(tw("fbp.intro")))
      + '<button class="gcard-btn" type="button" data-fbp-open="1">' + esc(tw("models.connect")) + "</button></div>";
  }

  function groupHtml(s) {
    var pages = (s && s.pages) || [];
    if (!pages.length) return "";
    var bad = pages.filter(function (p) { return !p.token_ok || p.relogin_soon; }).length;
    return '<div class="prov-card conn-card fbp-group">'
      + '<div class="prov-head"><span class="conn-ico">' + logo("24px") + "</span>"
      + '<div class="prov-info"><div class="prov-name">' + esc(tw("fbp.head")) + infoBtn() + "</div>"
      + '<div class="prov-status j-clamp2">' + esc(tw("fbp.card_desc")) + "</div>"
      + infoBody(esc(tw("fbp.intro"))) + "</div></div>"
      + '<button type="button" class="cb-st msc-more" data-fbp-pages aria-haspopup="dialog"><span class="cb-st-chips">'
      + '<span class="cb-st-chip">' + esc(tw("fbp.pages_n", { n: pages.length })) + "</span>"
      + (bad ? '<span class="cb-st-chip warn">' + esc(tw("fbp.need_login_n", { n: bad })) + "</span>" : "")
      + '</span><span class="cb-st-more">' + esc(tw("fbp.view")) + " " + icon("chevron-right") + "</span></button>"
      + '<div class="conn-accounts"><button class="conn-chip add" type="button" data-fbp-add="1">＋ ' + esc(tw("fbp.add_more"))
      + '</button><button class="conn-chip" type="button" data-fbp-open="1">' + esc(tw("fbp.settings")) + "</button></div></div>";
  }

  async function api(url, body) {
    try {
      var r = await fetch(url, body === undefined ? undefined : {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      return await r.json();
    } catch (e) { return { ok: false, error: tw("fbp.err_net") }; }
  }

  var setup = null, host = null;

  async function load() {
    setup = await api("/facebook-pages/setup");
    if (!host) return setup;
    if (!setup || !setup.ok) { host.innerHTML = ""; return setup; }
    host.innerHTML = groupHtml(setup);
    var n = (setup.pages || []).length;
    if (window.UniMateMessenger && window.UniMateMessenger.addToConnCount) {
      var total = window.UniMateMessenger.addToConnCount("fbp", n);
      var empty = document.querySelector("#connList > .mp-empty");
      if (empty) empty.hidden = total > 0;
    }
    wire(host);
    return setup;
  }

  function wire(root) {
    root.querySelectorAll("[data-fbp-open]").forEach(function (b) { b.onclick = function () { openSetup(); }; });
    root.querySelectorAll("[data-fbp-add]").forEach(function (b) { b.onclick = function () { login(); }; });
    var more = root.querySelector("[data-fbp-pages]");
    if (more) more.onclick = function () { openPages(); };
  }

  function login() { window.location.href = "/facebook-pages/login"; }

  async function openSetup() {
    var M = typeof window !== "undefined" && window.UniMateConnModal;
    if (!M) return;
    if (!setup) await load();
    var m = M.open(M.head(esc(tw("fbp.dialog_head"))) + '<div class="conn-form">' + setupHtml(setup || {}) + "</div>", 640);
    var f = m.querySelector(".fbp-form");
    var msg = f.querySelector(".lv-msg");
    f.querySelector('[data-f="copy"]').onclick = function () {
      var inp = f.querySelector('[data-f="redirect"]');
      try { navigator.clipboard.writeText(inp.value); msg.textContent = tw("fbp.copied"); } catch (e) { inp.select(); }
    };
    f.querySelector('[data-f="save"]').onclick = async function () {
      var v = { app_id: f.querySelector('[data-f="app_id"]').value.trim(),
                app_secret: f.querySelector('[data-f="app_secret"]').value.trim(),
                config_id: f.querySelector('[data-f="config_id"]').value.trim() };
      msg.textContent = tw("fbp.working");
      var r = await api("/facebook-pages/app", v);
      if (r.ok) r = await api("/facebook-pages/retention", { months: f.querySelector('[data-f="months"]').value });
      f.querySelector('[data-f="app_secret"]').value = "";
      if (!r.ok) { msg.textContent = r.error || tw("fbp.err_net"); return; }
      await load();
      msg.textContent = tw("fbp.saved");
      var go = f.querySelector('[data-f="login"]');
      go.disabled = !(setup && setup.app_id && setup.app_secret_set && setup.https);
    };
    f.querySelector('[data-f="login"]').onclick = login;
  }

  function openPages() {
    var M = typeof window !== "undefined" && window.UniMateConnModal;
    var pages = (setup && setup.pages) || [];
    if (!M || !pages.length) return;
    var m = M.open(M.head(esc(tw("fbp.pages_head", { n: pages.length })))
      + '<div class="conn-form fbp-list">' + pages.map(function (p) { return pageHtml(p); }).join("") + "</div>", 680);
    m.querySelectorAll(".fbp-page").forEach(function (card) {
      card.querySelectorAll("[data-act]").forEach(function (btn) {
        btn.onclick = function () { act(card, btn); };
      });
    });
  }

  async function act(card, btn) {
    var id = card.dataset.id, what = btn.dataset.act;
    var msg = card.querySelector(".lv-msg");
    var p = ((setup && setup.pages) || []).filter(function (x) { return x.page_id === id; })[0] || {};
    var r;
    msg.textContent = tw("fbp.working");
    if (what === "read") {
      r = await api("/facebook-pages/read-now", { page_id: id });
      msg.textContent = r.ok ? tw("fbp.read_done", { n: r.new || 0 }) : (r.error || tw("fbp.err_net"));
      await load();
      return;
    }
    if (what === "watch") {
      r = await api("/facebook-pages/watch", { page_id: id, on: !p.watch });
    } else if (what === "follow") {
      r = await api("/facebook-pages/follow", { page_id: id, url: card.querySelector('[data-f="url"]').value.trim() });
    } else if (what === "unfollow") {
      r = await api("/facebook-pages/unfollow", { page_id: id, post_id: btn.closest(".fbp-fol").dataset.post });
    } else if (what === "disconnect") {
      if (btn.dataset.confirm !== "1") {
        r = await api("/facebook-pages/disconnect", { page_id: id });
        if (!r.ok) { msg.textContent = r.error || tw("fbp.err_net"); return; }
        btn.dataset.confirm = "1";
        btn.textContent = tw("fbp.disconnect_confirm", { n: r.comments || 0 });
        btn.classList.add("danger");
        msg.textContent = tw("fbp.disconnect_warn");
        return;
      }
      r = await api("/facebook-pages/disconnect", { page_id: id, confirm: true });
    }
    if (!r || !r.ok) { msg.textContent = (r && r.error) || tw("fbp.err_net"); return; }
    await load();
    if (what === "disconnect") {
      var M = window.UniMateConnModal;
      if ((setup.pages || []).length) openPages(); else if (M) M.close();
      return;
    }
    openPages();
  }

  function mount(el) {
    host = el || null;
    if (host) load();
  }

  var api_ = { mount: mount, catCard: catCard, groupHtml: groupHtml, pageHtml: pageHtml, setupHtml: setupHtml,
    statusOf: statusOf, openSetup: openSetup, openPages: openPages, wire: wire };
  if (typeof window !== "undefined") window.UniMateFbPages = api_;
  if (typeof module !== "undefined" && module.exports) module.exports = api_;
})();
