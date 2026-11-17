# Hata analizi — B1 (sadece şema)

- **Model:** qwen3:8b (Ollama, RTX 4070 Laptop, düşünme modu kapalı)
- **Yöntem:** Tek LLM çağrısı; istemde yalnızca tablo ve kolon adları/tipleri var. Anlam sözlüğü yok, hata düzeltme yok.
- **Değerlendirme:** Execution accuracy. Tahmin edilen SQL'in sonucu altın SQL'in sonucuyla karşılaştırılır; satır sırası yok sayılır, sayılar 2 ondalığa yuvarlanır.
- **Sonuç dosyası:** `eval/results/baseline_20261118_0115.json`

## Özet

| Tür | Doğru |
|---|---|
| tek_tablo | 5/5 |
| gruplama | 5/5 |
| zaman | 3/6 |
| join | 0/4 |
| tuzak | 0/5 |
| cok_adimli | 0/1 |
| **Toplam** | **13/26 (%50)** |

## Hatalar

| Soru | Model ne yaptı | Hata türü |
|---|---|---|
| q002 | `customer_id` saydı | Müşteri tanımı |
| q009 | `COUNT(*)` ile müşteri saydı | Müşteri tanımı |
| q026 | `orders.customer_id` ile tekrar müşteri aradı; her ID tek siparişli olduğu için %0 | Müşteri tanımı |
| q004 | Ciroyu `payment_value` ile hesapladı (kargo dahil) | Ciro tanımı |
| q006 | Teslim filtresi yok; çevirisi olmayan kategoriler düştü | Ciro tanımı |
| q022 | `price + freight_value`, teslim filtresi yok | Ciro tanımı |
| q021 | Sipariş değil, ödeme satırı ortalaması aldı | Çok adımlı mantık + ciro tanımı |
| q023 | `payment_value` kullandı; `BETWEEN ... '2018-03-31'` 31 Mart'ın gün içindeki siparişlerini dışarıda bıraktı | Ciro tanımı + tarih aralığı |
| q011 | `CURRENT_DATE` kullandı (2026) | Göreli zaman |
| q027 | `CURRENT_DATE - 1` → 2025 | Göreli zaman + ciro tanımı |
| q025 | Süreyi gün değil saniye verdi; eyalet sıralaması doğru | Birim |
| q005 | Ay için tarih yerine 1–12 döndürdü; sayılar doğru | Katı değerlendirme |
| q020 | Eyalet kolonunu eklemedi; şehir listesi doğru | Katı değerlendirme |

## Hata türlerinin dağılımı

| Hata türü | Soru sayısı |
|---|---|
| İş tanımı (ciro, müşteri) | 8 |
| Göreli zaman (`CURRENT_DATE`) | 2 |
| Katı değerlendirme / biçim | 2 |
| Birim | 1 |

Bir soruda birden fazla hata varsa ana hata sayıldı.

## Çıkarımlar

1. Model SQL sözdizimini biliyor (basit sorularda 10/10), ama iş tanımlarını ve verinin zaman aralığını bilmiyor. Hataların büyük kısmı bu.
2. Bir sonraki deney (B2): anlam sözlüğünü (`semantic.yaml`) isteme eklemek. Beklenti: müşteri, ciro ve göreli zaman hatalarının çoğunun düzelmesi.
3. `BETWEEN` ile tarih aralığı gibi genel SQL tuzakları sözlükle çözülmez. Bunları sonucu kontrol edip yeniden deneyen ajan döngüsü hedefleyecek.
4. Değerlendirme, biçim farklarında (ay numarası/tarih, fazladan ya da eksik kolon) cevabı yanlış sayıyor. Değerlendirmeyi gevşetmek yerine soruları netleştirmeyi ve iki sayıyı ayrı raporlamayı tercih ediyorum: katı doğruluk %50, biçim farkları hariç yaklaşık %58.
