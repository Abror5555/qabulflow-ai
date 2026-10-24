/*! QabulFlow AI — veb-chat vidjeti. Saytga qo'shish:
 *  <script src="https://SIZNING-DOMEN/widget.js" data-key="wk_..." async></script>
 */
(function () {
  "use strict";
  if (window.__qabulflowWidget) return;
  window.__qabulflowWidget = true;

  var script = document.currentScript || document.querySelector('script[src*="widget.js"][data-key]');
  if (!script) return;
  var key = script.getAttribute("data-key");
  if (!key) return;
  var base = new URL(script.src, window.location.href).origin;
  var position = script.getAttribute("data-position") || "right";
  var color = script.getAttribute("data-color") || "#4F46E5";
  var label = script.getAttribute("data-label") || "Chat";

  function el(tag, styles, attrs) {
    var node = document.createElement(tag);
    Object.keys(styles || {}).forEach(function (k) { node.style[k] = styles[k]; });
    Object.keys(attrs || {}).forEach(function (k) { node.setAttribute(k, attrs[k]); });
    return node;
  }

  fetch(base + "/api/public/widget/" + encodeURIComponent(key) + "/config/", { credentials: "omit" })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (cfg) {
      if (cfg) {
        color = cfg.accent_color || color;
        position = cfg.position || position;
        label = cfg.title || label;
      }
      mount();
    })
    .catch(mount);

  var mounted = false;
  function mount() {
    if (mounted) return;
    mounted = true;
    var side = position === "left" ? "left" : "right";
    var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    var button = el("button", {
      position: "fixed", bottom: "20px", zIndex: "2147483000", width: "60px", height: "60px", borderRadius: "999px",
      border: "none", background: color, color: "#fff", cursor: "pointer", boxShadow: "0 10px 30px rgba(15,23,42,.25)",
      display: "flex", alignItems: "center", justifyContent: "center", transition: reduced ? "none" : "transform .15s ease"
    }, { type: "button", "aria-label": label + " — chatni ochish", "aria-expanded": "false" });
    button.style[side] = "20px";
    button.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';

    var frameWrap = el("div", {
      position: "fixed", bottom: "92px", zIndex: "2147483000", width: "380px", maxWidth: "calc(100vw - 24px)",
      height: "600px", maxHeight: "calc(100vh - 120px)", borderRadius: "16px", overflow: "hidden",
      boxShadow: "0 20px 60px rgba(15,23,42,.28)", display: "none", background: "#fff"
    });
    frameWrap.style[side] = "16px";
    var frame = el("iframe", { width: "100%", height: "100%", border: "0" }, {
      src: base + "/chat/" + encodeURIComponent(key) + "?embed=1", title: label, allow: "microphone"
    });
    frameWrap.appendChild(frame);

    function toggle(open) {
      var isOpen = typeof open === "boolean" ? open : frameWrap.style.display === "none";
      frameWrap.style.display = isOpen ? "block" : "none";
      button.setAttribute("aria-expanded", String(isOpen));
      button.setAttribute("aria-label", label + (isOpen ? " — chatni yopish" : " — chatni ochish"));
    }
    button.addEventListener("click", function () { toggle(); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") toggle(false); });
    window.addEventListener("message", function (e) {
      if (e.origin === base && e.data && e.data.type === "qabulflow:close") toggle(false);
    });
    document.body.appendChild(frameWrap);
    document.body.appendChild(button);
  }
})();
