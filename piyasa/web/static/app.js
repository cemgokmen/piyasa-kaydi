"use strict";

// ---------------------------------------------------------------------------
// Filtre formu: seçim kutuları değişince gönderilir
// ---------------------------------------------------------------------------

const filtreFormu = document.querySelector("#filtre-formu");
const aramaKutusu = document.querySelector("#search");

if (filtreFormu) {
  // Arama kutusu Enter ile gönderilir; yazarken altta öneriler açılır (aşağıda)
  if (aramaKutusu) {
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


// ---------------------------------------------------------------------------
// Arama önerileri: data-oneri taşıyan kutulara yazılırken altta liste açılır.
// Fare ya da klavyeyle (↑ ↓ Enter, Esc) seçilir; seçilen sayfa açılır.
// Hiçbiri seçilmeden Enter'a basılırsa form normal arama yapar.
// ---------------------------------------------------------------------------

document.querySelectorAll("input[data-oneri]").forEach(function (kutu, sira) {
  const form = kutu.form;
  const liste = document.createElement("ul");
  liste.className = "oneri-listesi";
  liste.id = `oneri-listesi-${sira}`;
  liste.setAttribute("role", "listbox");
  liste.hidden = true;
  form.appendChild(liste);

  kutu.setAttribute("role", "combobox");
  kutu.setAttribute("aria-autocomplete", "list");
  kutu.setAttribute("aria-expanded", "false");
  kutu.setAttribute("aria-controls", liste.id);

  let secenekler = [];
  let aktif = -1;
  let zamanlayici = null;
  let istek = null;

  function kapat() {
    liste.hidden = true;
    aktif = -1;
    kutu.setAttribute("aria-expanded", "false");
    kutu.removeAttribute("aria-activedescendant");
  }

  // Harf harf sadeleştirir (uzunluk korunur): I/İ/ı → i, aksanlar atılır.
  // Böylece "nvid" NVIDIA'da, "altin" Altın'da bulunur.
  function sadelestir(metin) {
    return Array.from(metin, function (c) {
      if (c === "I" || c === "İ" || c === "ı") return "i";
      return c.toLowerCase().normalize("NFD")[0];
    }).join("");
  }

  function vurgula(metin, aranan) {
    // Eşleşen kısmı kalın gösterir; metin her zaman textContent olarak eklenir
    const parca = document.createElement("span");
    const i = sadelestir(metin).indexOf(sadelestir(aranan));
    if (!aranan || i < 0) {
      parca.textContent = metin;
      return parca;
    }
    const kalin = document.createElement("mark");
    kalin.textContent = metin.slice(i, i + aranan.length);
    parca.append(metin.slice(0, i), kalin, metin.slice(i + aranan.length));
    return parca;
  }

  function aktifYap(yeni) {
    secenekler.forEach((s, i) => s.setAttribute("aria-selected", i === yeni ? "true" : "false"));
    aktif = yeni;
    if (yeni >= 0) {
      kutu.setAttribute("aria-activedescendant", secenekler[yeni].id);
      secenekler[yeni].scrollIntoView({ block: "nearest" });
    } else {
      kutu.removeAttribute("aria-activedescendant");
    }
  }

  function goster(oneriler, aranan) {
    liste.innerHTML = "";
    secenekler = [];
    oneriler.forEach(function (o, i) {
      const li = document.createElement("li");
      li.id = `${liste.id}-${i}`;
      li.setAttribute("role", "option");
      li.dataset.adres = o.adres;
      const tur = document.createElement("span");
      tur.className = `oneri-tur oneri-${o.tur.toLocaleLowerCase("tr-TR").replace(/[^a-zçğıöşü]/g, "")}`;
      tur.textContent = o.tur;
      const govde = document.createElement("span");
      govde.className = "oneri-govde";
      const etiket = vurgula(o.etiket, aranan);
      etiket.className = "oneri-etiket";
      const alt = vurgula(o.alt || "", aranan);
      alt.className = "oneri-alt";
      govde.append(etiket, alt);
      li.append(tur, govde);
      liste.appendChild(li);
      secenekler.push(li);
    });

    const hepsi = document.createElement("li");
    hepsi.id = `${liste.id}-hepsi`;
    hepsi.setAttribute("role", "option");
    hepsi.className = "oneri-hepsi";
    hepsi.dataset.hepsi = "1";
    hepsi.textContent = `“${aranan}” için bütün işlemlerde ara →`;
    liste.appendChild(hepsi);
    secenekler.push(hepsi);

    liste.hidden = false;
    kutu.setAttribute("aria-expanded", "true");
    aktifYap(-1);
  }

  function sec(li) {
    if (li.dataset.hepsi) {
      kapat();
      form.requestSubmit();
    } else {
      window.location.href = li.dataset.adres;
    }
  }

  kutu.addEventListener("input", function () {
    clearTimeout(zamanlayici);
    const aranan = kutu.value.trim();
    if (!aranan) {
      kapat();
      return;
    }
    zamanlayici = setTimeout(function () {
      if (istek) istek.abort();
      istek = new AbortController();
      fetch(`/api/oneri?q=${encodeURIComponent(aranan)}`, { signal: istek.signal })
        .then((cevap) => cevap.json())
        .then(function (veri) {
          // Yanıt gelene kadar kutu değiştiyse eski yanıtı gösterme
          if (veri.sorgu !== kutu.value.trim().slice(0, 60)) return;
          goster(veri.oneriler, aranan);
        })
        .catch(() => {});
    }, 120);
  });

  kutu.addEventListener("keydown", function (olay) {
    if (liste.hidden) return;
    if (olay.key === "ArrowDown") {
      olay.preventDefault();
      aktifYap((aktif + 1) % secenekler.length);
    } else if (olay.key === "ArrowUp") {
      olay.preventDefault();
      aktifYap(aktif <= 0 ? secenekler.length - 1 : aktif - 1);
    } else if (olay.key === "Enter" && aktif >= 0) {
      olay.preventDefault();
      sec(secenekler[aktif]);
    } else if (olay.key === "Escape") {
      kapat();
    }
  });

  // mousedown: kutu odağını kaybetmeden (liste kapanmadan) seçim yapılsın
  liste.addEventListener("mousedown", function (olay) {
    const li = olay.target.closest("li[role=option]");
    if (!li) return;
    olay.preventDefault();
    sec(li);
  });
  liste.addEventListener("mousemove", function (olay) {
    const li = olay.target.closest("li[role=option]");
    if (li) aktifYap(secenekler.indexOf(li));
  });

  kutu.addEventListener("blur", () => setTimeout(kapat, 100));
  kutu.addEventListener("focus", function () {
    if (kutu.value.trim() && secenekler.length) {
      liste.hidden = false;
      kutu.setAttribute("aria-expanded", "true");
    }
  });
});


// ---------------------------------------------------------------------------
// Tema: sistem → açık → koyu. Seçim tarayıcıda saklanır.
// ---------------------------------------------------------------------------

const temaDugmesi = document.getElementById("tema-dugmesi");
if (temaDugmesi) {
  const sira = [undefined, "acik", "koyu"];
  const adlar = { undefined: "sistem", acik: "açık", koyu: "koyu" };
  const guncelle = () => {
    temaDugmesi.title = `Tema: ${adlar[document.documentElement.dataset.tema]} (değiştirmek için tıklayın)`;
  };
  guncelle();
  temaDugmesi.addEventListener("click", function () {
    const simdiki = document.documentElement.dataset.tema;
    const sonraki = sira[(sira.indexOf(simdiki) + 1) % sira.length];
    if (sonraki) document.documentElement.dataset.tema = sonraki;
    else delete document.documentElement.dataset.tema;
    try {
      if (sonraki) localStorage.setItem("tema", sonraki);
      else localStorage.removeItem("tema");
    } catch (hata) { /* gizli pencerede saklanamayabilir */ }
    guncelle();
  });
}

// ---------------------------------------------------------------------------
// Telefon menüsü ve kaydırınca üst çubuk gölgesi
// ---------------------------------------------------------------------------

const ustCubuk = document.querySelector(".ust");
const menuDugmesi = document.getElementById("menu-dugmesi");
if (menuDugmesi && ustCubuk) {
  menuDugmesi.addEventListener("click", function () {
    const acik = ustCubuk.classList.toggle("menu-acik");
    menuDugmesi.setAttribute("aria-expanded", acik ? "true" : "false");
    menuDugmesi.setAttribute("aria-label", acik ? "Menüyü kapat" : "Menüyü aç");
  });
  document.addEventListener("keydown", function (olay) {
    if (olay.key === "Escape" && ustCubuk.classList.contains("menu-acik")) menuDugmesi.click();
  });
}
if (ustCubuk) {
  const golge = () => ustCubuk.classList.toggle("kaydirildi", window.scrollY > 4);
  window.addEventListener("scroll", golge, { passive: true });
  golge();
}

// ---------------------------------------------------------------------------
// Piyasa şeridi: sayfa açıldıktan sonra doldurulur
// ---------------------------------------------------------------------------

const serit = document.getElementById("piyasa-seridi");
if (serit) {
  const bicim = (n, basamak) => new Intl.NumberFormat("tr-TR", {
    minimumFractionDigits: basamak, maximumFractionDigits: basamak,
  }).format(n);

  fetch(serit.dataset.adres)
    .then((cevap) => (cevap.ok ? cevap.json() : Promise.reject(cevap.status)))
    .then(function (veri) {
      const ic = serit.querySelector(".serit-ic");
      veri.gostergeler.forEach(function (g) {
        const oge = document.createElement(g.adres ? "a" : "span");
        oge.className = "serit-oge";
        if (g.adres) oge.href = g.adres;
        const ad = document.createElement("span");
        ad.className = "serit-ad";
        ad.textContent = g.ad;
        const deger = document.createElement("span");
        deger.className = "serit-deger";
        deger.textContent = `${g.birim === "$" ? "$" : ""}${bicim(g.deger, g.basamak)}${g.birim === "₺" ? " ₺" : ""}`;
        oge.append(ad, deger);
        if (g.degisim !== null) {
          const degisim = document.createElement("span");
          degisim.className = "serit-degisim " + (g.degisim >= 0 ? "tutar-buy" : "tutar-sell");
          degisim.textContent = `${g.degisim >= 0 ? "▲" : "▼"} %${bicim(Math.abs(g.degisim * 100), 2)}`;
          oge.appendChild(degisim);
        }
        ic.appendChild(oge);
      });
      if (veri.gostergeler.length) serit.hidden = false;
    })
    .catch(() => { /* şerit yalnızca süs; hata olursa gizli kalır */ });
}
