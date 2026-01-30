# Detaylar için iletişime geçiniz

# iyzico Payment Provider for Odoo 18

## Genel Bakış / Overview

Bu modül, Odoo 18 ile iyzico ödeme entegrasyonunu sağlar. Türkiye'nin önde gelen ödeme sağlayıcılarından biri olan iyzico ile güvenli online ödemeler alabilirsiniz.

This module provides iyzico payment integration for Odoo 18. Accept secure online payments using iyzico, one of Turkey's leading payment providers.

---
[Odoo Apps Store](https://apps.odoo.com/apps/modules/18.0/iyzico_odoo_payment)
## Özellikler / Features

### ✅ Temel Özellikler / Core Features
- **3D Secure Desteği**: Otomatik 3D Secure doğrulama
- **Taksit Desteği**: Kredi kartları için esnek taksit seçenekleri (1-12 ay)
- **Çoklu Para Birimi**: TRY, USD, EUR, GBP ve daha fazlası
- **Kısmi İade**: Partial refund desteği
- **Gerçek Zamanlı Callback**: Webhook ile anlık ödeme bildirimleri

### ✅ Güvenlik / Security
- **HMACSHA256 Authentication**: İyzico API v2 standardı
- **Webhook İmza Doğrulama**: Callback güvenliği
- **PCI-DSS Uyumluluk**: iyzico tarafından sağlanır
- **Hassas Veri Maskeleme**: Loglarda güvenli veri yönetimi

### ✅ Gelişmiş Özellikler / Advanced Features
- **BIN Check**: Kart doğrulama ve banka bilgisi
- **Detaylı Sepet**: Otomatik sipariş satırı gönderimi
- **3D Secure Tracking**: ECI ve card detay takibi
- **Test Modu**: Sandbox API desteği
- **Gelişmiş Loglama**: Structured logging ve debugging

---

## Kurulum / Installation

### 1. Modülü Yükleyin
```bash
# Modülü custom_addons klasörüne kopyalayın
cp -r payment_iyzico /path/to/odoo/custom_addons/

# Odoo'yu yeniden başlatın
sudo systemctl restart odoo
```

### 2. Modülü Aktifleştirin
1. Odoo'ya giriş yapın
2. **Apps** menüsüne gidin
3. "**payment_iyzico**" aratın
4. **Install** butonuna tıklayın

---

## Yapılandırma / Configuration

### 1. iyzico API Anahtarlarını Alın

#### Test Modu (Sandbox):
1. [https://sandbox-merchant.iyzipay.com](https://sandbox-merchant.iyzipay.com) adresine gidin
2. Test hesabı oluşturun
3. **Ayarlar → API Anahtarları** bölümünden:
   - **API Key** (Sandbox)
   - **Secret Key** (Sandbox)

#### Canlı Mod (Production):
1. [https://merchant.iyzipay.com](https://merchant.iyzipay.com) adresine gidin
2. İşyeri başvurusu yapın ve onay alın
3. **Ayarlar → API Anahtarları** bölümünden:
   - **API Key** (Production)
   - **Secret Key** (Production)

### 2. Odoo'da Payment Provider Ayarları

1. **Accounting/Invoicing → Configuration → Payment Providers** menüsüne gidin
2. **iyzico** provider'ı bulun ve açın
3. Aşağıdaki alanları doldurun:

| Alan / Field | Açıklama / Description |
|-------------|------------------------|
| **State** | Test (Sandbox) veya Enabled (Production) |
| **API Key** | iyzico panel'den aldığınız API Key |
| **Secret Key** | iyzico panel'den aldığınız Secret Key |
| **Enable Installments** | Taksit özelliğini aktifleştir |
| **Maximum Installments** | Maksimum taksit sayısı (1, 3, 6, 9, 12) |
| **Force 3D Secure** | 3D Secure'u zorunlu kıl (önerilir) |

4. **Save** butonuna tıklayın

---

## Test Kartları / Test Cards

Test modunda (Sandbox) aşağıdaki kartları kullanabilirsiniz:

| Banka / Bank | Kart No / Card Number | Expire | CVV | Tip / Type |
|--------------|----------------------|---------|-----|-----------|
| **Halkbank** | 5528790000000008 | 12/30 | 123 | Credit |
| **Denizbank** | 4766620000000001 | 12/30 | 123 | Credit |
| **Akbank** | 4355084355084358 | 12/30 | 123 | Credit |

**3D Secure Şifre**: İstediğiniz şifreyi girebilirsiniz (test modunda)

---

## Kullanım / Usage

### E-Ticaret Sitesinde Ödeme

1. Müşteri sepetine ürün ekler
2. Checkout sayfasında **iyzico** ödeme yöntemini seçer
3. "Pay Now" butonuna tıklar
4. iyzico ödeme sayfasına yönlendirilir
5. Kart bilgilerini girer
6. 3D Secure doğrulama yapar
7. Ödeme tamamlanır ve Odoo'ya geri döner

### Backend'den Sipariş

1. Sales → Orders → Create
2. Müşteri ve ürünleri seçin
3. Invoice oluşturun
4. "Register Payment" → iyzico seçin
5. Müşteri ödeme linkini alır

---

## Taksit Yapılandırması / Installment Configuration

### Provider Seviyesinde:
```python
provider.iyzico_enable_installments = True
provider.iyzico_max_installments = '12'  # 1, 3, 6, 9, 12
```

### Dinamik Taksit Seçenekleri:
Modül otomatik olarak:
- **Debit kartlar**: Sadece tek çekim
- **Credit kartlar**: Yapılandırılan maksimum taksit

---

## Webhook Yapılandırması / Webhook Configuration

iyzico panelinde callback URL'yi ayarlayın:

```
https://yourdomain.com/payment/iyzico/callback
```

**Not**: SSL sertifikası zorunludur (HTTPS)

---

## Loglama ve Debugging / Logging and Debugging

### Log Seviyeleri

Odoo conf dosyasında log seviyesini ayarlayın:

```ini
[options]
log_level = info
log_handler = odoo.addons.payment_iyzico:INFO
```

### Debug Modu

Provider'ın debug bilgilerini almak için:

```python
from odoo.addons.payment_iyzico import utils as iyzico_utils

debug_info = iyzico_utils.get_debug_info(provider)
print(debug_info)
```

### Transaction Flow Tracking

```python
iyzico_utils.log_transaction_flow(
    transaction_ref='SO001',
    step='payment_initiated',
    details={'amount': 100.00, 'currency': 'TRY'}
)
```

---

## API Referansı / API Reference

### Provider Methods

#### `_iyzico_create_checkout_form(tx_values)`
Checkout formu oluşturur ve ödeme sayfası URL'si döner.

#### `_iyzico_retrieve_checkout_result(token)`
Token ile ödeme sonucunu iyzico API'sinden çeker.

#### `_iyzico_create_refund(payment_id, amount, currency)`
Kısmi veya tam iade oluşturur.

#### `_iyzico_bin_check(bin_number)`
Kart BIN numarasını kontrol eder (ilk 6 hane).

#### `_iyzico_get_installment_info(bin_number, price)`
Kart için kullanılabilir taksit seçeneklerini döner.

### Utility Functions

#### `iyzico_utils.format_amount(amount, currency)`
Tutarı iyzico formatına çevirir.

#### `iyzico_utils.format_phone(phone)`
Telefon numarasını +90 formatına çevirir.

#### `iyzico_utils.prepare_basket_items_from_order(sale_order)`
Sale order'dan detaylı basket items oluşturur.

#### `iyzico_utils.log_api_request(endpoint, payload, sanitize=True)`
API isteklerini loglar (hassas veriyi maskeler).

---

## Hata Çözümleri / Troubleshooting

### Sık Karşılaşılan Hatalar / Common Errors

#### 1. "Invalid signature" Hatası
```
Çözüm: API Key ve Secret Key'i kontrol edin
        Test modunda test, canlıda production anahtarları kullanın
```

#### 2. "Kartınızda yetersiz bakiye" (Error 10051)
```
Çözüm: Test kartlarında bile bakiye hatası alıyorsanız,
        iyzico sandbox ayarlarınızı kontrol edin
```

#### 3. "3D Secure doğrulaması başarısız" (Error 10201)
```
Çözüm: Test modunda herhangi bir şifre girebilirsiniz
        Canlı modda müşterinin bankadan aldığı şifreyi girmeli
```

#### 4. "Transaction not found"
```
Çözüm: Callback URL'nin doğru yapılandırıldığından emin olun
        SSL sertifikasının aktif olduğunu kontrol edin
```

### Debug Modu Aktifleştirme

```bash
# Odoo loglarını canlı izleyin
tail -f /var/log/odoo/odoo.log | grep iyzico
```

---

## Test Senaryoları / Test Scenarios

### 1. Başarılı Ödeme Testi
1. Test modunda provider'ı aktifleştirin
2. Sipariş oluşturun (100 TL)
3. iyzico ile ödeme yapın
4. Test kartı: 5528790000000008
5. 3D Secure: Herhangi bir şifre
6. Ödemenin "Paid" durumuna geçtiğini kontrol edin

### 2. Taksitli Ödeme Testi
1. Provider'da taksiti aktifleştirin
2. 1000 TL'lik sipariş oluşturun
3. iyzico sayfasında 6 taksit seçin
4. Ödemeyi tamamlayın
5. Transaction detaylarında taksit sayısını kontrol edin

### 3. İade Testi
1. Başarılı bir ödeme yapın
2. Invoice'ta "Register Payment" seçin
3. "Refund" seçeneğini kullanın
4. Kısmi tutar girin (örn: 50 TL)
5. iyzico panelinde iadeni kontrol edin

### 4. BIN Check Testi
```python
provider = env['payment.provider'].search([('code', '=', 'iyzico')], limit=1)
result = provider._iyzico_bin_check('552879')
print(result)
# Output: {'cardType': 'CREDIT_CARD', 'bankName': 'Halkbank', ...}
```

---

## Performans / Performance

### Önerilen Ayarlar

- **Workers**: En az 2 worker kullanın
- **Timeout**: API timeout 60 saniye (varsayılan)
- **Database Pooling**: Aktif
- **Caching**: Redis kullanın

### Monitoring

```python
# Transaction başarı oranı
success_rate = env['payment.transaction'].search_count([
    ('provider_code', '=', 'iyzico'),
    ('state', '=', 'done')
]) / env['payment.transaction'].search_count([
    ('provider_code', '=', 'iyzico')
]) * 100

print(f"Success Rate: {success_rate}%")
```

---

## Güvenlik Önlemleri / Security Recommendations

1. ✅ **SSL Sertifikası**: Mutlaka HTTPS kullanın
2. ✅ **API Anahtarları**: Asla version control'e eklemeyin
3. ✅ **Force 3D Secure**: Canlı modda aktif tutun
4. ✅ **Webhook İmzası**: Signature verification açık
5. ✅ **Log Maskeleme**: Hassas verileri loglarda maskeyin
6. ✅ **Regular Updates**: Modülü güncel tutun

---

## Lisans / License

LGPL-3

---

## Destek / Support

- **iyzico Destek**: [https://dev.iyzipay.com/tr](https://dev.iyzipay.com/tr)
- **Odoo Community**: [Odoo Apps Store](https://apps.odoo.com/apps/modules/18.0/iyzico_odoo_payment) / [Odoo Forum](https://www.odoo.com/forum)
- **GitHub Issues**: Module repository

---

## Changelog

### Version 18.0.1.0.0 (Current)
- ✅ Odoo 18 uyumluluk güncellemeleri
- ✅ STATUS_MAPPING eklendi (iyzico status → Odoo state)
- ✅ _get_specific_secret_keys() metodu eklendi (token masking)
- ✅ _get_default_payment_method_id() metodu eklendi
- ✅ __manifest__.py versiyon formatı güncellendi
- ✅ Assets bölümü eklendi (static/src/**/*)
- ✅ Template iyileştirmeleri (auto-submit script)
- ✅ iyzico dokümantasyonuna göre HMACSHA256 authentication
- ✅ Base URL: sandbox-merchant vs production

### Version 1.0.0
- ✅ İlk sürüm / Initial release
- ✅ Phase 1: Kritik hata düzeltmeleri
- ✅ Phase 2: İyileştirmeler (45+ error code, webhook security)
- ✅ Phase 3: Gelişmiş özellikler (taksit UI, 3DS tracking, logging)
- ✅ Phase 4: Test ve dokümantasyon

---

## Katkıda Bulunma / Contributing

Bu bir açık kaynak projedir. Katkılarınızı bekliyoruz!

1. Fork yapın
2. Feature branch oluşturun
3. Değişikliklerinizi commit edin
4. Pull request gönderin

---

## Yazarlar / Authors

- **Initial Development**: iyzico Payment Integration Team
- **Phase 1-4 Enhancements**: OpenCode AI Assistant

---

**Teşekkürler! / Thank you for using iyzico Payment Provider for Odoo 18!**
