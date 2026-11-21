import json, glob

dosya = sorted(glob.glob("eval/results/b7_geri_bildirim_*.json"))[-1]
d = json.load(open(dosya, encoding="utf-8"))
for s in d["temel"]:
    print(f"{s['id']}  {'DOĞRU ' if s['esnek'] else 'YANLIŞ'}  {s['soru']}")