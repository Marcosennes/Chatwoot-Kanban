/**
 * Adds a "Kanban" entry to the Chatwoot main sidebar.
 *
 * Load it through Chatwoot's DASHBOARD_SCRIPTS installation config:
 *   <script src="https://<kanban-host>/chatwoot-sidebar.js" defer></script>
 *
 * The entry is cloned from the first native sidebar item so it inherits the
 * current markup and theme. Clicking it shows the board in the main area.
 */
(function () {
  "use strict";

  if (window.__kanbanSidebarLoaded) return;
  window.__kanbanSidebarLoaded = true;

  var script = document.currentScript;
  var KANBAN_URL = new URL("/kanban", script ? script.src : location.href).href;
  var ITEM_ATTR = "data-kanban-sidebar-item";
  var LABEL = "Kanban";
  var ACTIVE = ["text-n-slate-12", "bg-n-alpha-2", "font-medium"];
  var INACTIVE = ["text-n-slate-11", "hover:bg-n-alpha-2"];
  var ICON_SVG =
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" ' +
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
    'stroke-linejoin="round" class="size-4" aria-hidden="true">' +
    '<rect width="18" height="18" x="3" y="3" rx="2"/>' +
    '<path d="M8 7v7"/><path d="M12 7v4"/><path d="M16 7v9"/></svg>';

  var panel = null;
  var isOpen = false;

  function sidebarList() {
    return document.querySelector("aside nav > ul");
  }

  function isCollapsed(li) {
    return !li.querySelector(".truncate");
  }

  function setActive(item, active) {
    var link = item.querySelector("a, button");
    if (!link) return;
    ACTIVE.forEach(function (c) { link.classList.toggle(c, active); });
    INACTIVE.forEach(function (c) { link.classList.toggle(c, !active); });
  }

  function buildItem(template) {
    var item = template.cloneNode(true);
    item.setAttribute(ITEM_ATTR, "");

    var link = item.querySelector("a, button");
    if (link) {
      link.setAttribute("href", "#kanban");
      link.setAttribute("title", LABEL);
      link.removeAttribute("aria-current");
    }

    var icon = item.querySelector('[class*="i-lucide-"], [class*="i-ph-"]');
    if (icon) icon.outerHTML = ICON_SVG;

    item.querySelectorAll(".rounded-full").forEach(function (el) { el.remove(); });

    var label = item.querySelector(".truncate");
    if (label) label.textContent = LABEL;

    item.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      openPanel();
    }, true);

    setActive(item, isOpen);
    return item;
  }

  function ensureItem() {
    var list = sidebarList();
    if (!list) return;

    var natives = Array.prototype.filter.call(list.children, function (li) {
      return !li.hasAttribute(ITEM_ATTR);
    });
    if (!natives.length) return;

    var existing = list.querySelector("[" + ITEM_ATTR + "]");
    if (existing && isCollapsed(existing) === isCollapsed(natives[0])) return;
    if (existing) existing.remove();

    var anchor = natives[2] || null;
    list.insertBefore(buildItem(natives[0]), anchor);
  }

  function positionPanel() {
    if (!panel) return;
    var aside = document.querySelector("aside");
    var left = aside ? aside.getBoundingClientRect().right : 0;
    panel.style.left = left + "px";
  }

  function openPanel() {
    if (!panel) {
      panel = document.createElement("div");
      panel.className = "bg-n-background";
      panel.style.cssText =
        "position:fixed;top:0;right:0;bottom:0;z-index:40;display:none;";
      var frame = document.createElement("iframe");
      frame.src = KANBAN_URL;
      frame.title = LABEL;
      frame.style.cssText = "width:100%;height:100%;border:0;display:block;";
      panel.appendChild(frame);
      document.body.appendChild(panel);
    }
    isOpen = true;
    positionPanel();
    panel.style.display = "block";
    var item = document.querySelector("[" + ITEM_ATTR + "]");
    if (item) setActive(item, true);
  }

  function closePanel() {
    if (!isOpen) return;
    isOpen = false;
    if (panel) panel.style.display = "none";
    var item = document.querySelector("[" + ITEM_ATTR + "]");
    if (item) setActive(item, false);
  }

  document.addEventListener("click", function (event) {
    if (!isOpen) return;
    var target = event.target;
    if (!(target instanceof Element)) return;
    if (target.closest("[" + ITEM_ATTR + "]")) return;
    if (target.closest("aside a, aside button")) closePanel();
  }, true);

  window.addEventListener("popstate", closePanel);

  window.addEventListener("message", function (event) {
    var data = event.data;
    if (!panel || event.source !== panel.firstChild.contentWindow) return;
    if (!data || data.type !== "kanban:navigate") return;
    if (typeof data.path !== "string" || data.path.indexOf("/app/") !== 0) return;
    event.source.postMessage({ type: "kanban:navigate-ack" }, event.origin);
    closePanel();
    var router = chatwootRouter();
    if (router) router.push(data.path);
    else location.assign(data.path);
  });

  function chatwootRouter() {
    var roots = document.querySelectorAll("[data-v-app]");
    for (var i = 0; i < roots.length; i++) {
      var app = roots[i].__vue_app__;
      var router = app && app.config.globalProperties.$router;
      if (router) return router;
    }
    return null;
  }
  window.addEventListener("resize", positionPanel);

  var observedAside = null;
  var asideObserver =
    "ResizeObserver" in window ? new ResizeObserver(positionPanel) : null;

  function watchAside() {
    var aside = document.querySelector("aside");
    if (!asideObserver || !aside || aside === observedAside) return;
    if (observedAside) asideObserver.unobserve(observedAside);
    asideObserver.observe(aside);
    observedAside = aside;
  }

  var scheduled = false;
  new MutationObserver(function () {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(function () {
      scheduled = false;
      ensureItem();
      watchAside();
      positionPanel();
    });
  }).observe(document.body, { childList: true, subtree: true });

  ensureItem();
})();
