// --- Arama: yazmayı bırakınca formu gönder ---

const form = document.querySelector("#filtre-formu");
const searchInput = document.querySelector("#search");

if (form && searchInput) {
  let zamanlayici = null;

  searchInput.addEventListener("input", function () {
    clearTimeout(zamanlayici);
    zamanlayici = setTimeout(function () {
      form.submit();
    }, 400);
  });

  if (searchInput.value) {
    searchInput.focus();
    searchInput.setSelectionRange(searchInput.value.length, searchInput.value.length);
  }
}

// --- Klavye kısayolu: / tuşu arama kutusuna götürür ---

document.addEventListener("keydown", function (olay) {
  if (olay.key === "/" && document.activeElement !== searchInput) {
    olay.preventDefault();
    searchInput.focus();
  }
});

// --- Özet rakamlarını sayarak göster ---

function sayiyiCanlandir(element) {
  const hedefMetin = element.textContent;

  // Metnin içindeki ilk sayıyı bul. "52,2 mn $" -> 52,2
  const eslesme = hedefMetin.match(/[\d.]+,?\d*/);
  if (!eslesme) return;

  const hamSayi = parseFloat(eslesme[0].replace(/\./g, "").replace(",", "."));
  if (isNaN(hamSayi) || hamSayi === 0) return;

  const ondalikli = eslesme[0].includes(",");
  const sure = 550;
  const baslangic = performance.now();

  function adim(simdi) {
    const ilerleme = Math.min((simdi - baslangic) / sure, 1);
    // Sona doğru yavaşlasın
    const yumusak = 1 - Math.pow(1 - ilerleme, 3);
    const anlik = hamSayi * yumusak;

    let metin;
    if (ondalikli) {
      metin = anlik.toFixed(1).replace(".", ",");
    } else {
      metin = Math.round(anlik).toLocaleString("tr-TR");
    }

    element.textContent = hedefMetin.replace(eslesme[0], metin);

    if (ilerleme < 1) requestAnimationFrame(adim);
  }

  requestAnimationFrame(adim);
}

const hareketAzalt = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

if (!hareketAzalt) {
  document.querySelectorAll(".stat-value").forEach(sayiyiCanlandir);
}

