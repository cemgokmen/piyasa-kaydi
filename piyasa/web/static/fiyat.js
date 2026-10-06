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
    })
    .catch(() => hataGoster("Fiyat bilgisine şu an ulaşılamıyor. Sayfayı biraz sonra yenileyin."));
})();
