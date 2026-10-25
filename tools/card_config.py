import json
from pathlib import Path

CARDS_PATH = Path(__file__).resolve().parent.parent / "data" / "cards.json"


def load_cards() -> dict:
    """Load the card and UPI configuration from data/cards.json."""
    with open(CARDS_PATH, encoding="utf-8") as file:
        return json.load(file)


def all_payment_options() -> list[dict]:
    """Return every credit card and UPI option as one list, tagged with its type."""
    cards = load_cards()
    credit_cards = [{**card, "type": "credit_card"} for card in cards.get("credit_cards", [])]
    upi = [{**option, "type": "upi"} for option in cards.get("upi", [])]
    return credit_cards + upi


def get_option(payment_id: str) -> dict | None:
    for option in all_payment_options():
        if option["id"] == payment_id:
            return option
    return None
