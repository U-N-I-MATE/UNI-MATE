/* chat-steps.js - khoi "tien trinh tung buoc" trong khung chat UNI MATE.

   Van de: server DA ban ra su kien tool_call cho moi engine (main.py), nhung dashboard chi co
   MOT dong trang thai (showActivity): buoc moi ghi de buoc cu, het luot thi xoa sach. Luot
   chay lau thi nguoi dung ngoi nhin mot dong nhay loan, khong biet da lam nhung gi.

   File nay gom cac buoc do lai thanh mot khoi nam ngay tren bong bong tra loi:
     - MAC DINH GAP ca luc dang chay lan luc xong (chu repo yeu cau 2026-09-24: hai chuc dong
       "Dang goi: Bash" bung san day kin khung chat). Dong tom tat van noi dang chay, bao nhieu
       buoc va buoc moi nhat; bam vao moi bung ra. Nguoi dung da bam bung thi giu bung.
     - moi buoc ghi RO viec: "Chay lenh: git status", "Doc file: wiki/a.md" (server gui kem
       truong `detail` rut tu tham so lenh goi, xem server/tool_label.py)

   Chia lam hai tang de test duoc bang node: `nhan`/`tomTat` la ham THUAN (khong dung DOM),
   con `taoKhoi`/`ve` chi ve. Khong goi MCP, khong phu thuoc engine.

   An toan: nhan buoc la chu do SERVER gui xuong (ten cong cu, nhan do model dat) nen phai
   escape het truoc khi nhet vao innerHTML.
   Ghi chu: KHONG dung ky tu em dash o bat ky dau. */
(function () {
  "use strict";

  // Tran so buoc GIU LAI de ve. Mot loop goi hang tram cong cu thi ve het la dung khung chat
  // lam bai log. Tong so buoc van dem du (truong `so`) nen dong tom tat khong noi doi.
  var TRAN = 50;

  // Chu hien ra lay tu tu dien. Trong trinh duyet la window.t; duoi node - noi test require()
  // thang file nay - `window` CHUA KHAI BAO nen phai hoi bang typeof, roi doc thang vi.json.
  // Cung khuon voi chat-ask.js.
  function tw(khoa, bien) {
    if (typeof window !== "undefined" && window.t) return window.t(khoa, bien);
    try {
      var s = require("./i18n/vi.json")[khoa] || khoa;
      return String(s).replace(/\{(\w+)\}/g, function (m, ten) {
        return (bien && bien[ten] != null) ? String(bien[ten]) : m;
      });
    } catch (e) { return khoa; }
  }

  function esc(t) {
    return String(t == null ? "" : t)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  // Loai cong cu -> KHOA i18n cua dong tu nguoi doc duoc (viet du khoa de test_i18n soi duoc).
  // Ten lay theo cac engine that (Claude Code, Codex,
  // Grok, Antigravity, API); ten la thi giu nguyen ten cong cu, khong doan.
  var LOAI = [
    [/^(bash|shell|run_shell_command|command_execution|local_shell_call|run_terminal_command|run_command|exec)$/, "app.step_v_run"],
    [/^(read|read_file|view|view_file|notebookread|read_many_files|cat)$/, "app.step_v_read"],
    [/^(write|write_file|create_file|write_to_file)$/, "app.step_v_write"],
    [/^(edit|multiedit|notebookedit|str_replace|str_replace_editor|apply_patch|edit_file|replace|patch)$/, "app.step_v_edit"],
    [/^(grep|search_file_content|grep_search|codebase_search)$/, "app.step_v_grep"],
    [/^(glob|ls|list_directory|list_dir|find|find_by_name)$/, "app.step_v_find"],
    [/^(webfetch|web_fetch|fetch|read_url_content|fetch_url)$/, "app.step_v_web"],
    [/^(websearch|web_search|web_search_call|google_search|search_web)$/, "app.step_v_search"],
    [/^(task|agent)$/, "app.step_v_agent"],
    [/^(todowrite|todo_write|update_plan)$/, "app.step_v_todo"],
    [/^(skill|unimate_use_skill)$/, "app.step_v_skill"]
  ];
  function loaiCongCu(ten) {
    var t = String(ten || "").toLowerCase().trim();
    for (var i = 0; i < LOAI.length; i++) if (LOAI[i][0].test(t)) return LOAI[i][1];
    return "";
  }
  // "mcp__zalo__zalo_send_message" -> "zalo_send_message": phan dau chi la ten may chu.
  function tenGon(ten) {
    var t = String(ten || "").trim();
    var m = t.match(/^mcp__[^_]+(?:_[^_]+)*?__(.+)$/);
    return m ? m[1] : t;
  }

  // Nhan mot dong buoc. Co `detail` (server rut tu tham so lenh goi) thi ghi ro viec:
  // "Chay lenh: git status". Khong co thi giu cau server dat san ("Dang goi: pos_order"),
  // bo ky tu banh rang U+2699 dan dau vi khoi nay tu ve icon rieng.
  // Cat bang lop "moi ky tu dau khong phai chu/so" chu KHONG viet thang ky tu banh rang vao
  // day: test_icons.py cam emoji trong file dashboard. Luat rong nay cung ben hon khi server
  // doi sang dau khac.
  function nhanBuoc(ev) {
    var ten = String((ev && ev.tool) || "").trim();
    var ct = String((ev && ev.detail) || "").replace(/\s+/g, " ").trim();
    var loai = loaiCongCu(tenGon(ten));
    if (ct) return (loai ? tw(loai) : tenGon(ten) || tw("app.step_unknown")) + ": " + ct;
    if (loai) return tw(loai);
    var noi = String((ev && ev.content) || "").replace(/^[^\p{L}\p{N}]+/u, "").trim();
    if (noi) return noi;
    return ten || tw("app.step_unknown");
  }

  /* 0.451.0: what a step produced, as the server sends it in tool_result.res (server/step_media.py). Cleaned here
     again because it is drawn and kept in the browser: only our own picture and file addresses, short text, a few
     pictures and documents per step. */
  var RES_TEXT = 600, RES_IMGS = 4, RES_FILES = 4;
  var KIND = { "Word": 1, "Excel": 1, "PDF": 1, "PowerPoint": 1 };
  function srcOk(u) {
    u = String(u || "");
    return /^\/step-media\/[A-Za-z0-9_.:%-]+\/[0-9a-f]{32}\.(png|jpg|webp|gif)$/.test(u) || /^\/files\/raw\?/.test(u);
  }
  function gonRes(r, tran) {
    if (!r || typeof r !== "object") return null;
    var t = String(r.text || "").slice(0, tran || RES_TEXT);
    var imgs = (Array.isArray(r.imgs) ? r.imgs : []).filter(function (x) { return x && srcOk(x.src); })
      .slice(0, RES_IMGS).map(function (x) { return { src: String(x.src), path: String(x.path || "").slice(0, 300) }; });
    var files = (Array.isArray(r.files) ? r.files : []).filter(function (f) {
      return f && f.path && KIND[f.kind] && !/(^|\/)\.\.(\/|$)/.test(String(f.path));
    }).slice(0, RES_FILES).map(function (f) {
      return { name: String(f.name || "").slice(0, 120), path: String(f.path).slice(0, 300), kind: String(f.kind) };
    });
    var more = Math.max(0, parseInt(r.more, 10) || 0);
    if (!t && !imgs.length && !files.length && !r.err) return null;
    return { text: t, more: more, err: !!r.err, imgs: imgs, files: files };
  }

  function chuanHoa(st) {
    var ds = (st && Array.isArray(st.ds)) ? st.ds : [];
    var so = (st && typeof st.so === "number" && isFinite(st.so)) ? st.so : ds.length;
    return { ds: ds, so: so };
  }

  /* Gop mot su kien WS vao mach buoc. Ham THUAN: tra ve state MOI, khong sua state cu.
     Chi tool_call moi sinh buoc - `status` ("dang suy nghi") va `stream` la trang thai cua ca
     luot, khong phai viec da lam. */
  function nhan(st, ev) {
    var cu = chuanHoa(st);
    var loai = ev && ev.type;
    if (loai === "tool_call") {
      var b0 = { tool: String((ev && ev.tool) || ""), label: nhanBuoc(ev), xong: false };
      if (ev && ev.id) b0.id = String(ev.id);
      var ds = cu.ds.concat([b0]);
      if (ds.length > TRAN) ds = ds.slice(ds.length - TRAN);   // giu cac buoc MOI NHAT
      return { ds: ds, so: cu.so + 1 };
    }
    if (loai === "tool_result") {
      // Danh dau buoc la xong va gan ket qua. Co ma buoc (0.451.0) thi khop dung buoc do; khong
      // co (may chu cu) thi buoc dang chay cuoi cung nhu truoc. Khung tool_result lac long (chua
      // co buoc nao) thi bo qua - khong phai loi.
      var idx = -1, id = ev && ev.id ? String(ev.id) : "";
      if (id) for (var j = cu.ds.length - 1; j >= 0; j--) { if (cu.ds[j].id === id) { idx = j; break; } }
      if (idx < 0) for (var i = cu.ds.length - 1; i >= 0; i--) { if (!cu.ds[i].xong) { idx = i; break; } }
      if (idx >= 0) {
        var ds2 = cu.ds.slice();
        var nb = { tool: cu.ds[idx].tool, label: cu.ds[idx].label, xong: true };
        if (cu.ds[idx].id) nb.id = cu.ds[idx].id;
        var res = gonRes(ev && ev.res);
        if (res) nb.res = res;
        ds2[idx] = nb;
        return { ds: ds2, so: cu.so };
      }
    }
    return cu;
  }

  /* Luot KHONG goi cong cu nao thi `hien` = false: app.js khong dung khoi nao ca. Mot dong
     xam "Da chay 0 buoc" duoi moi cau chao hoi la rac. */
  function tomTat(st) {
    var cu = chuanHoa(st);
    return { hien: cu.ds.length > 0, so: cu.so, nhan: tw("app.steps_done", { n: cu.so }) };
  }

  /* Ban gon de luu vao lich su cua trinh duyet (app.js recordTurn): localStorage co han,
     nen moi buoc giu toi da 300 ky tu chu va ca luot toi da 4000; anh va the tep la duong dan
     ngan nen giu nguyen. */
  function gon(st) {
    var cu = chuanHoa(st), con = 4000;
    return { so: cu.so, ds: cu.ds.map(function (b) {
      var o = { tool: b.tool, label: b.label, xong: !!b.xong };
      if (b.id) o.id = b.id;
      if (b.res) {
        var t = String(b.res.text || "").slice(0, Math.max(0, Math.min(300, con)));
        con -= t.length;
        o.res = gonRes({ text: t, more: b.res.more + (t.length < String(b.res.text || "").length ? 1 : 0),
                         err: b.res.err, imgs: b.res.imgs, files: b.res.files }, 300);
        if (!o.res) delete o.res;
      }
      return o;
    }) };
  }

  function chevron() {
    return (typeof ic === "function") ? ic("chevron-down") : "›";
  }

  function taoKhoi() {
    var el = document.createElement("div");
    el.className = "msg msg-steps steps-fold";
    el.innerHTML =
      '<button class="steps-sum" type="button">' + chevron() +
      '<span class="steps-sum-text"></span><span class="steps-sum-now"></span></button>' +
      '<div class="steps-list"></div>';
    var nut = el.querySelector(".steps-sum");
    if (nut) {
      nut.setAttribute("aria-label", tw("app.steps_toggle"));
      nut.addEventListener("click", function () {
        el.classList.toggle("steps-fold");
        // Nho lua chon cua nguoi dung: lan ve lai sau (moi buoc moi) khong duoc gap nguoc.
        el._moTay = !el.classList.contains("steps-fold");
        if (nut.setAttribute) nut.setAttribute("aria-expanded", el._moTay ? "true" : "false");
      });
      nut.setAttribute("aria-expanded", "false");
    }
    // Bam vao mot buoc co ket qua -> mo/gap phan chu cua buoc do. Anh va the tep ben trong
    // da co bo bam chung cua khung chat (lightbox, mo tep), nen chi bat dong nhan buoc.
    var ds = el.querySelector(".steps-list");
    if (ds && ds.addEventListener) {
      ds.addEventListener("keydown", function (e) {
        if ((e.key === "Enter" || e.key === " ") && e.target && e.target.classList &&
            e.target.classList.contains("step-row")) { e.preventDefault(); e.target.click(); }
      });
      ds.addEventListener("click", function (e) {
        var row = e.target && e.target.closest ? e.target.closest(".step-row") : null;
        if (!row) return;
        var st = row.closest(".step");
        if (!st || !st.classList.contains("has-text")) return;
        var k = st.getAttribute("data-k") || "";
        el._moBuoc = el._moBuoc || {};
        el._moBuoc[k] = !el._moBuoc[k];
        st.classList.toggle("step-open", !!el._moBuoc[k]);
        row.setAttribute("aria-expanded", el._moBuoc[k] ? "true" : "false");
      });
    }
    return el;
  }

  /* Phan ket qua duoi nhan buoc. Anh va the tep hien san (nhu Claude), chu chi hien khi bam. */
  function veRes(r) {
    if (!r) return "";
    var h = "";
    if (r.imgs && r.imgs.length) {
      h += '<div class="step-imgs">' + r.imgs.map(function (x) {
        var vp = x.path ? ' data-vault-path="' + esc(x.path) + '"' : "";
        return '<a class="jv-img-link" href="' + esc(x.src) + '"' + vp + ' target="_blank" rel="noopener" title="' +
          esc(tw("chat.att_zoom")) + '"><img class="chat-img step-img" src="' + esc(x.src) +
          '" alt="" loading="lazy" onerror="jvImgGone(this)"></a>';
      }).join("") + "</div>";
    }
    if (r.files && r.files.length) {
      h += '<div class="step-files">' + r.files.map(function (f) {
        return '<a class="jv-floc step-file" href="#open=' + esc(encodeURIComponent(f.path)) + '" data-vault-path="' +
          esc(f.path) + '" title="' + esc(f.path) + '">' + (typeof ic === "function" ? ic("file-text") : "") +
          '<span class="step-file-name">' + esc(f.name) + '</span><span class="step-file-kind">' + esc(f.kind) +
          "</span></a>";
      }).join("") + "</div>";
    }
    if (r.text || r.err) {
      h += '<div class="step-out' + (r.err ? " step-out-err" : "") + '">' + esc(r.text || tw("app.step_err")) +
        (r.more ? '<span class="step-more">' + esc(tw("app.step_more", { n: r.more })) + "</span>" : "") + "</div>";
    }
    return h;
  }

  /* Ve lai khoi theo mach buoc. MAC DINH GAP, ca luc dang chay: dong tom tat da noi dang
     chay, bao nhieu buoc, buoc moi nhat la gi. Chi bung khi nguoi dung bam (`_moTay`). */
  function ve(el, st, dangChay) {
    if (!el) el = taoKhoi();
    // Nhớ mạch để vẽ lại khi từ điển về (xem bộ nghe "unimate:i18n" cuối file).
    el._st = st; el._dangChay = !!dangChay;
    var cu = chuanHoa(st);
    var txt = el.querySelector(".steps-sum-text");
    if (txt) txt.textContent = dangChay ? tw("app.steps_running_n", { n: cu.so }) : tomTat(cu).nhan;
    var now = el.querySelector(".steps-sum-now");
    if (now) {
      var cuoi = cu.ds.length ? cu.ds[cu.ds.length - 1] : null;
      now.textContent = (dangChay && cuoi) ? cuoi.label : "";
    }
    var ds = el.querySelector(".steps-list");
    if (ds) {
      var mo = el._moBuoc || {};
      ds.innerHTML = cu.ds.map(function (b, i) {
        var song = dangChay && i === cu.ds.length - 1 && !b.xong;
        var r = b.res || null;
        var coChu = !!(r && (r.text || r.err));
        var k = b.id ? "i:" + b.id : "n:" + i;
        return '<div class="step' + (song ? " step-live" : "") + (b.xong ? " step-done" : "") +
               (coChu ? " has-text" : "") + (r && r.err ? " step-err" : "") + (coChu && mo[k] ? " step-open" : "") +
               '" data-k="' + esc(k) + '">' +
               '<div class="step-row"' + (coChu ? ' role="button" tabindex="0" aria-expanded="' + (mo[k] ? "true" : "false") +
               '" title="' + esc(tw("app.step_open_res")) + '"' : ' title="' + esc(b.label) + '"') + ">" +
               esc(b.label) + "</div>" + veRes(r) + "</div>";
      }).join("");
    }
    el.classList.toggle("steps-fold", el._moTay !== true);
    return el;
  }

  var API = { nhan: nhan, tomTat: tomTat, taoKhoi: taoKhoi, ve: ve, nhanDong: nhanBuoc, TRAN: TRAN, gon: gon,
              gonRes: gonRes, veRes: veRes };
  if (typeof window !== "undefined") window.UniMateSteps = API;
  // Mở lại hội thoại (restoreSession) vẽ khối bước TRƯỚC khi từ điển tải xong, lúc đó t() trả
  // về chính cái khoá, nên người dùng thấy chữ thô "app.steps_done" (chủ repo báo 27/09). Từ
  // điển về thì vẽ lại mọi khối đang có.
  if (typeof window !== "undefined" && window.addEventListener) {
    window.addEventListener("unimate:i18n", function () {
      var ds = document.querySelectorAll(".msg-steps");
      for (var i = 0; i < ds.length; i++) {
        if (ds[i]._st) { try { ve(ds[i], ds[i]._st, ds[i]._dangChay); } catch (e) {} }
      }
    });
  }
  if (typeof module !== "undefined" && module.exports) module.exports = API;
})();
