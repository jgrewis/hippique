/* Client-side filtering of the day's races (hippodrome, discipline, distance, Quinté+). */
(function () {
  "use strict";

  var form = document.querySelector("form[data-filter-table]");
  if (!form) return;
  var table = document.getElementById(form.getAttribute("data-filter-table"));
  if (!table) return;

  var controls = form.querySelectorAll("[data-filter]");
  var counter = form.querySelector(".filter-count");
  var groups = table.querySelectorAll("tbody[data-group]");

  function activeFilters() {
    var filters = {};
    controls.forEach(function (control) {
      var key = control.getAttribute("data-filter");
      var value = control.type === "checkbox" ? (control.checked ? control.value : "") : control.value;
      if (value) filters[key] = value;
    });
    return filters;
  }

  function apply() {
    var filters = activeFilters();
    var visible = 0;
    var total = 0;
    groups.forEach(function (group) {
      var shownInGroup = 0;
      group.querySelectorAll("tr:not(.group-row)").forEach(function (row) {
        total += 1;
        var match = Object.keys(filters).every(function (key) {
          return row.getAttribute("data-" + key) === filters[key];
        });
        row.hidden = !match;
        if (match) shownInGroup += 1;
      });
      group.hidden = shownInGroup === 0;
      visible += shownInGroup;
    });
    if (counter) {
      counter.textContent = visible === total ? total + " courses" : visible + " course(s) sur " + total;
    }
  }

  form.hidden = false;
  form.addEventListener("change", apply);
  form.addEventListener("submit", function (event) { event.preventDefault(); });
  // "reset" fires before the controls are cleared: re-apply on the next tick.
  form.addEventListener("reset", function () { setTimeout(apply, 0); });
  apply();
})();
