"""Deney B8: Daha önce onaylanan bir soru farklı kelimelerle sorulunca ajan daha iyi cevaplıyor mu?

eval/paraphrase.yaml: test sorularının elle yeniden yazılmış hâlleri (aynı anlam, aynı altın SQL).
Asıl sorunun havuzda olması bilinçlidir; ölçülen senaryo "bu soru daha önce soruldu" senaryosudur.

Koşullar (hepsi yeniden yazılmış sorular üzerinde):
  temel    : havuz = geliştirme seti
  onay     : + test sorularından B7 temel koşulunda doğru çıkıp onaylanan model cevapları
  duzeltme : + tüm test sorularının altın SQL'leri
"""
import sys, json, glob, time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import yaml
from verisor.ajan import Ajan, jsonla
from deney_geri_bildirim import kati, esnek


def main():
    bas = time.time()
    b7_dosya = sorted(glob.glob("eval/results/b7_geri_bildirim_*.json"))[-1]
    b7 = json.load(open(b7_dosya, encoding="utf-8"))
    asil_sonuc = {s["id"]: s for s in b7["temel"]}

    tum = yaml.safe_load(open("eval/golden.yaml", encoding="utf-8-sig"))
    test = {q["id"]: q for q in tum if q.get("set") == "test" and q.get("sql")}
    para = yaml.safe_load(open("eval/paraphrase.yaml", encoding="utf-8-sig"))

    eksik = [p["asil"] for p in para if p["asil"] not in test]
    if eksik:
        print("Bu asil id'ler test setinde yok ya da belirsiz soru:", eksik)
        return
    print(f"{len(para)} yeniden yazılmış soru | B7 dosyası: {b7_dosya}")

    ajan = Ajan()
    dev = [{"soru": q["soru"], "sql": q["sql"], "kaynak": "golden"}
           for q in tum if q.get("sql") and q.get("set", "dev") == "dev"]
    dev_v = ajan._vektor([q["soru"] for q in dev])

    altin = {}
    with ajan.engine.connect() as conn:
        for p in para:
            rows = conn.exec_driver_sql(test[p["asil"]]["sql"]).fetchall()
            altin[p["id"]] = [[jsonla(v) for v in r] for r in rows]

    def havuz_kur(ekler):
        ajan.havuz = dev + ekler
        ajan.havuz_v = np.vstack([dev_v, ajan._vektor([e["soru"] for e in ekler])]) if ekler else dev_v

    def calistir(kosul):
        sonuc = []
        for i, p in enumerate(para, 1):
            c = ajan.sor(p["soru"])
            s = {
                "id": p["id"], "asil": p["asil"], "soru": p["soru"], "kosul": kosul,
                "sql": c["sql"], "hata": c["hata"],
                "kati": not c["hata"] and kati(altin[p["id"]], c["satirlar"]),
                "esnek": not c["hata"] and esnek(altin[p["id"]], c["satirlar"]),
                "asil_dogruydu": asil_sonuc[p["asil"]]["esnek"],
                "asil_bulundu": test[p["asil"]]["soru"] in c["benzer_ornekler"],
            }
            print(f"  [{kosul}] {i}/{len(para)} {p['id']}({p['asil']})  esnek={s['esnek']!s:5}  "
                  f"asıl bulundu={s['asil_bulundu']}", flush=True)
            sonuc.append(s)
        return sonuc

    onaylar = [{"soru": s["soru"], "sql": s["sql"], "kaynak": "onay"} for s in b7["temel"] if s["esnek"]]
    duzeltmeler = [{"soru": q["soru"], "sql": q["sql"], "kaynak": "onay"} for q in test.values()]

    sonuclar = {}
    for ad, ekler in (("temel", []), ("onay", onaylar), ("duzeltme", duzeltmeler)):
        print(f"\n{ad}: havuza {len(ekler)} örnek eklendi")
        havuz_kur(ekler)
        sonuclar[ad] = calistir(ad)

    n = len(para)
    print(f"\n================ SONUÇ (yeniden yazılmış sorular, n={n}) ================")
    print(f"{'koşul':10} {'katı':>10} {'esnek':>10} {'asıl soru bulundu':>18}")
    ozet = {}
    for ad, liste in sonuclar.items():
        k = sum(s["kati"] for s in liste)
        e = sum(s["esnek"] for s in liste)
        b = sum(s["asil_bulundu"] for s in liste)
        ozet[ad] = {"kati": k, "esnek": e, "asil_bulundu": b, "n": n}
        print(f"{ad:10} {k:>4}/{n} %{100*k/n:3.0f} {e:>4}/{n} %{100*e/n:3.0f} {b:>14}/{n}")

    print("\nAsıl sorunun B7'deki durumuna göre (esnek doğru):")
    for grup, deger in (("asıl DOĞRU idi", True), ("asıl YANLIŞ idi", False)):
        satir = []
        for ad, liste in sonuclar.items():
            alt = [s for s in liste if s["asil_dogruydu"] == deger]
            satir.append(f"{ad} {sum(s['esnek'] for s in alt)}/{len(alt)}")
        print(f"  {grup:16} " + "   ".join(satir))

    temel_id = {s["id"]: s for s in sonuclar["temel"]}
    for ad in ("onay", "duzeltme"):
        kaz = [s["id"] for s in sonuclar[ad] if s["esnek"] and not temel_id[s["id"]]["esnek"]]
        kay = [s["id"] for s in sonuclar[ad] if not s["esnek"] and temel_id[s["id"]]["esnek"]]
        ozet[ad]["kazanilan"], ozet[ad]["kaybedilen"] = kaz, kay
        print(f"\n{ad}: yanlıştan doğruya {len(kaz)} {kaz}")
        print(f"{ad}: doğrudan yanlışa {len(kay)} {kay}")

    Path("eval/results").mkdir(parents=True, exist_ok=True)
    dosya = f"eval/results/b8_tekrar_{datetime.now():%Y%m%d_%H%M}.json"
    with open(dosya, "w", encoding="utf-8") as f:
        json.dump({"ozet": ozet, **sonuclar}, f, ensure_ascii=False, indent=2)
    print(f"\nKaydedildi: {dosya}  ({(time.time() - bas) / 60:.1f} dk)")


if __name__ == "__main__":
    main()