import json
from datetime import date, timedelta

from tools.budget import DEFAULT_MONTHLY_BUDGET, check_budget
from tools.db import VALID_CATEGORIES, get_transactions
from tools.llm import ask, ask_json

PERIODS = ["today", "this_week", "this_month", "last_month", "all_time"]

PARSE_PROMPT = (
    "Extract filters from a question about personal spending. "
    'Return JSON: {"period": one of ' + json.dumps(PERIODS) + ', "category": one of '
    + json.dumps(VALID_CATEGORIES) + " or null}. "
    "Use this_month when no period is mentioned. Use null category when none is mentioned."
)

ANSWER_PROMPT = (
    "You are PayMind, a friendly spending analyst for a user in India. Answer the question in "
    "2-4 sentences using only the data provided. Show amounts as ₹ with 2 decimals. If there "
    "are no transactions for the period, say so and suggest logging some."
)


def date_range(period: str, today: date) -> tuple[str | None, str | None]:
    if period == "today":
        start = today
    elif period == "this_week":
        start = today - timedelta(days=today.weekday())
    elif period == "last_month":
        last_day = today.replace(day=1) - timedelta(days=1)
        return last_day.replace(day=1).isoformat(), last_day.isoformat()
    elif period == "all_time":
        return None, None
    else:
        start = today.replace(day=1)
    return start.isoformat(), today.isoformat()


def summarize(transactions: list[dict]) -> dict:
    category_totals: dict[str, float] = {}
    merchant_totals: dict[str, float] = {}
    for item in transactions:
        category_totals[item["category"]] = category_totals.get(item["category"], 0) + item["amount"]
        merchant_totals[item["merchant"]] = merchant_totals.get(item["merchant"], 0) + item["amount"]
    top_merchants = sorted(merchant_totals.items(), key=lambda pair: -pair[1])[:5]
    return {
        "total_spend": round(sum(item["amount"] for item in transactions), 2),
        "total_cashback": round(sum(item["cashback_earned"] for item in transactions), 2),
        "transaction_count": len(transactions),
        "category_totals": {key: round(value, 2) for key, value in category_totals.items()},
        "top_merchants": [{"merchant": name, "amount": round(total, 2)} for name, total in top_merchants],
    }


def analyze_spending(question: str, monthly_budget: float = DEFAULT_MONTHLY_BUDGET) -> dict:
    """Answer a natural-language spending question from SQLite data."""
    try:
        filters = ask_json(PARSE_PROMPT, f"Today is {date.today().isoformat()}. Question: {question}")
        period = filters.get("period") if filters.get("period") in PERIODS else "this_month"
        category = filters.get("category") if filters.get("category") in VALID_CATEGORIES else None

        today = date.today()
        start, end = date_range(period, today)
        transactions = get_transactions(start_date=start, end_date=end, category=category)
        stats = summarize(transactions)

        month_start, _ = date_range("this_month", today)
        month_total = sum(item["amount"] for item in get_transactions(month_start, today.isoformat()))
        budget = check_budget(month_total, monthly_budget)

        context = {
            "period": period,
            "date_range": f"{start or 'beginning'} to {end or 'today'}",
            "category_filter": category or "all categories",
            **stats,
            "this_month_budget": budget,
        }
        answer = ask(ANSWER_PROMPT, f"Question: {question}\nData: {json.dumps(context, ensure_ascii=False)}")
        return {"answer": answer, "period": period, "category": category, "budget": budget, **stats}
    except Exception as error:
        return {"answer": f"Sorry, I couldn't analyse that: {error}", "error": True, "category_totals": {}}
