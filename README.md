# VeriSor — Türkçe soruları güvenli SQL'e çeviren analiz ajanı

KOBİ'lerde satış ve operasyon ekipleri basit bir rapor için bile SQL bilen birine ya da elle güncellenen Excel dosyalarına bağımlı. VeriSor, Türkçe sorulan iş sorularını PostgreSQL sorgusuna çevirip **salt okuma yetkisiyle** çalıştıran yerel bir LLM sistemi.

Bu repo bir demo değil, bir **ölçüm çalışması**: her tasarım kararı elle doğrulanmış bir soru setiyle test edildi. İşe yaramayan yöntemler de raporlandı.

## Sonuçlar

Test seti (30 soru, sistem ayarları yapılırken hiç görülmedi):

| Sistem | Katı doğruluk | Esnek doğruluk |
|---|---|---|
| B1: yalnızca şema | 7/30 (%23) | 9/30 (%30) |
| B2: şema + anlam sözlüğü | 12/30 (%40) | 15/30 (%50) |
| Ajan v2: B2 + hataya özel geri bildirimle yeniden deneme | 12/30 (%40) | 15/30 (%50) |

Geliştirme seti (26 soru, sistem bu sorulara bakılarak ayarlandı):

| Sistem | Katı doğruluk | Esnek doğruluk |
|---|---|---|
| B1 | 11/26 (%42) | 13/26 (%50) |
| B2 | 15/26 (%58) | 19/26 (%73) |
| Ajan v2 | 15/26 (%58) | 20/26 (%77) |

Model: `qwen3:8b` (Ollama, yerel), RTX 4070 Laptop 8 GB, `temperature=0`, `seed=42`, düşünme modu kapalı. Ölçümler tekrarlarda ±1 soru oynayabiliyor.

## Bulgular

1. **İş tanımları en büyük kazancı getirdi.** "Ciro", "müşteri" ve "geçen ay" gibi kavramların açıkça tanımlandığı bir anlam sözlüğü, test setinde katı doğruluğu 17 puan artırdı. Tuzak sorularında artış 0/10'dan 6/10'a çıktı.
2. **Daha fazla bağlam her zaman daha iyi değil.** Sözlüğün ilk sürümü puanı düşürdü (%50 → %38): model "teslim edilmiş siparişler" kuralını ilgisiz sorulara da uyguladı. Kuralları kapsamlı ("SADECE ciro hesaplarında") ve somut ("son sipariş tarihi 2018-10-17; CURRENT_DATE kullanma") yazınca sorun büyük ölçüde çözüldü.
3. **Hata geri bildirimiyle yeniden deneme bu modelde işe yaramadı.** İki sette de yeniden denemeyle düzelen soru sayısı 0. Kalan hataların çoğu "sessiz": SQL çalışıyor ama sonuç yanlış. Çalışma zamanı hatası görmeyen bir döngü bunları yakalayamıyor.
4. **En zayıf alan zaman soruları** (test setinde katı 0/7): ortalama süre hesapları, tarih aralıkları ve dönemsel karşılaştırmalar.
5. **Tek çalıştırmaya güvenilmez.** Sabit seed olmadan aynı sistem iki çalıştırmada 4 soru fark verdi. Bu yüzden seed sabitlendi ve sonuçlar tekrarlanarak doğrulandı.

Ayrıntılı hata analizi: [docs/hata_analizi_b1.md](docs/hata_analizi_b1.md)

## Nasıl çalışıyor?

**Güvenlik:** Ajan, veritabanına yalnızca `SELECT` yetkisi olan, `default_transaction_read_only = on` ve `statement_timeout = 5s` ayarlı bir kullanıcıyla bağlanır. Model `DELETE` ya da `DROP` üretse bile veritabanı reddeder. Bu katman testlerde gerçekten devreye girdi: gereksiz bir `geolocation` JOIN'i zaman aşımıyla durduruldu.

## Değerlendirme yöntemi

- **Altın set:** 60 soru (geliştirme 28, test 32). Her soru için doğru SQL elle yazılıp çalıştırılarak doğrulandı. Türler: tek tablo, gruplama, join, zaman, tuzak, çok adımlı, belirsiz. Belirsiz sorular (4 adet) SQL ile puanlanmıyor; doğru davranış geri soru sormak.
- **Katı doğruluk:** Tahmin edilen SQL'in sonucu altın sonuçla birebir aynı mı? Satır sırası yok sayılır, sayılar 2 ondalığa yuvarlanır.
- **Esnek doğruluk:** Biçim farklarını affeder. Altın cevap tek satırsa modelin ilk satırına bakılır; altın cevaptaki tüm sayısal kolonlar modelin sonucunda bulunmalıdır. Fazladan kolon ya da farklı tarih biçimi cezalandırılmaz, yanlış sayı cezalandırılır.
- **Sınır:** Esnek ölçü etiket kolonlarını (şehir adı gibi) kontrol etmez; rakamlar tesadüfen tutarsa yanlış bir cevabı doğru sayabilir. Bu yüzden iki ölçü birlikte raporlanıyor.
- **Şeffaflık notu:** Test setinin soru metinleri ve SQL taslakları yapay zekâ yardımıyla hazırlandı; hepsi çalıştırılıp sonuçları elle kontrol edildi.

## Veri

[Olist Brezilya e-ticaret veri seti](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce): yaklaşık 99 bin sipariş (2016-09 – 2018-10), 9 tablo. Lisans: CC BY-NC-SA 4.0 (ticari olmayan kullanım, atıf, aynı lisansla paylaşım). Veri repoya dahil değildir.

**Veri notları:**
- `customer_id` her siparişte yeniden üretilir. Gerçek müşteri `customer_unique_id`'dir (99.441'e karşı 96.096).
- `order_reviews.review_id` ve `geolocation` posta kodları tekrar eder; bu tablolara birincil anahtar konmadı.
- Müşterilerin yalnızca yaklaşık %3'ü birden fazla sipariş vermiş.
- Kaynak kolon adlarında yazım hatası var: `product_name_lenght`, `product_description_lenght`.

## Kurulum

Gereksinimler: Docker Desktop, Python 3.12, Ollama.

```bash
git clone https://github.com/<kullanici>/verisor.git
cd verisor
docker compose up -d
python -m venv .venv
.venv\Scripts\activate          # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # Mac/Linux: cp .env.example .env
ollama pull qwen3:8b
```

Olist CSV dosyalarını Kaggle'dan indirip `data/` klasörüne koy, sonra:

```bash
python scripts/load_data.py
docker compose exec -T db psql -U admin -d olist < scripts/setup.sql
docker compose exec db psql -U admin -d olist -c "ALTER TABLE orders ALTER COLUMN order_approved_at TYPE timestamp USING order_approved_at::timestamp;"
python eval/check_golden.py     # 60 soru, 0 hata olmalı
```

## Deneyleri tekrarlama

```bash
python eval/baseline.py              # B1
python eval/baseline.py --sozluk     # B2
python eval/agent_v2.py              # Ajan v2
python eval/rescore.py b2_sozluk     # katı + esnek puan
```

Varsayılan olarak geliştirme seti çalışır. Test seti için `SET=test` ortam değişkenini ayarla (PowerShell: `$env:SET = "test"`).

## Proje yapısı

## Yol haritası

- [ ] Benzer örnek getirme: geliştirme setinden en benzer soru–SQL çiftlerini `embeddinggemma` ile bulup isteme eklemek (hedef: zaman soruları)
- [ ] Belirsiz sorularda geri soru sorma ve bunun ölçümü
- [ ] Güvenlik test seti: zararlı ya da enjeksiyon içeren 20 soru
- [ ] FastAPI ile `POST /ask` uç noktası ve basit bir arayüz
- [ ] Daha büyük bir modelle (API ya da `qwen3:14b`) karşılaştırma

## Lisans

Kod: MIT. Veri: Olist, CC BY-NC-SA 4.0.
