import os, re, json, time, argparse, datetime, decimal
from collections import defaultdict
import yaml, ollama
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()
MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
engine = create_engine(os.environ["DATABASE_URL_RO"])

SISTEM = """Sen bir PostgreSQL uzmanısın. Kullanıcının Türkçe sorusunu aşağıdaki şemaya göre tek bir SELECT sorgusuna çevir.
Sadece SQL yaz, açıklama yazma. SQL'i ```sql bloğu içinde ver.

Şema:
{sema}
{sozluk}"""

SOZLUK_BASLIK = """
Anlam sözlüğü (iş terimleri ve kurallar; bunlara mutlaka uy):
"""


def sema_metni(conn):
    rows = conn.exec_driver_sql(
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'public' ORDER BY table_name, ordinal_position"
    ).fetchall()
    tablolar = {}
    for tablo, kolon, tip in rows:
        tablolar.setdefault(tablo, []).append(f"{kolon} {tip}")
    return "\n".join(f"{t}({', '.join(k)})" for t, k in tablolar.items())


def sql_cikar(metin):
    metin = re.sub(r"<think>.*?</think>", "", metin, flags=re.S)
    m = re.search(r"```(?:sql)?\s*(.*?)```", metin, flags=re.S | re.I)
    sql = (m.group(1) if m else metin).strip()
    return sql.rstrip(";") + ";"


def normalize(rows):
    def deger(v):
        if isinstance(v, (float, decimal.Decimal)):
            return round(float(v), 2)
        if isinstance(v, (datetime.date, datetime.datetime)):
            return v.isoformat()
        return v
    return sorted((tuple(deger(v) for v in r) for r in rows), key=repr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sozluk", action="store_true", help="Anlam sözlüğünü isteme ekle (B2)")
    args = ap.parse_args()
    deney = "b2_sozluk" if args.sozluk else "b1_sema"

    sozluk = ""
    if args.sozluk:
        sozluk = SOZLUK_BASLIK + open("semantic.yaml", encoding="utf-8-sig").read()

    sorular = [q for q in yaml.safe_load(open("eval/golden.yaml", encoding="utf-8-sig")) if q.get("sql")]
    sonuclar, tur_skor = [], defaultdict(lambda: [0, 0])

    with engine.connect() as conn:
        sistem = SISTEM.format(sema=sema_metni(conn), sozluk=sozluk)
        for q in sorular:
            altin = normalize(conn.exec_driver_sql(q["sql"]).fetchall())
            bas = time.time()
            cevap = ollama.chat(
                model=MODEL,
                messages=[
                    {"role": "system", "content": sistem},
                    {"role": "user", "content": q["soru"]},
                ],
                options={"temperature": 0},
                think=False,
            )
            sure = round(time.time() - bas, 1)
            tahmin = sql_cikar(cevap["message"]["content"])
            try:
                dogru = normalize(conn.exec_driver_sql(tahmin).fetchall()) == altin
                hata = None
            except Exception as e:
                conn.rollback()
                dogru, hata = False, str(e).splitlines()[0]

            tur_skor[q["tur"]][0] += dogru
            tur_skor[q["tur"]][1] += 1
            sonuclar.append({"id": q["id"], "tur": q["tur"], "dogru": dogru,
                             "sure_sn": sure, "tahmin_sql": tahmin, "hata": hata})
            print(f"{'✓' if dogru else '✗'} {q['id']} [{q['tur']}] {sure}s" + (f"  HATA: {hata}" if hata else ""))

    toplam = sum(r["dogru"] for r in sonuclar)
    print(f"\n[{deney}] Doğruluk: {toplam}/{len(sonuclar)} = %{100 * toplam / len(sonuclar):.0f}")
    for tur, (d, n) in sorted(tur_skor.items()):
        print(f"  {tur}: {d}/{n}")

    os.makedirs("eval/results", exist_ok=True)
    dosya = f"eval/results/{deney}_{datetime.datetime.now():%Y%m%d_%H%M}.json"
    with open(dosya, "w", encoding="utf-8") as f:
        json.dump({"deney": deney, "model": MODEL, "sonuclar": sonuclar}, f, ensure_ascii=False, indent=2)
    print(f"Kaydedildi: {dosya}")


if __name__ == "__main__":
    main()
