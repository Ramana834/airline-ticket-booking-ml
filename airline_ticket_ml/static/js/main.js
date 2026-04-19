document.addEventListener("DOMContentLoaded", function () {

  // ✅ Account dropdown (base.html)
  const accBtn = document.getElementById("accBtn");
  const accMenu = document.getElementById("accMenu");

  if (accBtn && accMenu) {
    accBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      accMenu.classList.toggle("show");
    });

    document.addEventListener("click", function (e) {
      if (!e.target.closest(".account")) {
        accMenu.classList.remove("show");
      }
    });
  }

  // ✅ Optional: demo alert for buttons with class .book-btn
  // (If you use it somewhere else)
  document.querySelectorAll(".book-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      alert("Booking feature demo version 🙂");
    });
  });

});
