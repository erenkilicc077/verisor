"""VeriSor çekirdeği: Türkçe soru -> güvenli SQL -> sonuç.

İstem, değerlendirmede en iyi sonucu veren B5 yöntemiyle aynıdır:
şema + anlam sözlüğü + geliştirme setinden 3 benzer soru-SQL örneği.
"""
import os, re, time, decimal, datetime
import numpy as np
import yaml, ollama
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
EMB_MODEL = os.getenv("EMB_MODEL", "embeddinggemma:300m")
MAX_SATIR = 200

SISTEM = """Sen bir PostgreSQL uzmanısın. Kullanıcının Türkçe sorusunu aşağıdaki şemaya göre tek bir SELECT sorgusuna çevir.
Sadece SQL yaz, açıklama yazma. SQL'i ```sql bloğu içinde ver.

Şema:
{sema}
{sozluk}"""

SOZLUK_BASLIK = "\nAnlam sözlüğü (iş terimleri ve kurallar; bunlara mutlaka uy):\n"

# İkinci güvenlik katmanı: salt okuma kullanıcısına ek olarak, SQL veritabanına gitmeden kontrol edilir.
GUVENLI_BASLANGIC = re.compile(r"^\s*(select|with)\b", re.I)
YASAK = re.compile(r"\b(insert|update|delete|drop|alter|create|grant|revoke|truncate|copy)\b", re.I)


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


def ornek_metni(ornekler):
    parcalar = ["\nBenzer sorular ve doğru SQL'leri (yalnızca yöntem için örnek; yeni soruyu kendi şartlarına göre çöz):"]
    for o in ornekler:
        parcalar.append(f"Soru: {o['soru']}\n```sql\n{o['sql'].strip()}\n```")
    return "\n\n".join(parcalar)


def jsonla(v):
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()
    return v


class Ajan:
    def __init__(self):
        self.engine = create_engine(os.environ["DATABASE_URL_RO"])
        self.sozluk = SOZLUK_BASLIK + open("semantic.yaml", encoding="utf-8-sig").read()
        tum = yaml.safe_load(open("eval/golden.yaml", encoding="utf-8-sig"))
        # Örnek havuzu değerlendirmeyle aynı: yalnızca geliştirme seti.
        self.havuz = [q for q in tum if q.get("sql") and q.get("set", "dev") == "dev"]
        self.havuz_v = self._vektor([q["soru"] for q in self.havuz])
        with self.engine.connect() as conn:
            self.sema = sema_metni(conn)

    def _vektor(self, metinler):
        v = np.array(ollama.embed(model=EMB_MODEL, input=metinler)["embeddings"], dtype=float)
        return v / np.linalg.norm(v, axis=1, keepdims=True)

    def _calistir(self, conn, sql):
        if not GUVENLI_BASLANGIC.match(sql) or YASAK.search(sql):
            return None, None, "Güvenlik: yalnızca tek bir SELECT sorgusu çalıştırılabilir."
        try:
            sonuc = conn.exec_driver_sql(sql)
            return list(sonuc.keys()), sonuc.fetchmany(MAX_SATIR + 1), None
        except Exception as e:
            conn.rollback()
            return None, None, str(e).splitlines()[0]

    def sor(self, soru, k=3, max_deneme=2):
        bas = time.time()
        soru_v = self._vektor([soru])[0]
        sira = np.argsort(-(self.havuz_v @ soru_v))[:k]
        ornekler = [self.havuz[j] for j in sira]
        sistem = SISTEM.format(sema=self.sema, sozluk=self.sozluk) + ornek_metni(ornekler)
        mesajlar = [{"role": "system", "content": sistem}, {"role": "user", "content": soru}]

        deneme = 0
        with self.engine.connect() as conn:
            for deneme in range(1, max_deneme + 1):
                cevap = ollama.chat(model=MODEL, messages=mesajlar,
                                    options={"temperature": 0, "seed": 42}, think=False)
                icerik = cevap["message"]["content"]
                sql = sql_cikar(icerik)
                kolonlar, satirlar, hata = self._calistir(conn, sql)
                if not hata:
                    break
                mesajlar += [{"role": "assistant", "content": icerik},
                             {"role": "user", "content": f"Bu SQL hata verdi:\n{hata}\nHatayı düzeltip SQL'i tekrar yaz."}]

        satirlar = satirlar or []
        return {
            "soru": soru,
            "sql": sql,
            "hata": hata,
            "kolonlar": kolonlar or [],
            "satirlar": [[jsonla(v) for v in r] for r in satirlar[:MAX_SATIR]],
            "kesildi": len(satirlar) > MAX_SATIR,
            "benzer_ornekler": [o["soru"] for o in ornekler],
            "deneme": deneme,
            "sure_sn": round(time.time() - bas, 2),
            "model": MODEL,
        }