import os, json, time, datetime
from collections import defaultdict
import yaml, ollama
from baseline import MODEL, engine, SISTEM, SOZLUK_BASLIK, sema_metni, sql_cikar, normalize
from agent_v1 import calistir

MAX_DENEME = 3
OZET_KELIMELER = ("ortalama", "toplam", "kaç", "oran", "yüzde", "en çok", "en yüksek", "en uzun", "hangi")


def geri_bildirim(soru, sql, rows, hata, onceki_sqller):
    if sql in onceki_sqller:
        return ("Bir önceki denemedeki SQL'in aynısını yazdın. Farklı bir yaklaşım dene: "
                "gereksiz JOIN'leri kaldır ya da sorguyu WITH ile adımlara böl.")
    if hata:
        ipucu = ""
        if "statement timeout" in hata:
            ipucu = ("Sorgu 5 saniyede bitmedi. Büyük ihtimalle gereksiz büyük bir tablo "
                     "(örneğin geolocation) JOIN'lendi; o tabloyu kullanmadan yaz.")
        elif "aggregate function calls cannot" in hata:
            ipucu = ("Toplama fonksiyonlarını iç içe kullanamazsın. Önce WITH ile ara sonucu "
                     "(örneğin müşteri başına sipariş sayısı) hesapla, sonra dış sorguda topla.")
        elif "does not exist" in hata:
            ipucu = ("Sadece şemadaki tablo ve kolonları ve PostgreSQL fonksiyonlarını kullan. "
                     "DATEDIFF yoktur; gün farkı için EXTRACT(EPOCH FROM a - b) / 86400 kullan.")
        return f"Bu SQL PostgreSQL'de hata verdi:\n{hata}\n{ipucu}\nSQL'i düzeltip tekrar yaz."
    if len(rows) == 0:
        return "Sorgu çalıştı ama hiç satır döndürmedi. Filtreleri ve tarih aralığını kontrol edip SQL'i tekrar yaz."
    if len(rows) > 100 and any(k in soru.lower() for k in OZET_KELIMELER):
        return (f"Soru özet bir cevap istiyor ama sorgu {len(rows)} satır döndürdü. "
                "Toplama fonksiyonunu (AVG, SUM, COUNT) ya da GROUP BY'ı unutmuş olabilirsin. SQL'i düzeltip tekrar yaz.")
    return None


def main():
    sozluk = SOZLUK_BASLIK + open("semantic.yaml", encoding="utf-8-sig").read()
    sorular = [q for q in yaml.safe_load(open("eval/golden.yaml", encoding="utf-8-sig")) if q.get("sql")]
    sonuclar, tur_skor = [], defaultdict(lambda: [0, 0])

    with engine.connect() as conn:
        sistem = SISTEM.format(sema=sema_metni(conn), sozluk=sozluk)
        for q in sorular:
            altin = normalize(conn.exec_driver_sql(q["sql"]).fetchall())
            mesajlar = [{"role": "system", "content": sistem}, {"role": "user", "content": q["soru"]}]
            adimlar, onceki, rows, bas = [], [], None, time.time()

            for deneme in range(1, MAX_DENEME + 1):
                cevap = ollama.chat(model=MODEL, messages=mesajlar, options={"temperature": 0, "seed": 42}, think=False)
                icerik = cevap["message"]["content"]
                sql = sql_cikar(icerik)
                rows, hata = calistir(conn, sql)
                geri = geri_bildirim(q["soru"], sql, rows, hata, onceki)
                adimlar.append({"sql": sql, "hata": hata, "satir": None if rows is None else len(rows), "geri_bildirim": geri})
                onceki.append(sql)
                if geri is None:
                    break
                mesajlar += [{"role": "assistant", "content": icerik}, {"role": "user", "content": geri}]

            # Altın cevap sadece puanlamada kullanılır; ajan onu hiç görmez.
            dogru = rows is not None and len(rows) > 0 and normalize(rows) == altin
            sure = round(time.time() - bas, 1)
            tur_skor[q["tur"]][0] += dogru
            tur_skor[q["tur"]][1] += 1
            sonuclar.append({"id": q["id"], "tur": q["tur"], "dogru": dogru, "deneme": len(adimlar),
                             "sure_sn": sure, "adimlar": adimlar})
            print(f"{'✓' if dogru else '✗'} {q['id']} [{q['tur']}] {len(adimlar)} deneme, {sure}s")

    toplam = sum(r["dogru"] for r in sonuclar)
    duzelen = sum(1 for r in sonuclar if r["dogru"] and r["deneme"] > 1)
    print(f"\n[b4_ajan_v2] Doğruluk (katı): {toplam}/{len(sonuclar)} = %{100 * toplam / len(sonuclar):.0f}")
    print(f"  Yeniden denemeyle düzelen: {duzelen}")
    print(f"  Ortalama deneme: {sum(r['deneme'] for r in sonuclar) / len(sonuclar):.2f}")

    os.makedirs("eval/results", exist_ok=True)
    dosya = f"eval/results/b4_ajan_v2_{datetime.datetime.now():%Y%m%d_%H%M}.json"
    with open(dosya, "w", encoding="utf-8") as f:
        json.dump({"deney": "b4_ajan_v2", "model": MODEL, "sonuclar": sonuclar}, f, ensure_ascii=False, indent=2)
    print(f"Kaydedildi: {dosya}")


if __name__ == "__main__":
    main()
