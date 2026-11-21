p = "app/static/index.html"
t = open(p, encoding="utf-8-sig").read()
if "function degerlendirme" in t:
    print("Düğmeler zaten ekli, değişiklik yapılmadı.")
    raise SystemExit

CSS = r'''
  .havuz { margin: .6rem 0 0; color: var(--soluk); font-size: .85rem; }
  .degerlendir {
    display: flex; flex-wrap: wrap; align-items: center; gap: 10px;
    margin-top: 1.1rem; color: var(--soluk); font-size: .95rem;
  }
  .secim {
    padding: 4px 16px;
    border: 1px solid var(--kursun); border-radius: 3px;
    background: transparent; color: var(--kursun);
    font: inherit; cursor: pointer;
  }
  .secim:hover { border-color: var(--murekkep); color: var(--murekkep); }
  .secim:disabled { opacity: .5; cursor: wait; }
  .karar { font-variation-settings: "CASL" 1, "MONO" 0; }
  .karar.onay { color: var(--murekkep); }
  .karar.ret { color: var(--kursun); }
  .karar.sorun { color: var(--kirmizi); }
'''

JS = r'''
  async function havuzGuncelle() {
    const yer = document.getElementById("havuz");
    try {
      const h = (await (await fetch("/health")).json()).havuz;
      if (!h) return;
      yer.textContent = `Örnek havuzu: ${h.golden} doğrulanmış soru, ${h.onayli} onaylı cevap.`;
    } catch (e) {
      yer.textContent = "";
    }
  }

  const KARAR_METNI = {
    eklendi: "✓ Onaylandı. Benzer sorularda örnek olarak kullanılacak.",
    guncellendi: "✓ Onaylandı. Bu sorunun örneği yeni SQL ile güncellendi.",
    golden_degismez: "✓ Onaylandı. Bu soru zaten doğrulanmış örnekler arasında.",
    cikarildi: "Not edildi. Daha önce onaylanan örnek havuzdan çıkarıldı.",
  };

  function degerlendirme(cevap) {
    const kutu = el("div", "degerlendir");
    if (!cevap.id) return kutu;
    kutu.append(el("span", null, "Bu cevap doğru mu?"));
    const dogruB = el("button", "secim", "Doğru");
    const yanlisB = el("button", "secim", "Yanlış");
    dogruB.type = yanlisB.type = "button";
    if (!cevap.hata) kutu.append(dogruB);
    kutu.append(yanlisB);
    let sorun = null;

    async function gonderKarar(dogru) {
      dogruB.disabled = yanlisB.disabled = true;
      try {
        const y = await fetch("/feedback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: cevap.id, dogru }),
        });
        const j = await y.json();
        if (!y.ok) throw new Error(j.detail || `HTTP ${y.status}`);
        const metin = KARAR_METNI[j.havuz] ||
          (dogru ? KARAR_METNI.eklendi : "Not edildi. Bu cevap örnek olarak kullanılmayacak.");
        kutu.replaceChildren(el("span", dogru ? "karar onay" : "karar ret", metin));
        havuzGuncelle();
      } catch (e) {
        dogruB.disabled = yanlisB.disabled = false;
        if (sorun) sorun.remove();
        sorun = el("span", "karar sorun", "Kaydedilemedi: " + e.message);
        kutu.append(sorun);
      }
    }

    dogruB.addEventListener("click", () => gonderKarar(true));
    yanlisB.addEventListener("click", () => gonderKarar(false));
    return kutu;
  }
'''

def degistir(eski, yeni, ad):
    global t
    adet = t.count(eski)
    if adet == 1:
        t = t.replace(eski, yeni)
    print(f"{ad}: {adet == 1}")

degistir("</style>", CSS + "</style>", "Stiller")
degistir("  </header>", '    <p class="havuz" id="havuz"></p>\n  </header>', "Havuz sayaci")
degistir("  function sonucuYaz(", JS + "\n  function sonucuYaz(", "Fonksiyonlar")
degistir("    kayit.append(nasilHesaplandi(cevap));",
         "    kayit.append(degerlendirme(cevap));\n    kayit.append(nasilHesaplandi(cevap));",
         "Dugmeler cevaba baglandi")
degistir('      d.append(el("p", "not", "Model şu benzer sorulardan yararlandı:"));',
         '      const onay = cevap.onayli_ornek_sayisi ? ` (${cevap.onayli_ornek_sayisi} tanesi senin onayladığın cevaplardan)` : "";\n'
         '      d.append(el("p", "not", "Model şu benzer sorulardan yararlandı" + onay + ":"));',
         "Onayli ornek notu")
degistir("  girdi.focus();", "  havuzGuncelle();\n  girdi.focus();", "Sayac acilista")

open(p, "w", encoding="utf-8").write(t)
print("Kaydedildi.")