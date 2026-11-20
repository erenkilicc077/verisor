import yaml
p = "semantic.yaml"
s = yaml.safe_load(open(p, encoding="utf-8-sig"))
s["is_terimleri"]["gecen_ay"] = "Son siparişin bulunduğu aydan (2018-10) bir önceki takvim ayı: 2018-09-01 ile 2018-10-01 arası."
s["is_terimleri"]["gecen_yil"] = "Son siparişin bulunduğu yıldan (2018) bir önceki takvim yılı: 2017-01-01 ile 2018-01-01 arası."
yaml.safe_dump(s, open(p, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False, width=200)
print("Eklendi. Is terimi sayisi:", len(s["is_terimleri"]))
