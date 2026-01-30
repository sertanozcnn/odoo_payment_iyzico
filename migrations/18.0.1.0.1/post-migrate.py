# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""
Migration script to link payment methods to iyzico provider.

This migration is needed because:
1. The original XML data uses noupdate="1", so updates won't apply
2. Existing installations may not have the 'card' payment method linked
3. The payment method must be linked for the provider to appear on checkout
4. Payment method icons need to be set for proper display

This script runs after module upgrade and ensures proper configuration.
"""

import base64
import logging
import os

_logger = logging.getLogger(__name__)


def _get_image_as_base64(module_path, image_filename):
    """Read an image file and return its base64 encoded content.
    
    :param str module_path: The path to the module directory
    :param str image_filename: The name of the image file
    :return: Base64 encoded image content or None
    :rtype: str|None
    """
    try:
        image_path = os.path.join(module_path, 'static', 'description', image_filename)
        if os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                return base64.b64encode(f.read())
        _logger.warning("Image file not found: %s", image_path)
    except Exception as e:
        _logger.error("Failed to read image %s: %s", image_filename, e)
    return None


def migrate(cr, version):
    """Link the 'card' payment method to iyzico provider and set icons."""
    _logger.info("Running iyzico migration: linking payment methods and setting icons...")
    
    # Find all iyzico providers
    cr.execute("""
        SELECT id FROM payment_provider WHERE code = 'iyzico'
    """)
    provider_results = cr.fetchall()
    
    if not provider_results:
        _logger.warning("iyzico provider not found, skipping migration")
        return
    
    provider_ids = [r[0] for r in provider_results]
    _logger.info("Found %s iyzico providers: %s", len(provider_ids), provider_ids)
    
    # Find the 'card' payment method
    cr.execute("""
        SELECT id FROM payment_method WHERE code = 'card' LIMIT 1
    """)
    method_result = cr.fetchone()
    
    if not method_result:
        _logger.warning("Card payment method not found, skipping migration")
        return
    
    method_id = method_result[0]
    
    # Link card payment method to all iyzico providers
    for provider_id in provider_ids:
        cr.execute("""
            SELECT 1 FROM payment_method_payment_provider_rel 
            WHERE payment_method_id = %s AND payment_provider_id = %s
        """, (method_id, provider_id))
        
        if not cr.fetchone():
            cr.execute("""
                INSERT INTO payment_method_payment_provider_rel 
                (payment_method_id, payment_provider_id)
                VALUES (%s, %s)
            """, (method_id, provider_id))
            _logger.info("Linked card payment method to iyzico provider (id=%s)", provider_id)
    
    # Activate the card payment method if not active
    cr.execute("""
        UPDATE payment_method SET active = TRUE WHERE id = %s AND active = FALSE
    """, (method_id,))
    
    if cr.rowcount > 0:
        _logger.info("Activated card payment method")
    
    # CRITICAL FIX: Set is_published = True for test mode
    cr.execute("""
        UPDATE payment_provider 
        SET is_published = TRUE 
        WHERE code = 'iyzico' AND state IN ('test', 'enabled') AND is_published = FALSE
    """)
    
    if cr.rowcount > 0:
        _logger.info("Set iyzico providers to published (was unpublished)")
    
    # CRITICAL FIX: Remove country restrictions (allow all countries)
    cr.execute("""
        DELETE FROM payment_country_rel 
        WHERE payment_id IN (SELECT id FROM payment_provider WHERE code = 'iyzico')
    """)
    _logger.info("Removed country restrictions from iyzico providers (now accepts all countries)")
    
    # CRITICAL FIX: Remove currency restrictions (allow all currencies)
    cr.execute("""
        DELETE FROM payment_currency_rel 
        WHERE payment_provider_id IN (SELECT id FROM payment_provider WHERE code = 'iyzico')
    """)
    _logger.info("Removed currency restrictions from iyzico providers (now accepts all currencies)")
    
    # CRITICAL FIX: Set payment method icons
    # Get module path for loading images
    try:
        import odoo.addons.payment_iyzico as iyzico_module
        module_path = os.path.dirname(iyzico_module.__file__)
    except ImportError:
        _logger.warning("Could not determine module path, skipping icon updates")
        _logger.info("iyzico migration completed (with warnings)")
        return
    
    # Load checkout icon (64x64) for payment method
    checkout_icon_b64 = _get_image_as_base64(module_path, 'checkout_icon.png')
    
    if checkout_icon_b64:
        # Update the card payment method icon for iyzico
        cr.execute("""
            UPDATE payment_method
            SET image_payment_form = %s
            WHERE id = %s
        """, (checkout_icon_b64, method_id))
        if cr.rowcount > 0:
            _logger.info("Set checkout icon for card payment method (id=%s)", method_id)
        
        # Also check if there's a specific iyzico payment method and update it too
        cr.execute("""
            SELECT id FROM payment_method WHERE code LIKE 'iyzico%%' LIMIT 1
        """)
        iyzico_pm_result = cr.fetchone()
        if iyzico_pm_result:
            iyzico_pm_id = iyzico_pm_result[0]
            cr.execute("""
                UPDATE payment_method
                SET image_payment_form = %s
                WHERE id = %s
            """, (checkout_icon_b64, iyzico_pm_id))
            _logger.info("Set checkout icon for iyzico payment method (id=%s)", iyzico_pm_id)
    
    # Load provider icon (128x128) - note: provider icons are loaded from icon.png
    # This is automatically handled by Odoo for module icons
    
    _logger.info("iyzico migration completed successfully")
