/* "Go to date" control: jumps to jour/YYYY-MM-DD.html. */
(function () {
  "use strict";

  var form = document.querySelector("form.date-jump");
  if (!form) return;
  var input = form.querySelector("input[type=date]");
  var root = form.getAttribute("data-root") || "";

  form.hidden = false;
  form.addEventListener("submit", function (event) {
    event.preventDefault();
    if (/^\d{4}-\d{2}-\d{2}$/.test(input.value)) {
      window.location.href = root + "jour/" + input.value + ".html";
    }
  });
})();
