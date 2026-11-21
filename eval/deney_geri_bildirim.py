"""Deney B7: Geri bildirim döngüsü başarıyı artırıyor mu?

Test seti (belirsizler hariç) ikiye bölünür: A ve B.
Bir yarı "kullanım" yarısıdır: ajan cevaplar, kullanıcı doğru olanları onaylar
(kullanıcıyı altın SQL ile karşılaştırarak simüle ediyoruz). Onaylananlar havuza girer,
diğer yarı ölçülür. Sonra yarılar yer değiştirir. Hiçbir soru kendi cevabını havuzda görmez.

Koşullar:
  temel    : havuz = geliştirme seti
  onay     : + diğer yarıda doğru çıkan model cevapları
  duzeltme : + diğer yarının altın SQL'leri (analist yanlışları da düzeltirse; üst sınır)
"""
import sys, json, time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import yaml
from verisor.ajan import Ajan, jsonla


def deger(v):
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    return "" if v is None else str(v)


def normal(rows):
    return sorted((tuple(deger(v) for v in r) for r in rows), key=repr)


def kati(altin, tahmin):
    return normal(altin) == normal(tahmin)


def esnek(altin, tahmin):
    """Altın cevaptaki sayılar tahminde varsa doğru sayar (fazladan kolon serbest)."""
    if kati(altin, tahmin):
        return True
    if not altin or not tahmin:
        return False
    A = normal(altin)
    if len(A) == 1:
        ilk = [deger(v) for v in tahmin[0]]
        sayilar = [v for v in A[0] if isinstance(v, float)]
        hedef = sayilar or list(A[0])
        return all(v in ilk for v in hedef)
    T = normal(tahmin)
    if len(A) != len(T):
        return False
    tahmin_kolonlari = [sorted(k, key=repr) for k in zip(*T)]
    eslesen = 0
    for kolon in zip(*A):
        if all(isinstance(v, float) for v in kolon):
            if sorted(kolon, key=repr) not in tahmin_kolonlari:
                return False
            eslesen += 1
    return eslesen > 0


def main():
    bas = time.time()
    ajan = Ajan()
    tum = yaml.safe_load(open("eval/golden.yaml", encoding="utf-8-sig"))
    dev = [{"soru": q["soru"], "sql": q["sql"], "kaynak": "golden"}
           for q in tum if q.get("sql") and q.get("set", "dev") == "dev"]
    test = [q for q in tum if q.get("set") == "test" and q.get("sql")]
    katlar = {"A": test[0::2], "B": test[1::2]}
    dev_v = ajan._vektor([q["soru"] for q in dev])
    print(f"Geliştirme havuzu: {len(dev)} | Test: {len(test)} (A={len(katlar['A'])}, B={len(katlar['B'])})")

    altin = {}
    with ajan.engine.connect() as conn:
        for q in test:
            altin[q["id"]] = [[jsonla(v) for v in r] for r in conn.exec_driver_sql(q["sql"]).fetchall()]

    def havuz_kur(ekler):
        # Sunucudaki gerçek onaylar (kayitlar.jsonl) bu deneye karışmaz: havuzu sıfırdan kuruyoruz.
        ajan.havuz = dev + ekler
        ajan.havuz_v = np.vstack([dev_v, ajan._vektor([e["soru"] for e in ekler])]) if ekler else dev_v

    def calistir(sorular, kosul):
        sonuc = []
        for i, q in enumerate(sorular, 1):
            c = ajan.sor(q["soru"])
            tahmin = c["satirlar"]
            s = {
                "id": q["id"], "soru": q["soru"], "tip": q.get("tip"), "kosul": kosul,
                "sql": c["sql"], "hata": c["hata"],
                "kati": not c["hata"] and kati(altin[q["id"]], tahmin),
                "esnek": not c["hata"] and esnek(altin[q["id"]], tahmin),
                "eklenen_ornek_kullanildi": c["onayli_ornek_sayisi"],
            }
            print(f"  [{kosul}] {i}/{len(sorular)} {q['id']}  katı={s['kati']!s:5}  esnek={s['esnek']}", flush=True)
            sonuc.append(s)
        return sonuc

    print("\n1/3 temel (yalnızca geliştirme havuzu)")
    havuz_kur([])
    temel = calistir(test, "temel")
    temel_id = {s["id"]: s for s in temel}

    onay, duzeltme = [], []
    for hedef, kaynak in (("B", "A"), ("A", "B")):
        ekler = [{"soru": q["soru"], "sql": temel_id[q["id"]]["sql"], "kaynak": "onay"}
                 for q in katlar[kaynak] if temel_id[q["id"]]["esnek"]]
        print(f"\n2/3 onay: {kaynak} yarısından {len(ekler)} onaylı cevap eklendi, {hedef} ölçülüyor")
        havuz_kur(ekler)
        onay += calistir(katlar[hedef], "onay")

        ekler = [{"soru": q["soru"], "sql": q["sql"], "kaynak": "onay"} for q in katlar[kaynak]]
        print(f"\n3/3 duzeltme: {kaynak} yarısının {len(ekler)} altın SQL'i eklendi, {hedef} ölçülüyor")
        havuz_kur(ekler)
        duzeltme += calistir(katlar[hedef], "duzeltme")

    print("\n================ SONUÇ (test, n=%d) ================" % len(test))
    print(f"{'koşul':10} {'katı':>12} {'esnek':>12} {'ek örnek kullanan':>18}")
    ozet = {}
    for ad, liste in (("temel", temel), ("onay", onay), ("duzeltme", duzeltme)):
        k = sum(s["kati"] for s in liste)
        e = sum(s["esnek"] for s in liste)
        kullanan = sum(s["eklenen_ornek_kullanildi"] > 0 for s in liste)
        ozet[ad] = {"kati": k, "esnek": e, "n": len(liste), "ek_ornek_kullanan": kullanan}
        print(f"{ad:10} {k:>4}/{len(liste)} %{100*k/len(liste):4.0f} {e:>4}/{len(liste)} %{100*e/len(liste):4.0f} {kullanan:>18}")

    for ad, liste in (("onay", onay), ("duzeltme", duzeltme)):
        kazanilan = [s["id"] for s in liste if s["esnek"] and not temel_id[s["id"]]["esnek"]]
        kaybedilen = [s["id"] for s in liste if not s["esnek"] and temel_id[s["id"]]["esnek"]]
        ozet[ad]["kazanilan"], ozet[ad]["kaybedilen"] = kazanilan, kaybedilen
        print(f"\n{ad}: yanlıştan doğruya {len(kazanilan)} {kazanilan}")
        print(f"{ad}: doğrudan yanlışa {len(kaybedilen)} {kaybedilen}")

    Path("eval/results").mkdir(parents=True, exist_ok=True)
    dosya = f"eval/results/b7_geri_bildirim_{datetime.now():%Y%m%d_%H%M}.json"
    with open(dosya, "w", encoding="utf-8") as f:
        json.dump({"ozet": ozet, "temel": temel, "onay": onay, "duzeltme": duzeltme},
                  f, ensure_ascii=False, indent=2)
    print(f"\nKaydedildi: {dosya}  ({(time.time() - bas) / 60:.1f} dk)")


if __name__ == "__main__":
    main()