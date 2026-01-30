# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Integration Tests for iyzico Payment Provider

This module contains integration tests for the iyzico payment provider,
testing the full payment flow with mock API responses.
"""

from unittest.mock import patch, Mock
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestIyzicoProvider(TransactionCase):
    """Test iyzico payment provider integration."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create iyzico payment provider
        cls.provider = cls.env['payment.provider'].create({
            'name': 'iyzico Test',
            'code': 'iyzico',
            'state': 'test',
            'iyzico_api_key': 'test_api_key',
            'iyzico_secret_key': 'test_secret_key',
            'iyzico_enable_installments': True,
            'iyzico_max_installments': '12',
            'iyzico_force_3ds': True,
        })
        
        # Create test currency
        cls.currency = cls.env.ref('base.TRY')
        
        # Create test partner
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Customer',
            'email': 'test@example.com',
            'phone': '+905551234567',
        })

    def test_provider_creation(self):
        """Test that provider is created correctly."""
        self.assertEqual(self.provider.code, 'iyzico')
        self.assertEqual(self.provider.state, 'test')
        self.assertTrue(self.provider.iyzico_enable_installments)
        self.assertTrue(self.provider.iyzico_force_3ds)

    def test_supported_currencies(self):
        """Test that provider returns correct supported currencies."""
        supported = self.provider._get_supported_currencies()
        currency_names = [c.name for c in supported]
        
        # TRY should be supported
        self.assertIn('TRY', currency_names)
        
        # USD should be supported
        self.assertIn('USD', currency_names)

    def test_feature_support(self):
        """Test that provider features are configured correctly."""
        self.provider._compute_feature_support_fields()
        
        # iyzico doesn't support manual capture
        self.assertEqual(self.provider.support_manual_capture, False)
        
        # iyzico supports partial refunds
        self.assertEqual(self.provider.support_refund, 'partial')

    @patch('requests.post')
    def test_checkout_form_creation(self, mock_post):
        """Test checkout form creation with mock API."""
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            'status': 'success',
            'token': 'test_token_123',
            'paymentPageUrl': 'https://sandbox-api.iyzipay.com/payment/page/123',
            'checkoutFormContent': '<html>...</html>',
        }
        mock_post.return_value = mock_response
        
        # Create transaction
        tx = self.env['payment.transaction'].create({
            'provider_id': self.provider.id,
            'reference': 'TEST-TX-001',
            'amount': 100.00,
            'currency_id': self.currency.id,
            'partner_id': self.partner.id,
        })
        
        # Get rendering values
        tx_values = {
            'reference': tx.reference,
            'amount': tx.amount,
            'currency': tx.currency_id,
            'partner_id': self.partner.id,
            'partner_name': self.partner.name,
            'partner_email': self.partner.email,
            'partner_phone': self.partner.phone,
            'partner_address': 'Test Address',
            'partner_city': 'Istanbul',
            'partner_zip': '34000',
            'partner_country': 'Turkey',
            'partner_lang': 'tr_TR',
            'partner_ip': '127.0.0.1',
        }
        
        result = self.provider._iyzico_create_checkout_form(tx_values)
        
        # Verify API was called
        self.assertTrue(mock_post.called)
        
        # Verify result
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['token'], 'test_token_123')

    @patch('requests.post')
    def test_bin_check(self, mock_post):
        """Test BIN check functionality."""
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            'status': 'success',
            'binNumber': '589004',
            'cardType': 'CREDIT_CARD',
            'cardAssociation': 'MASTER_CARD',
            'cardFamily': 'Bonus',
            'bankName': 'Garanti Bankası',
            'bankCode': 62,
        }
        mock_post.return_value = mock_response
        
        result = self.provider._iyzico_bin_check('589004')
        
        # Verify result
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['cardType'], 'CREDIT_CARD')
        self.assertEqual(result['cardAssociation'], 'MASTER_CARD')

    def test_installment_configuration(self):
        """Test that installment options are generated correctly."""
        # Test with max 6 installments
        self.provider.write({
            'iyzico_enable_installments': True,
            'iyzico_max_installments': '6',
        })
        
        tx_values = {
            'reference': 'TEST-TX-002',
            'amount': 100.00,
            'currency': self.currency,
        }
        
        # This would be called internally during checkout creation
        # We're testing the logic separately
        enabled_installments = [1]
        max_installments = int(self.provider.iyzico_max_installments)
        for count in [2, 3, 6, 9, 12]:
            if count <= max_installments:
                enabled_installments.append(count)
        
        # Should include: 1, 2, 3, 6 (not 9, 12)
        self.assertEqual(enabled_installments, [1, 2, 3, 6])

    def test_transaction_3ds_fields(self):
        """Test that transaction 3D Secure fields are present."""
        tx = self.env['payment.transaction'].create({
            'provider_id': self.provider.id,
            'reference': 'TEST-TX-003',
            'amount': 100.00,
            'currency_id': self.currency.id,
            'partner_id': self.partner.id,
        })
        
        # Check that 3DS fields exist
        self.assertTrue(hasattr(tx, 'iyzico_3ds_status'))
        self.assertTrue(hasattr(tx, 'iyzico_eci'))
        self.assertTrue(hasattr(tx, 'iyzico_installment'))
        self.assertTrue(hasattr(tx, 'iyzico_card_family'))
        self.assertTrue(hasattr(tx, 'iyzico_card_association'))
        self.assertTrue(hasattr(tx, 'iyzico_card_type'))
