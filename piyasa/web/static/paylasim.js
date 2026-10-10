// Paylaşım kartları: SVG kartı PNG olarak indir, metni kopyala, X'te aç, paylaşıldı olarak işaretle.
(function () {
  "use strict";

  // X bağlantıları 23 karakter sayar
  const uzunluk = (m) => m.replace(/\S+\.(com|org|net)\S*/g, "x".repeat(23)).length;

  function pngIndir(svg, dosya) {
    const veri = new XMLSerializer().serializeToString(svg);
    const resim = new Image();
    resim.onload = function () {
      const tuval = document.createElement("canvas");
      tuval.width = 2400;            // 2× çözünürlük: X'te net görünsün
      tuval.height = 1350;
      const c = tuval.getContext("2d");
      c.drawImage(resim, 0, 0, tuval.width, tuval.height);
      tuval.toBlob(function (blob) {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `piyasakaydi-${dosya}.png`;
        a.click();
        setTimeout(() => URL.revokeObjectURL(a.href), 2000);
      }, "image/png");
    };
    resim.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(veri);
  }

  function isaretle(kart, durum) {
    return fetch("/paylasim/isaretle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ anahtar: kart.dataset.anahtar, durum, metin: kart.querySelector("textarea").value }),
    }).then((c) => {
      if (!c.ok) throw new Error(c.status);
      kart.classList.add("paylasim-bitti");
      setTimeout(() => kart.remove(), 400);
    });
  }

  document.querySelectorAll(".paylasim-kart").forEach(function (kart) {
    const metin = kart.querySelector("textarea");
    const sayac = kart.querySelector(".paylasim-sayac");
    const say = () => { const n = uzunluk(metin.value); sayac.textContent = `${n} karakter`; sayac.classList.toggle("tutar-sell", n > 280); };
    metin.addEventListener("input", say);
    say();
    kart.addEventListener("click", function (olay) {
      const dugme = olay.target.closest("[data-islem]");
      if (!dugme) return;
      const islem = dugme.dataset.islem;
      if (islem === "indir") pngIndir(kart.querySelector("svg"), kart.dataset.dosya);
      else if (islem === "kopyala") navigator.clipboard.writeText(metin.value).then(() => {
        dugme.textContent = "Kopyalandı"; setTimeout(() => (dugme.textContent = "Metni kopyala"), 1500);
      });
      else if (islem === "x") window.open("https://x.com/intent/post?text=" + encodeURIComponent(metin.value), "_blank", "noopener");
      else if (islem === "paylasildi") isaretle(kart, "elle");
      else if (islem === "atla") isaretle(kart, "atlandi");
    });
  });
})();
