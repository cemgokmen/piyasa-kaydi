"use strict";

// ---------------------------------------------------------------------------
// Fiyat paneli (hisse ve emtia sayfaları): son fiyat, dönemsel değişimler,
// hacim ve fiyat grafiği. Veri panelin data-fiyat-url adresinden gelir;
// sayfa onu beklemeden açılır. Grafiği PiyasaGrafik (grafik.js) çizer.
// ---------------------------------------------------------------------------

(function () {
  const panel = document.getElementById("fiyat");
  if (!panel || !window.PiyasaGrafik) return;

  const G = window.PiyasaGrafik;
  const alan = (ad) => panel.querySelector(`[data-alan="${ad}"]`);
  const sayi = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const birim = panel.dataset.birim ? ` ${panel.dataset.birim}` : " $";
  const fiyatYaz = (n) => `${sayi.format(n)}${birim}`;

  let veri = null;
  let aralik = "1y";

  function degisimleriYaz() {
    const liste = alan("degisimler");
    liste.innerHTML = "";
    veri.degisimler.forEach(function (d) {
      const li = document.createElement("li");
      li.className = "degisim " + (d.oran > 0 ? "artis" : d.oran < 0 ? "azalis" : "notr");
      const etiket = document.createElement("span");
      etiket.className = "degisim-etiket";
      etiket.textContent = d.etiket;
      const deger = document.createElement("span");
      deger.className = "degisim-deger";
      deger.textContent = d.oran === null ? "—" : G.yuzde(d.oran);
      if (d.oran === null) li.title = "Bu süre için fiyat geçmişi yok";
      li.append(etiket, deger);
      liste.appendChild(li);
    });
  }

  function hacimYaz() {
    const kutu = alan("hacim");
    if (!kutu) return;
    if (!veri.hacim) {
      kutu.hidden = true;
      return;
    }
    const h = veri.hacim;
    const oran = h.oran ? Math.round(h.oran * 100) : null;
    let yorum = "";
    if (oran !== null) {
      yorum = oran >= 150 ? " · ortalamanın çok üstünde"
        : oran >= 115 ? " · ortalamanın üstünde"
        : oran <= 70 ? " · ortalamanın altında" : " · ortalama civarında";
    }
    kutu.textContent = `${G.tarih(h.tarih)} hacmi: ${G.kisaSayi(h.son)} ` +
      `(20 günlük ortalama ${G.kisaSayi(h.ortalama)}${oran !== null ? `, %${oran}` : ""})${yorum}`;
    kutu.hidden = false;
  }

  function grafikCiz() {
    G.cizgi(alan("grafik"), veri.seriler[aralik], { bicim: fiyatYaz });
  }

  panel.querySelectorAll("[data-aralik]").forEach(function (dugme) {
    dugme.addEventListener("click", function () {
      aralik = dugme.dataset.aralik;
      panel.querySelectorAll("[data-aralik]").forEach(function (d) {
        const secili = d === dugme;
        d.classList.toggle("secili", secili);
        d.setAttribute("aria-pressed", secili ? "true" : "false");
      });
      if (veri) grafikCiz();
    });
  });

  let zaman = null;
  window.addEventListener("resize", function () {
    clearTimeout(zaman);
    zaman = setTimeout(() => veri && grafikCiz(), 150);
  });

  function hataGoster(mesaj) {
    panel.classList.add("fiyat-yok");
    alan("fiyat").textContent = "—";
    alan("tarih").textContent = "";
    alan("degisimler").hidden = true;
    if (alan("hacim")) alan("hacim").hidden = true;
    panel.querySelector(".fiyat-grafik-kap").hidden = true;
    const hata = alan("hata");
    hata.textContent = mesaj;
    hata.hidden = false;
  }

  fetch(panel.dataset.fiyatUrl)
    .then((cevap) => cevap.json().then((govde) => ({ tamam: cevap.ok, govde })))
    .then(function ({ tamam, govde }) {
      if (!tamam) {
        hataGoster(govde.hata || "Fiyat bilgisi alınamadı.");
        return;
      }
      veri = govde;
      alan("fiyat").textContent = fiyatYaz(veri.fiyat);
      alan("tarih").textContent = `${G.tarih(veri.tarih)} kapanışı`;
      degisimleriYaz();
      hacimYaz();
      grafikCiz();
      anlikBaslat();
    })
    .catch(() => hataGoster("Fiyat bilgisine şu an ulaşılamıyor. Sayfayı biraz sonra yenileyin."));

  // -------------------------------------------------------------------------
  // Anlık fiyat: son işlem fiyatı ve seans durumu. Sayfa açık ve görünürken
  // dakikada bir yenilenir; sekme arka plandayken istek atılmaz.
  // -------------------------------------------------------------------------
  const saat = new Intl.DateTimeFormat("tr-TR", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Istanbul" });
  const gunSaat = new Intl.DateTimeFormat("tr-TR", {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Istanbul",
  });

  function zamanYaz(saniye) {
    const t = new Date(saniye * 1000);
    const bugun = new Date().toDateString() === t.toDateString();
    return (bugun ? saat : gunSaat).format(t);
  }

  function acilisMetni(a) {
    if (!a.acilis) return "";
    const gun = a.acilis.gun === 0 ? "bugün" : a.acilis.gun === 1 ? "yarın" : a.acilis.gun_adi;
    return `ABD borsası ${gun} ${a.acilis.saat}'da açılır`;
  }

  function anlikYaz(a) {
    const acik = a.durum === "REGULAR";
    // Seans dışındayken canlı olan seans öncesi / sonrası fiyatıdır; ana fiyat odur
    const disi = !acik && a.seans_disi ? a.seans_disi : null;
    alan("etiket").innerHTML = "";
    const nokta = document.createElement("span");
    nokta.className = "canli-nokta" + (acik || disi ? " acik" : "");
    nokta.setAttribute("aria-hidden", "true");
    alan("etiket").append(nokta, acik ? "Anlık fiyat" : disi ? `${disi.etiket} fiyatı` : "Son fiyat");

    alan("fiyat").textContent = fiyatYaz(disi ? disi.fiyat : a.fiyat);
    const parcalar = [];
    if (a.durum_etiket) parcalar.push(a.durum_etiket);
    // Seans dışı fiyatta saat, o fiyatın saatidir (kapanışınki değil)
    const saat = disi ? disi.zaman : a.zaman;
    if (saat) parcalar.push(`${zamanYaz(saat)} (TSİ)`);
    if (a.gecikme) parcalar.push(`${a.gecikme} dk gecikmeli`);
    const acilis = acilisMetni(a);
    if (acilis) parcalar.push(acilis);
    alan("tarih").textContent = parcalar.join(" · ");

    const ek = alan("seans-disi");
    if (disi) {
      ek.textContent = `Son kapanış ${fiyatYaz(a.fiyat)}` + (disi.degisim === null ? "" : ` · kapanışa göre ${G.yuzde(disi.degisim)}`);
      ek.className = "fiyat-seans-disi " + (disi.degisim > 0 ? "artis" : disi.degisim < 0 ? "azalis" : "");
      ek.hidden = false;
    } else {
      ek.hidden = true;
    }

    // "1 gün" değişimi önceki kapanışa göre anlık fiyattan
    const gunluk = veri.degisimler.find((d) => d.anahtar === "1g");
    if (gunluk && a.degisim !== null) {
      gunluk.oran = a.degisim;
      degisimleriYaz();
    }
  }

  function anlikGetir() {
    if (document.hidden) return;
    fetch(panel.dataset.anlikUrl)
      .then((cevap) => (cevap.ok ? cevap.json() : null))
      .then((a) => a && anlikYaz(a))
      .catch(() => { /* anlık fiyat alınamazsa son kapanış görünmeye devam eder */ });
  }

  function anlikBaslat() {
    if (!panel.dataset.anlikUrl) return;
    anlikGetir();
    setInterval(anlikGetir, 60 * 1000);
    document.addEventListener("visibilitychange", anlikGetir);
  }
})();
