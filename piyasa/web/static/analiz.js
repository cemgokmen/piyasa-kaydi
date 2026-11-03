"use strict";

// ---------------------------------------------------------------------------
// Analiz sayfaları
//   /analiz        tarama tablosu: sıralama ve süzgeçler
//   /analiz/<kod>  mum grafiği (ortalamalar, Bollinger, Süpertrend, destek/direnç,
//                  Fibonacci, tepe-dip, hacim, RSI, MACD) ve pozisyon hesaplayıcı
// Bağımlılık yok; grafik SVG ile çizilir, renkler CSS'ten gelir (tema değişince kendiliğinden uyar).
// ---------------------------------------------------------------------------

(function () {
  const SVG = "http://www.w3.org/2000/svg";
  const AYLAR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
  const sayi = (b) => new Intl.NumberFormat("tr-TR", { minimumFractionDigits: b, maximumFractionDigits: b });
  const tam = sayi(0), iki = sayi(2);

  function bellek(anahtar, deger) {
    try {
      if (deger === undefined) return localStorage.getItem(anahtar);
      localStorage.setItem(anahtar, deger);
    } catch (e) { return null; }
    return null;
  }

  function oge(ad, ozellik, ust) {
    const o = document.createElementNS(SVG, ad);
    for (const k in ozellik || {}) o.setAttribute(k, ozellik[k]);
    if (ust) ust.appendChild(o);
    return o;
  }

  function trSayi(metin) {
    // "300.000" → 300000; "1,5" → 1.5; "12.345,67" → 12345.67
    let m = String(metin || "").trim().replace(/\s|TL|₺|\$|%/g, "");
    if (!m) return NaN;
    if (m.includes(",")) m = m.replace(/\./g, "").replace(",", ".");
    else if ((m.match(/\./g) || []).length > 1 || /^\d{1,3}\.\d{3}$/.test(m)) m = m.replace(/\./g, "");
    return parseFloat(m);
  }

  function tarihYazi(iso, kisa) {
    const [y, a, g] = iso.split("-").map(Number);
    return kisa ? `${AYLAR[a - 1]} ${String(y).slice(2)}` : `${g} ${AYLAR[a - 1]} ${y}`;
  }

  // =========================================================================
  // 1. TARAMA TABLOSU
  // =========================================================================

  function tarama() {
    const tablo = document.querySelector("[data-siralanir]");
    if (!tablo) return;
    const govde = tablo.tBodies[0];
    const satirlar = Array.from(govde.rows);
    let anahtar = "birlesik", azalan = true;

    function deger(s, k) {
      const v = s.dataset[k];
      if (k === "kod") return v;
      return v === "" || v === undefined ? null : parseFloat(v);
    }

    function sirala() {
      const sirali = satirlar.slice().sort(function (a, b) {
        const x = deger(a, anahtar), y = deger(b, anahtar);
        if (x === null && y === null) return 0;
        if (x === null) return 1;
        if (y === null) return -1;
        if (typeof x === "string") return azalan ? y.localeCompare(x, "tr") : x.localeCompare(y, "tr");
        return azalan ? y - x : x - y;
      });
      sirali.forEach((s) => govde.appendChild(s));
      tablo.querySelectorAll("th[data-sirala]").forEach(function (th) {
        th.setAttribute("aria-sort", th.dataset.sirala === anahtar ? (azalan ? "descending" : "ascending") : "none");
      });
    }

    tablo.querySelectorAll("th[data-sirala]").forEach(function (th) {
      th.tabIndex = 0;
      const tikla = function () {
        if (anahtar === th.dataset.sirala) azalan = !azalan;
        else { anahtar = th.dataset.sirala; azalan = th.dataset.tur !== "metin" && !["rsi", "fk"].includes(anahtar); }
        sirala();
      };
      th.addEventListener("click", tikla);
      th.addEventListener("keydown", (o) => { if (o.key === "Enter") tikla(); });
    });

    const suzgecler = {
      hepsi: () => true,
      guclu: (s) => (deger(s, "orta") ?? 0) >= 60 && (deger(s, "temel") ?? 0) >= 55,
      lider: (s) => s.dataset.ust200 === "1" && (deger(s, "relatif") ?? -1) > 0 && (deger(s, "orta") ?? 0) >= 55,
      izle: (s) => (deger(s, "orta") ?? 100) <= 45 && (deger(s, "temel") ?? 0) >= 55,
      ucuz: (s) => (deger(s, "degerleme") ?? -1) > 0.3 && (deger(s, "kalite") ?? -1) > 0.1,
      uzak: (s) => (deger(s, "orta") ?? 100) <= 40 && (deger(s, "temel") ?? 100) < 45,
    };
    let secili = "hepsi", sektor = "";
    const kutu = document.querySelector("[data-suzgec]");
    const bos = document.querySelector("[data-bos]");

    function uygula() {
      let gorunen = 0;
      satirlar.forEach(function (s) {
        const goster = suzgecler[secili](s) && (!sektor || s.dataset.sektor === sektor);
        s.hidden = !goster;
        if (goster) gorunen++;
      });
      if (bos) bos.hidden = gorunen > 0;
      bellek("analiz-suzgec", secili);
    }

    if (kutu) {
      kutu.querySelectorAll("button[data-suz]").forEach(function (d) {
        d.addEventListener("click", function () {
          secili = d.dataset.suz;
          kutu.querySelectorAll("button[data-suz]").forEach((x) => x.setAttribute("aria-pressed", x === d ? "true" : "false"));
          uygula();
        });
      });
      const sec = kutu.querySelector("[data-sektor]");
      if (sec) sec.addEventListener("change", function () { sektor = sec.value; uygula(); });
      const onceki = bellek("analiz-suzgec");
      if (onceki && suzgecler[onceki]) {
        const d = kutu.querySelector(`button[data-suz="${onceki}"]`);
        if (d) d.click();
      }
    }
  }

  // =========================================================================
  // 2. MUM GRAFİĞİ
  // =========================================================================

  function grafik() {
    const kap = document.querySelector("[data-grafik]");
    const kaynak = document.getElementById("grafik-verisi");
    if (!kap || !kaynak) return;
    const V = JSON.parse(kaynak.textContent);
    const N = V.t.length;
    const fiyatF = sayi(V.basamak);
    const katman = { ort: true, bb: false, st: false, sr: true, fib: false, zz: false };
    let gun = Math.min(252, N);

    document.querySelectorAll("[data-katman]").forEach(function (k) {
      const kayitli = bellek("analiz-katman-" + k.dataset.katman);
      if (kayitli !== null) k.checked = kayitli === "1";
      katman[k.dataset.katman] = k.checked;
      k.addEventListener("change", function () {
        katman[k.dataset.katman] = k.checked;
        bellek("analiz-katman-" + k.dataset.katman, k.checked ? "1" : "0");
        ciz();
      });
    });
    const aralik = document.querySelector("[data-aralik]");
    if (aralik) {
      const kayitli = parseInt(bellek("analiz-aralik") || "", 10);
      aralik.querySelectorAll("button").forEach(function (d) {
        if (kayitli && parseInt(d.dataset.gun, 10) === kayitli) gun = Math.min(kayitli, N);
        d.addEventListener("click", function () {
          gun = Math.min(parseInt(d.dataset.gun, 10), N);
          bellek("analiz-aralik", d.dataset.gun);
          isaretle();
          ciz();
        });
      });
      isaretle();
    }
    function isaretle() {
      aralik.querySelectorAll("button").forEach((d) => d.setAttribute("aria-pressed", Math.min(parseInt(d.dataset.gun, 10), N) === gun ? "true" : "false"));
    }

    function guzelAdimlar(alt, ust, adet) {
      const ham = (ust - alt) / adet;
      const us = Math.pow(10, Math.floor(Math.log10(ham)));
      const adim = [1, 2, 2.5, 5, 10].map((k) => k * us).find((a) => a >= ham) || ham;
      const sonuc = [];
      for (let v = Math.ceil(alt / adim) * adim; v <= ust; v += adim) sonuc.push(v);
      return sonuc;
    }

    function ciz() {
      kap.innerHTML = "";
      const G = Math.max(kap.clientWidth, 300);
      const dar = G < 600;
      const sag = dar ? 52 : 64;
      const UST_Y = dar ? 260 : 380, HACIM_Y = 0.18, RSI_Y = dar ? 70 : 90, MACD_Y = dar ? 70 : 90, ARA = 10, ALT = 22;
      const H = UST_Y + ARA + RSI_Y + ARA + MACD_Y + ALT;
      const bas = N - gun;
      const n = N - bas;
      const genislik = G - sag - 4;
      const adim = genislik / n;
      const x = (i) => 4 + (i - bas + 0.5) * adim;
      const svg = oge("svg", { viewBox: `0 0 ${G} ${H}`, width: G, height: H, class: "an-svg" }, kap);

      // --- Fiyat ölçeği (görünen mumlar + açık katmanlar)
      let enDusuk = Infinity, enYuksek = -Infinity;
      for (let i = bas; i < N; i++) {
        if (V.l[i] !== null) enDusuk = Math.min(enDusuk, V.l[i]);
        if (V.h[i] !== null) enYuksek = Math.max(enYuksek, V.h[i]);
        if (katman.bb && V.bbu[i] !== null) { enYuksek = Math.max(enYuksek, V.bbu[i]); enDusuk = Math.min(enDusuk, V.bba[i]); }
      }
      const pay = (enYuksek - enDusuk) * 0.06 || 1;
      enDusuk -= pay; enYuksek += pay;
      const y = (v) => 8 + (1 - (v - enDusuk) / (enYuksek - enDusuk)) * (UST_Y - 16);
      const icinde = (v) => v >= enDusuk && v <= enYuksek;

      // Izgara ve fiyat ekseni
      const izgara = oge("g", { class: "an-izgara" }, svg);
      guzelAdimlar(enDusuk, enYuksek, dar ? 4 : 6).forEach(function (v) {
        oge("line", { x1: 4, x2: G - sag, y1: y(v), y2: y(v) }, izgara);
        const yz = oge("text", { x: G - sag + 6, y: y(v) + 4, class: "an-eksen" }, svg);
        yz.textContent = fiyatF.format(v);
      });

      // Tarih ekseni: ay ya da yıl başları
      const etiketAraligi = Math.max(1, Math.round(n / (dar ? 4 : 8)));
      let son = -Infinity;
      for (let i = bas + 1; i < N; i++) {
        const yeniAy = V.t[i].slice(5, 7) !== V.t[i - 1].slice(5, 7);
        if (yeniAy && i - son >= etiketAraligi) {
          son = i;
          oge("line", { x1: x(i), x2: x(i), y1: 0, y2: H - ALT, class: "an-izgara-dik" }, svg);
          const yz = oge("text", { x: x(i), y: H - 6, class: "an-eksen", "text-anchor": "middle" }, svg);
          yz.textContent = tarihYazi(V.t[i], true);
        }
      }

      // --- Destek / direnç bölgeleri
      if (katman.sr) {
        const g = oge("g", {}, svg);
        V.bolgeler.forEach(function (b) {
          if (b.ust < enDusuk || b.alt > enYuksek) return;
          const ust = Math.min(b.ust, enYuksek), alt = Math.max(b.alt, enDusuk);
          oge("rect", { x: 4, width: G - sag - 4, y: y(ust), height: Math.max(1, y(alt) - y(ust)),
            class: b.tur === "destek" ? "an-bolge-destek" : "an-bolge-direnc", "fill-opacity": (0.06 + 0.22 * b.puan / 100).toFixed(2) }, g);
          const yz = oge("text", { x: 8, y: y(ust) - 3, class: "an-bolge-yazi " + (b.tur === "destek" ? "an-iyi-yazi" : "an-kotu-yazi") }, g);
          yz.textContent = `${b.tur === "destek" ? "Destek" : "Direnç"} ${fiyatF.format(b.alt)}–${fiyatF.format(b.ust)} · güç ${Math.round(b.puan)}`;
        });
      }

      // --- Fibonacci
      if (katman.fib && V.fib.length) {
        const g = oge("g", { class: "an-fib" }, svg);
        V.fib.forEach(function (f) {
          if (!icinde(f.fiyat)) return;
          oge("line", { x1: 4, x2: G - sag, y1: y(f.fiyat), y2: y(f.fiyat) }, g);
          const yz = oge("text", { x: G - sag - 4, y: y(f.fiyat) - 3, "text-anchor": "end" }, g);
          yz.textContent = `%${iki.format(f.oran * 100).replace(",00", "")} · ${fiyatF.format(f.fiyat)}`;
        });
      }

      function cizgi(dizi, sinif, ust) {
        let d = "", acik = false;
        for (let i = bas; i < N; i++) {
          const v = dizi[i];
          if (v === null || v === undefined) { acik = false; continue; }
          d += (acik ? "L" : "M") + x(i).toFixed(1) + " " + y(v).toFixed(1);
          acik = true;
        }
        if (d) oge("path", { d, class: sinif }, ust || svg);
      }

      // --- Bollinger
      if (katman.bb) {
        let d = "", geri = "";
        for (let i = bas; i < N; i++) {
          if (V.bbu[i] === null) continue;
          d += (d ? "L" : "M") + x(i).toFixed(1) + " " + y(V.bbu[i]).toFixed(1);
          geri = "L" + x(i).toFixed(1) + " " + y(V.bba[i]).toFixed(1) + geri;
        }
        if (d) oge("path", { d: d + geri + "Z", class: "an-bb-alan" }, svg);
        cizgi(V.bbu, "an-bb");
        cizgi(V.bba, "an-bb");
      }

      // --- Hacim (fiyat panelinin altında)
      const hacimTaban = UST_Y;
      let hMax = 0;
      for (let i = bas; i < N; i++) hMax = Math.max(hMax, V.v[i] || 0);
      if (hMax > 0) {
        const g = oge("g", { class: "an-hacim" }, svg);
        for (let i = bas; i < N; i++) {
          const h = (V.v[i] / hMax) * UST_Y * HACIM_Y;
          if (h <= 0) continue;
          oge("rect", { x: x(i) - Math.max(0.5, adim * 0.35), width: Math.max(1, adim * 0.7), y: hacimTaban - h, height: h,
            class: V.c[i] >= V.o[i] ? "an-hacim-arti" : "an-hacim-eksi" }, g);
        }
      }

      // --- Mumlar (çok sıkışınca çizgi)
      if (adim >= 2.2) {
        const g = oge("g", {}, svg);
        const gw = Math.max(1, Math.min(12, adim * 0.66));
        for (let i = bas; i < N; i++) {
          if (V.o[i] === null) continue;
          const artis = V.c[i] >= V.o[i];
          const sinif = artis ? "an-mum-arti" : "an-mum-eksi";
          oge("line", { x1: x(i), x2: x(i), y1: y(V.h[i]), y2: y(V.l[i]), class: sinif }, g);
          const ust = y(Math.max(V.o[i], V.c[i])), alt = y(Math.min(V.o[i], V.c[i]));
          oge("rect", { x: x(i) - gw / 2, width: gw, y: ust, height: Math.max(1, alt - ust), class: sinif }, g);
        }
      } else {
        cizgi(V.c, "an-kapanis");
      }

      // --- Ortalamalar
      if (katman.ort) {
        cizgi(V.sma20, "an-sma20");
        cizgi(V.sma50, "an-sma50");
        cizgi(V.sma200, "an-sma200");
      }

      // --- Süpertrend (yöne göre renkli)
      if (katman.st) {
        [1, -1].forEach(function (yon) {
          let d = "", acik = false;
          for (let i = bas; i < N; i++) {
            if (V.st[i] === null || V.sty[i] !== yon) { acik = false; continue; }
            d += (acik ? "L" : "M") + x(i).toFixed(1) + " " + y(V.st[i]).toFixed(1);
            acik = true;
          }
          if (d) oge("path", { d, class: yon > 0 ? "an-st-arti" : "an-st-eksi" }, svg);
        });
      }

      // --- Tepe-dip noktaları
      if (katman.zz && V.noktalar.length) {
        const sira = {};
        V.t.forEach((t, i) => { sira[t] = i; });
        const noktalar = V.noktalar.map((p) => ({ i: sira[p.tarih], ...p })).filter((p) => p.i !== undefined && p.i >= bas);
        if (noktalar.length) {
          oge("path", { d: noktalar.map((p, j) => (j ? "L" : "M") + x(p.i).toFixed(1) + " " + y(p.fiyat).toFixed(1)).join(""), class: "an-zz" }, svg);
          noktalar.forEach(function (p) {
            const yz = oge("text", { x: x(p.i), y: y(p.fiyat) + (p.tur === "tepe" ? -6 : 14), "text-anchor": "middle", class: "an-zz-yazi" }, svg);
            yz.textContent = fiyatF.format(p.fiyat);
          });
        }
      }

      // --- Son fiyat etiketi
      const sonF = V.c[N - 1];
      oge("line", { x1: 4, x2: G - sag, y1: y(sonF), y2: y(sonF), class: "an-son-cizgi" }, svg);
      oge("rect", { x: G - sag + 1, y: y(sonF) - 9, width: sag - 2, height: 18, rx: 4, class: V.c[N - 1] >= (V.c[N - 2] || sonF) ? "an-son-arti" : "an-son-eksi" }, svg);
      const sy = oge("text", { x: G - sag + 6, y: y(sonF) + 4, class: "an-son-yazi" }, svg);
      sy.textContent = fiyatF.format(sonF);

      // --- RSI paneli
      const r0 = UST_Y + ARA, r1 = r0 + RSI_Y;
      const ry = (v) => r0 + (1 - v / 100) * RSI_Y;
      oge("rect", { x: 4, y: ry(70), width: G - sag - 4, height: ry(30) - ry(70), class: "an-rsi-bant" }, svg);
      [30, 50, 70].forEach(function (v) {
        oge("line", { x1: 4, x2: G - sag, y1: ry(v), y2: ry(v), class: v === 50 ? "an-izgara-cizgi" : "an-rsi-sinir" }, svg);
        const yz = oge("text", { x: G - sag + 6, y: ry(v) + 4, class: "an-eksen" }, svg);
        yz.textContent = v;
      });
      let d = "";
      for (let i = bas; i < N; i++) if (V.rsi[i] !== null) d += (d ? "L" : "M") + x(i).toFixed(1) + " " + ry(V.rsi[i]).toFixed(1);
      if (d) oge("path", { d, class: "an-rsi" }, svg);
      const rb = oge("text", { x: 8, y: r0 + 12, class: "an-panel-ad" }, svg);
      rb.textContent = "RSI (14)";

      // --- MACD paneli
      const m0 = r1 + ARA, m1 = m0 + MACD_Y;
      let mMax = 0;
      for (let i = bas; i < N; i++) {
        [V.macd[i], V.macds[i], V.macdh[i]].forEach((v) => { if (v !== null) mMax = Math.max(mMax, Math.abs(v)); });
      }
      mMax = mMax || 1;
      const my = (v) => m0 + MACD_Y / 2 - (v / mMax) * (MACD_Y / 2 - 4);
      oge("line", { x1: 4, x2: G - sag, y1: my(0), y2: my(0), class: "an-izgara-cizgi" }, svg);
      const mg = oge("g", {}, svg);
      for (let i = bas; i < N; i++) {
        const v = V.macdh[i];
        if (v === null) continue;
        const y1 = my(Math.max(v, 0)), y2 = my(Math.min(v, 0));
        oge("rect", { x: x(i) - Math.max(0.5, adim * 0.3), width: Math.max(1, adim * 0.6), y: y1, height: Math.max(0.5, y2 - y1),
          class: v >= 0 ? "an-hacim-arti" : "an-hacim-eksi" }, mg);
      }
      [["macd", "an-macd"], ["macds", "an-macds"]].forEach(function ([k, sinif]) {
        let d2 = "";
        for (let i = bas; i < N; i++) if (V[k][i] !== null) d2 += (d2 ? "L" : "M") + x(i).toFixed(1) + " " + my(V[k][i]).toFixed(1);
        if (d2) oge("path", { d: d2, class: sinif }, svg);
      });
      const mb = oge("text", { x: 8, y: m0 + 12, class: "an-panel-ad" }, svg);
      mb.textContent = "MACD (12, 26, 9)";
      oge("line", { x1: 4, x2: G - sag, y1: m1, y2: m1, class: "an-izgara-cizgi" }, svg);

      // --- İmleç ve ipucu
      const imlec = oge("line", { y1: 0, y2: H - ALT, class: "an-imlec", visibility: "hidden" }, svg);
      const imlecY = oge("line", { x1: 4, x2: G - sag, class: "an-imlec", visibility: "hidden" }, svg);
      const ipucu = document.createElement("div");
      ipucu.className = "an-ipucu";
      ipucu.hidden = true;
      kap.appendChild(ipucu);
      const alan = oge("rect", { x: 0, y: 0, width: G - sag, height: H - ALT, fill: "transparent" }, svg);

      function goster(olay) {
        const kutu = svg.getBoundingClientRect();
        const istemci = olay.touches ? olay.touches[0] : olay;
        const px = (istemci.clientX - kutu.left) * (G / kutu.width);
        const py = (istemci.clientY - kutu.top) * (H / kutu.height);
        const i = Math.min(N - 1, Math.max(bas, Math.floor((px - 4) / adim) + bas));
        imlec.setAttribute("x1", x(i)); imlec.setAttribute("x2", x(i)); imlec.setAttribute("visibility", "visible");
        if (py < UST_Y) { imlecY.setAttribute("y1", py); imlecY.setAttribute("y2", py); imlecY.setAttribute("visibility", "visible"); }
        else imlecY.setAttribute("visibility", "hidden");
        const onceki = i > 0 ? V.c[i - 1] : null;
        const deg = onceki ? V.c[i] / onceki - 1 : null;
        const satirlar = [
          `<b>${tarihYazi(V.t[i])}</b>`,
          `<span>Açılış</span> ${fiyatF.format(V.o[i])} <span>Yüksek</span> ${fiyatF.format(V.h[i])}`,
          `<span>Düşük</span> ${fiyatF.format(V.l[i])} <span>Kapanış</span> <b>${fiyatF.format(V.c[i])}</b>`
            + (deg !== null ? ` <em class="${deg >= 0 ? "tutar-buy" : "tutar-sell"}">${deg >= 0 ? "+" : "−"}%${iki.format(Math.abs(deg) * 100)}</em>` : ""),
          V.v[i] ? `<span>Hacim</span> ${kisaSayi(V.v[i])}` : "",
          `<span>RSI</span> ${V.rsi[i] !== null ? tam.format(V.rsi[i]) : "—"}`
            + (V.sma50[i] !== null ? ` <span>50g</span> ${fiyatF.format(V.sma50[i])}` : "")
            + (V.sma200[i] !== null ? ` <span>200g</span> ${fiyatF.format(V.sma200[i])}` : ""),
        ];
        if (py < UST_Y) satirlar.push(`<span>İmleç</span> ${fiyatF.format(enDusuk + (1 - (py - 8) / (UST_Y - 16)) * (enYuksek - enDusuk))}`);
        ipucu.innerHTML = satirlar.filter(Boolean).join("<br>");
        ipucu.hidden = false;
        const solda = x(i) / G > 0.55;
        ipucu.style.left = solda ? "" : `${(x(i) / G) * 100 + 1.5}%`;
        ipucu.style.right = solda ? `${(1 - x(i) / G) * 100 + 1.5}%` : "";
      }
      function gizle() {
        imlec.setAttribute("visibility", "hidden");
        imlecY.setAttribute("visibility", "hidden");
        ipucu.hidden = true;
      }
      alan.addEventListener("mousemove", goster);
      alan.addEventListener("touchmove", goster, { passive: true });
      alan.addEventListener("touchstart", goster, { passive: true });
      alan.addEventListener("mouseleave", gizle);

      // Lejant
      const lejant = document.querySelector("[data-lejant]");
      if (lejant) {
        const i = N - 1;
        const parca = [];
        if (katman.ort) {
          parca.push(`<span class="an-lj an-lj-sma20">20g ${V.sma20[i] !== null ? fiyatF.format(V.sma20[i]) : "—"}</span>`);
          parca.push(`<span class="an-lj an-lj-sma50">50g ${V.sma50[i] !== null ? fiyatF.format(V.sma50[i]) : "—"}</span>`);
          parca.push(`<span class="an-lj an-lj-sma200">200g ${V.sma200[i] !== null ? fiyatF.format(V.sma200[i]) : "—"}</span>`);
        }
        if (katman.st && V.st[i] !== null) parca.push(`<span class="an-lj ${V.sty[i] > 0 ? "an-lj-st-arti" : "an-lj-st-eksi"}">Süpertrend ${fiyatF.format(V.st[i])}</span>`);
        if (katman.bb && V.bbu[i] !== null) parca.push(`<span class="an-lj an-lj-bb">Bollinger ${fiyatF.format(V.bba[i])} – ${fiyatF.format(V.bbu[i])}</span>`);
        lejant.innerHTML = parca.join("");
      }
    }

    function kisaSayi(n) {
      if (n >= 1e9) return iki.format(n / 1e9) + " mr";
      if (n >= 1e6) return iki.format(n / 1e6) + " mn";
      if (n >= 1e3) return tam.format(n / 1e3) + " bin";
      return tam.format(n);
    }

    ciz();
    let bekleyen = null;
    if (window.ResizeObserver) {
      let onceki = kap.clientWidth;
      new ResizeObserver(function () {
        if (Math.abs(kap.clientWidth - onceki) < 4) return;
        onceki = kap.clientWidth;
        clearTimeout(bekleyen);
        bekleyen = setTimeout(ciz, 80);
      }).observe(kap);
    }
  }

  // =========================================================================
  // 3. POZİSYON HESAPLAYICI
  // =========================================================================

  function pozisyon() {
    const kutu = document.querySelector(".an-pozisyon");
    if (!kutu) return;
    const para = kutu.dataset.para;
    const kur = para === "TRY" ? 1 : parseFloat(kutu.dataset.kur) || null;
    const hedefler = JSON.parse(kutu.dataset.hedefler || "[]");
    const rejim = kutu.dataset.rejim;
    const sonuc = kutu.querySelector("[data-sonuc]");
    const alan = (ad) => kutu.querySelector(`[data-alan="${ad}"]`);
    const simge = para === "TRY" ? "₺" : para === "USD" ? "$" : para;
    const fiyatF = sayi(2);
    const tl = (n) => tam.format(Math.round(n)) + " TL";

    ["sermaye", "risk", "tavan"].forEach(function (ad) {
      const kayitli = bellek("analiz-" + ad);
      if (kayitli) alan(ad).value = kayitli;
    });

    function hesapla() {
      const sermaye = trSayi(alan("sermaye").value);
      const risk = trSayi(alan("risk").value) / 100;
      const tavan = trSayi(alan("tavan").value) / 100;
      const giris = trSayi(alan("giris").value);
      const secim = kutu.querySelector('input[name="stop"]:checked');
      let stop = secim && secim.value === "ozel" ? trSayi(alan("ozel-stop").value) : parseFloat(secim ? secim.value : "");
      ["sermaye", "risk", "tavan"].forEach((ad) => bellek("analiz-" + ad, alan(ad).value));

      if (!(sermaye > 0) || !(risk > 0) || !(giris > 0)) { sonuc.innerHTML = `<p class="bos">Sermaye, risk ve giriş fiyatını yaz.</p>`; return; }
      if (!kur) { sonuc.innerHTML = `<p class="bos">Döviz kuru alınamadı; TL karşılığı hesaplanamıyor.</p>`; return; }
      if (!(stop > 0) || stop >= giris) { sonuc.innerHTML = `<p class="bos">Stop, giriş fiyatının altında olmalı.</p>`; return; }

      const hisseRiski = (giris - stop) * kur;
      const riskTL = sermaye * risk;
      let adet = Math.floor(riskTL / hisseRiski);
      let tavanda = false;
      const enCok = Math.floor((sermaye * tavan) / (giris * kur));
      if (tavan > 0 && adet > enCok) { adet = enCok; tavanda = true; }
      const tutar = adet * giris * kur;
      const kayip = adet * hisseRiski;
      const stopYuzde = stop / giris - 1;

      let html = `<div class="an-poz-kpi">
        <div><span>Alınacak adet</span><b>${tam.format(adet)}</b><small>${fiyatF.format(giris)} ${simge} giriş</small></div>
        <div><span>Pozisyon tutarı</span><b>${tl(tutar)}</b><small>sermaye payı %${iki.format((tutar / sermaye) * 100)}</small></div>
        <div class="an-kotu"><span>Stop olursa kayıp</span><b>−${tl(kayip)}</b><small>sermayeye oranı %${iki.format((kayip / sermaye) * 100)} · stop ${fiyatF.format(stop)} ${simge} (−%${iki.format(Math.abs(stopYuzde) * 100)})</small></div>
      </div>`;
      if (tavanda) html += `<p class="an-uyari">Stop yakın olduğu için risk kuralı daha fazla hisse izin veriyordu; tek hisse tavanına (%${tam.format(tavan * 100)}) göre sınırlandı.</p>`;
      if (rejim === "ayi") html += `<p class="an-uyari">Piyasa düşüş rejiminde: yarım pozisyon önerilir → ${tam.format(Math.floor(adet / 2))} adet (${tl(tutar / 2)}).</p>`;
      else if (rejim === "karisik") html += `<p class="an-not">Kararsız rejim: pozisyonu iki parçada açmayı düşün (önce ${tam.format(Math.floor(adet / 2))} adet, teyitte kalanı).</p>`;
      if (hedefler.length) {
        html += `<table class="an-gosterge an-hedefler"><thead><tr><th>Hedef</th><th class="sag">Fiyat</th><th class="sag">Kazanç</th><th class="sag">R</th></tr></thead><tbody>`;
        hedefler.forEach(function (h) {
          const r = (h.fiyat - giris) / (giris - stop);
          html += `<tr><th>${h.ad}</th><td class="sag mono">${fiyatF.format(h.fiyat)} ${simge}</td><td class="sag mono tutar-buy">+${tl(adet * (h.fiyat - giris) * kur)}</td>
            <td class="sag mono ${r >= 2 ? "tutar-buy" : r < 1 ? "tutar-sell" : ""}">${iki.format(r)}</td></tr>`;
        });
        html += `</tbody></table><p class="an-not">R: kazancın riske oranı. 2'nin altındaki işlemlerde, isabet oranın %50'nin çok üstünde değilse uzun vadede kâr kalmaz.</p>`;
      }
      sonuc.innerHTML = html;
    }

    kutu.addEventListener("input", hesapla);
    kutu.addEventListener("change", hesapla);
    hesapla();
  }

  tarama();
  grafik();
  pozisyon();
})();
