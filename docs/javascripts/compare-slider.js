// Home page before/after comparison. The range input carries keyboard and pointer
// input; this script mirrors its value into the --fc-pos custom property.
function initCompareSliders() {
  for (const figure of document.querySelectorAll("[data-fc-compare]")) {
    const stage = figure.querySelector(".fc-compare__stage");
    const range = figure.querySelector(".fc-compare__range");
    if (!stage || !range || range.dataset.fcBound === "true") {
      continue;
    }
    const update = () => stage.style.setProperty("--fc-pos", `${range.value}%`);
    range.addEventListener("input", update);
    range.dataset.fcBound = "true";
    update();
  }
}

if (window.document$) {
  window.document$.subscribe(initCompareSliders);
} else {
  document.addEventListener("DOMContentLoaded", initCompareSliders);
}
