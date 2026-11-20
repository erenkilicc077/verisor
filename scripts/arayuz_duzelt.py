p = "app/static/index.html"
t = open(p, encoding="utf-8-sig").read()
duzeltmeler = [
    ('tablo.append(el("thead")).append(bas);',
     'const thead = el("thead"); thead.append(bas); tablo.append(thead);'),
    ('"Sunucuya ulaşılamadı. Terminalde uvicorn\'un çalıştığını kontrol et."',
     '"Bir hata oluştu: " + e.message'),
    ("2017'de her ay kaç sipariş geldi?", "2017'nin son çeyreğinde toplam ciro ne kadar?"),
    ("Teslim edilen siparişlerin yüzde kaçı geç geldi?", "Eyaletlere göre müşteri sayısı nedir?"),
    ("Kaç farklı müşterimiz var?", "Müşteriler kaç farklı eyalette bulunuyor?"),
]
for eski, yeni in duzeltmeler:
    if eski in t:
        t = t.replace(eski, yeni)
        print("UYGULANDI :", yeni[:50])
    elif yeni in t:
        print("ZATEN VAR :", yeni[:50])
    else:
        print("BULUNAMADI:", eski[:50])
open(p, "w", encoding="utf-8").write(t)
