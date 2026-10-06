"use strict";

// ---------------------------------------------------------------------------
// Filtre formu: arama kutusu yazmayı bırakınca, seçim kutuları değişince gönderilir
// ---------------------------------------------------------------------------

const filtreFormu = document.querySelector("#filtre-formu");
const aramaKutusu = document.querySelector("#search");

if (filtreFormu) {
  let zamanlayici = null;

  if (aramaKutusu) {
    aramaKutusu.addEventListener("input", function () {
      clearTimeout(zamanlayici);
      zamanlayici = setTimeout(() => filtreFormu.requestSubmit(), 500);
    });

    if (aramaKutusu.value) {
      aramaKutusu.focus();
      aramaKutusu.setSelectionRange(aramaKutusu.value.length, aramaKutusu.value.length);
    }
  }

  filtreFormu.querySelectorAll("select[data-otomatik]").forEach(function (secim) {
    secim.addEventListener("change", () => filtreFormu.requestSubmit());
  });

  // Boş arama kutusu adres çubuğunda "q=" olarak görünmesin
  filtreFormu.addEventListener("submit", function () {
    if (aramaKutusu && !aramaKutusu.value.trim()) aramaKutusu.disabled = true;
  });
}

// ---------------------------------------------------------------------------
// Klavye kısayolu: "/" tuşu arama kutusuna götürür
// ---------------------------------------------------------------------------

const genelArama = document.querySelector("#genel-arama");

document.addEventListener("keydown", function (olay) {
  const hedef = aramaKutusu || genelArama;
  const yaziyor = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName);
  if (olay.key === "/" && !yaziyor && hedef) {
    olay.preventDefault();
    hedef.focus();
  }
});

// ---------------------------------------------------------------------------
// Tıklanabilir satırlar: satırın herhangi bir yerine tıklayınca sayfayı açar.
// Satırdaki bağlantılar kendi işini yapar; metin seçerken de tetiklenmez.
// ---------------------------------------------------------------------------

document.querySelectorAll("tr.tiklanir[data-href]").forEach(function (satir) {
  satir.addEventListener("click", function (olay) {
    if (olay.target.closest("a, button, input, select")) return;
    if (window.getSelection().toString()) return;
    if (olay.metaKey || olay.ctrlKey) {
      window.open(satir.dataset.href, "_blank");
    } else {
      window.location.href = satir.dataset.href;
    }
  });
});

// ---------------------------------------------------------------------------
// Tabloyu süz: isim veya eyalete göre satırları gizler
// ---------------------------------------------------------------------------

document.querySelectorAll("#tablo-suz").forEach(function (kutu) {
  const tablo = document.getElementById(kutu.dataset.tablo);
  if (!tablo) return;
  const kucult = (metin) => metin.toLocaleLowerCase("tr-TR");

  kutu.addEventListener("input", function () {
    const aranan = kucult(kutu.value.trim());
    tablo.querySelectorAll("tbody tr").forEach(function (satir) {
      satir.hidden = Boolean(aranan) && !kucult(satir.textContent).includes(aranan);
    });
  });
});

// ---------------------------------------------------------------------------
// Sıralanabilir tablolar: başlığa tıklayınca (ya da Enter) sıralar
// ---------------------------------------------------------------------------

document.querySelectorAll("table[data-siralanabilir]").forEach(function (tablo) {
  const basliklar = Array.from(tablo.querySelectorAll("th"));

  basliklar.forEach(function (baslik, sutun) {
    const tur = baslik.dataset.sirala;
    if (!tur) return;

    baslik.tabIndex = 0;
    baslik.title = "Sıralamak için tıklayın";

    function sirala() {
      const azalan = baslik.getAttribute("aria-sort") !== "descending";
      basliklar.forEach((b) => b.removeAttribute("aria-sort"));
      baslik.setAttribute("aria-sort", azalan ? "descending" : "ascending");

      const govde = tablo.tBodies[0];
      const deger = (satir) => satir.cells[sutun].dataset.deger ?? satir.cells[sutun].textContent.trim();
      const satirlar = Array.from(govde.rows).sort(function (a, b) {
        const fark = tur === "sayi"
          ? (parseFloat(deger(a)) || 0) - (parseFloat(deger(b)) || 0)
          : deger(a).localeCompare(deger(b), "tr");
        return azalan ? -fark : fark;
      });
      govde.append(...satirlar);
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

// ---------------------------------------------------------------------------
// Geri düğmesi: siteden gelindiyse tarayıcı geçmişinde bir adım geri gider,
// böylece önceki sayfa filtreleri ve kaydırma konumuyla geri gelir.
// Sayfa doğrudan açıldıysa bağlantının kendi adresine (üst sayfaya) gider.
// ---------------------------------------------------------------------------

document.querySelectorAll("[data-geri]").forEach(function (dugme) {
  let siteIcinden = false;
  try {
    siteIcinden = document.referrer && new URL(document.referrer).origin === location.origin;
  } catch (hata) {
    siteIcinden = false;
  }

  if (siteIcinden && history.length > 1) {
    dugme.title = "Önceki sayfaya dön";
    dugme.addEventListener("click", function (olay) {
      if (olay.metaKey || olay.ctrlKey || olay.shiftKey) return;  // yeni sekmede üst sayfa
      olay.preventDefault();
      history.back();
    });
  } else {
    dugme.title = "Üst sayfaya git";
  }
});

// ---------------------------------------------------------------------------
// Günlük özet: gün seçimi ve "metni kopyala"
// ---------------------------------------------------------------------------

const gunSec = document.getElementById("gun-sec");
if (gunSec) {
  gunSec.addEventListener("change", () => { window.location.href = gunSec.value; });
}

const kopyala = document.getElementById("kopyala");
if (kopyala) {
  const durum = document.getElementById("kopyala-durum");
  const metin = document.getElementById(kopyala.dataset.hedef);

  kopyala.addEventListener("click", async function () {
    try {
      await navigator.clipboard.writeText(metin.value);
      durum.textContent = "Kopyalandı.";
    } catch (hata) {
      // Pano izni yoksa metni seç; kullanıcı Ctrl/Cmd+C ile kopyalayabilir
      metin.focus();
      metin.select();
      durum.textContent = "Metin seçildi, Ctrl+C (Mac'te Cmd+C) ile kopyalayın.";
    }
  });
}
