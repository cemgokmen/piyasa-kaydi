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
// Günlük özet: gün seçimi
// ---------------------------------------------------------------------------

const gunSec = document.getElementById("gun-sec");
if (gunSec) {
  gunSec.addEventListener("change", () => { window.location.href = gunSec.value; });
}

// ---------------------------------------------------------------------------
// Arama önerileri: data-oneri taşıyan kutulara yazılırken altta liste açılır.
// Fare ya da klavyeyle (↑ ↓ Enter, Esc) seçilir; seçilen sayfa açılır.
// Hiçbiri seçilmeden Enter'a basılırsa form normal arama yapar.
// Kutu boşken odaklanınca son 5 arama listelenir (yalnızca bu tarayıcıda saklanır).
// ---------------------------------------------------------------------------

const SON_ARAMA_ANAHTARI = "son_aramalar";
const SON_ARAMA_SAYISI = 5;

function sonAramalar() {
  try {
    return JSON.parse(localStorage.getItem(SON_ARAMA_ANAHTARI) || "[]");
  } catch (e) {
    return [];
  }
}

function sonAramaKaydet(kayit) {
  try {
    const liste = sonAramalar().filter((k) => k.adres !== kayit.adres);
    liste.unshift(kayit);
    localStorage.setItem(SON_ARAMA_ANAHTARI, JSON.stringify(liste.slice(0, SON_ARAMA_SAYISI)));
  } catch (e) { /* gizli pencere vb.: saklanamazsa önemli değil */ }
}

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
  let escBasildi = false;
  let zamanlayici = null;
  let istek = null;

  function kapat() {
    liste.hidden = true;
    delete liste.dataset.gecmis;
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
    const i = aranan ? sadelestir(metin).indexOf(sadelestir(aranan)) : -1;
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
    delete liste.dataset.gecmis;
    secenekler = [];
    oneriler.forEach(function (o, i) {
      const li = document.createElement("li");
      li.id = `${liste.id}-${i}`;
      li.setAttribute("role", "option");
      li.dataset.adres = o.adres;
      li.dataset.kayit = JSON.stringify({ etiket: o.etiket, alt: o.alt || "", tur: o.tur, adres: o.adres });
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

    if (aranan === null) {
      // Son aramalar: başlık ve temizleme düğmesi
      const baslik = document.createElement("li");
      baslik.className = "oneri-baslik";
      baslik.setAttribute("role", "presentation");
      baslik.textContent = "Son aramalar";
      liste.prepend(baslik);
      const temizle = document.createElement("li");
      temizle.id = `${liste.id}-temizle`;
      temizle.setAttribute("role", "option");
      temizle.className = "oneri-temizle";
      temizle.dataset.temizle = "1";
      temizle.textContent = "Geçmişi temizle";
      liste.appendChild(temizle);
      secenekler.push(temizle);
      liste.dataset.gecmis = "1";
      liste.hidden = false;
      kutu.setAttribute("aria-expanded", "true");
      aktifYap(-1);
      return;
    }

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
    if (li.dataset.temizle) {
      try { localStorage.removeItem(SON_ARAMA_ANAHTARI); } catch (e) { /* önemli değil */ }
      kapat();
      return;
    }
    if (li.dataset.hepsi) {
      kapat();
      form.requestSubmit();
    } else {
      if (li.dataset.kayit) sonAramaKaydet(JSON.parse(li.dataset.kayit));
      window.location.href = li.dataset.adres;
    }
  }

  function sonlariGoster() {
    const liste_ = sonAramalar();
    if (!liste_.length) return;
    goster(liste_, null);
  }

  // Serbest metinle arama da geçmişe yazılır
  form.addEventListener("submit", function () {
    const aranan = kutu.value.trim();
    if (aranan) {
      sonAramaKaydet({ etiket: aranan, alt: "bütün işlemlerde arama", tur: "Arama",
                       adres: `/islemler?q=${encodeURIComponent(aranan)}&donem=365` });
    }
  });

  kutu.addEventListener("input", function () {
    clearTimeout(zamanlayici);
    const aranan = kutu.value.trim();
    if (!aranan) {
      if (escBasildi) escBasildi = false;
      else sonlariGoster();
      return;
    }
    escBasildi = false;
    // Yazmaya başlanınca son aramalar listesi hemen kapanır; öneriler gelince yenisi açılır
    if (liste.dataset.gecmis) kapat();
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
      // Yoldaki öneri isteği sonradan gelip listeyi yeniden açmasın
      clearTimeout(zamanlayici);
      if (istek) istek.abort();
      escBasildi = true;      // tarayıcı Esc ile kutuyu da temizler; geçmiş listesi açılmasın
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
    if (!kutu.value.trim()) {
      sonlariGoster();
    } else if (secenekler.length) {
      liste.hidden = false;
      kutu.setAttribute("aria-expanded", "true");
    }
  });
  // Odaktayken tekrar tıklanırsa da açılsın
  kutu.addEventListener("click", function () {
    if (!kutu.value.trim() && liste.hidden) sonlariGoster();
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

  const degerYaz = (g) => `${g.birim === "$" ? "$" : ""}${bicim(g.deger, g.basamak)}${g.birim === "₺" ? " ₺" : ""}`;
  const degisimYaz = function (span, oran) {
    span.className = "serit-degisim " + (oran >= 0 ? "tutar-buy" : "tutar-sell");
    span.textContent = `${oran >= 0 ? "▲" : "▼"} %${bicim(Math.abs(oran * 100), 2)}`;
  };

  // Sayfa açıkken dakikada bir: değerler yerinde güncellenir (kayan kopyalar dahil)
  const tazele = function () {
    if (document.hidden) return;
    fetch(serit.dataset.adres)
      .then((cevap) => (cevap.ok ? cevap.json() : null))
      .then(function (veri) {
        if (!veri) return;
        veri.gostergeler.forEach(function (g) {
          serit.querySelectorAll(`[data-kod="${CSS.escape(g.kod)}"]`).forEach(function (oge) {
            oge.querySelector(".serit-deger").textContent = degerYaz(g);
            const d = oge.querySelector(".serit-degisim");
            if (d && g.degisim !== null) degisimYaz(d, g.degisim);
          });
        });
      })
      .catch(() => {});
  };

  fetch(serit.dataset.adres)
    .then((cevap) => (cevap.ok ? cevap.json() : Promise.reject(cevap.status)))
    .then(function (veri) {
      const ic = document.createElement("div");
      ic.className = "serit-akis";
      serit.querySelector(".serit-ic").appendChild(ic);
      veri.gostergeler.forEach(function (g) {
        const oge = document.createElement(g.adres ? "a" : "span");
        oge.className = "serit-oge";
        oge.dataset.kod = g.kod;
        if (g.adres) oge.href = g.adres;
        const ad = document.createElement("span");
        ad.className = "serit-ad";
        ad.textContent = g.ad;
        const deger = document.createElement("span");
        deger.className = "serit-deger";
        deger.textContent = degerYaz(g);
        oge.append(ad, deger);
        if (g.degisim !== null) {
          const degisim = document.createElement("span");
          degisimYaz(degisim, g.degisim);
          oge.appendChild(degisim);
        }
        ic.appendChild(oge);
      });
      if (veri.gostergeler.length) serit.hidden = false;
      seridiKaydir(serit, ic);
      setInterval(tazele, 60 * 1000);
    })
    .catch(() => { /* şerit yalnızca süs; hata olursa gizli kalır */ });
}


// Şerit kendiliğinden kayar: öğeler bir kez kopyalanır, içerik her karede
// biraz kaydırılır ve yarı genişliğe gelince başa sarılır (dikişsiz döngü).
// Kaydırma CSS animasyonu yerine kare kare yapılır: fare girdiği anda o
// karede durur, imlecin altındaki öğe yerinden oynamaz. Dokununca ve klavye
// odağında da durur. "Hareketi azalt" ayarında kopya yoktur, şerit sabittir.
function seridiKaydir(serit, akis) {
  const azHareket = window.matchMedia("(prefers-reduced-motion: reduce)");
  const HIZ = 40;                       // piksel / saniye
  let konum = 0;
  let onceki = null;
  let kare = null;
  let duraklat = 0;                     // fare, dokunma ve odak ayrı ayrı sayılır
  const durdur = () => { duraklat += 1; serit.dataset.durdu = "1"; };
  const surdur = () => {
    duraklat = Math.max(0, duraklat - 1);
    if (!duraklat) delete serit.dataset.durdu;
  };

  function adim(zaman) {
    if (onceki !== null && !duraklat && !document.hidden) {
      const yari = akis.scrollWidth / 2;
      // Sekme uzun süre arka planda kaldıysa büyük sıçrama olmasın
      konum += Math.min(zaman - onceki, 100) / 1000 * HIZ;
      if (yari > 0 && konum >= yari) konum -= yari;
      akis.style.transform = `translate3d(${-konum}px, 0, 0)`;
    }
    onceki = zaman;
    kare = requestAnimationFrame(adim);
  }

  function ayarla() {
    akis.querySelectorAll("[data-kopya]").forEach((o) => o.remove());
    serit.classList.remove("kayan");
    cancelAnimationFrame(kare);
    akis.style.transform = "";
    konum = 0;
    onceki = null;
    if (azHareket.matches) return;
    Array.from(akis.children).forEach(function (oge) {
      const kopya = oge.cloneNode(true);
      kopya.dataset.kopya = "1";
      kopya.setAttribute("aria-hidden", "true");
      kopya.tabIndex = -1;
      akis.appendChild(kopya);
    });
    serit.classList.add("kayan");
    kare = requestAnimationFrame(adim);
  }

  serit.addEventListener("mouseenter", durdur);
  serit.addEventListener("mouseleave", surdur);
  serit.addEventListener("focusin", durdur);
  serit.addEventListener("focusout", surdur);
  // Dokunmatik ekranda parmak kalkınca iki saniye daha durur, okunabilsin
  serit.addEventListener("touchstart", durdur, { passive: true });
  serit.addEventListener("touchend", () => setTimeout(surdur, 2000), { passive: true });

  ayarla();
  azHareket.addEventListener("change", ayarla);
}

// Alt gezinmedeki "Ara": sayfanın başına çıkıp arama kutusuna odaklanır
document.querySelectorAll("[data-arama-odak]").forEach(function (bag) {
  bag.addEventListener("click", function (olay) {
    const kutu = document.getElementById("genel-arama");
    if (!kutu) return;
    olay.preventDefault();
    window.scrollTo({ top: 0, behavior: "smooth" });
    kutu.focus({ preventScroll: true });
  });
});


// ---------------------------------------------------------------------------
// Sonradan yüklenen parçalar: data-parca-adres taşıyan yer tutucu, sunucunun
// döndürdüğü HTML ile değiştirilir (ör. profili henüz kaydedilmemiş hissenin
// "Şirket ne iş yapıyor?" kutusu, şirketin rakamları). Cevap boşsa ya da
// istek başarısızsa yer tutucu kaldırılır.
// ---------------------------------------------------------------------------

// Kaynak (Yahoo, Google) anlık olarak boş dönebiliyor: iki kez daha denenir
function parcaYukle(yer, kalan) {
  fetch(yer.dataset.parcaAdres)
    .then((cevap) => (cevap.status === 200 ? cevap.text() : ""))
    .then(function (html) {
      if (html) yer.outerHTML = html;
      else if (kalan > 0) setTimeout(() => parcaYukle(yer, kalan - 1), 4000);
      else yer.remove();
    })
    .catch(() => (kalan > 0 ? setTimeout(() => parcaYukle(yer, kalan - 1), 4000) : yer.remove()));
}
document.querySelectorAll("[data-parca-adres]").forEach((yer) => parcaYukle(yer, 2));


// ---------------------------------------------------------------------------
// Sekmeler: [data-sekmeler] içinde [data-sekme] düğmesi aynı numaralı
// [data-sekme-panel]'i açar. Sonradan yüklenen parçalarda da çalışsın diye
// tıklama belge düzeyinde dinlenir. Ok tuşlarıyla sekmeler arasında gezilir.
// ---------------------------------------------------------------------------

function sekmeAc(dugme) {
  const kap = dugme.closest("[data-sekmeler]");
  if (!kap) return;
  kap.querySelectorAll("[data-sekme]").forEach(function (d) {
    const secili = d === dugme;
    d.classList.toggle("secili", secili);
    d.setAttribute("aria-selected", secili ? "true" : "false");
    d.tabIndex = secili ? 0 : -1;
  });
  kap.querySelectorAll("[data-sekme-panel]").forEach(function (p) {
    p.hidden = p.dataset.sekmePanel !== dugme.dataset.sekme;
  });
}

document.addEventListener("click", function (olay) {
  const dugme = olay.target.closest("[data-sekme]");
  if (dugme) sekmeAc(dugme);
});

document.addEventListener("keydown", function (olay) {
  const dugme = olay.target.closest && olay.target.closest("[data-sekme]");
  if (!dugme || (olay.key !== "ArrowRight" && olay.key !== "ArrowLeft")) return;
  const hepsi = Array.from(dugme.closest("[data-sekmeler]").querySelectorAll("[data-sekme]"));
  const sira = (hepsi.indexOf(dugme) + (olay.key === "ArrowRight" ? 1 : -1) + hepsi.length) % hepsi.length;
  sekmeAc(hepsi[sira]);
  hepsi[sira].focus();
  olay.preventDefault();
});


// ---------------------------------------------------------------------------
// Uzun tablolar: [data-kisalt="10"] içindeki tablonun ilk 10 satırı görünür,
// altına "Tümünü göster" düğmesi eklenir.
// ---------------------------------------------------------------------------

document.querySelectorAll("[data-kisalt]").forEach(function (kap) {
  const sinir = parseInt(kap.dataset.kisalt, 10);
  const satirlar = Array.from(kap.querySelectorAll("tbody > tr"));
  if (satirlar.length <= sinir + 2) return;            // 1-2 fazla satır için düğme gereksiz
  const fazla = satirlar.slice(sinir);
  fazla.forEach((s) => { s.hidden = true; });
  const dugme = document.createElement("button");
  dugme.type = "button";
  dugme.className = "dugme tumunu-goster";
  const yaz = (acik) => {
    dugme.textContent = acik ? "Daha az göster" : `Tümünü göster (${satirlar.length})`;
    dugme.setAttribute("aria-expanded", acik ? "true" : "false");
  };
  yaz(false);
  dugme.addEventListener("click", function () {
    const acik = dugme.getAttribute("aria-expanded") !== "true";
    fazla.forEach((s) => { s.hidden = !acik; });
    yaz(acik);
    if (!acik) kap.scrollIntoView({ block: "nearest", behavior: "smooth" });
  });
  kap.after(dugme);
});


// ---------------------------------------------------------------------------
// Sayfa içi bölüm menüsü: üst çubuğun hemen altına yapışır, kaydırırken
// görünen bölüm vurgulanır.
// ---------------------------------------------------------------------------

(function () {
  const ust = document.querySelector(".ust");
  const ayarla = () => ust && document.documentElement.style.setProperty("--ust-yukseklik", `${ust.offsetHeight}px`);
  ayarla();
  window.addEventListener("resize", ayarla);

  const menu = document.querySelector("[data-bolum-menu]");
  if (!menu || !("IntersectionObserver" in window)) return;
  const baglar = new Map(Array.from(menu.querySelectorAll("a[href^='#']")).map((a) => [a.hash.slice(1), a]));
  const gorunen = new Set();
  const isaretle = function () {
    // Sayfadaki sıraya göre görünen ilk bölüm
    const ilk = Array.from(baglar.keys()).find((id) => gorunen.has(id));
    baglar.forEach((a, id) => a.classList.toggle("secili", id === ilk));
  };
  const gozcu = new IntersectionObserver(function (girdiler) {
    girdiler.forEach((g) => (g.isIntersecting ? gorunen.add(g.target.id) : gorunen.delete(g.target.id)));
    isaretle();
  }, { rootMargin: "-140px 0px -55% 0px" });
  const izle = () => baglar.forEach((_, id) => {
    const bolum = document.getElementById(id);
    if (bolum) gozcu.observe(bolum);
  });
  izle();
  // Sonradan yüklenen parçalar (rakamlar, haberler) yerine geçince yeniden izle
  new MutationObserver(izle).observe(document.querySelector("main") || document.body, { childList: true, subtree: true });
})();
