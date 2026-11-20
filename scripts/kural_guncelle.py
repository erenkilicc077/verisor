import yaml
p = "semantic.yaml"
s = yaml.safe_load(open(p, encoding="utf-8-sig"))
s["genel_kurallar"] = [
    "Verideki ilk sipariş 2016-09-04, son sipariş 2018-10-17 tarihlidir. CURRENT_DATE, NOW() veya bugünün tarihini ASLA kullanma. 'Geçen ay', 'geçen yıl' gibi ifadeleri 2018-10-17'ye göre hesapla.",
    "Filtreleri yalnızca soru gerektiriyorsa ekle. order_status = 'delivered' filtresini SADECE ciro ve ortalama sepet hesaplarında kullan; sayım, dağılım, puan ve ödeme sorularında kullanma.",
    "Soru gerektirmiyorsa JOIN ekleme. Tek tabloda cevaplanabilen soruyu tek tabloda cevapla.",
    "Tarih filtrelerinde order_purchase_timestamp kullan.",
    "Kategori adlarını göstermek için product_category_name_translation tablosundaki İngilizce adı kullan.",
]
yaml.safe_dump(s, open(p, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False, width=200)
print("Guncellendi:", len(s["genel_kurallar"]), "kural")
