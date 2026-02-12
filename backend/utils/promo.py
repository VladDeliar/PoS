from datetime import datetime

from .. import database
from ..utils.serializers import serialize_doc
from ..utils.demo_data import DEMO_PROMO_CODES


def validate_promo_code(code: str, order_total: float):
    """Validate promo code and return discount info or error"""
    if not database.connected or database.promo_codes is None:
        for promo in DEMO_PROMO_CODES:
            if promo["code"].upper() == code.upper() and promo.get("is_active"):
                return {"valid": True, "promo": promo}
        return {"valid": False, "error": "Промокод не знайдено"}

    promo = database.promo_codes.find_one({"code": code.upper()})
    if not promo:
        return {"valid": False, "error": "Промокод не знайдено"}

    if not promo.get("is_active"):
        return {"valid": False, "error": "Промокод неактивний"}

    now = datetime.utcnow()
    if promo.get("valid_from") and now < promo["valid_from"]:
        return {"valid": False, "error": "Промокод ще не активний"}

    if promo.get("valid_to") and now > promo["valid_to"]:
        return {"valid": False, "error": "Термін дії промокоду закінчився"}

    if promo.get("usage_limit") and promo.get("usage_count", 0) >= promo["usage_limit"]:
        return {"valid": False, "error": "Ліміт використання вичерпано"}

    if order_total < promo.get("min_order_amount", 0):
        return {"valid": False, "error": f"Мінімальна сума замовлення: {promo['min_order_amount']} грн"}

    return {"valid": True, "promo": serialize_doc(promo)}


def calculate_discount(promo: dict, order_total: float) -> float:
    """Calculate discount amount based on promo code"""
    if promo["discount_type"] == "percentage":
        return round(order_total * promo["discount_value"] / 100, 2)
    else:
        return min(promo["discount_value"], order_total)
