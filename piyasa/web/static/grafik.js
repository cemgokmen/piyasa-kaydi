"use strict";

// ---------------------------------------------------------------------------
// PiyasaGrafik: sitedeki bütün grafikler için küçük, bağımlılıksız SVG çizici.
//
//   PiyasaGrafik.cizgi(kap, seri, ayar)   fiyat/stok gibi zaman serileri
//   PiyasaGrafik.cubuk(kap, seri, ayar)   artı/eksi değerli haftalık çubuklar
//
// seri: [[tarih "YYYY-AA-GG", değer, (hacim)], ...]
// Fareyle (ya da dokunarak) üzerine gelince tarih ve değer gösterilir.
// ---------------------------------------------------------------------------

window.PiyasaGrafik = (function () {
  const SVG = "http://www.w3.org/2000/svg";
  const AYLAR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
  const sayi2 = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const tamSayi = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 0 });

  function oge(ad, ozellik) {
    const o = document.createElementNS(SVG, ad);
    Object.entries(ozellik || {}).forEach(([k, v]) => o.setAttribute(k, v));
    return o;
  }

  function tarih(iso) {
    const [y, a, g] = iso.split("-").map(Number);
    return `${g} ${AYLAR[a - 1]} ${y}`;
  }

  function kisaSayi(n) {
    const m = Math.abs(n);
    if (m >= 1e9) return `${sayi2.format(n / 1e9)} mr`;
    if (m >= 1e6) return `${sayi2.format(n / 1e6)} mn`;
    if (m >= 1e3) return `${tamSayi.format(n / 1e3)} bin`;
    return tamSayi.format(n);
  }

  function yuzde(oran) {
    const isaret = oran > 0 ? "+" : oran < 0 ? "−" : "";
    return `${isaret}%${sayi2.format(Math.abs(oran * 100))}`;
  }

  // Ortak iskelet: SVG, eksen yazıları, fare izleme ve ipucu kutusu
  function iskelet(kap, seri, ayar, yukseklik) {
    kap.innerHTML = "";
    const G = Math.max(kap.clientWidth, 280);
    const bosluk = { sol: 8, sag: ayar.sagBosluk || 64, ust: 12, alt: 26 };
    const svg = oge("svg", {
      viewBox: `0 0 ${G} ${yukseklik}`, width: G, height: yukseklik, role: "img",
      "aria-label": ayar.etiket || `${tarih(seri[0][0])} – ${tarih(seri[seri.length - 1][0])} grafiği`,
    });
    const x = (i) => bosluk.sol + (seri.length === 1 ? 0.5 : i / (seri.length - 1)) * (G - bosluk.sol - bosluk.sag);

    [[0, "start"], [seri.length - 1, "end"]].forEach(function ([i, hiza]) {
      const yazi = oge("text", { x: hiza === "start" ? bosluk.sol : G - bosluk.sag, y: yukseklik - 6, "text-anchor": hiza, class: "eksen-yazi" });
      yazi.textContent = tarih(seri[i][0]);
      svg.appendChild(yazi);
    });

    const ipucu = document.createElement("div");
    ipucu.className = "grafik-ipucu";
    ipucu.hidden = true;
    const dikey = oge("line", { y1: bosluk.ust, y2: yukseklik - bosluk.alt, class: "imlec-cizgi", visibility: "hidden" });

    function izle(goster, gizle) {
      function konum(istemciX) {
        const kutu = svg.getBoundingClientRect();
        const oran = (istemciX - kutu.left - bosluk.sol) / (kutu.width - bosluk.sol - bosluk.sag);
        const i = Math.max(0, Math.min(seri.length - 1, Math.round(oran * (seri.length - 1))));
        dikey.setAttribute("x1", x(i));
        dikey.setAttribute("x2", x(i));
        dikey.setAttribute("visibility", "visible");
        ipucu.innerHTML = "";
        goster(i, ipucu);
        ipucu.hidden = false;
        ipucu.style.left = `${Math.min(Math.max((x(i) / G) * kutu.width, 80), kutu.width - 80)}px`;
      }
      function kapat() {
        dikey.setAttribute("visibility", "hidden");
        ipucu.hidden = true;
        if (gizle) gizle();
      }
      svg.addEventListener("mousemove", (o) => konum(o.clientX));
      svg.addEventListener("mouseleave", kapat);
      svg.addEventListener("touchmove", (o) => konum(o.touches[0].clientX), { passive: true });
      svg.addEventListener("touchend", kapat);
    }

    function satir(ipucuKutusu, sinif, metin) {
      const o = document.createElement(sinif === "b" ? "b" : sinif === "small" ? "small" : "span");
      o.textContent = metin;
      ipucuKutusu.appendChild(o);
    }

    return { svg, G, bosluk, x, dikey, ipucu, izle, satir };
  }

  // ----- Çizgi grafiği (isteğe bağlı hacim çubuklarıyla) -----

  function cizgi(kap, seri, ayar = {}) {
    seri = (seri || []).filter((n) => n[1] !== null && n[1] !== undefined);
    if (seri.length < 2) {
      kap.innerHTML = '<p class="bos">Bu aralık için yeterli veri yok.</p>';
      return;
    }

    const bicim = ayar.bicim || ((v) => sayi2.format(v));
    const hacimVar = ayar.hacim !== false && seri.some((n) => n[2] > 0);
    const yukseklik = ayar.yukseklik || 240;
    const g = iskelet(kap, seri, ayar, yukseklik);
    const { svg, G, bosluk, x } = g;

    // Hacim varsa grafiğin alt beşte biri hacim çubuklarına ayrılır
    const fiyatAlt = yukseklik - bosluk.alt - (hacimVar ? yukseklik * 0.2 : 0);
    const degerler = seri.map((n) => n[1]);
    let enAz = Math.min(...degerler);
    let enCok = Math.max(...degerler);
    if (enAz === enCok) { enAz -= Math.abs(enAz) * 0.01 || 1; enCok += Math.abs(enCok) * 0.01 || 1; }
    const y = (v) => bosluk.ust + (1 - (v - enAz) / (enCok - enAz)) * (fiyatAlt - bosluk.ust - 6);

    const yon = ayar.renk === "notr" ? "cizgi-notr"
      : degerler[degerler.length - 1] >= degerler[0] ? "cizgi-artis" : "cizgi-azalis";

    for (let i = 0; i <= 3; i++) {
      const v = enAz + ((enCok - enAz) * i) / 3;
      svg.appendChild(oge("line", { x1: bosluk.sol, x2: G - bosluk.sag, y1: y(v), y2: y(v), class: "kilavuz" }));
      const yazi = oge("text", { x: G - bosluk.sag + 8, y: y(v) + 4, class: "eksen-yazi" });
      yazi.textContent = ayar.eksenBicim ? ayar.eksenBicim(v) : sayi2.format(v);
      svg.appendChild(yazi);
    }

    if (hacimVar) {
      const enCokHacim = Math.max(...seri.map((n) => n[2] || 0));
      const cubukGenislik = Math.max(1, ((G - bosluk.sol - bosluk.sag) / seri.length) * 0.7);
      const taban = yukseklik - bosluk.alt;
      const grup = oge("g", { class: "hacim-cubuklari" });
      seri.forEach(function (n, i) {
        const h = ((n[2] || 0) / enCokHacim) * (yukseklik * 0.2 - 4);
        grup.appendChild(oge("rect", { x: x(i) - cubukGenislik / 2, y: taban - h, width: cubukGenislik, height: h }));
      });
      svg.appendChild(grup);
    }

    const noktalar = seri.map((n, i) => `${x(i).toFixed(1)},${y(n[1]).toFixed(1)}`);
    svg.appendChild(oge("path", {
      d: `M${noktalar[0]} L${noktalar.join(" L")} L${x(seri.length - 1)},${fiyatAlt} L${x(0)},${fiyatAlt} Z`,
      class: `alan ${yon}`,
    }));
    svg.appendChild(oge("polyline", { points: noktalar.join(" "), class: `cizgi ${yon}` }));

    const nokta = oge("circle", { r: 4, class: `imlec-nokta ${yon}`, visibility: "hidden" });
    svg.append(g.dikey, nokta);

    g.izle(function (i, kutu) {
      const [t, v, h] = seri[i];
      nokta.setAttribute("cx", x(i));
      nokta.setAttribute("cy", y(v));
      nokta.setAttribute("visibility", "visible");
      g.satir(kutu, "b", bicim(v));
      g.satir(kutu, "span", tarih(t));
      if (ayar.karsilastir !== false) g.satir(kutu, "small", `aralık başına göre ${yuzde(v / seri[0][1] - 1)}`);
      if (hacimVar && h) g.satir(kutu, "small", `hacim ${kisaSayi(h)}`);
    }, () => nokta.setAttribute("visibility", "hidden"));

    kap.append(svg, g.ipucu);
  }

  // ----- Artı/eksi çubuk grafiği -----

  function cubuk(kap, seri, ayar = {}) {
    seri = (seri || []).filter((n) => n[1] !== null && n[1] !== undefined);
    if (!seri.length) {
      kap.innerHTML = '<p class="bos">Veri yok.</p>';
      return;
    }
    const bicim = ayar.bicim || ((v) => tamSayi.format(v));
    const yukseklik = ayar.yukseklik || 200;
    const g = iskelet(kap, seri, ayar, yukseklik);
    const { svg, G, bosluk, x } = g;

    const enCok = Math.max(...seri.map((n) => Math.abs(n[1])), 1);
    const enAz = Math.min(0, ...seri.map((n) => n[1]));
    const ust = Math.max(0, ...seri.map((n) => n[1]));
    const aralik = (ust - enAz) || enCok;
    const y = (v) => bosluk.ust + ((ust - v) / aralik) * (yukseklik - bosluk.ust - bosluk.alt);

    [ust, 0, enAz].filter((v, i, d) => d.indexOf(v) === i).forEach(function (v) {
      svg.appendChild(oge("line", { x1: bosluk.sol, x2: G - bosluk.sag, y1: y(v), y2: y(v), class: v === 0 ? "sifir-cizgi" : "kilavuz" }));
      const yazi = oge("text", { x: G - bosluk.sag + 8, y: y(v) + 4, class: "eksen-yazi" });
      yazi.textContent = kisaSayi(v);
      svg.appendChild(yazi);
    });

    const genislik = Math.max(1.5, ((G - bosluk.sol - bosluk.sag) / seri.length) * 0.72);
    seri.forEach(function (n, i) {
      const ustY = Math.min(y(n[1]), y(0));
      svg.appendChild(oge("rect", {
        x: x(i) - genislik / 2, y: ustY, width: genislik, height: Math.max(1, Math.abs(y(n[1]) - y(0))),
        class: n[1] >= 0 ? "cubuk-arti" : "cubuk-eksi",
      }));
    });
    svg.appendChild(g.dikey);

    g.izle(function (i, kutu) {
      const [t, v] = seri[i];
      g.satir(kutu, "b", bicim(v));
      g.satir(kutu, "span", tarih(t));
      if (ayar.aciklama) g.satir(kutu, "small", ayar.aciklama(seri[i], i));
    });

    kap.append(svg, g.ipucu);
  }

  // Sayfadaki <script type="application/json" data-grafik> öğelerini kendiliğinden çizer
  function sayfadakileriCiz() {
    document.querySelectorAll("[data-grafik-veri]").forEach(function (kap) {
      const veri = JSON.parse(document.getElementById(kap.dataset.grafikVeri).textContent);
      const birim = kap.dataset.birim || "";
      const ayar = {
        bicim: (v) => `${kap.dataset.isaret && v > 0 ? "+" : ""}${sayi2.format(v)}${birim ? " " + birim : ""}`,
        eksenBicim: (v) => sayi2.format(v),
        renk: "notr",
        karsilastir: kap.dataset.karsilastir !== "hayir",
        hacim: false,
        yukseklik: Number(kap.dataset.yukseklik) || undefined,
      };
      const ciz = () => (kap.dataset.grafik === "cubuk" ? cubuk : cizgi)(kap, veri, ayar);
      ciz();
      let zaman = null;
      window.addEventListener("resize", () => { clearTimeout(zaman); zaman = setTimeout(ciz, 150); });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", sayfadakileriCiz);
  } else {
    sayfadakileriCiz();
  }

  return { cizgi, cubuk, tarih, kisaSayi, yuzde };
})();
