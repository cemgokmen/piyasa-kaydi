"use strict";

// ---------------------------------------------------------------------------
// Hisse sayfası: güncel fiyat, dönemsel değişimler ve fiyat grafiği.
// Veri /api/fiyat/<kod> adresinden gelir; sayfa onu beklemeden açılır.
// ---------------------------------------------------------------------------

(function () {
  const panel = document.getElementById("fiyat");
  if (!panel) return;

  const alan = (ad) => panel.querySelector(`[data-alan="${ad}"]`);
  const sayi = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const AYLAR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];

  const fiyatYaz = (n) => `${sayi.format(n)} $`;
  const tarihYaz = (iso, yilli = true) => {
    const [y, a, g] = iso.split("-").map(Number);
    return `${g} ${AYLAR[a - 1]}${yilli ? " " + y : ""}`;
  };
  const yuzdeYaz = (oran) => {
    if (oran === null || oran === undefined) return "—";
    const isaret = oran > 0 ? "+" : oran < 0 ? "−" : "";
    return `${isaret}%${sayi.format(Math.abs(oran * 100))}`;
  };

  let veri = null;
  let aralik = "1y";

  // ----- Değişim kutucukları -----

  function degisimleriYaz() {
    const liste = alan("degisimler");
    liste.innerHTML = "";
    veri.degisimler.forEach(function (d) {
      const li = document.createElement("li");
      li.className = "degisim " + (d.oran > 0 ? "artis" : d.oran < 0 ? "azalis" : "notr");
      li.innerHTML = `<span class="degisim-etiket"></span><span class="degisim-deger"></span>`;
      li.firstChild.textContent = d.etiket;
      li.lastChild.textContent = yuzdeYaz(d.oran);
      if (d.oran === null) li.title = "Bu süre için fiyat geçmişi yok";
      liste.appendChild(li);
    });
  }

  // ----- Grafik -----

  const SVG = "http://www.w3.org/2000/svg";
  const svgOge = (ad, ozellik) => {
    const o = document.createElementNS(SVG, ad);
    Object.entries(ozellik || {}).forEach(([k, v]) => o.setAttribute(k, v));
    return o;
  };

  function grafikCiz() {
    const kap = alan("grafik");
    const seri = (veri.seriler[aralik] || []).filter((n) => n[1] !== null);
    kap.innerHTML = "";
    if (seri.length < 2) {
      kap.innerHTML = '<p class="bos">Bu aralık için yeterli fiyat verisi yok.</p>';
      return;
    }

    const G = Math.max(kap.clientWidth, 280);
    const Y = 240;
    const bosluk = { sol: 8, sag: 64, ust: 12, alt: 26 };
    const degerler = seri.map((n) => n[1]);
    let enAz = Math.min(...degerler);
    let enCok = Math.max(...degerler);
    if (enAz === enCok) { enAz *= 0.99; enCok *= 1.01; }

    const x = (i) => bosluk.sol + (i / (seri.length - 1)) * (G - bosluk.sol - bosluk.sag);
    const y = (v) => bosluk.ust + (1 - (v - enAz) / (enCok - enAz)) * (Y - bosluk.ust - bosluk.alt);
    const yukseldi = degerler[degerler.length - 1] >= degerler[0];
    const sinif = yukseldi ? "cizgi-artis" : "cizgi-azalis";

    const svg = svgOge("svg", {
      viewBox: `0 0 ${G} ${Y}`, width: G, height: Y, role: "img",
      "aria-label": `${tarihYaz(seri[0][0])} ile ${tarihYaz(seri[seri.length - 1][0])} arası fiyat grafiği`,
    });

    // Yatay kılavuz çizgileri ve fiyat etiketleri
    for (let i = 0; i <= 3; i++) {
      const v = enAz + ((enCok - enAz) * i) / 3;
      svg.appendChild(svgOge("line", { x1: bosluk.sol, x2: G - bosluk.sag, y1: y(v), y2: y(v), class: "kilavuz" }));
      const yazi = svgOge("text", { x: G - bosluk.sag + 8, y: y(v) + 4, class: "eksen-yazi" });
      yazi.textContent = sayi.format(v);
      svg.appendChild(yazi);
    }

    // Başlangıç ve bitiş tarihleri
    [[0, "start"], [seri.length - 1, "end"]].forEach(function ([i, hiza]) {
      const yazi = svgOge("text", { x: hiza === "start" ? bosluk.sol : G - bosluk.sag, y: Y - 6, "text-anchor": hiza, class: "eksen-yazi" });
      yazi.textContent = tarihYaz(seri[i][0]);
      svg.appendChild(yazi);
    });

    const noktalar = seri.map((n, i) => `${x(i).toFixed(1)},${y(n[1]).toFixed(1)}`);
    svg.appendChild(svgOge("path", {
      d: `M${noktalar[0]} L${noktalar.join(" L")} L${x(seri.length - 1)},${Y - bosluk.alt} L${x(0)},${Y - bosluk.alt} Z`,
      class: `alan ${sinif}`,
    }));
    svg.appendChild(svgOge("polyline", { points: noktalar.join(" "), class: `cizgi ${sinif}` }));

    // Fareyle üzerine gelince tarih ve fiyat
    const dikey = svgOge("line", { y1: bosluk.ust, y2: Y - bosluk.alt, class: "imlec-cizgi", visibility: "hidden" });
    const nokta = svgOge("circle", { r: 4, class: `imlec-nokta ${sinif}`, visibility: "hidden" });
    svg.append(dikey, nokta);

    const ipucu = document.createElement("div");
    ipucu.className = "grafik-ipucu";
    ipucu.hidden = true;

    function goster(istemciX) {
      const kutu = svg.getBoundingClientRect();
      const oran = (istemciX - kutu.left - bosluk.sol) / (kutu.width - bosluk.sol - bosluk.sag);
      const i = Math.max(0, Math.min(seri.length - 1, Math.round(oran * (seri.length - 1))));
      const [t, v] = seri[i];
      dikey.setAttribute("x1", x(i)); dikey.setAttribute("x2", x(i));
      nokta.setAttribute("cx", x(i)); nokta.setAttribute("cy", y(v));
      dikey.setAttribute("visibility", "visible"); nokta.setAttribute("visibility", "visible");
      const ilkFiyat = seri[0][1];
      ipucu.innerHTML = `<b></b><span></span><small></small>`;
      ipucu.children[0].textContent = fiyatYaz(v);
      ipucu.children[1].textContent = tarihYaz(t);
      ipucu.children[2].textContent = `aralık başına göre ${yuzdeYaz(v / ilkFiyat - 1)}`;
      ipucu.hidden = false;
      const solKonum = (x(i) / G) * kutu.width;
      ipucu.style.left = `${Math.min(Math.max(solKonum, 70), kutu.width - 70)}px`;
    }

    function gizle() {
      dikey.setAttribute("visibility", "hidden");
      nokta.setAttribute("visibility", "hidden");
      ipucu.hidden = true;
    }

    svg.addEventListener("mousemove", (o) => goster(o.clientX));
    svg.addEventListener("mouseleave", gizle);
    svg.addEventListener("touchmove", (o) => { goster(o.touches[0].clientX); }, { passive: true });
    svg.addEventListener("touchend", gizle);

    kap.append(svg, ipucu);
  }

  // ----- Aralık düğmeleri -----

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

  let yenidenCizZamanlayici = null;
  window.addEventListener("resize", function () {
    clearTimeout(yenidenCizZamanlayici);
    yenidenCizZamanlayici = setTimeout(() => veri && grafikCiz(), 150);
  });

  // ----- Veriyi al -----

  function hataGoster(mesaj) {
    panel.classList.add("fiyat-yok");
    alan("fiyat").textContent = "—";
    alan("tarih").textContent = "";
    alan("degisimler").hidden = true;
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
      alan("tarih").textContent = `${tarihYaz(veri.tarih)} kapanışı`;
      degisimleriYaz();
      grafikCiz();
    })
    .catch(() => hataGoster("Fiyat bilgisine şu an ulaşılamıyor. Sayfayı biraz sonra yenileyin."));
})();
