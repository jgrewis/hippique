/* Phones: fold the long secondary blocks marked data-fold-mobile so the page stays short.
   They are open in the HTML, so without JavaScript (and on larger screens) everything stays visible. */
(() => {
  "use strict";

  const phone = window.matchMedia("(max-width: 639px)");
  const blocks = document.querySelectorAll("details[data-fold-mobile]");
  if (!blocks.length) return;

  const setOpen = (open) => {
    blocks.forEach((details) => { details.open = open; });
  };

  if (phone.matches) setOpen(false);
  // Above 640px the filter toggle is hidden: reopen everything so nothing stays out of reach.
  const onChange = (event) => {
    if (!event.matches) setOpen(true);
  };
  // Safari before 14 only knows addListener.
  if (phone.addEventListener) phone.addEventListener("change", onChange);
  else phone.addListener(onChange);
  // A printout must hold every block, then the phone layout comes back.
  window.addEventListener("beforeprint", () => setOpen(true));
  window.addEventListener("afterprint", () => setOpen(!phone.matches));
})();
