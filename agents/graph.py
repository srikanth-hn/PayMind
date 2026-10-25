import json
from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langsmith import traceable

from agents.expense_tracker import log_expense
from agents.offer_fetcher import get_offers
from agents.payment_advisor import get_payment_recommendation
from agents.spend_analyst import analyze_spending
from tools.card_config import all_payment_options
from tools.db import VALID_CATEGORIES
from tools.llm import ask_json

INTENTS = ["advise", "log", "analyze", "offers"]


class PayMindState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    intent: str  # "advise" | "log" | "analyze" | "offers"
    merchant: str
    amount: float
    category: str
    payment_used: str  # payment_id of the card/UPI used
    recommendation: dict
    analysis: str
    transactions: list
    # Added for the UI: the user's selected methods, their budget, and the structured result.
    payment_ids: list
    monthly_budget: float
    result: dict


SUPERVISOR_PROMPT = (
    "You route requests for PayMind, a payments assistant for India.\n"
    "Intents:\n"
    "- advise: which card or UPI to pay with for a purchase\n"
    "- log: record an expense the user already made\n"
    "- analyze: questions about past spending, merchants or budget\n"
    "- offers: card or UPI offers and rewards available\n"
    "Also extract, if present: merchant (string), amount (number in rupees), category (one of "
    + json.dumps(VALID_CATEGORIES)
    + "), payment (name of the card or UPI the user paid with).\n"
    'Return JSON: {"intent": "...", "merchant": null, "amount": null, "category": null, "payment": null}'
)


def last_user_text(state: PayMindState) -> str:
    messages = state.get("messages", [])
    return str(messages[-1].content) if messages else ""


def resolve_payment(name: str, payment_ids: list | None) -> str | None:
    """Match a card/UPI name the user typed to one of their payment_ids."""
    name = name.lower()
    for option in all_payment_options():
        if payment_ids is not None and option["id"] not in payment_ids:
            continue
        if option["name"].lower() in name or name in option["name"].lower():
            return option["id"]
    return None


def supervisor_node(state: PayMindState) -> dict:
    # Forms in the UI already know the intent; free-text questions are classified by the LLM.
    if state.get("intent") in INTENTS:
        return {}
    try:
        data = ask_json(SUPERVISOR_PROMPT, last_user_text(state))
    except Exception as error:
        return {"intent": "error", "result": {"type": "error", "error": f"Couldn't understand the request: {error}"}}

    update: dict = {"intent": data.get("intent") if data.get("intent") in INTENTS else "analyze"}
    if data.get("merchant"):
        update["merchant"] = str(data["merchant"])
    if data.get("category") in VALID_CATEGORIES:
        update["category"] = data["category"]
    try:
        if data.get("amount") is not None:
            update["amount"] = float(data["amount"])
    except (TypeError, ValueError):
        pass
    if data.get("payment"):
        payment_id = resolve_payment(str(data["payment"]), state.get("payment_ids"))
        if payment_id:
            update["payment_used"] = payment_id
    return update


def route_intent(state: PayMindState) -> str:
    return state.get("intent", "error")


def payment_advisor_node(state: PayMindState) -> dict:
    try:
        if not state.get("merchant") or not state.get("amount"):
            return {"result": {"type": "advise", "error": "Tell me the merchant and the amount, e.g. 'Best card for ₹2000 on Amazon?'"}}
        recommendation = get_payment_recommendation(
            state["merchant"], state["amount"], state.get("category", "other"), state.get("payment_ids")
        )
        return {"recommendation": recommendation, "result": {"type": "advise", **recommendation}}
    except Exception as error:
        return {"result": {"type": "advise", "error": f"Payment advisor failed: {error}"}}


def expense_tracker_node(state: PayMindState) -> dict:
    try:
        if not state.get("merchant") or not state.get("amount"):
            return {"result": {"type": "log", "status": "error", "message": "Tell me the merchant and amount to log."}}
        if not state.get("payment_used"):
            return {"result": {"type": "log", "status": "error", "message": "Which card or UPI did you pay with? You can also use the Log tab."}}
        outcome = log_expense(
            state["merchant"], state["amount"], state["payment_used"], state.get("category")
        )
        return {"result": {"type": "log", **outcome}}
    except Exception as error:
        return {"result": {"type": "log", "status": "error", "message": f"Expense tracker failed: {error}"}}


def spend_analyst_node(state: PayMindState) -> dict:
    try:
        analysis = analyze_spending(last_user_text(state), state.get("monthly_budget", 30000))
        return {"analysis": analysis["answer"], "result": {"type": "analyze", **analysis}}
    except Exception as error:
        return {"result": {"type": "analyze", "answer": f"Spend analyst failed: {error}", "error": True}}


def offer_fetcher_node(state: PayMindState) -> dict:
    try:
        offers = get_offers(state.get("category"), state.get("payment_ids"))
        return {"result": {"type": "offers", **offers}}
    except Exception as error:
        return {"result": {"type": "offers", "cards": [], "error": f"Offer fetcher failed: {error}"}}


def create_graph():
    workflow = StateGraph(PayMindState)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("payment_advisor", payment_advisor_node)
    workflow.add_node("expense_tracker", expense_tracker_node)
    workflow.add_node("spend_analyst", spend_analyst_node)
    workflow.add_node("offer_fetcher", offer_fetcher_node)

    workflow.add_edge(START, "supervisor")
    workflow.add_conditional_edges(
        "supervisor",
        route_intent,
        {
            "advise": "payment_advisor",
            "log": "expense_tracker",
            "analyze": "spend_analyst",
            "offers": "offer_fetcher",
            "error": END,
        },
    )
    for node in ["payment_advisor", "expense_tracker", "spend_analyst", "offer_fetcher"]:
        workflow.add_edge(node, END)
    return workflow.compile()


graph = create_graph()


@traceable(name="PayMind Agent Run")
def run_graph(input_dict: dict) -> dict:
    """Run the graph and return its structured result. Traced in LangSmith."""
    state = dict(input_dict)
    if isinstance(state.get("messages"), str):
        state["messages"] = [HumanMessage(content=state["messages"])]
    try:
        final_state = graph.invoke(state)
        return final_state.get("result", {"type": "error", "error": "The agent returned no result."})
    except Exception as error:
        return {"type": "error", "error": f"Something went wrong: {error}"}
