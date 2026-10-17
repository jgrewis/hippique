/* Export a table's visible rows to CSV (semicolon-separated, UTF-8 BOM for Excel FR). */
(function () {
  "use strict";

  function cellText(cell) {
    return cell.textContent.replace(/\s+/g, " ").trim();
  }

  function csvValue(text) {
    // Neutralise spreadsheet formulas (OWASP CSV injection), except plain
    // signed numbers such as "-1,5" or "+12,3 %", then quote.
    if (/^[=+\-@\t\r|]/.test(text) && !/^[-+]\d+(?:[.,]\d+)?(?:\s?%)?$/.test(text)) text = "'" + text;
    return '"' + text.replace(/"/g, '""') + '"';
  }

  function tableToCsv(table) {
    var lines = [];
    table.querySelectorAll("tr").forEach(function (row) {
      if (row.hasAttribute("data-no-export") || row.hidden) return;
      var body = row.closest("tbody");
      if (body && body.hidden) return;
      var cells = Array.prototype.map.call(row.querySelectorAll("th, td"), function (cell) {
        return csvValue(cellText(cell));
      });
      lines.push(cells.join(";"));
    });
    return "﻿" + lines.join("\r\n");
  }

  function download(filename, content) {
    var blob = new Blob([content], { type: "text/csv;charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  document.querySelectorAll("[data-export-table]").forEach(function (button) {
    var table = document.getElementById(button.getAttribute("data-export-table"));
    if (!table) return;
    button.hidden = false;
    button.addEventListener("click", function () {
      download(button.getAttribute("data-export-filename") || "export.csv", tableToCsv(table));
    });
  });
})();
