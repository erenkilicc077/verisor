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
| B5: B2 + embeddinggemma ile 3 benzer örnek (geliştirme setinden) | 16/30 (%53) | 17/30 (%57) |
Geliştirme seti (26 soru, sistem bu sorulara bakılarak ayarlandı):
| B5 (birini dışarıda bırak) | 18/26 (%69) | 20/26 (%77) |
| Sistem | Katı doğruluk | Esnek doğruluk |
|---|---|---|
| B1 | 11/26 (%42) | 13/26 (%50) |
| B2 | 15/26 (%58) | 19/26 (%73) |
| Ajan v2 | 15/26 (%58) | 20/26 (%77) |

Model: `qwen3:8b` (Ollama, yerel), RTX 4070 Laptop 8 GB, `temperature=0`, `seed=42`, düşünme modu kapalı. Ölçümler tekrarlarda ±1 soru oynayabiliyor.

## Bulgular
0. **Benzer örnek getirme en büyük ikinci kazancı sağladı.** Geliştirme setinden anlamca en yakın 3 soru–SQL çifti isteme eklendiğinde test setinde katı doğruluk %40'tan %53'e çıktı. Örnek havuzunda test sorusu yoktur; geliştirme setinde ölçerken sorunun kendisi havuzdan çıkarılır. İlgisiz örnek getirildiğinde ise model yanlış kalıba yönlendirilebiliyor (örnek: q021).
1. **İş tanımları en büyük kazancı getirdi.** "Ciro", "müşteri" ve "geçen ay" gibi kavramların açıkça tanımlandığı bir anlam sözlüğü, test setinde katı doğruluğu 17 puan artırdı. Tuzak sorularında artış 0/10'dan 6/10'a çıktı.
2. **Daha fazla bağlam her zaman daha iyi değil.** Sözlüğün ilk sürümü puanı düşürdü (%50 → %38): model "teslim edilmiş siparişler" kuralını ilgisiz sorulara da uyguladı. Kuralları kapsamlı ("SADECE ciro hesaplarında") ve somut ("son sipariş tarihi 2018-10-17; CURRENT_DATE kullanma") yazınca sorun büyük ölçüde çözüldü.
3. **Hata geri bildirimiyle yeniden deneme bu modelde işe yaramadı.** İki sette de yeniden denemeyle düzelen soru sayısı 0. Kalan hataların çoğu "sessiz": SQL çalışıyor ama sonuç yanlış. Çalışma zamanı hatası görmeyen bir döngü bunları yakalayamıyor.
4. **En zayıf alan zaman soruları** (test setinde katı 0/7): ortalama süre hesapları, tarih aralıkları ve dönemsel karşılaştırmalar.
5. **Tek çalıştırmaya güvenilmez.** Sabit seed olmadan aynı sistem iki çalıştırmada 4 soru fark verdi. Bu yüzden seed sabitlendi ve sonuçlar tekrarlanarak doğrulandı.

Ayrıntılı hata analizi: [docs/hata_analizi_b1.md](docs/hata_analizi_b1.md)
## Geri bildirim döngüsü: kullandıkça öğreniyor mu?

Arayüzdeki **Doğru / Yanlış** düğmeleriyle onaylanan soru–SQL çiftleri ajanın örnek havuzuna eklenir. Etkisini iki deneyle ölçtüm. Kullanıcıyı simüle etmek için cevapları altın SQL ile karşılaştırdım. Değerlendirme betikleri canlı uygulamanın havuzunu kullanmaz.

### Deney B7: yeni türde sorular

Test setini (belirsizler hariç 30 soru) ikiye böldüm. Bir yarıda doğru çıkan cevaplar onaylanıp havuza eklendi, diğer yarı ölçüldü, sonra yarılar yer değiştirdi. **Hiçbir soru kendi cevabını havuzda görmedi.**

| Koşul | Havuz | Katı | Esnek |
|---|---|---|---|
| temel | geliştirme seti | 16/30 (%53) | 17/30 (%57) |
| onay | + diğer yarının onaylanan cevapları | 17/30 (%57) | 18/30 (%60) |
| düzeltme | + diğer yarının doğru SQL'leri | 17/30 (%57) | 18/30 (%60) |

Fark 1 soru; daha önce ölçtüğüm ±1 soruluk oynamanın içinde. **Yeni türde sorularda ölçülebilir bir artış yok.** Onay koşulunda hiçbir soru doğrudan yanlışa dönmedi. Düzeltme koşulunda 2 soru kazanıldı, 1 soru yanıltıcı örnek yüzünden kaybedildi.

### Deney B8: aynı soru, farklı kelimelerle

Gerçek kullanımda aynı soru farklı biçimlerde tekrar sorulur. Test setinden 15 soruyu (8'i modelin doğru, 7'si yanlış cevapladığı sorular) **anlamı değiştirmeden kendi cümlelerimle yeniden yazdım** (`eval/paraphrase.yaml`). Burada asıl sorunun havuzda olması bilinçli; ölçülen senaryo "bu soru daha önce soruldu".

| Koşul | Esnek | Asıl soru benzer örneklerde bulundu |
|---|---|---|
| temel | 8/15 (%53) | 0/15 |
| onay | 9/15 (%60) | 8/15 (havuzdaki 8 sorunun hepsi) |
| düzeltme | **14/15 (%93)** | 15/15 |

| Asıl soru B7'de… | temel | onay | düzeltme |
|---|---|---|---|
| doğru cevaplanmıştı (8) | 8/8 | 8/8 | 8/8 |
| yanlış cevaplanmıştı (7) | 0/7 | 1/7 | **6/7** |

### Bulgular

- **Arama sorunsuz.** Yeniden yazılmış soru, havuzdaki asıl soruyu her seferinde buldu.
- **Doğruları onaylamak doğruluk eklemiyor.** Model bu soruları zaten biliyor. Ayrıca soruyu farklı kelimelerle sormak modeli bozmadı (8/8).
- **Asıl değer düzeltmede.** Modelin yanlış yaptığı 7 sorunun 6'sı, doğru SQL havuza girince düzeldi. Hiçbir soru bozulmadı. En değerli geri bildirim "doğru" tıkı değil, yanlışın düzeltilmesi. Bu yüzden sıradaki özellik arayüzden SQL düzeltme.

**Sınırlar:**
- n=15 küçük; oranlar kesin değil, bir yön gösteriyor.
- Düzeltme koşulu kusursuz bir analisti varsayıyor.
- Yeniden yazımları asıl soruları bilerek yaptım; bu, yazımları farkında olmadan kolaylaştırmış olabilir.
- Yanlış bir onay havuzu kirletebilir. Önlemler: geliştirme seti örnekleri ezilemez, yanlış onay "Yanlış" ile geri alınabilir, etki test setiyle ölçülür.
## Nasıl çalışıyor?

## Arayüz

![VeriSor arayüzü](docs/ekran.png)

```
uvicorn app.main:app --reload
```
Tarayıcıda http://127.0.0.1:8000 adresini aç. API belgeleri http://127.0.0.1:8000/docs adresinde.

- Tek sayı dönen cevaplar büyük gösterilir. Tablo dönen cevaplarda sonuç tablosu ve otomatik grafik çıkar: tarih bazlı sonuçlarda çizgi, diğerlerinde çubuk.
- **Excel için indir (CSV):** Türkçe Excel'in doğrudan açtığı biçimde (`;` ayırıcı, virgüllü ondalık, UTF-8).
- **Nasıl hesaplandı?** Çalıştırılan SQL'i ve modelin yararlandığı benzer soruları gösterir.
- **Doğru / Yanlış:** Onaylanan cevaplar örnek havuzuna eklenir; sayfanın üstündeki sayaç havuzun büyüklüğünü gösterir. Tarayıcı sunucuya SQL göndermez, sadece cevabın kimliğini gönderir. Sunucu SQL'i kendi kaydından alır, böylece havuza dışarıdan sorgu sokulamaz.
- **Düzelt:** "Yanlış" işaretlenen cevapta analist SQL'i düzenleyip çalıştırabilir ve sonucu önizleyebilir. Sadece başarıyla çalışmış SQL kaydedilebilir. Sunucu, kaydetmeden önce SQL'i aynı iki güvenlik katmanından (regex kontrolü + salt okuma kullanıcısı) geçirerek kendisi yeniden çalıştırır. Düzeltilmiş soru–SQL çifti havuza girer.
- Geri bildirimler `geri_bildirim/kayitlar.jsonl` dosyasına yazılır (git'e eklenmez). Sunucu yeniden başlayınca havuz bu dosyadan yeniden kurulur.

Grafikler kütüphane kullanılmadan SVG ile çizildi.
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
app/main.py                    FastAPI: /ask, /feedback, /health
app/static/index.html          arayüz (tek dosya)
verisor/ajan.py                ajan çekirdeği ve örnek havuzu
eval/deney_geri_bildirim.py    Deney B7
eval/deney_tekrar.py           Deney B8
eval/paraphrase.yaml           elle yeniden yazılmış 15 test sorusu

## Sonuçları yeniden üretme

```
python eval\check_golden.py                  # altın SQL'lerin hepsi çalışıyor mu
python eval\baseline.py                      # B1: sadece şema
python eval\baseline.py --sozluk             # B2: şema + anlam sözlüğü
python eval\agent_v3.py                      # B5: + 3 benzer örnek
python eval\rescore.py <deney_adi>           # katı ve esnek puan
python eval\deney_geri_bildirim.py           # B7: yeni türde sorular
python eval\deney_tekrar.py                  # B8: aynı soru, farklı kelimelerle
```

Test seti için başına `$env:SET="test";` ekle. Sonuçlar `eval/results/` klasörüne kaydedilir. Model qwen3:8b, `temperature=0`, `seed=42`. Yine de aynı ayarlarla sonuçlar ±1 soru oynayabiliyor.

## Yol haritası

- [x] Grafik ve Excel/CSV indirme
- [x] Doğru/Yanlış geri bildirimi ve büyüyen örnek havuzu
- [x] Geri bildirimin etkisini ölçme (B7, B8)
- [x] Arayüzden SQL düzeltme: analist yanlış SQL'i düzeltir, çalıştırıp     onaylar (B8'e göre en değerli geri bildirim)
- [ ] Belirsiz sorularda kullanıcıya netleştirme sorusu sorma
- [ ] Önceki cevaba bağlı takip soruları ("bunu eyalete göre böl")

## Lisans

Kod: MIT. Veri: Olist, CC BY-NC-SA 4.0.
