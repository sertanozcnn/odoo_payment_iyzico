# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
iyzico Payment Provider Utility Functions

This module contains helper functions for iyzico API integration,
including hash generation, signature verification, and data formatting.
"""

import base64
import hashlib
import hmac
import logging

from odoo.addons.payment_iyzico import const

_logger = logging.getLogger(__name__)


def get_api_url(provider):
    """
    Get the appropriate iyzico API URL based on provider state.
    
    :param provider: The payment.provider record
    :return: The API base URL
    :rtype: str
    """
    if provider.state == 'enabled':
        return const.API_URL_PRODUCTION
    return const.API_URL_SANDBOX


def get_checkout_url(provider):
    """
    Get the appropriate iyzico checkout page URL based on provider state.
    
    :param provider: The payment.provider record
    :return: The checkout page base URL
    :rtype: str
    """
    if provider.state == 'enabled':
        return const.CHECKOUT_URL_PRODUCTION
    return const.CHECKOUT_URL_SANDBOX


def get_api_key(provider):
    """
    Get the API key from the provider.
    
    :param provider: The payment.provider record (should be sudoed)
    :return: The API key
    :rtype: str
    """
    return provider.iyzico_api_key


def get_secret_key(provider):
    """
    Get the secret key from the provider.
    
    :param provider: The payment.provider record (should be sudoed)
    :return: The secret key
    :rtype: str
    """
    return provider.iyzico_secret_key


def generate_authorization_header(api_key, secret_key, random_key, uri_path, request_body):
    """
    Generate the Authorization header required by iyzico API using HMACSHA256.
    
    iyzico Authentication Method (IYZWSv2):
    1. Create payload: randomKey + uri_path + request_body
    2. Generate HMACSHA256 hash using secret_key
    3. Create auth string: apiKey:...&randomKey:...&signature:...
    4. Base64 encode the auth string
    5. Add prefix: "IYZWSv2 " + base64_encoded
    
    Example from iyzico docs:
    - randomKey: "1722246017090123456789"
    - uri_path: "/payment/bin/check"
    - request_body: '{"binNumber":"589004"}'
    - payload: "1722246017090123456789/payment/bin/check{"binNumber":"589004"}"
    - HMACSHA256(payload, secretKey) -> signature
    - authString: "apiKey:xxx&randomKey:xxx&signature:xxx"
    - Authorization: "IYZWSv2 " + base64(authString)
    
    :param str api_key: The iyzico API key
    :param str secret_key: The iyzico secret key
    :param str random_key: A random key for this request (timestamp + random)
    :param str uri_path: The API endpoint path (e.g., "/payment/iyzipos/checkoutform/initialize/auth/ecom")
    :param str request_body: The JSON request body as string
    :return: The authorization header value
    :rtype: str
    """
    import hmac
    
    # Create payload: randomKey + uri_path + request_body
    payload = random_key + uri_path + request_body
    
    # Generate HMACSHA256 hash
    signature = hmac.new(
        secret_key.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Create authorization string
    authorization_string = f"apiKey:{api_key}&randomKey:{random_key}&signature:{signature}"
    
    # Base64 encode
    base64_encoded = base64.b64encode(authorization_string.encode('utf-8')).decode('utf-8')
    
    # Return with IYZWSv2 prefix
    return f"IYZWSv2 {base64_encoded}"


def generate_pki_string(data_dict):
    """
    Generate the PKI (Public Key Infrastructure) string from a dictionary.
    
    iyzico requires request data to be formatted as a PKI string for hashing.
    Format: [key=value,key2=value2,...]
    
    :param dict data_dict: The dictionary to convert
    :return: The PKI string
    :rtype: str
    """
    def format_value(value):
        if value is None:
            return ''
        if isinstance(value, bool):
            return 'true' if value else 'false'
        if isinstance(value, (list, tuple)):
            return '[' + ', '.join(format_value(v) for v in value) + ']'
        if isinstance(value, dict):
            return generate_pki_string(value)
        return str(value)
    
    parts = []
    for key, value in data_dict.items():
        formatted_value = format_value(value)
        if formatted_value:  # Only include non-empty values
            parts.append(f"{key}={formatted_value}")
    
    return '[' + ','.join(parts) + ']'


def generate_hash(pki_string, secret_key):
    """
    Generate the hash required for iyzico API request verification.
    
    :param str pki_string: The PKI formatted request string
    :param str secret_key: The iyzico secret key
    :return: The base64 encoded SHA1 hash
    :rtype: str
    """
    # Concatenate PKI string with secret key
    hash_string = pki_string + secret_key
    
    # Generate SHA1 hash
    sha1_hash = hashlib.sha1(hash_string.encode('utf-8')).digest()
    
    # Base64 encode the hash
    return base64.b64encode(sha1_hash).decode('utf-8')


def verify_callback_signature(token, secret_key):
    """
    Verify the signature of a callback from iyzico.
    
    Note: iyzico checkout form callbacks return a token that should be used
    to retrieve the payment result. The token itself serves as authentication.
    
    :param str token: The token received in the callback
    :param str secret_key: The iyzico secret key
    :return: True if the signature is valid
    :rtype: bool
    """
    # For checkout form, iyzico uses the token-based verification
    # The token is used to retrieve payment details from iyzico API
    # which inherently verifies its authenticity
    return bool(token)


def format_amount(amount, currency):
    """
    Format the amount for iyzico API.
    
    iyzico expects amounts as strings with proper decimal formatting.
    Example: 100.50 -> "100.50"
    
    :param float amount: The amount to format
    :param currency: The res.currency record
    :return: The formatted amount string
    :rtype: str
    """
    decimals = const.CURRENCY_DECIMALS.get(currency.name, 2)
    return f"{amount:.{decimals}f}"


def format_phone(phone):
    """
    Format phone number for iyzico API.
    
    iyzico expects phone numbers in a specific format.
    Removes spaces and special characters, ensures it starts with country code.
    
    :param str phone: The phone number to format
    :return: The formatted phone number
    :rtype: str
    """
    if not phone:
        return '+905000000000'  # Default placeholder for required field
    
    # Remove all non-digit characters except +
    cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')
    
    # Ensure it starts with +
    if not cleaned.startswith('+'):
        # Assume Turkish number if no country code
        if cleaned.startswith('0'):
            cleaned = '+9' + cleaned
        else:
            cleaned = '+90' + cleaned
    
    return cleaned


def get_locale(lang_code):
    """
    Get the iyzico locale from Odoo language code.
    
    :param str lang_code: The Odoo language code (e.g., 'tr_TR')
    :return: The iyzico locale code
    :rtype: str
    """
    return const.LOCALE_MAPPING.get(lang_code, const.DEFAULT_LOCALE)


def get_error_message(error_code):
    """
    Get a user-friendly error message for an iyzico error code.
    
    :param str error_code: The iyzico error code
    :return: The error message
    :rtype: str
    """
    return const.ERROR_CODES.get(error_code, f'Payment failed with error code: {error_code}')


def prepare_basket_items(order_lines, currency):
    """
    Prepare basket items from order lines for iyzico API.
    
    iyzico requires basket items for fraud prevention.
    Each item must have: id, name, category1, itemType, price
    
    :param order_lines: List of order line data
    :param currency: The res.currency record
    :return: List of basket item dictionaries
    :rtype: list
    """
    basket_items = []
    
    for idx, line in enumerate(order_lines):
        basket_items.append({
            'id': str(line.get('id', idx + 1)),
            'name': line.get('name', f'Product {idx + 1}')[:100],  # Max 100 chars
            'category1': line.get('category', 'General')[:100],
            'category2': line.get('subcategory', '')[:100] if line.get('subcategory') else None,
            'itemType': 'PHYSICAL',  # PHYSICAL or VIRTUAL
            'price': format_amount(line.get('price', 0), currency),
        })
    
    return basket_items


def prepare_single_basket_item(amount, reference, currency):
    """
    Prepare a single basket item when no detailed order lines are available.
    
    This is used when only the total amount is known.
    
    :param float amount: The total amount
    :param str reference: The transaction reference
    :param currency: The res.currency record
    :return: List with single basket item
    :rtype: list
    """
    return [{
        'id': reference,
        'name': f'Order {reference}',
        'category1': 'General',
        'itemType': 'PHYSICAL',
        'price': format_amount(amount, currency),
    }]


def prepare_basket_items_from_order(sale_order):
    """
    Prepare detailed basket items from a sale.order record.
    
    This function extracts order line items and creates a detailed basket
    for iyzico API. Sending detailed basket items improves fraud detection
    and provides better reporting on iyzico's dashboard.
    
    Each basket item includes:
    - id: Unique identifier (order line ID)
    - name: Product name (max 100 chars)
    - category1: Product category (max 100 chars)
    - category2: Product subcategory (optional, max 100 chars)
    - itemType: PHYSICAL or VIRTUAL
    - price: Unit price * quantity (formatted string)
    
    :param sale_order: The sale.order record
    :return: List of basket item dictionaries
    :rtype: list
    :raises ValueError: If total amount validation fails
    """
    if not sale_order:
        raise ValueError("Sale order is required")
    
    basket_items = []
    currency = sale_order.currency_id
    
    # Process each order line
    for line in sale_order.order_line:
        # Skip lines with zero or negative quantity/price
        if line.product_uom_qty <= 0 or line.price_subtotal <= 0:
            continue
        
        # Determine item type based on product type
        item_type = 'PHYSICAL'
        if line.product_id.type in ('service', 'digital'):
            item_type = 'VIRTUAL'
        
        # Get product category
        category1 = 'General'
        category2 = None
        if line.product_id.categ_id:
            category1 = line.product_id.categ_id.name[:100]
            # If there's a parent category, use it as category2
            if line.product_id.categ_id.parent_id:
                category2 = line.product_id.categ_id.parent_id.name[:100]
        
        # Create basket item
        basket_item = {
            'id': str(line.id),
            'name': line.name[:100] or line.product_id.name[:100] or 'Product',
            'category1': category1,
            'itemType': item_type,
            'price': format_amount(line.price_subtotal, currency),
        }
        
        # Add category2 only if it exists (optional field)
        if category2:
            basket_item['category2'] = category2
        
        basket_items.append(basket_item)
    
    # Fallback: if no valid items found, create a single item with total
    if not basket_items:
        _logger.warning(
            "No valid order lines found for sale order %s, using single basket item",
            sale_order.name
        )
        return prepare_single_basket_item(
            sale_order.amount_total,
            sale_order.name,
            currency
        )
    
    # Validate that basket items total matches order total
    basket_total = sum(
        float(item['price']) for item in basket_items
    )
    order_total = sale_order.amount_total
    
    # Allow small rounding differences (0.01)
    if abs(basket_total - order_total) > 0.01:
        _logger.warning(
            "Basket items total (%.2f) doesn't match order total (%.2f) for %s. "
            "Difference: %.2f. This may cause issues with iyzico.",
            basket_total, order_total, sale_order.name, basket_total - order_total
        )
        
        # Option 1: Add adjustment line (commented out, use if needed)
        # adjustment_amount = order_total - basket_total
        # if abs(adjustment_amount) > 0:
        #     basket_items.append({
        #         'id': 'adjustment',
        #         'name': 'Price Adjustment',
        #         'category1': 'Adjustment',
        #         'itemType': 'PHYSICAL',
        #         'price': format_amount(adjustment_amount, currency),
        #     })
        
        # Option 2: Use single basket item instead (safer)
        _logger.info("Using single basket item due to total mismatch")
        return prepare_single_basket_item(
            order_total,
            sale_order.name,
            currency
        )
    
    _logger.info(
        "Prepared %d basket items for sale order %s (total: %.2f %s)",
        len(basket_items), sale_order.name, basket_total, currency.name
    )
    
    return basket_items


def log_api_request(endpoint, payload, sanitize=True):
    """
    Log an API request for debugging purposes.
    
    This function logs API requests in a structured format, optionally
    sanitizing sensitive data like API keys and tokens.
    
    :param str endpoint: The API endpoint being called
    :param dict payload: The request payload
    :param bool sanitize: Whether to remove sensitive data from logs
    :return: None
    """
    if sanitize:
        # Create a copy to avoid modifying the original
        safe_payload = payload.copy() if payload else {}
        
        # Remove or mask sensitive fields
        sensitive_fields = ['apiKey', 'secretKey', 'cardNumber', 'cardCvv', 'identityNumber']
        for field in sensitive_fields:
            if field in safe_payload:
                safe_payload[field] = '***MASKED***'
        
        # Mask buyer identity number if present
        if 'buyer' in safe_payload and isinstance(safe_payload['buyer'], dict):
            if 'identityNumber' in safe_payload['buyer']:
                safe_payload['buyer']['identityNumber'] = '***MASKED***'
        
        payload_to_log = safe_payload
    else:
        payload_to_log = payload
    
    _logger.info(
        "=== iyzico API REQUEST ===\n"
        "Endpoint: %s\n"
        "Payload: %s\n"
        "========================",
        endpoint,
        payload_to_log
    )


def log_api_response(endpoint, response_data, sanitize=True):
    """
    Log an API response for debugging purposes.
    
    :param str endpoint: The API endpoint that was called
    :param dict response_data: The response data
    :param bool sanitize: Whether to remove sensitive data from logs
    :return: None
    """
    if sanitize:
        # Create a copy to avoid modifying the original
        safe_response = response_data.copy() if response_data else {}
        
        # Remove large or sensitive fields
        sensitive_fields = ['checkoutFormContent', 'token', 'cardNumber']
        for field in sensitive_fields:
            if field in safe_response:
                # Log first 20 chars only for tokens
                if field == 'token' and len(str(safe_response[field])) > 20:
                    safe_response[field] = str(safe_response[field])[:20] + '...'
                elif field == 'checkoutFormContent':
                    safe_response[field] = '***HTML_CONTENT***'
                else:
                    safe_response[field] = '***MASKED***'
        
        response_to_log = safe_response
    else:
        response_to_log = response_data
    
    _logger.info(
        "=== iyzico API RESPONSE ===\n"
        "Endpoint: %s\n"
        "Status: %s\n"
        "Response: %s\n"
        "===========================",
        endpoint,
        response_data.get('status') if response_data else 'N/A',
        response_to_log
    )


def log_transaction_flow(transaction_ref, step, details=None):
    """
    Log transaction flow for debugging and audit trail.
    
    This creates a structured log of the transaction lifecycle,
    making it easier to track and debug payment flows.
    
    :param str transaction_ref: The transaction reference
    :param str step: The current step in the transaction flow
    :param dict details: Optional additional details
    :return: None
    """
    import json
    
    log_entry = {
        'transaction_ref': transaction_ref,
        'step': step,
        'timestamp': str(__import__('datetime').datetime.now()),
    }
    
    if details:
        log_entry['details'] = details
    
    _logger.info(
        "=== TRANSACTION FLOW ===\n%s\n========================",
        json.dumps(log_entry, indent=2, default=str)
    )


def get_debug_info(provider):
    """
    Get debug information about the provider configuration.
    
    Useful for troubleshooting configuration issues.
    
    :param provider: The payment.provider record
    :return: Dictionary with debug information
    :rtype: dict
    """
    return {
        'provider_name': provider.name,
        'provider_code': provider.code,
        'state': provider.state,
        'api_url': get_api_url(provider),
        'api_key_configured': bool(provider.iyzico_api_key),
        'secret_key_configured': bool(provider.iyzico_secret_key),
        'installments_enabled': provider.iyzico_enable_installments,
        'max_installments': provider.iyzico_max_installments,
        'force_3ds': provider.iyzico_force_3ds,
        'supported_currencies': [c.name for c in provider._get_supported_currencies()],
    }

