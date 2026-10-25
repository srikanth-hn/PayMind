from tools.card_config import all_payment_options, get_option


def _match_rule(option: dict, merchant: str, category: str) -> tuple[float, str]:
    """Pick the cashback % for one payment option.

    Priority: merchant keyword match (highest wins), then exact category, then default.
    """
    merchant_lower = merchant.lower()
    rules = option.get("cashback_rules", [])

    merchant_matches = [
        rule
        for rule in rules
        if any(keyword in merchant_lower for keyword in rule.get("merchant_keywords", []))
    ]
    if merchant_matches:
        best = max(merchant_matches, key=lambda rule: rule["cashback_pct"])
        return best["cashback_pct"], f"{best['cashback_pct']:g}% merchant offer on {merchant}"

    for rule in rules:
        if rule.get("category") == category:
            return rule["cashback_pct"], f"{rule['cashback_pct']:g}% on {category}"

    for rule in rules:
        if rule.get("category") == "default":
            return rule["cashback_pct"], f"{rule['cashback_pct']:g}% base rate"

    return 0.0, "no cashback"


def _cashback_for(option: dict, merchant: str, amount: float, category: str) -> dict:
    pct, rule = _match_rule(option, merchant, category)
    cashback = amount * pct / 100
    cap = option.get("max_cashback_per_txn")
    capped = cap is not None and cashback > cap
    if capped:
        cashback = float(cap)
        rule += f", capped at ₹{cap}"
    return {
        "payment_id": option["id"],
        "name": option["name"],
        "type": option["type"],
        "pct": pct,
        "cashback": round(cashback, 2),
        "rule": rule,
        "capped": capped,
    }


def calculate_cashback(payment_id: str, merchant: str, amount: float, category: str) -> float:
    option = get_option(payment_id)
    if option is None:
        return 0.0
    return _cashback_for(option, merchant, amount, category)["cashback"]


def rank_payment_options(
    merchant: str,
    amount: float,
    category: str,
    payment_ids: list[str] | None = None,
) -> list[dict]:
    """Return payment options sorted by cashback, best first.

    If payment_ids is given, only those options are compared.
    """
    options = all_payment_options()
    if payment_ids is not None:
        options = [option for option in options if option["id"] in payment_ids]
    results = [_cashback_for(option, merchant, amount, category) for option in options]
    return sorted(results, key=lambda item: (-item["cashback"], item["name"]))
