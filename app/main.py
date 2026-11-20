from fastapi import FastAPI
from pydantic import BaseModel, Field
from verisor.ajan import Ajan, MODEL

app = FastAPI(
    title="VeriSor",
    description="Türkçe soruları güvenli SQL'e çeviren analiz ajanı",
    version="0.1.0",
)
ajan = Ajan()


class SoruIstegi(BaseModel):
    soru: str = Field(min_length=3, max_length=500, examples=["2017'de her ay kaç sipariş geldi?"])


@app.get("/health")
def health():
    return {"durum": "ok", "model": MODEL}


@app.post("/ask")
def ask(istek: SoruIstegi):
    return ajan.sor(istek.soru)