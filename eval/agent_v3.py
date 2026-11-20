import os, json, time, datetime, argparse
from collections import defaultdict
import numpy as np
import yaml, ollama
from baseline import MODEL, engine, SISTEM, SOZLUK_BASLIK, sema_metni, sql_cikar, normalize
from agent_v1 import calistir
from agent_v2 import geri_bildirim, MAX_DENEME

EMB_MODEL = os.getenv("EMB_MODEL", "embeddinggemma:300m")


def vektor(metinler):
    v = np.array(ollama.embed(model=EMB_MODEL, input=metinler)["embeddings"], dtype=float)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def ornek_metni(ornekler):
    parcalar = ["\nBenzer sorular ve doğru SQL'leri (yalnızca yöntem için örnek; yeni soruyu kendi şartlarına göre çöz):"]
    for o in ornekler:
        parcalar.append(f"Soru: {o['soru']}\n```sql\n{o['sql'].strip()}\n```")
    return "\n\n".join(parcalar)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=3, help="Kaç örnek eklensin")
    ap.add_argument("--dongu", action="store_true", help="Hata geri bildirim döngüsünü aç")
    args = ap.parse_args()
    deney = "b6_ornek_dongu" if args.dongu else "b5_ornek"
    max_deneme = MAX_DENEME if args.dongu else 1

    tum = yaml.safe_load(open("eval/golden.yaml", encoding="utf-8-sig"))
    havuz = [q for q in tum if q.get("sql") and q.get("set", "dev") == "dev"]
    sorular = [q for q in tum if q.get("sql") and q.get("set", "dev") == os.getenv("SET", "dev")]

    havuz_v = vektor([q["soru"] for q in havuz])
    soru_v = vektor([q["soru"] for q in sorular])
    sozluk = SOZLUK_BASLIK + open("semantic.yaml", encoding="utf-8-sig").read()
    sonuclar, tur_skor = [], defaultdict(lambda: [0, 0])

    with engine.connect() as conn:
        sema = sema_metni(conn)
        for i, q in enumerate(sorular):
            benzerlik = havuz_v @ soru_v[i]
            # Sızıntı önlemi: sorunun kendisi örnek olarak kullanılmaz.
            sira = [j for j in np.argsort(-benzerlik) if havuz[j]["id"] != q["id"]][: args.k]
            ornekler = [havuz[j] for j in sira]
            sistem = SISTEM.format(sema=sema, sozluk=sozluk) + ornek_metni(ornekler)

            altin = normalize(conn.exec_driver_sql(q["sql"]).fetchall())
            mesajlar = [{"role": "system", "content": sistem}, {"role": "user", "content": q["soru"]}]
            adimlar, onceki, rows, bas = [], [], None, time.time()

            for deneme in range(max_deneme):
                cevap = ollama.chat(model=MODEL, messages=mesajlar,
                                    options={"temperature": 0, "seed": 42}, think=False)
                icerik = cevap["message"]["content"]
                sql = sql_cikar(icerik)
                rows, hata = calistir(conn, sql)
                geri = geri_bildirim(q["soru"], sql, rows, hata, onceki) if args.dongu else None
                adimlar.append({"sql": sql, "hata": hata, "satir": None if rows is None else len(rows)})
                onceki.append(sql)
                if geri is None:
                    break
                mesajlar += [{"role": "assistant", "content": icerik}, {"role": "user", "content": geri}]

            # Altın cevap sadece puanlamada kullanılır; ajan onu hiç görmez.
            dogru = rows is not None and len(rows) > 0 and normalize(rows) == altin
            sure = round(time.time() - bas, 1)
            tur_skor[q["tur"]][0] += dogru
            tur_skor[q["tur"]][1] += 1
            ids = [o["id"] for o in ornekler]
            sonuclar.append({"id": q["id"], "tur": q["tur"], "dogru": dogru, "deneme": len(adimlar),
                             "sure_sn": sure, "ornekler": ids, "adimlar": adimlar})
            print(f"{'✓' if dogru else '✗'} {q['id']} [{q['tur']}] ornekler={ids} {sure}s")

    toplam = sum(r["dogru"] for r in sonuclar)
    print(f"\n[{deney}] Doğruluk (katı): {toplam}/{len(sonuclar)} = %{100 * toplam / len(sonuclar):.0f}")
    for tur, (d, n) in sorted(tur_skor.items()):
        print(f"  {tur}: {d}/{n}")

    os.makedirs("eval/results", exist_ok=True)
    dosya = f"eval/results/{deney}_{datetime.datetime.now():%Y%m%d_%H%M}.json"
    with open(dosya, "w", encoding="utf-8") as f:
        json.dump({"deney": deney, "model": MODEL, "k": args.k, "sonuclar": sonuclar},
                  f, ensure_ascii=False, indent=2)
    print(f"Kaydedildi: {dosya}")


if __name__ == "__main__":
    main()