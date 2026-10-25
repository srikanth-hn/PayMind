from datetime import date

from tools.card_config import get_option
from tools.db import VALID_CATEGORIES, insert_transaction
from tools.llm import ask
from tools.rewards import calculate_cashback

CLASSIFY_PROMPT = (
    "Classify an Indian merchant into exactly one spending category from this list: "
    + ", ".join(VALID_CATEGORIES)
    + ". Reply with the category word only."
)


def classify_category(merchant: str) -> str:
    answer = ask(CLASSIFY_PROMPT, f"Merchant: {merchant}", temperature=0).lower().strip(" .\n")
    return answer if answer in VALID_CATEGORIES else "other"


def log_expense(
    merchant: str,
    amount: float,
    payment_id: str,
    category: str | None = None,
    txn_date: str | None = None,
) -> dict:
    """Log one expense. If category is missing, the LLM detects it from the merchant name."""
    try:
        if not merchant.strip():
            raise ValueError("Enter a merchant name.")
        if amount <= 0:
            raise ValueError("Amount must be more than ₹0.")
        option = get_option(payment_id)
        if option is None:
            raise ValueError("Choose a valid card or UPI method.")

        detected = False
        if not category:
            category = classify_category(merchant)
            detected = True

        cashback = calculate_cashback(payment_id, merchant, amount, category)
        transaction_id = insert_transaction(
            date=txn_date or date.today().isoformat(),
            merchant=merchant.strip(),
            amount=round(amount, 2),
            category=category,
            payment_method=option["name"],
            payment_id=payment_id,
            cashback_earned=cashback,
        )
        category_note = f" (category detected: {category})" if detected else ""
        return {
            "status": "success",
            "transaction_id": transaction_id,
            "category": category,
            "cashback_earned": cashback,
            "message": (
                f"Logged ₹{amount:,.2f} at {merchant.strip()} on {option['name']}{category_note}. "
                f"Cashback earned: ₹{cashback:.2f}."
            ),
        }
    except Exception as error:
        return {"status": "error", "message": f"Couldn't log the expense: {error}"}
