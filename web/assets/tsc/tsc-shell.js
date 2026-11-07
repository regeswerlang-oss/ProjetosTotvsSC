/* ═══════════════════════════════════════════════════════════════════════════
   tsc-shell.js — Trilho lateral global dos dashboards TOTVS SC
   ---------------------------------------------------------------------------
   Monta, em qualquer página, a barra lateral única com a navegação entre os
   quatro apps (Hub/DashboardIndex, Cockpit Único, Gestor de Projetos e
   Service Desk). Não toca na lógica da página: só adiciona o <nav> e a classe
   html.tsc. Requer tsc-ui.css.

     <link rel="stylesheet" href="ui/tsc-ui.css">
     <script src="ui/tsc-shell.js" data-app="Dashboard v2"></script>

   Opções (antes do script, opcional):
     window.TSC_SHELL = {
       app: "Nome do painel",                 // subtítulo da marca
       user: { name, email, role },           // usuário (apps sem window.TSC)
       logout: "/api/logout" | function(){},  // ação do botão sair
       urls: { sd: "https://..." }            // sobrescreve URLs dos apps
     }
   Fonte canônica: DashboardIndex/ui/tsc-shell.js — cópias idênticas nos
   outros repos (ServiceDesk-/ui, ProjetosTotvsSC/web/assets/tsc).
   ═══════════════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";
  if (window.__tscShell) return;
  window.__tscShell = true;

  var cfg = window.TSC_SHELL || {};
  var me = document.currentScript;
  var URLS = Object.assign({
    hub: "https://dashboard-index-kappa.vercel.app",
    cockpit: "https://cockpit-unico-tsc-7s5e.vercel.app",
    projetos: "https://projetos-totvs-sc.vercel.app",
    sd: "" // SDHub: preencha em urls.sd quando o domínio estiver definido
  }, cfg.urls || {});

  var root = document.documentElement;
  root.classList.add("tsc", "tsc-has-rail");
  var pageKey = cfg.page || (me && me.dataset.page);
  if (pageKey) root.setAttribute("data-tsc-page", pageKey);
  var PIN_KEY = "tsc.rail.pinned";
  var pinned = false;
  try { pinned = localStorage.getItem(PIN_KEY) === "1"; } catch (e) {}
  if (pinned) root.classList.add("tsc-rail-pinned");

  var P = 'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"';
  var IC = {
    hub: '<svg viewBox="0 0 24 24" ' + P + '><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>',
    rocket: '<svg viewBox="0 0 24 24" ' + P + '><path d="M5 15c-1.5 1.5-2 5-2 5s3.5-.5 5-2"/><path d="M9 15l-3-3c1-4 4-8 12-9-1 8-5 11-9 12z"/><circle cx="15" cy="9" r="1.6"/></svg>',
    inbox: '<svg viewBox="0 0 24 24" ' + P + '><path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5h13L22 12v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6z"/></svg>',
    gauge: '<svg viewBox="0 0 24 24" ' + P + '><path d="M12 14l4-4"/><path d="M3.3 17a9 9 0 1 1 17.4 0"/></svg>',
    mail: '<svg viewBox="0 0 24 24" ' + P + '><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg>',
    brain: '<svg viewBox="0 0 24 24" ' + P + '><path d="M9 4a3 3 0 0 0-3 3 3 3 0 0 0-2 5 3 3 0 0 0 2 5 3 3 0 0 0 6 1V4.5A2.5 2.5 0 0 0 9 4z"/><path d="M15 4a3 3 0 0 1 3 3 3 3 0 0 1 2 5 3 3 0 0 1-2 5 3 3 0 0 1-6 1"/></svg>',
    layers: '<svg viewBox="0 0 24 24" ' + P + '><path d="m12 3 9 5-9 5-9-5z"/><path d="m3 13 9 5 9-5"/></svg>',
    chart: '<svg viewBox="0 0 24 24" ' + P + '><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>',
    compass: '<svg viewBox="0 0 24 24" ' + P + '><circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2 5-5 2 2-5z"/></svg>',
    users: '<svg viewBox="0 0 24 24" ' + P + '><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7M21.5 20a6.5 6.5 0 0 0-4-6"/></svg>',
    sliders: '<svg viewBox="0 0 24 24" ' + P + '><path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/></svg>',
    map: '<svg viewBox="0 0 24 24" ' + P + '><path d="m9 4-6 2v14l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v14M15 6v14"/></svg>',
    brief: '<svg viewBox="0 0 24 24" ' + P + '><rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M3 12h18"/></svg>',
    trend: '<svg viewBox="0 0 24 24" ' + P + '><path d="M3 17l6-6 4 4 8-8"/><path d="M14 7h7v7"/></svg>',
    headset: '<svg viewBox="0 0 24 24" ' + P + '><path d="M4 14v-2a8 8 0 0 1 16 0v2"/><rect x="2.5" y="14" width="4" height="6" rx="1.5"/><rect x="17.5" y="14" width="4" height="6" rx="1.5"/><path d="M20 20a4 4 0 0 1-4 2h-2"/></svg>',
    pin: '<svg viewBox="0 0 24 24" ' + P + '><path d="M9 4h6l-1 6 3 3H7l3-3z"/><path d="M12 13v7"/></svg>',
    out: '<svg viewBox="0 0 24 24" ' + P + '><path d="M10 17l5-5-5-5M15 12H3M21 3v18"/></svg>',
    menu: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg>'
  };

  var NAV = [
    { g: "Início", items: [
      { id: "hub", lbl: "Hub de dashboards", ic: "hub", app: "hub", path: "/" },
      { id: "cockpit-next", lbl: "Cockpit Único", ic: "rocket", app: "cockpit", path: "/", prefix: true }
    ]},
    { g: "Operação", items: [
      { lbl: "Triagem Inbox", ic: "inbox", app: "hub", path: "/inbox-triage.html" },
      { lbl: "Cockpit executivo", ic: "gauge", app: "hub", path: "/cockpit.html" },
      { lbl: "Tasks ↔ E-mails", ic: "mail", app: "cockpit", path: "/painel/dashboard-tasks-emails.html" },
      { lbl: "InboxIntel", ic: "brain", app: "hub", path: "/inboxintel.html" },
      { lbl: "Cockpit (KPIs + RAID)", ic: "layers", app: "hub", path: "/cockpit-unico-totvs-sc.html" },
      { lbl: "Service Desk (SDHub)", ic: "headset", app: "sd", path: "/" }
    ]},
    { g: "GAPs", items: [
      { lbl: "Dashboard GAPs", ic: "chart", app: "hub", path: "/dashboard.html" },
      { lbl: "Tomada de Decisão", ic: "compass", app: "hub", path: "/gaps-decisao.html" },
      { lbl: "Reunião de Decisão", ic: "users", app: "hub", path: "/gaps-reuniao.html" },
      { lbl: "Calibração OS × Tasks", ic: "sliders", app: "hub", path: "/painel_calibracao.html" }
    ]},
    { g: "Gestão", items: [
      { lbl: "Gestor de Projetos", ic: "map", app: "projetos", path: "/" },
      { lbl: "Comercial", ic: "brief", app: "hub", path: "/comercial.html" },
      { lbl: "Clientes (Analítico)", ic: "trend", app: "hub", path: "/clientesanalitico.html" }
    ]}
  ];

  function originOf(u) { try { return new URL(u).origin; } catch (e) { return ""; } }
  var ORIG = {}; Object.keys(URLS).forEach(function (k) { ORIG[k] = originOf(URLS[k]); });
  var here = location.origin;
  var hereApp = Object.keys(ORIG).filter(function (k) { return ORIG[k] && ORIG[k] === here; })[0];
  // em dev local (localhost / preview) a página é tratada como do próprio app
  if (!hereApp && me && me.dataset.appKey) hereApp = me.dataset.appKey;
  if (!hereApp && cfg.appKey) hereApp = cfg.appKey;

  function hrefOf(it) {
    if (it.app === hereApp) return it.path;
    return URLS[it.app] ? URLS[it.app].replace(/\/$/, "") + it.path : "";
  }
  function norm(p) { p = (p || "/").replace(/\/index\.html$/, "/"); return p === "" ? "/" : p; }
  function isActive(it) {
    if (it.app !== hereApp) return false;
    var p = norm(location.pathname);
    if (it.prefix) {
      // Cockpit Next: ativo em qualquer rota, menos as que têm item próprio
      return !/\/painel\//.test(p);
    }
    return norm(it.path) === p;
  }

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  function build() {
    if (document.querySelector(".tsc-rail")) return;
    var appName = cfg.app || (me && me.dataset.app) || document.title.split(/[·|—-]/)[0].trim() || "Dashboards";
    var html = '<div class="r-brand"><div class="r-logo">T</div><div class="r-brand-txt"><b>TOTVS SC</b><span>' + esc(appName) + '</span></div>' +
      '<button class="r-pin" type="button" title="Fixar menu aberto" aria-label="Fixar menu">' + IC.pin + '</button></div><div class="r-nav">';
    NAV.forEach(function (grp) {
      var rows = grp.items.map(function (it) {
        var h = hrefOf(it);
        if (!h) return "";
        var ext = it.app !== hereApp;
        return '<a class="r-item' + (isActive(it) ? " active" : "") + '" href="' + esc(h) + '" title="' + esc(it.lbl) + '"' +
          (isActive(it) ? ' aria-current="page"' : "") + '><span class="r-ic">' + IC[it.ic] + '</span><span class="r-lbl">' + esc(it.lbl) + '</span>' +
          (ext ? '<span class="r-ext">↗</span>' : "") + "</a>";
      }).join("");
      if (rows) html += '<div class="r-group"><div class="r-gtitle">' + esc(grp.g) + "</div>" + rows + "</div>";
    });
    html += '</div><div class="r-foot"><div class="r-user"><div class="r-avatar" id="tscRailAv">·</div><div class="r-uinfo"><b id="tscRailName">Visitante</b><span id="tscRailRole">sem sessão</span></div>' +
      '<button class="r-out" id="tscRailOut" type="button" title="Sair" aria-label="Sair" hidden>' + IC.out + "</button></div></div>";

    var nav = document.createElement("nav");
    nav.className = "tsc-rail" + (pinned ? " pinned" : "");
    nav.setAttribute("aria-label", "Dashboards TOTVS SC");
    nav.innerHTML = html;
    document.body.insertBefore(nav, document.body.firstChild);

    var burger = document.createElement("button");
    burger.className = "tsc-burger"; burger.type = "button"; burger.setAttribute("aria-label", "Abrir menu"); burger.innerHTML = IC.menu;
    burger.addEventListener("click", function (e) { e.stopPropagation(); nav.classList.toggle("open"); });
    document.body.appendChild(burger);
    document.addEventListener("click", function (e) { if (nav.classList.contains("open") && !nav.contains(e.target)) nav.classList.remove("open"); });

    nav.querySelector(".r-pin").addEventListener("click", function () {
      pinned = !pinned;
      nav.classList.toggle("pinned", pinned);
      root.classList.toggle("tsc-rail-pinned", pinned);
      try { localStorage.setItem(PIN_KEY, pinned ? "1" : "0"); } catch (e) {}
      window.dispatchEvent(new Event("resize"));
    });
    fillUser();
  }

  function setUser(u) {
    if (!u) return;
    var name = u.name || (u.email ? u.email.split("@")[0].replace(/[._]/g, " ") : "Usuário");
    var ini = name.split(/\s+/).filter(Boolean).slice(0, 2).map(function (w) { return w[0]; }).join("").toUpperCase();
    var av = document.getElementById("tscRailAv");
    av.textContent = ini || "U"; av.classList.add("on");
    document.getElementById("tscRailName").textContent = name.replace(/\b\w/g, function (c) { return c.toUpperCase(); });
    document.getElementById("tscRailRole").textContent = u.role || u.email || "conectado";
    var out = document.getElementById("tscRailOut");
    var lo = cfg.logout || (window.TSC && window.TSC.logout ? function () { return window.TSC.logout().then(function () { location.reload(); }); } : null);
    if (!lo) return;
    out.hidden = false;
    out.addEventListener("click", function () {
      if (typeof lo === "function") return lo();
      var f = document.createElement("form"); f.method = "POST"; f.action = lo; document.body.appendChild(f); f.submit();
    });
  }
  function fillUser() {
    if (cfg.user) return setUser(cfg.user);
    var t = window.TSC;
    if (!t || !t.currentUser) return;
    Promise.resolve().then(function () { return t.currentUser(); }).then(function (u) {
      if (u) setUser({ email: u.email, name: (u.user_metadata && (u.user_metadata.nome || u.user_metadata.name)) || "" });
    }).catch(function () {});
  }
  window.TSCShell = { setUser: setUser, urls: URLS };

  if (document.body) build(); else document.addEventListener("DOMContentLoaded", build);
})();
