// static/js/voice_fields.js
// Keep UI clean: do NOT add mic icons to every input.
// We only track the currently focused field so the single navbar Voice button
// can fill it via speech-to-text.

(function () {
  function isFillable(el){
    if (!el) return false;
    const tag = (el.tagName || "").toLowerCase();
    if (!["input", "textarea", "select"].includes(tag)) return false;
    const type = (el.getAttribute("type") || "").toLowerCase();
    if (["hidden","checkbox","radio","file","button","submit"].includes(type)) return false;
    if (el.disabled || el.readOnly) return false;
    return true;
  }

  function setActive(el){
    if (!isFillable(el)) return;
    window.__voiceActiveEl = el;
  }

  document.addEventListener("focusin", (e) => setActive(e.target), true);
  document.addEventListener("click", (e) => setActive(e.target), true);
})();
