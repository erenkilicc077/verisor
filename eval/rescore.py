import sys, glob, json, decimal, datetime
from collections import defaultdict
import yaml
from baseline import engine, normalize


def deger(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float, decimal.Decimal)):
        return round(float(v), 2)
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()
    return v


def esnek_esit(altin_rows, tahmin_rows):
    A = [tuple(deger(v) for v in r) for r in altin_rows]
    T = [tuple(deger(v) for v in r) for r in tahmin_rows]
    if len(A) == 1 and len(T) > 1:
        T = T[:1]
    if not A or len(A) != len(T):
        return False

    def kolonlar(rows):
        return [sorted(map(repr, kolon)) for kolon in zip(*rows)]

    a_kol, t_kol = kolonlar(A), kolonlar(T)
    sayisal = [i for i, v in enumerate(A[0]) if isinstance(v, float)]
    hedef = sayisal or range(len(a_kol))
    return all(a_kol[i] in t_kol for i in hedef)


def main():
    desen = sys.argv[1] if len(sys.argv) > 1 else "b3_ajan_v1"
    dosya = sorted(glob.glob(f"eval/results/{desen}_*.json"))[-1]
    veri = json.load(open(dosya, encoding="utf-8"))
    altinlar = {q["id"]: q for q in yaml.safe_load(open("eval/golden.yaml", encoding="utf-8-sig"))}

    skor = defaultdict(lambda: [0, 0, 0])
    affedilen = []
    with engine.connect() as conn:
        for r in veri["sonuclar"]:
            sql = r["adimlar"][-1]["sql"] if r.get("adimlar") else r.get("tahmin_sql")
            altin = conn.exec_driver_sql(altinlar[r["id"]]["sql"]).fetchall()
            try:
                tahmin = conn.exec_driver_sql(sql).fetchall()
            except Exception:
                conn.rollback()
                tahmin = None
            katı = tahmin is not None and normalize(tahmin) == normalize(altin)
            esnek = katı or (tahmin is not None and esnek_esit(altin, tahmin))
            if esnek and not katı:
                affedilen.append(r["id"])
            for anahtar in (r["tur"], "TOPLAM"):
                skor[anahtar][0] += katı
                skor[anahtar][1] += esnek
                skor[anahtar][2] += 1

    print(f"Dosya: {dosya}\n")
    print(f"{'tur':<12}{'kati':>8}{'esnek':>8}")
    for tur in sorted(k for k in skor if k != "TOPLAM") + ["TOPLAM"]:
        k, e, n = skor[tur]
        print(f"{tur:<12}{f'{k}/{n}':>8}{f'{e}/{n}':>8}")
    k, e, n = skor["TOPLAM"]
    print(f"\nKati: %{100*k/n:.0f}  Esnek: %{100*e/n:.0f}")
    print("Bicim farki affedilen:", ", ".join(affedilen) or "-")


if __name__ == "__main__":
    main()
