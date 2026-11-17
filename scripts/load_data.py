import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine

engine = create_engine("postgresql+psycopg://admin:admin123@localhost:5432/olist")

for csv in sorted(Path("data").glob("*.csv")):
    table = csv.stem.replace("olist_", "").replace("_dataset", "")
    df = pd.read_csv(csv)
    for col in df.columns:
        if "timestamp" in col or "date" in col:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    df.to_sql(table, engine, if_exists="replace", index=False, chunksize=10_000)
    print(f"{table}: {len(df):,} satır")
