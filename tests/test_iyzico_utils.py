# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Unit Tests for iyzico Payment Provider Utilities

This module contains unit tests for the utility functions used in
the iyzico payment integration.
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.payment_iyzico import utils as iyzico_utils
from odoo.addons.payment_iyzico import const


@tagged('post_install', '-at_install')
class TestIyzicoUtils(TransactionCase):
    """Test iyzico utility functions."""

    def test_format_amount_try(self):
        """Test amount formatting for Turkish Lira."""
        currency = self.env.ref('base.TRY')
        
        # Test integer amount
        result = iyzico_utils.format_amount(100, currency)
        self.assertEqual(result, "100.00")
        
        # Test decimal amount
        result = iyzico_utils.format_amount(123.45, currency)
        self.assertEqual(result, "123.45")
        
        # Test rounding
        result = iyzico_utils.format_amount(99.999, currency)
        self.assertEqual(result, "100.00")

    def test_format_phone_turkish(self):
        """Test phone number formatting for Turkish numbers."""
        # Test with 0 prefix
        result = iyzico_utils.format_phone("05551234567")
        self.assertEqual(result, "+905551234567")
        
        # Test with +90 prefix
        result = iyzico_utils.format_phone("+905551234567")
        self.assertEqual(result, "+905551234567")
        
        # Test with spaces
        result = iyzico_utils.format_phone("0555 123 45 67")
        self.assertEqual(result, "+905551234567")
        
        # Test empty phone
        result = iyzico_utils.format_phone("")
        self.assertEqual(result, "+905000000000")

    def test_get_locale(self):
        """Test locale mapping."""
        # Turkish
        result = iyzico_utils.get_locale('tr_TR')
        self.assertEqual(result, 'tr')
        
        # English
        result = iyzico_utils.get_locale('en_US')
        self.assertEqual(result, 'en')
        
        # Default fallback
        result = iyzico_utils.get_locale('ar_SA')
        self.assertEqual(result, 'en')

    def test_get_error_message(self):
        """Test error message retrieval."""
        # Known error code
        result = iyzico_utils.get_error_message('10051')
        self.assertIn('bakiye', result.lower())  # Should contain 'bakiye' (balance)
        
        # Unknown error code
        result = iyzico_utils.get_error_message('99999')
        self.assertIn('99999', result)  # Should include the error code

    def test_generate_authorization_header(self):
        """Test authorization header generation."""
        api_key = "test_api_key"
        secret_key = "test_secret_key"
        random_key = "1234567890123456"
        uri_path = "/payment/bin/check"
        request_body = '{"binNumber":"589004"}'
        
        result = iyzico_utils.generate_authorization_header(
            api_key, secret_key, random_key, uri_path, request_body
        )
        
        # Check header format
        self.assertTrue(result.startswith("IYZWSv2 "))
        
        # Check it's base64 encoded
        import base64
        encoded_part = result.split(" ")[1]
        try:
            decoded = base64.b64decode(encoded_part).decode('utf-8')
            self.assertIn("apiKey:", decoded)
            self.assertIn("randomKey:", decoded)
            self.assertIn("signature:", decoded)
        except Exception:
            self.fail("Authorization header is not valid base64")

    def test_prepare_single_basket_item(self):
        """Test single basket item preparation."""
        currency = self.env.ref('base.TRY')
        
        result = iyzico_utils.prepare_single_basket_item(
            100.50, "TEST-REF-001", currency
        )
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], "TEST-REF-001")
        self.assertEqual(result[0]['price'], "100.50")
        self.assertEqual(result[0]['itemType'], 'PHYSICAL')

    def test_log_api_request_sanitization(self):
        """Test API request logging with sanitization."""
        payload = {
            'apiKey': 'secret_api_key',
            'secretKey': 'very_secret_key',
            'cardNumber': '5528790000000008',
            'amount': '100.00',
            'buyer': {
                'name': 'Test User',
                'identityNumber': '11111111111'
            }
        }
        
        # Should not raise exception
        try:
            iyzico_utils.log_api_request('/test/endpoint', payload, sanitize=True)
        except Exception as e:
            self.fail(f"log_api_request raised exception: {e}")

    def test_supported_currencies(self):
        """Test that all currencies in SUPPORTED_CURRENCIES have decimal config."""
        for currency_code in const.SUPPORTED_CURRENCIES:
            self.assertIn(
                currency_code, 
                const.CURRENCY_DECIMALS,
                f"Currency {currency_code} missing in CURRENCY_DECIMALS"
            )

    def test_error_codes_format(self):
        """Test that all error codes have proper Turkish messages."""
        for code, message in const.ERROR_CODES.items():
            # Check code format
            self.assertTrue(code.isdigit(), f"Error code {code} should be numeric")
            
            # Check message is not empty
            self.assertTrue(len(message) > 0, f"Error message for {code} is empty")
            
            # Check message contains Turkish or English
            self.assertTrue(
                any(char in message for char in 'ıİşŞğĞüÜöÖçÇ') or message.isascii(),
                f"Error message for {code} seems invalid"
            )
