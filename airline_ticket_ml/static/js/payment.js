function onlyDigits(s){ return (s || "").replace(/\D/g, ""); }

function formatCardNumber(raw){
  const digits = onlyDigits(raw).slice(0, 16);
  // 4-4-4-4 spacing
  return digits.replace(/(.{4})/g, "$1 ").trim();
}

function luhnCheck(num){
  const digits = onlyDigits(num);
  if (digits.length < 13) return false;
  let sum = 0, alt = false;
  for (let i = digits.length - 1; i >= 0; i--){
    let n = parseInt(digits[i], 10);
    if (alt){
      n *= 2;
      if (n > 9) n -= 9;
    }
    sum += n;
    alt = !alt;
  }
  return sum % 10 === 0;
}

function cardType(num){
  const d = onlyDigits(num);
  if (/^4/.test(d)) return "VISA";
  if (/^(5[1-5])/.test(d)) return "MASTERCARD";
  if (/^3[47]/.test(d)) return "AMEX";
  if (/^6/.test(d)) return "DISCOVER";
  return "";
}

document.addEventListener("DOMContentLoaded", () => {
  const cardNumber = document.getElementById("cardNumber");
  const cardHint = document.getElementById("cardHint");
  const cvv = document.getElementById("cvv");

  if (cardNumber){
    cardNumber.addEventListener("input", () => {
      const formatted = formatCardNumber(cardNumber.value);
      cardNumber.value = formatted;

      const type = cardType(formatted);
      const ok = luhnCheck(formatted);

      if (!onlyDigits(formatted).length){
        cardHint.textContent = "";
      } else if (type && ok){
        cardHint.textContent = `Card detected: ${type} ✓`;
      } else if (type && !ok && onlyDigits(formatted).length >= 14){
        cardHint.textContent = `Card detected: ${type} (number seems invalid)`;
      } else if (type){
        cardHint.textContent = `Card detected: ${type}`;
      } else {
        cardHint.textContent = "";
      }
    });
  }

  if (cvv){
    cvv.addEventListener("input", () => {
      cvv.value = onlyDigits(cvv.value).slice(0, 4);
    });
  }
});


document.addEventListener("DOMContentLoaded", function(){
  const cardInput = document.getElementById("card_number");
  const nameInput = document.getElementById("card_name");
  const cvvInput = document.getElementById("cvv");
  const mSel = document.getElementById("exp_month");
  const ySel = document.getElementById("exp_year");
  const btn = document.getElementById("payBtn");

  function isValid(){
    const digits = onlyDigits(cardInput?.value || "");
    const cvv = onlyDigits(cvvInput?.value || "");
    const name = (nameInput?.value || "").trim();
    const mm = parseInt((mSel?.value || "0"),10);
    const yy = parseInt((ySel?.value || "0"),10);
    // Requirement: proceed ONLY when 16 digits are entered (no Luhn strictness).
    if (digits.length !== 16) return false;
    if (cvv.length !== 3) return false;
    if (!name) return false;
    if (!(mm>=1 && mm<=12)) return false;
    if (!(yy>=2024 && yy<=2100)) return false;
    // month expiry check
    const now = new Date();
    const curY = now.getFullYear();
    const curM = now.getMonth()+1;
    if (yy < curY || (yy === curY && mm < curM)) return false;
    return true;
  }

  function update(){
    if (!btn) return;
    btn.disabled = !isValid();
  }

  [cardInput, nameInput, cvvInput, mSel, ySel].forEach(el=>{
    if(!el) return;
    el.addEventListener("input", update);
    el.addEventListener("change", update);
  });
  update();
});
