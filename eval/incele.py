import sys, json, glob

desen = sys.argv[1] if len(sys.argv) > 1 else "b3_ajan_v1"
dosya = sorted(glob.glob(f"eval/results/{desen}_*.json"))[-1]
veri = json.load(open(dosya, encoding="utf-8"))
print(f"Dosya: {dosya}\n")

for r in veri["sonuclar"]:
    if r["dogru"]:
        continue
    adimlar = r.get("adimlar") or [{"sql": r.get("tahmin_sql"), "hata": r.get("hata"), "satir": None}]
    print(f"=== {r['id']} [{r['tur']}] {len(adimlar)} deneme")
    for i, a in enumerate(adimlar, 1):
        print(f"--- deneme {i} | satir={a.get('satir')} | hata={a.get('hata')}")
        print(a.get("sql"))
    print()
