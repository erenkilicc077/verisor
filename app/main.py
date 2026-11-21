import json
import uuid
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from verisor.ajan import Ajan, MODEL

app = FastAPI(
    title="VeriSor",
    description="Türkçe soruları güvenli SQL'e çeviren analiz ajanı",
    version="0.3.0",
)
ajan = Ajan()

# Son verilen cevaplar: geri bildirim gelince soru ve SQL buradan alınır.
SON_CEVAPLAR: "OrderedDict[str, dict]" = OrderedDict()
MAX_HAFIZA = 200
KAYIT_DOSYASI = Path("geri_bildirim/kayitlar.jsonl")


class SoruIstegi(BaseModel):
    soru: str = Field(min_length=3, max_length=500, examples=["2017'de her ay kaç sipariş geldi?"])


class SqlDeneme(BaseModel):
    sql: str = Field(min_length=6, max_length=5000, examples=["SELECT COUNT(*) FROM orders;"])


class GeriBildirim(BaseModel):
    id: str = Field(min_length=32, max_length=32)
    dogru: bool
    duzeltilmis_sql: str | None = Field(default=None, max_length=5000)


@app.get("/", include_in_schema=False)
def arayuz():
    return FileResponse("app/static/index.html")


@app.get("/health")
def health():
    return {"durum": "ok", "model": MODEL, "havuz": ajan.havuz_ozeti()}


@app.post("/ask")
def ask(istek: SoruIstegi):
    cevap = ajan.sor(istek.soru)
    cevap["id"] = uuid.uuid4().hex
    SON_CEVAPLAR[cevap["id"]] = {"soru": cevap["soru"], "sql": cevap["sql"], "hata": cevap["hata"]}
    while len(SON_CEVAPLAR) > MAX_HAFIZA:
        SON_CEVAPLAR.popitem(last=False)
    return cevap


@app.post("/dene")
def dene(istek: SqlDeneme):
    """Analistin düzelttiği SQL'i önizleme için çalıştırır (aynı güvenlik katmanları)."""
    return ajan.sql_dene(istek.sql)


@app.post("/feedback")
def feedback(gb: GeriBildirim):
    kayit = SON_CEVAPLAR.get(gb.id)
    if kayit is None:
        raise HTTPException(404, "Bu cevap bulunamadı ya da zaten değerlendirildi. Soruyu yeniden sor.")

    duzeltme = None
    if gb.duzeltilmis_sql:
        if gb.dogru:
            raise HTTPException(400, "Düzeltme yalnızca yanlış işaretlenen cevaplar için gönderilir.")
        # Tarayıcının "çalıştı" demesine güvenmeyiz: sunucu SQL'i kendisi yeniden çalıştırır.
        sonuc = ajan.sql_dene(gb.duzeltilmis_sql)
        if sonuc["hata"]:
            raise HTTPException(400, f"Düzeltilmiş SQL çalışmadı: {sonuc['hata']}")
        duzeltme = sonuc["sql"]
    elif gb.dogru and (kayit["sql"] is None or kayit["hata"]):
        raise HTTPException(400, "Hatalı bir cevap doğru olarak işaretlenemez.")

    # Doğrulamalar geçti; artık bu cevap ikinci kez değerlendirilemez.
    SON_CEVAPLAR.pop(gb.id, None)
    satir = {
        "zaman": datetime.now().isoformat(timespec="seconds"),
        "soru": kayit["soru"],
        "sql": kayit["sql"],
        "dogru": gb.dogru,
        "duzeltilmis_sql": duzeltme,
        "model": MODEL,
    }
    KAYIT_DOSYASI.parent.mkdir(exist_ok=True)
    with KAYIT_DOSYASI.open("a", encoding="utf-8") as f:
        f.write(json.dumps(satir, ensure_ascii=False) + "\n")

    if duzeltme:
        havuz_durumu = ajan.geri_bildirim_isle(kayit["soru"], duzeltme, True)
    else:
        havuz_durumu = ajan.geri_bildirim_isle(kayit["soru"], kayit["sql"], gb.dogru)
    return {"durum": "kaydedildi", "dogru": gb.dogru, "duzeltildi": duzeltme is not None,
            "havuz": havuz_durumu, "havuz_ozeti": ajan.havuz_ozeti()}