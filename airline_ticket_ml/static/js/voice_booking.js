
// static/js/voice_booking.js
// Client STT (Web Speech API) + server NLP parse (/voice/parse/) + UI automation

(function () {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) return;

  function getCookie(name) {
    const v = `; ${document.cookie}`;
    const parts = v.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return "";
  }

  async function parseTranscript(transcript) {
    try {
      const res = await fetch("/voice/parse/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({ transcript }),
      });
      return await res.json();
    } catch (e) {
      return { ok: false };
    }
  }

  function qs(sel) { return document.querySelector(sel); }
  function qsa(sel) { return Array.from(document.querySelectorAll(sel)); }
  function isVisible(el) {
    if (!el) return false;
    return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  }

  function setFieldValue(el, value) {
    if (!el || !value) return false;

    if (el.tagName === "SELECT") {
      const normalized = String(value).trim().toLowerCase();
      const option = Array.from(el.options).find((opt) => {
        const optionValue = String(opt.value || "").trim().toLowerCase();
        const optionText = String(opt.textContent || "").trim().toLowerCase();
        return optionValue === normalized || optionText === normalized || optionText.includes(normalized);
      });

      if (!option) return false;
      el.value = option.value;
    } else {
      el.value = value;
    }

    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  function fillHomeSearch(slots) {
    const origin = qs("select[name='Origin'], input[name='Origin']");
    const dest = qs("select[name='Destination'], input[name='Destination']");
    const dep = qs("input[name='DepartDate']");
    const seat = qs("select[name='SeatClass'], input[name='SeatClass']");
    const originValue = slots.origin || slots.source_code || slots.source || null;
    const destinationValue = slots.destination_value || slots.destination_code || slots.destination || null;
    const originFilled = setFieldValue(origin, originValue);
    const destinationFilled =
      setFieldValue(dest, destinationValue) ||
      setFieldValue(dest, slots.destination) ||
      setFieldValue(dest, slots.destination_code);
    const dateFilled = setFieldValue(dep, slots.depart_date);
    setFieldValue(seat, slots.seat_class);

    const form = qs("#searchForm") || (origin ? origin.closest("form") : null);
    if (form && originFilled && destinationFilled && dateFilled) {
      setTimeout(() => form.submit(), 50);
    }
  }

  function selectFromResults(index1Based) {
    if (!index1Based) return;
    // Prefer currently visible result cards so voice numbering matches the UI.
    const cards = qsa("[data-flight-card], .flight-card").filter(isVisible);
    if (cards.length) {
      const card = cards[index1Based - 1];
      const btn = card && card.querySelector("a[data-book-btn], button[data-book-btn], a[href*='/bookings/review/']");
      if (btn) btn.click();
      return;
    }
    const links = qsa("a[data-book-btn], button[data-book-btn], a[href*='/bookings/review/']").filter(isVisible);
    if (links[index1Based - 1]) links[index1Based - 1].click();
  }

  function confirmOnReview() {
    const btn = qs("button[type='submit'][data-confirm-booking]") || qs("button[type='submit']");
    if (btn) btn.click();
  }

  function mount(btn) {
    const rec = new SpeechRecognition();
    rec.lang = "en-IN";
    rec.interimResults = false;
    rec.maxAlternatives = 1;

    const statusEl = qs("#voiceStatus");

    function setStatus(t) {
      if (statusEl) statusEl.textContent = t || "";
    }

    rec.onstart = () => {
      btn.classList.add("listening");
      setStatus("Listening...");
    };
    rec.onerror = () => {
      btn.classList.remove("listening");
      setStatus("Voice error. Try again.");
    };
    rec.onend = () => {
      btn.classList.remove("listening");
      setTimeout(() => setStatus(""), 1200);
    };
    rec.onresult = async (event) => {
      const transcript = event.results[0][0].transcript || "";
      setStatus(`Heard: ${transcript}`);

      // 1) If user is focused on an input/select/textarea, fill that field first.
      const active = window.__voiceActiveEl;
      if (active && (document.activeElement === active)) {
        let t = (transcript || "").trim();
        const type = (active.getAttribute("type") || "").toLowerCase();
        const isNumeric = type === "number" || active.inputMode === "numeric" || active.getAttribute("inputmode") === "numeric";
        if (isNumeric || active.id === "card_number" || active.id === "cvv") {
          t = t.replace(/[^\d]/g, "");
        }
        // card number: keep 16 digits max, spacing handled by payment page script
        if (active.id === "card_number") t = t.slice(0, 16);
        if (active.id === "cvv") t = t.slice(0, 3);

        active.value = t;
        active.dispatchEvent(new Event("input", { bubbles: true }));
        active.dispatchEvent(new Event("change", { bubbles: true }));
        setTimeout(() => setStatus(""), 1200);
        return;
      }

      const parsed = await parseTranscript(transcript);
      if (!parsed || !parsed.ok) {
        setStatus("Could not understand. Try again.");
        return;
      }

      // Home page search
      if (parsed.intent === "search") {
        fillHomeSearch(parsed);
        return;
      }

      // Results page selection
      if (parsed.intent === "select_flight") {
        selectFromResults(parsed.flight_index);
        return;
      }

      // Review page confirm
      if (parsed.intent === "confirm") {
        confirmOnReview();
        return;
      }

      setStatus("Try: 'search flights from Hyderabad to Delhi on 5 Feb economy' or 'book flight 2'");
    };

    btn.addEventListener("click", () => rec.start());
  }

  document.addEventListener("DOMContentLoaded", () => {
    const btn = document.querySelector("[data-voice-btn]");
    if (btn) mount(btn);
  });
})();
