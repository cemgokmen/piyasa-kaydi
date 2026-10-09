// Yatırım karşılaştırma: form davranışı, çok çizgili grafik (doğrusal / logaritmik), paylaşma.
(function () {
  "use strict";

  // ---------------------------------------------------------------- form
  const form = document.getElementById("kars-form");
  if (form) {
    const ay = document.getElementById("kars-ay");
    const yil = document.getElementById("kars-yil");
    const bas = document.getElementById("kars-bas");
    const gonder = () => { bas.value = `${yil.value}-${ay.value}`; form.requestSubmit ? form.requestSubmit() : form.submit(); };
    form.addEventListener("submit", () => { bas.value = `${yil.value}-${ay.value}`; });
    // Seçimler değişince sonuç hemen yenilenir; tutar ve hisse kutusu Enter ya da odak kaybında
    form.querySelectorAll("input[type=radio], input[type=checkbox], select").forEach((oge) => oge.addEventListener("change", gonder));
    form.querySelectorAll("input[type=text]").forEach(function (oge) {
      const ilk = oge.value;
      oge.addEventListener("change", () => { if (oge.value !== ilk) gonder(); });
    });
    // Tutar yazılırken binlik ayırıcı
    const tutar = form.querySelector("input[name=tutar]");
    tutar.addEventListener("input", function () {
      const rakam = tutar.value.replace(/\D/g, "").slice(0, 10);
      tutar.value = rakam ? Number(rakam).toLocaleString("tr-TR") : "";
    });
  }

  const paylas = document.getElementById("kars-paylas");
  if (paylas) {
    paylas.addEventListener("click", function () {
      const bitti = () => { paylas.textContent = "Kopyalandı"; setTimeout(() => (paylas.textContent = "Bağlantıyı kopyala"), 2000); };
      if (navigator.share && matchMedia("(max-width: 720px)").matches) {
        navigator.share({ title: document.title, url: location.href }).catch(() => {});
      } else if (navigator.clipboard) {
        navigator.clipboard.writeText(location.href).then(bitti);
      }
    });
  }

  // ---------------------------------------------------------------- grafik
  const kap = document.getElementById("kars-grafik");
  const veriOgesi = document.getElementById("kars-veri");
  if (!kap || !veriOgesi) return;
  const veri = JSON.parse(veriOgesi.textContent);
  const AYLAR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
  const SVG = "http://www.w3.org/2000/svg";
  const gizli = new Set();
  const logKutu = document.getElementById("kars-log");

  const seriler = veri.seriler.slice();
  if (veri.enflasyon) seriler.push({ ad: "Enflasyon", renk: "var(--yazi-3)", degerler: veri.enflasyon, kesik: true });

  // Değerler çok farklı büyüklükteyse (ör. Bitcoin) logaritmik ölçek varsayılan
  const tum = seriler.flatMap((s) => s.degerler).filter((d) => d > 0);
  logKutu.checked = Math.max(...tum) / Math.min(...tum) > 40;

  const kisa = function (n) {
    const p = veri.para === "TRY";
    const yaz = (x, ek) => `${p ? "" : "$"}${x.toLocaleString("tr-TR", { maximumFractionDigits: x < 10 ? 1 : 0 })}${ek}${p ? " ₺" : ""}`;
    if (n >= 1e9) return yaz(n / 1e9, " mr");
    if (n >= 1e6) return yaz(n / 1e6, " mn");
    if (n >= 1e4) return yaz(n / 1e3, " bin");
    return yaz(n, "");
  };
  const tam = (n) => (veri.para === "TRY" ? `${Math.round(n).toLocaleString("tr-TR")} ₺` : `$${Math.round(n).toLocaleString("tr-TR")}`);
  const ayYaz = (a) => `${AYLAR[Number(a.slice(5)) - 1]} ${a.slice(0, 4)}`;

  function el(ad, ozellik, ust) {
    const e = document.createElementNS(SVG, ad);
    for (const k in ozellik) e.setAttribute(k, ozellik[k]);
    if (ust) ust.appendChild(e);
    return e;
  }

  // Lejant: tıklayınca çizgi gizlenir / gösterilir
  const lejant = document.getElementById("kars-lejant");
  seriler.forEach(function (s) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "kars-lejant-oge" + (s.kesik ? " kesik" : "");
    b.style.setProperty("--renk", s.renk);
    b.innerHTML = "<i></i>";
    b.append(s.ad);
    b.setAttribute("aria-pressed", "true");
    b.addEventListener("click", function () {
      if (gizli.has(s.ad)) gizli.delete(s.ad); else gizli.add(s.ad);
      b.setAttribute("aria-pressed", String(!gizli.has(s.ad)));
      ciz();
    });
    lejant.appendChild(b);
  });

  function ciz() {
    const G = kap.clientWidth || 600;
    const Y = G < 560 ? 280 : 380;
    const sol = 8, sag = 64, ust = 12, alt = 26;
    const log = logKutu.checked;
    const gorunen = seriler.filter((s) => !gizli.has(s.ad));
    kap.replaceChildren();
    if (!gorunen.length) return;
    const degerler = gorunen.flatMap((s) => s.degerler).concat(veri.yatirilan);
    let az = Math.min(...degerler.filter((d) => d > 0)), cok = Math.max(...degerler);
    if (!log) az = 0;
    const f = log ? Math.log10 : (x) => x;
    const fa = f(az), fc = f(cok * (log ? 1.15 : 1.05));
    const n = veri.aylar.length;
    const x = (i) => sol + (i / (n - 1)) * (G - sol - sag);
    const y = (v) => ust + (1 - (f(Math.max(v, az)) - fa) / (fc - fa || 1)) * (Y - ust - alt);

    const svg = el("svg", { viewBox: `0 0 ${G} ${Y}`, width: G, height: Y, class: "kars-svg" }, kap);

    // Yatay çizgiler ve sağda değerler
    let isaretler = [];
    if (log) {
      for (let k = Math.floor(fa); k <= Math.ceil(fc); k++) [1, 2, 5].forEach((m) => isaretler.push(m * 10 ** k));
      isaretler = isaretler.filter((v) => v >= az && v <= 10 ** fc);
      if (isaretler.length > 7) isaretler = isaretler.filter((v) => String(v)[0] === "1");
    } else {
      const adim = 10 ** Math.floor(Math.log10(cok / 4));
      const kat = [1, 2, 2.5, 5, 10].find((m) => cok / (adim * m) <= 5) || 10;
      for (let v = 0; v <= cok * 1.05; v += adim * kat) isaretler.push(v);
    }
    isaretler.forEach(function (v) {
      el("line", { x1: sol, x2: G - sag, y1: y(v), y2: y(v), class: "kars-izgara" }, svg);
      el("text", { x: G - sag + 6, y: y(v) + 4, class: "kars-eksen" }, svg).textContent = kisa(v);
    });
    // Yıl etiketleri
    const yilAdimi = Math.max(1, Math.ceil((n / 12) / (G < 560 ? 4 : 8)));
    veri.aylar.forEach(function (a, i) {
      if (a.endsWith("-01") && Number(a.slice(0, 4)) % yilAdimi === 0) {
        el("text", { x: x(i), y: Y - 6, class: "kars-eksen", "text-anchor": "middle" }, svg).textContent = a.slice(0, 4);
      }
    });

    // Yatırılan para (kesikli ince çizgi)
    el("path", { d: veri.yatirilan.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(""), class: "kars-yatirilan" }, svg);

    gorunen.forEach(function (s) {
      el("path", {
        d: s.degerler.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(""),
        class: "kars-cizgi" + (s.kesik ? " kesik" : ""), stroke: s.renk,
      }, svg);
    });

    // İmleç: dikey çizgi ve o ayın değerleri
    const imlec = el("line", { y1: ust, y2: Y - alt, class: "kars-imlec", visibility: "hidden" }, svg);
    const noktalar = gorunen.map((s) => el("circle", { r: 3.5, fill: s.renk, visibility: "hidden", class: "kars-nokta-svg" }, svg));
    let kutu = kap.querySelector(".kars-ipucu-kutu");
    if (!kutu) { kutu = document.createElement("div"); kutu.className = "kars-ipucu-kutu"; kutu.hidden = true; }
    kap.appendChild(kutu);

    function goster(ex) {
      const r = svg.getBoundingClientRect();
      const px = (ex - r.left) * (G / r.width);
      const i = Math.max(0, Math.min(n - 1, Math.round(((px - sol) / (G - sol - sag)) * (n - 1))));
      imlec.setAttribute("x1", x(i)); imlec.setAttribute("x2", x(i)); imlec.setAttribute("visibility", "visible");
      gorunen.forEach((s, j) => { noktalar[j].setAttribute("cx", x(i)); noktalar[j].setAttribute("cy", y(s.degerler[i])); noktalar[j].setAttribute("visibility", "visible"); });
      const satirlar = gorunen.map((s) => [s, s.degerler[i]]).sort((a, b) => b[1] - a[1])
        .map(([s, v]) => `<div><i style="background:${s.renk}"></i><span>${s.ad}</span><b>${tam(v)}</b></div>`).join("");
      kutu.innerHTML = `<p>${ayYaz(veri.aylar[i])} · yatırılan ${tam(veri.yatirilan[i])}</p>${satirlar}`;
      kutu.hidden = false;
      const solKonum = (x(i) / G) * r.width;
      kutu.style.left = `${solKonum > r.width / 2 ? solKonum - kutu.offsetWidth - 12 : solKonum + 12}px`;
    }
    const gizle = () => { kutu.hidden = true; imlec.setAttribute("visibility", "hidden"); noktalar.forEach((p) => p.setAttribute("visibility", "hidden")); };
    svg.addEventListener("pointermove", (e) => goster(e.clientX));
    svg.addEventListener("pointerdown", (e) => goster(e.clientX));
    svg.addEventListener("pointerleave", gizle);
  }

  logKutu.addEventListener("change", ciz);
  let zamanlayici;
  window.addEventListener("resize", () => { clearTimeout(zamanlayici); zamanlayici = setTimeout(ciz, 150); });
  ciz();
})();

// Hisse ya da kripto ekleme kutusu: yazılan son kelime için öneriler; seçilen kod listeye eklenir
(function () {
  "use strict";
  const kutu = document.querySelector("input[data-kod-oneri]");
  if (!kutu) return;
  const liste = document.createElement("ul");
  liste.className = "oneri-listesi";
  liste.id = "kod-onerileri";
  liste.setAttribute("role", "listbox");
  liste.hidden = true;
  kutu.parentElement.appendChild(liste);
  kutu.setAttribute("role", "combobox");
  kutu.setAttribute("aria-autocomplete", "list");
  kutu.setAttribute("aria-controls", liste.id);
  kutu.setAttribute("aria-expanded", "false");

  let secenekler = [], aktif = -1, zamanlayici = null, istek = null;
  const parcalar = () => kutu.value.split(",").map((p) => p.trim());
  const sonParca = () => parcalar().pop() || "";

  function kapat() { liste.hidden = true; aktif = -1; kutu.setAttribute("aria-expanded", "false"); }
  function aktifYap(i) {
    secenekler.forEach((s, j) => s.setAttribute("aria-selected", j === i ? "true" : "false"));
    aktif = i;
    if (i >= 0) secenekler[i].scrollIntoView({ block: "nearest" });
  }
  function sec(li) {
    const onceki = parcalar().slice(0, -1).filter(Boolean).filter((p) => p.toUpperCase() !== li.dataset.deger);
    kutu.value = [...onceki, li.dataset.deger].slice(-4).join(", ") + ", ";
    kapat();
    kutu.focus();
  }
  function goster(oneriler) {
    liste.replaceChildren();
    secenekler = oneriler.filter((o) => o.deger).map(function (o, i) {
      const li = document.createElement("li");
      li.id = `kod-onerisi-${i}`;
      li.setAttribute("role", "option");
      li.dataset.deger = o.deger;
      const tur = document.createElement("span");
      tur.className = `oneri-tur oneri-${o.tur.toLocaleLowerCase("tr-TR").replace(/[^a-zçğıöşü]/g, "")}`;
      tur.textContent = o.tur === "Hisse" ? "ABD" : o.tur;
      const govde = document.createElement("span");
      govde.className = "oneri-govde";
      const etiket = document.createElement("span");
      etiket.className = "oneri-etiket";
      etiket.textContent = o.etiket;
      const alt = document.createElement("span");
      alt.className = "oneri-alt";
      alt.textContent = o.alt || "";
      govde.append(etiket, alt);
      li.append(tur, govde);
      // Kutu odağını kaybetmeden seçilsin
      li.addEventListener("mousedown", (e) => { e.preventDefault(); sec(li); });
      liste.appendChild(li);
      return li;
    });
    liste.hidden = !secenekler.length;
    kutu.setAttribute("aria-expanded", String(!liste.hidden));
    aktifYap(secenekler.length ? 0 : -1);
  }

  kutu.addEventListener("input", function () {
    clearTimeout(zamanlayici);
    const aranan = sonParca();
    if (!aranan) { kapat(); return; }
    zamanlayici = setTimeout(function () {
      if (istek) istek.abort();
      istek = new AbortController();
      fetch(`/api/oneri?turler=BIST,Hisse,Kripto&q=${encodeURIComponent(aranan)}`, { signal: istek.signal })
        .then((c) => c.json())
        .then((veri) => { if (veri.sorgu === sonParca().slice(0, 60)) goster(veri.oneriler); })
        .catch(() => {});
    }, 120);
  });
  kutu.addEventListener("keydown", function (e) {
    if (liste.hidden) return;
    if (e.key === "ArrowDown") { e.preventDefault(); aktifYap((aktif + 1) % secenekler.length); }
    else if (e.key === "ArrowUp") { e.preventDefault(); aktifYap(aktif <= 0 ? secenekler.length - 1 : aktif - 1); }
    else if (e.key === "Enter" && aktif >= 0) { e.preventDefault(); sec(secenekler[aktif]); }
    else if (e.key === "Escape") { kapat(); }
  });
  kutu.addEventListener("blur", () => setTimeout(kapat, 100));
})();
