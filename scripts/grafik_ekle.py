import re

p = "app/static/index.html"
t = open(p, encoding="utf-8-sig").read()
if "function grafikCiz" in t:
    print("Grafik zaten ekli, değişiklik yapılmadı.")
    raise SystemExit

CSS = r'''
  .grafik { margin: 1rem 0; padding: 12px 12px 6px; background: rgba(255, 255, 255, .75); border: 1px solid var(--kare); }
  .grafik svg { display: block; }
  .grafik figcaption { margin-top: 4px; color: var(--soluk); font-size: .85rem; }
  .g-etiket { font: 12px "Recursive", sans-serif; fill: var(--kursun); }
  .g-deger { font: 11px "Recursive", sans-serif; fill: var(--soluk); font-variant-numeric: tabular-nums; }
  .g-cubuk { fill: var(--murekkep); }
  .g-cizgi { fill: none; stroke: var(--murekkep); stroke-width: 2.5; stroke-linejoin: round; stroke-linecap: round; }
  .g-nokta { fill: var(--murekkep); }
  .g-izgara { stroke: var(--kare); stroke-width: 1; }
  .indir {
    margin-top: .7rem; padding: 6px 12px;
    border: 1px solid var(--murekkep); border-radius: 3px;
    background: transparent; color: var(--murekkep);
    font: inherit; font-size: .9rem; cursor: pointer;
  }
  .indir:hover { background: rgba(30, 58, 158, .06); }
'''

JS = r'''
  const SVGNS = "http://www.w3.org/2000/svg";
  function s(etiket, ozellik, metin) {
    const e = document.createElementNS(SVGNS, etiket);
    for (const [k, v] of Object.entries(ozellik || {})) e.setAttribute(k, v);
    if (metin !== undefined) e.textContent = metin;
    return e;
  }

  function cubukGrafik(etiket, deger) {
    if (deger.some(v => v < 0)) return null;
    const G = 720, sol = 190, sag = 90, satirH = 26;
    const H = etiket.length * satirH + 8;
    const max = Math.max(...deger) || 1;
    const svg = s("svg", { viewBox: `0 0 ${G} ${H}`, width: "100%" });
    etiket.forEach((et, i) => {
      const y = 4 + i * satirH;
      const w = (G - sol - sag) * deger[i] / max;
      const kisa = et.length > 24 ? et.slice(0, 23) + "…" : et;
      svg.append(s("text", { x: sol - 10, y: y + 17, "text-anchor": "end", class: "g-etiket" }, kisa));
      svg.append(s("rect", { x: sol, y: y + 4, width: Math.max(w, 1), height: 16, rx: 2, class: "g-cubuk" }));
      svg.append(s("text", { x: sol + w + 8, y: y + 17, class: "g-deger" }, sayiBicim.format(deger[i])));
    });
    return svg;
  }

  function cizgiGrafik(etiket, deger) {
    const G = 720, H = 260, sol = 72, sag = 24, ust = 16, alt = 36;
    const min = Math.min(0, ...deger), max = Math.max(...deger);
    const aralik = (max - min) || 1, n = deger.length;
    const x = i => sol + (G - sol - sag) * (n === 1 ? 0.5 : i / (n - 1));
    const y = v => ust + (H - ust - alt) * (1 - (v - min) / aralik);
    const svg = s("svg", { viewBox: `0 0 ${G} ${H}`, width: "100%" });
    [0, 0.5, 1].forEach(o => {
      const v = min + aralik * o;
      svg.append(s("line", { x1: sol, x2: G - sag, y1: y(v), y2: y(v), class: "g-izgara" }));
      svg.append(s("text", { x: sol - 8, y: y(v) + 4, "text-anchor": "end", class: "g-deger" }, sayiBicim.format(v)));
    });
    svg.append(s("polyline", { points: deger.map((v, i) => `${x(i)},${y(v)}`).join(" "), class: "g-cizgi" }));
    deger.forEach((v, i) => {
      const nokta = s("circle", { cx: x(i), cy: y(v), r: 3.5, class: "g-nokta" });
      nokta.append(s("title", {}, `${etiket[i]}: ${sayiBicim.format(v)}`));
      svg.append(nokta);
    });
    const adim = Math.ceil(n / 6);
    etiket.forEach((et, i) => {
      if (i % adim === 0 || i === n - 1) {
        svg.append(s("text", { x: x(i), y: H - 12, "text-anchor": "middle", class: "g-etiket" }, et.slice(0, 7)));
      }
    });
    return svg;
  }

  function grafikCiz(cevap) {
    const { kolonlar, satirlar } = cevap;
    if (kolonlar.length < 2 || satirlar.length < 2 || satirlar.length > 60) return null;
    const sayisal = kolonlar.map((_, i) => satirlar.every(r => r[i] === null || typeof r[i] === "number"));
    let eI = sayisal.findIndex(v => !v), dI;
    if (eI === -1) { eI = 0; dI = 1; } else { dI = sayisal.findIndex(v => v); }
    if (dI === -1) return null;
    const etiket = satirlar.map(r => bicimle(r[eI]));
    const deger = satirlar.map(r => (typeof r[dI] === "number" ? r[dI] : 0));
    const zaman = satirlar.every(r => typeof r[eI] === "string" && /^\d{4}-\d{2}/.test(r[eI]));
    const svg = zaman ? cizgiGrafik(etiket, deger) : cubukGrafik(etiket, deger);
    if (!svg) return null;
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", `${kolonlar[dI]} grafiği`);
    const kap = el("figure", "grafik");
    kap.append(svg);
    kap.append(el("figcaption", null, `${kolonlar[dI]}, ${kolonlar[eI]} bazında`));
    return kap;
  }

  function csvIndir(cevap) {
    const hucre = v => {
      if (v === null || v === undefined) return "";
      if (typeof v === "number") return String(v).replace(".", ",");
      const t = String(v);
      return /[;"\n]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t;
    };
    const satirlar = [cevap.kolonlar, ...cevap.satirlar].map(r => r.map(hucre).join(";"));
    const blob = new Blob(["\ufeff" + satirlar.join("\r\n")], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "verisor_" + cevap.soru.toLocaleLowerCase("tr").replace(/[^a-z0-9çğıöşü]+/g, "_").slice(0, 40) + ".csv";
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  function indirmeDugmesi(cevap) {
    const b = el("button", "indir", "Excel için indir (CSV)");
    b.type = "button";
    b.addEventListener("click", () => csvIndir(cevap));
    return b;
  }
'''

CAGRI = r'''kap.append(tablo);
      const grafik = grafikCiz(cevap);
      if (grafik) kayit.append(grafik);
      kayit.append(kap);
      kayit.append(indirmeDugmesi(cevap));'''

once = len(t)
t = t.replace("</style>", CSS + "</style>", 1)
print("Stiller eklendi:", len(t) > once)

once = len(t)
t = t.replace("function sonucuYaz(", JS + "\n  function sonucuYaz(", 1)
print("Fonksiyonlar eklendi:", len(t) > once)

t, n = re.subn(r"kap\.append\(tablo\);\s*kayit\.append\(kap\);", lambda m: CAGRI, t, count=1)
print("Tabloya baglandi:", n == 1)

open(p, "w", encoding="utf-8").write(t)
print("Kaydedildi.")