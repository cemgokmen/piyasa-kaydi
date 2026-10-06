// --- İşlemler sayfası: arama kutusu yazmayı bırakınca formu gönderir ---

const form = document.querySelector("#filtre-formu");
const searchInput = document.querySelector("#search");

if (form && searchInput) {
  let zamanlayici = null;

  searchInput.addEventListener("input", function () {
    clearTimeout(zamanlayici);
    zamanlayici = setTimeout(function () {
      form.submit();
    }, 450);
  });

  if (searchInput.value) {
    searchInput.focus();
    searchInput.setSelectionRange(searchInput.value.length, searchInput.value.length);
  }
}

// --- Sıralama seçimi değişince gizli alanı güncelleyip gönderir ---

document.querySelectorAll("select[data-hedef]").forEach(function (secim) {
  secim.addEventListener("change", function () {
    const hedef = secim.form.querySelector(`input[name="${secim.dataset.hedef}"]`);
    if (hedef) hedef.value = secim.value;
    secim.removeAttribute("name");
    secim.form.submit();
  });
});

// --- Klavye kısayolu: / tuşu arama kutusuna götürür ---

const genelArama = document.querySelector("#genel-arama");

document.addEventListener("keydown", function (olay) {
  const hedef = searchInput || genelArama;
  const yaziyor = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName);
  if (olay.key === "/" && !yaziyor && hedef) {
    olay.preventDefault();
    hedef.focus();
  }
});

// --- Tabloyu süz: isim veya eyalete göre satırları gizler ---

document.querySelectorAll("#tablo-suz").forEach(function (kutu) {
  const tablo = document.getElementById(kutu.dataset.tablo);
  if (!tablo) return;
  const kucult = (metin) => metin.toLocaleLowerCase("tr-TR");

  kutu.addEventListener("input", function () {
    const aranan = kucult(kutu.value.trim());
    tablo.querySelectorAll("tbody tr").forEach(function (satir) {
      satir.hidden = aranan && !kucult(satir.textContent).includes(aranan);
    });
  });
});

// --- Sıralanabilir tablolar: başlığa tıklayınca sıralar ---

document.querySelectorAll("table[data-siralanabilir]").forEach(function (tablo) {
  const basliklar = Array.from(tablo.querySelectorAll("th"));

  basliklar.forEach(function (baslik, sutun) {
    const tur = baslik.dataset.sirala;
    if (!tur) return;

    baslik.tabIndex = 0;

    function sirala() {
      const azalan = baslik.getAttribute("aria-sort") !== "descending";
      basliklar.forEach((b) => b.removeAttribute("aria-sort"));
      baslik.setAttribute("aria-sort", azalan ? "descending" : "ascending");

      const govde = tablo.tBodies[0];
      const satirlar = Array.from(govde.rows);
      satirlar.sort(function (a, b) {
        const x = a.cells[sutun].dataset.deger ?? a.cells[sutun].textContent;
        const y = b.cells[sutun].dataset.deger ?? b.cells[sutun].textContent;
        const fark = tur === "sayi" ? parseFloat(x) - parseFloat(y) : x.localeCompare(y, "tr");
        return azalan ? -fark : fark;
      });
      satirlar.forEach((s) => govde.appendChild(s));
    }

    baslik.addEventListener("click", sirala);
    baslik.addEventListener("keydown", function (olay) {
      if (olay.key === "Enter" || olay.key === " ") {
        olay.preventDefault();
        sirala();
      }
    });
  });
});
