/* Light / dark switch. Loaded without defer in <head> so the saved theme applies before first paint.
   Without a saved choice (or without storage), the page follows prefers-color-scheme. */
(function () {
  "use strict";

  var KEY = "francis-turf-theme";
  var root = document.documentElement;

  function saved() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }

  function save(theme) {
    try { localStorage.setItem(KEY, theme); } catch (e) { /* private mode: the choice lasts for this page only */ }
  }

  function current() {
    if (root.dataset.theme) return root.dataset.theme;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  var initial = saved();
  if (initial === "light" || initial === "dark") root.dataset.theme = initial;

  function render(button) {
    var dark = current() === "dark";
    button.querySelector(".theme-label").textContent = dark ? "Thème clair" : "Thème sombre";
    button.setAttribute("aria-label", dark ? "Passer au thème clair" : "Passer au thème sombre");
  }

  document.addEventListener("DOMContentLoaded", function () {
    var button = document.querySelector(".theme-toggle");
    if (!button) return;
    render(button);
    button.hidden = false;
    button.addEventListener("click", function () {
      var next = current() === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      save(next);
      render(button);
    });
  });
})();
