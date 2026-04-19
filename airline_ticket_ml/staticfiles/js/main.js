document.querySelectorAll('.book-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        alert("Booking feature demo version 🙂");
    });
});
document.addEventListener("DOMContentLoaded", function () {

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

});

