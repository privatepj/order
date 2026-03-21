(function () {
  var DEBOUNCE_MS = 300;
  var MAX_TEXT = 200;
  var lastKey = "";
  var lastAt = 0;

  function trunc(s, n) {
    if (!s) return "";
    s = String(s).trim().replace(/\s+/g, " ");
    return s.length <= n ? s : s.slice(0, n - 3) + "...";
  }

  function targetKey(el) {
    if (!el || !el.tagName) return "";
    var id = el.id || "";
    var cls = (el.className && String(el.className).split(" ").slice(0, 3).join(" ")) || "";
    return el.tagName + "#" + id + "." + cls;
  }

  function pickTarget(ev) {
    var el = ev.target;
    if (!el || !el.closest) return null;
    var t =
      el.closest("a[href]") ||
      el.closest('button, input[type="submit"], input[type="button"], [role="button"]');
    return t;
  }

  document.addEventListener(
    "click",
    function (ev) {
      var el = pickTarget(ev);
      if (!el) return;

      var key = targetKey(el);
      var now = Date.now();
      if (key === lastKey && now - lastAt < DEBOUNCE_MS) return;
      lastKey = key;
      lastAt = now;

      var payload = {
        page_path: window.location.pathname + window.location.search,
        tagName: el.tagName,
        text: trunc(el.innerText || el.value || el.getAttribute("aria-label") || "", MAX_TEXT),
        href: el.getAttribute("href") || null,
        id: el.id || null,
        className: el.className ? String(el.className) : null,
      };

      try {
        fetch("/audit/ui-click", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
          keepalive: true,
        }).catch(function () {});
      } catch (e) {}
    },
    true
  );
})();
