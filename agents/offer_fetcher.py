import json

from tools.card_config import all_payment_options
from tools.llm import ask_json

# Words that link an offer's text to a spending category.
CATEGORY_HINTS = {
    "shopping": ["amazon", "flipkart", "myntra", "shopping"],
    "dining": ["dining", "swiggy", "zomato"],
    "food": ["swiggy", "zomato", "dining", "food"],
    "entertainment": ["bookmyshow", "movie"],
    "travel": ["cleartrip", "travel", "flight"],
    "groceries": ["groceries", "grocery"],
    "fuel": ["fuel", "petrol"],
}

TIP_PROMPT = (
    "You are PayMind, a rewards advisor for India. Given the user's card offers, write a short, "
    "practical tip (max 20 words) for each card, and one overall tip on which offer to "
    "prioritise today. Use only the offers given. "
    'Return JSON: {"overall": "...", "tips": {"<card name>": "..."}}'
)


def offer_matches(offer: str, category: str) -> bool:
    text = offer.lower()
    return any(word in text for word in CATEGORY_HINTS.get(category, [category]))


def get_offers(category: str | None = None, payment_ids: list[str] | None = None) -> dict:
    """Return active offers (optionally filtered by category) plus LLM tips."""
    try:
        cards = []
        for option in all_payment_options():
            if payment_ids is not None and option["id"] not in payment_ids:
                continue
            offers = option.get("active_offers", [])
            if category:
                offers = [offer for offer in offers if offer_matches(offer, category)]
            if offers:
                cards.append({"payment_id": option["id"], "name": option["name"], "offers": offers})
    except Exception as error:
        return {"cards": [], "error": f"Couldn't load offers: {error}"}

    result = {"cards": cards, "overall_tip": "", "tips": {}}
    if not cards:
        return result
    try:
        offers_text = json.dumps({card["name"]: card["offers"] for card in cards}, ensure_ascii=False)
        tips = ask_json(TIP_PROMPT, f"Category focus: {category or 'any'}\nOffers: {offers_text}")
        result["overall_tip"] = str(tips.get("overall", ""))
        result["tips"] = {str(key): str(value) for key, value in tips.get("tips", {}).items()}
    except Exception as error:
        result["error"] = f"Couldn't generate tips: {error}"
    return result
