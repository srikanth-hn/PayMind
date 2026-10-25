import json
import re
from pathlib import Path

DEALS_PATH = Path(__file__).resolve().parent.parent / "data" / "deals.json"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# ---------- data ----------

def load_deal_data() -> dict:
    with open(DEALS_PATH, encoding="utf-8") as file:
        return json.load(file)


def save_deal_data(data: dict) -> None:
    with open(DEALS_PATH, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def get_category(data: dict, category_id: str) -> dict:
    return next(category for category in data["categories"] if category["id"] == category_id)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


# ---------- matching ----------

def offer_applies(offer: dict, card: dict, amount: float, day: str) -> tuple[bool, str]:
    """Check one bank offer against a specific card, the amount and the day.

    Offers can target a bank ("any" for all banks), a card type, exact card names
    ("cards"), exclusions ("exclude_cards") and card networks ("networks").
    Returns (applies, reason if not).
    """
    if offer["bank"] not in ("any", card["bank"]):
        return False, "different bank"
    if offer["card_type"] != "any" and offer["card_type"] != card["type"]:
        return False, f"needs a {offer['card_type']} card"
    if card["type"] == "upi" and offer["card_type"] != "upi":
        return False, "not valid on UPI"
    if offer.get("cards") and card["name"] not in offer["cards"]:
        return False, f"only for {', '.join(offer['cards'])}"
    if card["name"] in offer.get("exclude_cards", []):
        return False, f"{card['name']} is excluded"
    if offer.get("networks") and card.get("network") not in offer["networks"]:
        return False, f"only on {'/'.join(offer['networks'])} cards"
    if amount < offer.get("min_bill", 0):
        return False, f"needs ₹{offer['min_bill']:,}+"
    if offer.get("days") and day not in offer["days"]:
        return False, f"only on {', '.join(offer['days'])}"
    return True, ""


def offer_discount(offer: dict, amount: float) -> float:
    if "flat" in offer:
        return min(float(offer["flat"]), amount)
    discount = amount * offer["pct"] / 100
    return min(discount, offer["cap"]) if offer.get("cap") else discount


def _worth_mentioning(offer: dict, card: dict, reason: str) -> bool:
    """Show a missed offer if it targets this card's bank, or if the card qualified for an
    any-bank offer and missed only on the amount or the day."""
    if offer["bank"] == card["bank"]:
        return True
    return offer["bank"] == "any" and (reason.startswith("needs ₹") or reason.endswith(tuple(DAYS)))


# ---------- calculation ----------

def evaluate(platform: dict, card: dict, price: float, day: str) -> dict:
    """Final cost of paying `price` on `platform` with `card`, with every discount stacked."""
    platform_discount = price * platform["discount_pct"] / 100
    if platform.get("discount_cap"):
        platform_discount = min(platform_discount, platform["discount_cap"])
    after_platform = price - platform_discount

    bank_discount, best_offer, missed = 0.0, None, []
    for offer in platform["bank_offers"]:
        applies, reason = offer_applies(offer, card, price, day)
        if applies:
            discount = offer_discount(offer, after_platform)
            if discount > bank_discount:
                bank_discount, best_offer = discount, offer
        elif _worth_mentioning(offer, card, reason):
            missed.append(f"{offer['label']}: {reason}")

    fee = after_platform * platform.get("fee_pct", 0) / 100 + platform.get("fee_flat", 0)
    pay_now = max(after_platform - bank_discount + fee, 0)
    rewards = pay_now * card["reward_value_pct"] / 100
    effective = pay_now - rewards
    return {
        "platform_id": platform["id"],
        "platform": platform["name"],
        "card_id": card["id"],
        "card": card["name"],
        "owner": card["owner"],
        "network": card.get("network", ""),
        "card_type": card["type"],
        "price": round(price, 2),
        "platform_discount": round(platform_discount, 2),
        "bank_discount": round(bank_discount, 2),
        "bank_offer": best_offer["label"] if best_offer else "",
        "fee": round(fee, 2),
        "pay_now": round(pay_now, 2),
        "rewards": round(rewards, 2),
        "effective_cost": round(effective, 2),
        "missed_offers": missed,
    }


def find_best_deals(
    category_id: str,
    prices: dict[str, float],
    day: str,
    card_ids: list[str],
) -> list[dict]:
    """Every app × card combination for a category, cheapest effective cost first.

    `prices` maps platform id → the price on that app; only those apps are compared.
    Savings are measured against the highest listed price, so they include price differences.
    """
    data = load_deal_data()
    category = get_category(data, category_id)
    cards = [card for card in data["household_cards"] if card["id"] in card_ids]
    platforms = [platform for platform in category["platforms"] if platform["id"] in prices]
    reference = max(prices.values()) if prices else 0
    results = []
    for platform in platforms:
        for card in cards:
            item = evaluate(platform, card, prices[platform["id"]], day)
            item["savings"] = round(reference - item["effective_cost"], 2)
            results.append(item)
    return sorted(results, key=lambda item: (item["effective_cost"], item["pay_now"]))


# ---------- editing ----------

def add_household_card(name: str, bank: str, card_type: str, network: str, owner: str, reward_value_pct: float) -> None:
    data = load_deal_data()
    card_id = f"{slug(name)}_{slug(owner)}"
    if any(card["id"] == card_id for card in data["household_cards"]):
        raise ValueError(f"{name} ({owner}) is already in your wallet.")
    data["household_cards"].append({
        "id": card_id, "name": name, "bank": bank, "type": card_type,
        "network": network, "owner": owner, "reward_value_pct": reward_value_pct,
    })
    save_deal_data(data)


def remove_household_card(card_id: str) -> None:
    data = load_deal_data()
    data["household_cards"] = [card for card in data["household_cards"] if card["id"] != card_id]
    save_deal_data(data)


def add_platform(category_id: str, name: str, discount_pct: float, discount_cap: float, fee_pct: float, fee_flat: float) -> None:
    data = load_deal_data()
    category = get_category(data, category_id)
    platform_id = slug(name)
    if any(platform["id"] == platform_id for platform in category["platforms"]):
        raise ValueError(f"{name} is already listed under {category['name']}.")
    category["platforms"].append({
        "id": platform_id, "name": name, "discount_pct": discount_pct, "discount_cap": discount_cap,
        "fee_pct": fee_pct, "fee_flat": fee_flat, "user_added": True, "bank_offers": [],
    })
    save_deal_data(data)


def remove_platform(category_id: str, platform_id: str) -> None:
    data = load_deal_data()
    category = get_category(data, category_id)
    category["platforms"] = [p for p in category["platforms"] if p["id"] != platform_id]
    save_deal_data(data)


def describe_offer(offer: dict) -> str:
    """Build a readable label like '15% off up to ₹750 with ICICI credit cards'."""
    value = f"₹{offer['flat']:,.0f} off" if "flat" in offer else f"{offer['pct']:g}% off"
    if "pct" in offer and offer.get("cap"):
        value += f" up to ₹{offer['cap']:,.0f}"
    if offer.get("cards"):
        who = ", ".join(offer["cards"])
    else:
        kind = "" if offer["card_type"] == "any" else f" {offer['card_type']}"
        network = f" {'/'.join(offer['networks'])}" if offer.get("networks") else ""
        if offer["bank"] == "UPI":
            who = "UPI"
        elif offer["bank"] == "any":
            who = f"any{network}{kind} card"
        else:
            who = f"{offer['bank']}{network}{kind} cards"
    label = f"{value} with {who}"
    if offer.get("min_bill"):
        label += f", min ₹{offer['min_bill']:,.0f}"
    if offer.get("days"):
        label += f", {'/'.join(offer['days'])} only"
    return label


def add_offer(category_id: str, platform_id: str, offer: dict) -> None:
    data = load_deal_data()
    platform = next(p for p in get_category(data, category_id)["platforms"] if p["id"] == platform_id)
    offer = {key: value for key, value in offer.items() if value not in (None, [], "")}
    offer.setdefault("cap", 0)
    offer.setdefault("min_bill", 0)
    offer.setdefault("days", [])
    offer["label"] = offer.get("label") or describe_offer(offer)
    offer["user_added"] = True
    platform["bank_offers"].append(offer)
    save_deal_data(data)


def remove_offer(category_id: str, platform_id: str, index: int) -> None:
    data = load_deal_data()
    platform = next(p for p in get_category(data, category_id)["platforms"] if p["id"] == platform_id)
    platform["bank_offers"].pop(index)
    save_deal_data(data)