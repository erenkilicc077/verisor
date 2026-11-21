"""VeriSor çekirdeği: Türkçe soru -> güvenli SQL -> sonuç.

İstem, değerlendirmede en iyi sonucu veren B5 yöntemiyle aynıdır:
şema + anlam sözlüğü + 3 benzer soru-SQL örneği.
Örnek havuzu = geliştirme seti + kullanıcının "doğru" diye onayladığı cevaplar.
"""
import os, re, json, time, decimal, datetime, threading
import numpy as np
import yaml, ollama
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
EMB_MODEL = os.getenv("EMB_MODEL", "embeddinggemma:300m")
MAX_SATIR = 200
KAYIT_DOSYASI = "geri_bildirim/kayitlar.jsonl"

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


def anahtar(soru):
    """Aynı sorunun küçük yazım farklarını (büyük harf, boşluk, soru işareti) yok sayar."""
    return " ".join(soru.casefold().split()).rstrip("?").strip()


class Ajan:
    def __init__(self):
        self.engine = create_engine(os.environ["DATABASE_URL_RO"])
        self.sozluk = SOZLUK_BASLIK + open("semantic.yaml", encoding="utf-8-sig").read()
        self.kilit = threading.Lock()
        tum = yaml.safe_load(open("eval/golden.yaml", encoding="utf-8-sig"))
        # Test seti havuza hiç girmez; geliştirme seti sabit, onaylar üstüne eklenir.
        havuz = [{"soru": q["soru"], "sql": q["sql"], "kaynak": "golden"}
                 for q in tum if q.get("sql") and q.get("set", "dev") == "dev"]
        havuz += self._onaylari_oku({anahtar(q["soru"]) for q in havuz})
        self.havuz = havuz
        self.havuz_v = self._vektor([q["soru"] for q in havuz])
        with self.engine.connect() as conn:
            self.sema = sema_metni(conn)

    def _onaylari_oku(self, golden_anahtarlar):
        """Kayıt dosyasını baştan sona oynatır: doğru = ekle/güncelle, yanlış = çıkar."""
        if not os.path.exists(KAYIT_DOSYASI):
            return []
        onaylar = {}
        with open(KAYIT_DOSYASI, encoding="utf-8") as f:
            for satir in f:
                if not satir.strip():
                    continue
                k = json.loads(satir)
                a = anahtar(k["soru"])
                if a in golden_anahtarlar:
                    continue
                if k["dogru"] and k.get("sql"):
                    onaylar[a] = {"soru": k["soru"], "sql": k["sql"], "kaynak": "onay"}
                else:
                    onaylar.pop(a, None)
        return list(onaylar.values())

    def _vektor(self, metinler):
        v = np.array(ollama.embed(model=EMB_MODEL, input=metinler)["embeddings"], dtype=float)
        return v / np.linalg.norm(v, axis=1, keepdims=True)

    def geri_bildirim_isle(self, soru, sql, dogru):
        """Havuzu günceller. Listeler yerinde değiştirilmez, yenisiyle değiştirilir;
        böylece aynı anda çalışan bir soru eski ya da yeni havuzu tutarlı görür."""
        a = anahtar(soru)
        with self.kilit:
            idx = next((i for i, q in enumerate(self.havuz) if anahtar(q["soru"]) == a), None)
            if idx is not None and self.havuz[idx]["kaynak"] == "golden":
                return "golden_degismez"
            if dogru:
                yeni = {"soru": soru, "sql": sql, "kaynak": "onay"}
                if idx is None:
                    v = self._vektor([soru])
                    self.havuz, self.havuz_v = self.havuz + [yeni], np.vstack([self.havuz_v, v])
                    return "eklendi"
                self.havuz = self.havuz[:idx] + [yeni] + self.havuz[idx + 1:]
                return "guncellendi"
            if idx is not None:
                self.havuz = self.havuz[:idx] + self.havuz[idx + 1:]
                self.havuz_v = np.delete(self.havuz_v, idx, axis=0)
                return "cikarildi"
            return "degisiklik_yok"

    def havuz_ozeti(self):
        onay = sum(q["kaynak"] == "onay" for q in self.havuz)
        return {"toplam": len(self.havuz), "golden": len(self.havuz) - onay, "onayli": onay}

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
        with self.kilit:
            havuz, havuz_v = self.havuz, self.havuz_v
        soru_v = self._vektor([soru])[0]
        sira = np.argsort(-(havuz_v @ soru_v))[:k]
        ornekler = [havuz[j] for j in sira]
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
            "onayli_ornek_sayisi": sum(o["kaynak"] == "onay" for o in ornekler),
            "deneme": deneme,
            "sure_sn": round(time.time() - bas, 2),
            "model": MODEL,
        }