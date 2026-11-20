import os, json, time, datetime
from collections import defaultdict
import yaml, ollama
from baseline import MODEL, engine, SISTEM, SOZLUK_BASLIK, sema_metni, sql_cikar, normalize

MAX_DENEME = 3


def calistir(conn, sql):
    try:
        return conn.exec_driver_sql(sql).fetchall(), None
    except Exception as e:
        conn.rollback()
        return None, str(e).splitlines()[0]


def main():
    sozluk = SOZLUK_BASLIK + open("semantic.yaml", encoding="utf-8-sig").read()
    sorular = [q for q in yaml.safe_load(open("eval/golden.yaml", encoding="utf-8-sig")) if q.get("sql")]
    sonuclar, tur_skor = [], defaultdict(lambda: [0, 0])

    with engine.connect() as conn:
        sistem = SISTEM.format(sema=sema_metni(conn), sozluk=sozluk)
        for q in sorular:
            altin = normalize(conn.exec_driver_sql(q["sql"]).fetchall())
            mesajlar = [{"role": "system", "content": sistem}, {"role": "user", "content": q["soru"]}]
            adimlar, rows, bas = [], None, time.time()

            for deneme in range(1, MAX_DENEME + 1):
                cevap = ollama.chat(model=MODEL, messages=mesajlar, options={"temperature": 0, "seed": 42}, think=False)
                icerik = cevap["message"]["content"]
                sql = sql_cikar(icerik)
                rows, hata = calistir(conn, sql)
                adimlar.append({"sql": sql, "hata": hata, "satir": None if rows is None else len(rows)})

                if hata:
                    geri = f"Bu SQL PostgreSQL'de hata verdi:\n{hata}\nHatayı düzeltip SQL'i tekrar yaz."
                elif len(rows) == 0:
                    geri = "Sorgu çalıştı ama hiç satır döndürmedi. Filtreleri ve tarih aralığını kontrol edip SQL'i tekrar yaz."
                else:
                    break
                mesajlar += [{"role": "assistant", "content": icerik}, {"role": "user", "content": geri}]

            # Altın cevap sadece burada, puanlama için kullanılır; ajan onu hiç görmez.
            dogru = rows is not None and len(rows) > 0 and normalize(rows) == altin
            sure = round(time.time() - bas, 1)
            tur_skor[q["tur"]][0] += dogru
            tur_skor[q["tur"]][1] += 1
            sonuclar.append({"id": q["id"], "tur": q["tur"], "dogru": dogru, "deneme": len(adimlar),
                             "sure_sn": sure, "adimlar": adimlar})
            isaret = "✓" if dogru else "✗"
            print(f"{isaret} {q['id']} [{q['tur']}] {len(adimlar)} deneme, {sure}s")

    toplam = sum(r["dogru"] for r in sonuclar)
    duzelen = sum(1 for r in sonuclar if r["dogru"] and r["deneme"] > 1)
    print(f"\n[b3_ajan_v1] Doğruluk: {toplam}/{len(sonuclar)} = %{100 * toplam / len(sonuclar):.0f}")
    print(f"  Yeniden denemeyle düzelen: {duzelen}")
    print(f"  Ortalama deneme: {sum(r['deneme'] for r in sonuclar) / len(sonuclar):.2f}")
    for tur, (d, n) in sorted(tur_skor.items()):
        print(f"  {tur}: {d}/{n}")

    os.makedirs("eval/results", exist_ok=True)
    dosya = f"eval/results/b3_ajan_v1_{datetime.datetime.now():%Y%m%d_%H%M}.json"
    with open(dosya, "w", encoding="utf-8") as f:
        json.dump({"deney": "b3_ajan_v1", "model": MODEL, "sonuclar": sonuclar}, f, ensure_ascii=False, indent=2)
    print(f"Kaydedildi: {dosya}")


if __name__ == "__main__":
    main()
