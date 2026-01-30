# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
iyzico Payment Provider Constants

This module contains all constant values used throughout the iyzico payment integration.
"""

# iyzico API Base URLs
API_URL_SANDBOX = 'https://sandbox-api.iyzipay.com'
API_URL_PRODUCTION = 'https://api.iyzipay.com'

# iyzico Checkout Page URLs (for redirect)
CHECKOUT_URL_SANDBOX = 'https://sandbox-cpp.iyzipay.com'
CHECKOUT_URL_PRODUCTION = 'https://cpp.iyzipay.com'

# iyzico API Endpoints
# Note: These are the correct endpoints as per iyzico API documentation
ENDPOINT_CHECKOUT_FORM_INIT = '/payment/iyzipos/checkoutform/initialize/auth/ecom'
ENDPOINT_CHECKOUT_FORM_RETRIEVE = '/payment/iyzipos/checkoutform/auth/ecom/detail'
ENDPOINT_REFUND = '/payment/refund'
ENDPOINT_CANCEL = '/payment/cancel'
ENDPOINT_BIN_CHECK = '/payment/bin/check'  # Card BIN check endpoint

# iyzico Payment Status Codes
PAYMENT_STATUS_SUCCESS = 'success'
PAYMENT_STATUS_FAILURE = 'failure'

# iyzico supported currencies
# iyzico supports these currencies for international payments
SUPPORTED_CURRENCIES = {
    'TRY',  # Turkish Lira
    'EUR',  # Euro
    'USD',  # US Dollar
    'GBP',  # British Pound
    'IRR',  # Iranian Rial
    'NOK',  # Norwegian Krone
    'RUB',  # Russian Ruble
    'CHF',  # Swiss Franc
}

# Currency decimal places for amount conversion
# iyzico requires amounts in the format: "1.00" for most currencies
CURRENCY_DECIMALS = {
    'TRY': 2,
    'EUR': 2,
    'USD': 2,
    'GBP': 2,
    'IRR': 0,
    'NOK': 2,
    'RUB': 2,
    'CHF': 2,
}

# Default payment method codes for iyzico
DEFAULT_PAYMENT_METHOD_CODES = {
    'card',  # Credit/Debit cards
}

# iyzico Checkout Form locale options
LOCALE_MAPPING = {
    'tr_TR': 'tr',
    'en_US': 'en',
    'en_GB': 'en',
    'ar_001': 'en',  # Fallback for Arabic
}
DEFAULT_LOCALE = 'tr'

# iyzico Payment Group (for categorization)
PAYMENT_GROUP = 'PRODUCT'

# iyzico Installment options (for Turkish cards)
# This defines the number of installments available
INSTALLMENT_OPTIONS = [1, 2, 3, 6, 9, 12]

# Mapping of transaction states to iyzico payment statuses
# Based on iyzico documentation: https://docs.iyzico.com/
# iyzico payment statuses: SUCCESS, FAILURE, INIT_THREEDS, CALLBACK_THREEDS
STATUS_MAPPING = {
    'draft': ('INIT_THREEDS', 'CALLBACK_THREEDS'),
    'pending': ('CALLBACK_THREEDS',),
    'authorized': (),  # iyzico doesn't have separate authorize/capture flow
    'done': ('SUCCESS', 'success'),
    'cancel': ('FAILURE', 'failure'),
    'error': ('FAILURE', 'failure'),
}

# Webhook/Callback events
HANDLED_WEBHOOK_EVENTS = [
    'PAYMENT_SUCCESS',
    'PAYMENT_FAILURE',
    'REFUND_SUCCESS',
    'REFUND_FAILURE',
]

# Timeout for API requests (in seconds)
API_TIMEOUT = 60

# iyzico Error Codes mapping to user-friendly messages
# Source: iyzico API Documentation - Error Codes
# These are the most common error codes returned by iyzico API
ERROR_CODES = {
    # Card-related errors
    '10005': 'İşlem onaylanmadı. Lütfen bankanızla iletişime geçin. (Transaction not approved)',
    '10012': 'Geçersiz kart numarası. Lütfen kartınızı kontrol edin. (Invalid card number)',
    '10034': 'Dolandırıcılık şüphesi. Lütfen bankanızla iletişime geçin. (Fraud suspicion)',
    '10041': 'Kayıp kart. Bu kart kullanılamaz. (Lost card)',
    '10043': 'Çalıntı kart. Bu kart kullanılamaz. (Stolen card)',
    '10051': 'Kartınızda yetersiz bakiye bulunmaktadır. (Insufficient funds)',
    '10054': 'Kartınızın süresi dolmuş. Lütfen başka bir kart kullanın. (Expired card)',
    '10057': 'Kart sahibi bu işlemi gerçekleştiremez. (Card holder cannot perform this transaction)',
    '10058': 'Terminal bu işlem için yetkili değil. (Terminal not authorized)',
    '10084': 'CVC2 bilgisi hatalı. (Invalid CVC2)',
    
    # 3D Secure errors
    '10201': '3D Secure doğrulaması başarısız. (3D Secure authentication failed)',
    '10203': '3D Secure doğrulaması tamamlanamadı. (3D Secure not completed)',
    '10204': 'Kartınız 3D Secure desteklemiyor. (Card does not support 3D Secure)',
    
    # Transaction errors
    '10000': 'İşlem sırasında bir hata oluştu. Lütfen tekrar deneyin. (General transaction error)',
    '10001': 'Geçersiz istek. Lütfen bilgilerinizi kontrol edin. (Invalid request)',
    '10002': 'API anahtarı geçersiz. (Invalid API key)',
    '10003': 'İşlem tutarı geçersiz. (Invalid amount)',
    '10004': 'Para birimi desteklenmiyor. (Unsupported currency)',
    '10006': 'İşlem limiti aşıldı. (Transaction limit exceeded)',
    '10007': 'İşlem zaten gerçekleştirilmiş. (Duplicate transaction)',
    '10008': 'İşlem bulunamadı. (Transaction not found)',
    '10009': 'İade tutarı işlem tutarını aşıyor. (Refund amount exceeds transaction amount)',
    '10010': 'İşlem iade edilemez durumda. (Transaction cannot be refunded)',
    
    # Merchant/Terminal errors
    '10011': 'Üye işyeri bulunamadı. (Merchant not found)',
    '10013': 'Üye işyeri aktif değil. (Merchant not active)',
    '10014': 'Geçersiz imza. (Invalid signature)',
    '10015': 'Geçersiz IP adresi. (Invalid IP address)',
    
    # Installment errors
    '10060': 'Taksit sayısı geçersiz. (Invalid installment count)',
    '10061': 'Kartınız taksit desteklemiyor. (Card does not support installments)',
    '10062': 'Bu tutar için taksit yapılamaz. (Amount not eligible for installments)',
    
    # Timeout errors
    '10090': 'İşlem zaman aşımına uğradı. Lütfen tekrar deneyin. (Transaction timeout)',
    '10091': 'Banka yanıt vermedi. Lütfen tekrar deneyin. (Bank timeout)',
    
    # Refund/Cancel errors
    '10100': 'İade işlemi başarısız. (Refund failed)',
    '10101': 'İptal işlemi başarısız. (Cancel failed)',
    '10102': 'İade için geç kalındı. (Refund deadline passed)',
    '10103': 'Kısmi iade yapılamaz. (Partial refund not allowed)',
    
    # BIN/Card check errors
    '10120': 'Kart bilgileri alınamadı. (Unable to retrieve card info)',
    '10121': 'Kart BIN numarası geçersiz. (Invalid BIN number)',
    
    # General errors
    '10999': 'Bilinmeyen hata. Lütfen tekrar deneyin. (Unknown error)',
    '11000': 'Sistem hatası. Lütfen daha sonra tekrar deneyin. (System error)',
}
