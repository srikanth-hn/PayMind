from tools.llm import ask
from tools.rewards import rank_payment_options

SYSTEM_PROMPT = (
    "You are PayMind, a payments advisor for India. In 2-3 short sentences, explain why the "
    "top option is the best way to pay, using only the numbers given. Mention the runner-up "
    "and how many rupees more the top option earns. Never invent offers, rates or numbers. "
    "Show amounts as ₹ with 2 decimals."
)


def get_payment_recommendation(
    merchant: str,
    amount: float,
    category: str,
    payment_ids: list[str] | None = None,
) -> dict:
    """Rank payment options in Python, then ask the LLM to explain the ranking."""
    try:
        options = rank_payment_options(merchant, amount, category, payment_ids)
    except Exception as error:
        return {"error": f"Couldn't calculate rewards: {error}", "all_options": []}

    if not options:
        return {
            "recommended": None,
            "payment_id": None,
            "cashback_earned": 0.0,
            "reasoning": "No payment methods are selected. Add some in Settings.",
            "all_options": [],
        }

    top = options[0]
    result = {
        "recommended": top["name"],
        "payment_id": top["payment_id"],
        "cashback_earned": top["cashback"],
        "reasoning": "",
        "all_options": [
            {"name": option["name"], "cashback": option["cashback"], "rule": option["rule"]}
            for option in options
        ],
    }

    ranked_lines = "\n".join(
        f"{position}. {option['name']}: ₹{option['cashback']:.2f} ({option['rule']})"
        for position, option in enumerate(options, start=1)
    )
    try:
        result["reasoning"] = ask(
            SYSTEM_PROMPT,
            f"Purchase: ₹{amount:.2f} at {merchant} (category: {category}).\n"
            f"Options ranked by cashback:\n{ranked_lines}",
        )
    except Exception as error:
        result["error"] = f"Couldn't generate the explanation: {error}"
    return result
