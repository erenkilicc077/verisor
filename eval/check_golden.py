import os
import yaml
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()
engine = create_engine(os.environ["DATABASE_URL_RO"])
sorular = yaml.safe_load(open("eval/golden.yaml", encoding="utf-8-sig"))

hata = 0
with engine.connect() as conn:
    for q in sorular:
        if not q.get("sql"):
            print(f"{q['id']}: belirsiz soru, SQL yok")
            continue
        try:
            rows = conn.exec_driver_sql(q["sql"]).fetchall()
            ilk = rows[0] if rows else "-"
            print(f"{q['id']}: {len(rows)} satır | ilk satır: {ilk}")
        except Exception as e:
            hata += 1
            print(f"{q['id']}: HATA -> {e}")
            conn.rollback()

print(f"\nToplam {len(sorular)} soru, {hata} hata")
