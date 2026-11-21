# ---------- 1) verisor/ajan.py ----------
p = "verisor/ajan.py"
t = open(p, encoding="utf-8-sig").read()
if "def sql_dene" in t:
    print("ajan.py zaten güncel.")
else:
    eski = '''                if k["dogru"] and k.get("sql"):
                    onaylar[a] = {"soru": k["soru"], "sql": k["sql"], "kaynak": "onay"}'''
    yeni = '''                if k.get("duzeltilmis_sql"):
                    onaylar[a] = {"soru": k["soru"], "sql": k["duzeltilmis_sql"], "kaynak": "onay"}
                elif k["dogru"] and k.get("sql"):
                    onaylar[a] = {"soru": k["soru"], "sql": k["sql"], "kaynak": "onay"}'''
    print("ajan.py, duzeltmeleri yukleme:", t.count(eski) == 1)
    t = t.replace(eski, yeni)

    eski = "    def sor(self, soru, k=3, max_deneme=2):"
    yeni = '''    def sql_dene(self, sql):
        """Analistin yazdığı SQL'i modelinkiyle aynı iki güvenlik katmanından geçirerek çalıştırır."""
        sql = sql.strip().rstrip(";").strip() + ";"
        with self.engine.connect() as conn:
            kolonlar, satirlar, hata = self._calistir(conn, sql)
        satirlar = satirlar or []
        return {
            "sql": sql,
            "hata": hata,
            "kolonlar": kolonlar or [],
            "satirlar": [[jsonla(v) for v in r] for r in satirlar[:MAX_SATIR]],
            "kesildi": len(satirlar) > MAX_SATIR,
        }

''' + eski
    print("ajan.py, sql_dene eklendi:", t.count(eski) == 1)
    t = t.replace(eski, yeni)
    open(p, "w", encoding="utf-8").write(t)

# ---------- 2) app/static/index.html ----------
p = "app/static/index.html"
t = open(p, encoding="utf-8-sig").read()
if "function onizleme" in t:
    print("index.html zaten güncel.")
    raise SystemExit

CSS = r'''
  .duzelt { margin-top: 1.1rem; }
  .duzelt label { display: block; margin-bottom: .4rem; color: var(--soluk); font-size: .95rem; }
  .duzelt textarea {
    width: 100%; padding: 10px 12px;
    border: 1px solid var(--kare); border-left: 3px solid var(--murekkep);
    background: #fff; color: var(--kursun);
    font-family: inherit; font-variation-settings: "CASL" 0, "MONO" 1;
    font-size: .86rem; line-height: 1.45; resize: vertical;
  }
  .duzelt .degerlendir { margin-top: .6rem; }
  .onizleme { margin-top: .8rem; }
  p.karar { margin: 1.1rem 0 0; }
'''

JS = r'''  const KARAR_DUZELTME = {
    eklendi: "✓ Düzeltme kaydedildi. Bu soru ve benzerleri artık düzeltilmiş SQL'den örnek alacak.",
    guncellendi: "✓ Düzeltme kaydedildi. Bu sorunun örneği düzeltilmiş SQL ile güncellendi.",
    golden_degismez: "Düzeltme kaydedildi. Bu soru doğrulanmış örnekler arasında olduğu için havuz değişmedi.",
  };

  function dugme(metin) {
    const b = el("button", "secim", metin);
    b.type = "button";
    return b;
  }

  async function postJson(url, govde) {
    const y = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(govde),
    });
    const j = await y.json();
    if (!y.ok) throw new Error(typeof j.detail === "string" ? j.detail : `HTTP ${y.status}`);
    return j;
  }

  function onizleme(sonuc) {
    const kap = el("div", "onizleme");
    if (sonuc.hata) { kap.append(el("p", "hata", "Çalışmadı: " + sonuc.hata)); return kap; }
    if (!sonuc.satirlar.length) { kap.append(el("p", "not", "Sorgu çalıştı ama sonuç boş.")); return kap; }
    const tablo = el("table");
    const bas = el("tr");
    sonuc.kolonlar.forEach(k => bas.append(el("th", null, k)));
    const thead = el("thead"); thead.append(bas); tablo.append(thead);
    const govde = el("tbody");
    sonuc.satirlar.slice(0, 10).forEach(r => {
      const tr = el("tr");
      r.forEach(v => tr.append(el("td", typeof v === "number" ? "sayi" : null, bicimle(v))));
      govde.append(tr);
    });
    tablo.append(govde);
    const tk = el("div", "tablo-kap"); tk.append(tablo); kap.append(tk);
    if (sonuc.satirlar.length > 10) {
      kap.append(el("p", "not", `İlk 10 satır gösteriliyor (toplam ${sonuc.satirlar.length}${sonuc.kesildi ? "+" : ""}).`));
    }
    return kap;
  }

  function degerlendirme(cevap) {
    const kutu = el("div", "degerlendir-kap");
    if (!cevap.id) return kutu;
    const satir = el("div", "degerlendir");
    satir.append(el("span", null, "Bu cevap doğru mu?"));
    const dogruB = dugme("Doğru"), yanlisB = dugme("Yanlış");
    if (!cevap.hata) satir.append(dogruB);
    satir.append(yanlisB);
    kutu.append(satir);

    let sorun = null;
    const sorunYaz = (yer, metin) => {
      if (sorun) sorun.remove();
      sorun = el("p", "karar sorun", metin);
      yer.append(sorun);
    };
    const bitir = (metin, sinif) => {
      kutu.replaceChildren(el("p", "karar " + sinif, metin));
      havuzGuncelle();
    };

    dogruB.addEventListener("click", async () => {
      dogruB.disabled = yanlisB.disabled = true;
      try {
        const j = await postJson("/feedback", { id: cevap.id, dogru: true });
        bitir(KARAR_METNI[j.havuz] || KARAR_METNI.eklendi, "onay");
      } catch (e) {
        dogruB.disabled = yanlisB.disabled = false;
        sorunYaz(kutu, "Kaydedilemedi: " + e.message);
      }
    });

    yanlisB.addEventListener("click", () => {
      satir.hidden = true;
      const panel = el("div", "duzelt");
      const etiket = el("label", null, "Doğru SQL'i yaz ya da modelin SQL'ini düzelt:");
      const alan = el("textarea");
      alan.id = "duzelt-" + cevap.id;
      etiket.htmlFor = alan.id;
      alan.spellcheck = false;
      alan.value = cevap.sql || "";
      alan.rows = Math.min(14, Math.max(5, alan.value.split("\n").length + 1));
      const calistirB = dugme("Çalıştır");
      const kaydetB = dugme("Düzeltilmiş hâliyle kaydet");
      const sadeceB = dugme("Düzeltmeden yanlış olarak kaydet");
      const vazgecB = dugme("Vazgeç");
      kaydetB.disabled = true;
      const dugmeler = el("div", "degerlendir");
      dugmeler.append(calistirB, kaydetB, sadeceB, vazgecB);
      const sonucYeri = el("div");
      panel.append(etiket, alan, dugmeler, sonucYeri);
      kutu.append(panel);
      alan.focus();

      // Kaydedilen SQL her zaman sonucu görülmüş SQL olsun.
      let denenen = null;
      alan.addEventListener("input", () => { kaydetB.disabled = alan.value !== denenen; });

      calistirB.addEventListener("click", async () => {
        calistirB.disabled = true;
        calistirB.textContent = "Çalışıyor…";
        try {
          const s = await postJson("/dene", { sql: alan.value });
          sonucYeri.replaceChildren(onizleme(s));
          denenen = s.hata ? null : alan.value;
          kaydetB.disabled = denenen === null;
        } catch (e) {
          sonucYeri.replaceChildren(el("p", "hata", "Çalıştırılamadı: " + e.message));
        } finally {
          calistirB.disabled = false;
          calistirB.textContent = "Çalıştır";
        }
      });

      kaydetB.addEventListener("click", async () => {
        kaydetB.disabled = sadeceB.disabled = true;
        try {
          const j = await postJson("/feedback", { id: cevap.id, dogru: false, duzeltilmis_sql: alan.value });
          bitir(KARAR_DUZELTME[j.havuz] || KARAR_DUZELTME.eklendi, "onay");
        } catch (e) {
          kaydetB.disabled = sadeceB.disabled = false;
          sorunYaz(panel, "Kaydedilemedi: " + e.message);
        }
      });

      sadeceB.addEventListener("click", async () => {
        kaydetB.disabled = sadeceB.disabled = true;
        try {
          const j = await postJson("/feedback", { id: cevap.id, dogru: false });
          bitir(KARAR_METNI[j.havuz] || "Not edildi. Bu cevap örnek olarak kullanılmayacak.", "ret");
        } catch (e) {
          sadeceB.disabled = false;
          kaydetB.disabled = alan.value !== denenen;
          sorunYaz(panel, "Kaydedilemedi: " + e.message);
        }
      });

      vazgecB.addEventListener("click", () => {
        panel.remove();
        if (sorun) { sorun.remove(); sorun = null; }
        satir.hidden = false;
        yanlisB.focus();
      });
    });
    return kutu;
  }
'''

bas = t.find("  function degerlendirme(cevap) {")
son_isaret = "    return kutu;\n  }\n"
son = t.find(son_isaret, bas)
print("index.html, eski fonksiyon bulundu:", bas != -1 and son != -1)
if bas != -1 and son != -1:
    t = t[:bas] + JS + t[son + len(son_isaret):]
    print("index.html, stiller:", t.count("</style>") == 1)
    t = t.replace("</style>", CSS + "</style>", 1)
    open(p, "w", encoding="utf-8").write(t)
    print("Kaydedildi.")