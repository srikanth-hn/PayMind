DEFAULT_MONTHLY_BUDGET = 30000.0
WARNING_THRESHOLD_PCT = 80


def check_budget(spent: float, budget: float = DEFAULT_MONTHLY_BUDGET) -> dict:
    """Compare spending against the monthly budget."""
    used_pct = (spent / budget * 100) if budget else 0.0
    if spent > budget:
        status = "over"
    elif used_pct >= WARNING_THRESHOLD_PCT:
        status = "warning"
    else:
        status = "ok"
    return {
        "status": status,
        "spent": round(spent, 2),
        "budget": round(budget, 2),
        "remaining": round(budget - spent, 2),
        "used_pct": round(used_pct, 1),
    }
