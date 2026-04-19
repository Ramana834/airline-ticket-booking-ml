document.addEventListener("DOMContentLoaded", function () {
  // ---------- helpers ----------
  const toMinutes = (hhmm) => {
    if (!hhmm) return 0;
    const parts = String(hhmm).split(":");
    const h = parseInt(parts[0] || "0", 10);
    const m = parseInt(parts[1] || "0", 10);
    return (h * 60) + m;
  };

  const inRange = (mins, rangeKey) => {
    // mins = minutes in day
    if (!rangeKey) return true;
    if (rangeKey === "before6") return mins < 360;             // < 06:00
    if (rangeKey === "6to12") return mins >= 360 && mins < 720; // 06-12
    if (rangeKey === "12to18") return mins >= 720 && mins < 1080; // 12-18
    if (rangeKey === "after18") return mins >= 1080;           // >= 18:00
    return true;
  };

  // ---------- dropdown (account) ----------
  const accBtn = document.getElementById("accBtn");
  const accMenu = document.getElementById("accMenu");
  if (accBtn && accMenu) {
    accBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      accMenu.classList.toggle("show");
    });
    document.addEventListener("click", function (e) {
      if (!e.target.closest(".account")) accMenu.classList.remove("show");
    });
  }

  // ---------- elements ----------
  const cards = Array.from(document.querySelectorAll(".flight-card"));
  const list = document.getElementById("flightList");
  const noMsg = document.getElementById("noFlightsMsg");

  const priceRange = document.getElementById("priceRange");
  const selectedPriceLabel = document.getElementById("selectedPriceLabel");
  const sortSelect = document.getElementById("sortSelect");
  const resetBtn = document.getElementById("resetFilters");

  const timeBtns = Array.from(document.querySelectorAll(".time-btn"));

  // store minutes on each card once (fast)
  cards.forEach(c => {
    const dep = c.getAttribute("data-depart") || "00:00";
    const arr = c.getAttribute("data-arrive") || "00:00";
    c.dataset.departMin = String(toMinutes(dep));
    c.dataset.arriveMin = String(toMinutes(arr));
  });

  // current filters
  let maxPrice = priceRange ? parseInt(priceRange.value || "0", 10) : Infinity;
  let departFilter = null; // one of before6/6to12/12to18/after18
  let arriveFilter = null;

  const applyFilters = () => {
    let visibleCount = 0;

    cards.forEach(card => {
      const price = parseInt(card.dataset.price || "0", 10);
      const depMin = parseInt(card.dataset.departMin || "0", 10);
      const arrMin = parseInt(card.dataset.arriveMin || "0", 10);

      const okPrice = price <= maxPrice;
      const okDep = inRange(depMin, departFilter);
      const okArr = inRange(arrMin, arriveFilter);

      const show = okPrice && okDep && okArr;
      card.style.display = show ? "flex" : "none";
      if (show) visibleCount += 1;
    });

    if (noMsg) noMsg.style.display = visibleCount === 0 ? "block" : "none";
  };

  const sortCards = () => {
    if (!list) return;

    const mode = sortSelect ? sortSelect.value : "depart_asc";

    // sort only the cards array order, then re-append to DOM
    const sorted = cards.slice().sort((a, b) => {
      const pa = parseInt(a.dataset.price || "0", 10);
      const pb = parseInt(b.dataset.price || "0", 10);
      const da = parseInt(a.dataset.departMin || "0", 10);
      const db = parseInt(b.dataset.departMin || "0", 10);

      if (mode === "price_asc") return pa - pb;
      if (mode === "price_desc") return pb - pa;
      if (mode === "depart_desc") return db - da;
      return da - db; // depart_asc
    });

    // re-append in new order
    sorted.forEach(el => list.appendChild(el));
  };

  // ---------- price slider ----------
  if (priceRange) {
    selectedPriceLabel.textContent = priceRange.value;
    priceRange.addEventListener("input", function () {
      maxPrice = parseInt(this.value || "0", 10);
      selectedPriceLabel.textContent = this.value;
      applyFilters();
    });
  }

  // ---------- time buttons (toggle single selection per type) ----------
  timeBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const type = btn.dataset.type;   // "depart" or "arrive"
      const range = btn.dataset.range; // range key

      // same button clicked again => OFF
      const isActive = btn.classList.contains("active");

      // clear all buttons of same type
      timeBtns
        .filter(b => b.dataset.type === type)
        .forEach(b => b.classList.remove("active"));

      if (isActive) {
        // turn off
        if (type === "depart") departFilter = null;
        else arriveFilter = null;
      } else {
        // turn on
        btn.classList.add("active");
        if (type === "depart") departFilter = range;
        else arriveFilter = range;
      }

      applyFilters();
    });
  });

  // ---------- sort ----------
  if (sortSelect) {
    sortSelect.addEventListener("change", () => {
      sortCards();
      applyFilters(); // keep filters applied after sorting
    });
  }

  // ---------- reset ----------
  if (resetBtn) {
    resetBtn.addEventListener("click", (e) => {
      e.preventDefault();

      // reset slider to max
      if (priceRange) {
        priceRange.value = priceRange.max;
        maxPrice = parseInt(priceRange.value || "0", 10);
        selectedPriceLabel.textContent = priceRange.value;
      }

      // clear time filters
      departFilter = null;
      arriveFilter = null;
      timeBtns.forEach(b => b.classList.remove("active"));

      // reset sort
      if (sortSelect) sortSelect.value = "depart_asc";
      sortCards();
      applyFilters();
    });
  }

  // first load
  sortCards();
  applyFilters();
});
