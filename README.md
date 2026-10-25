# 💳 PayMind

PayMind is a multi-agent personal finance assistant that tells you which credit card or UPI method to use for each purchase in India, logs your spending and answers questions about it in plain English. It does the reward maths deterministically in Python and uses an LLM only for routing, categorising and explaining, so the numbers are always exact.

## Setup

```bash
git clone https://github.com/srikanth-hn/paymind.git
cd paymind
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # then add your OpenRouter and LangSmith keys
streamlit run app.py
```

Open the app on **💸 Best deal** and click **Find the best way to pay**. For the agent features, go to **📊 Spending → Add 10 sample transactions**, then try **🤖 Ask PayMind**.

## Best deal: the cheapest way to pay any bill

Pick what you're paying for (🍽️ restaurant bill, 🎬 movie tickets, 🚌 bus, ✈️ flights) and PayMind compares every app against every card in your household, with all offers stacked:

**final cost = app price − app discount − bank offer + fees − card rewards**

- **Standard apps per category** (EazyDiner, District, Swiggy Dineout, BookMyShow, redBus, AbhiBus, MakeMyTrip, Cleartrip, ixigo and more), plus any app you add yourself.
- **Card-level offer matching**: offers can target a bank, exact cards ("Axis Atlas only"), exclusions ("excl. Atlas"), networks ("RuPay credit cards"), card type, minimum amount and days of the week. Both % (with caps) and flat ₹ discounts.
- **Different prices per app** for bus and flights, so savings include price differences, not just offers.
- **Household wallet**: cards tagged by owner, so the answer says whose card to use.
- **Explainable**: a step-by-step breakdown, a savings chart, the top 5 options and the offers you just missed. An LLM adds a two-sentence explanation.
- **Log this payment** records the winner in Spending, with the amount saved.

Apps, offers and cards live in `data/deals.json` (sample data for the demo) and can be edited in the app. The engine is `tools/deals.py`.

## Architecture

```
            ┌──────────────┐
 user ──▶   │  Supervisor  │  LLM classifies intent + extracts merchant / amount / card
            └──────┬───────┘
   ┌───────────────┼────────────────┬────────────────┐
   ▼               ▼                ▼                ▼
Payment        Expense          Spend            Offer
Advisor        Tracker          Analyst          Fetcher
(rank + LLM    (LLM category    (LLM parses      (filter offers
 explanation)   + SQLite write)  question → SQL   + LLM tips)
                                 → LLM answer)
```

- **LangGraph** `StateGraph`: `START → supervisor → one of 4 agents → END`.
- Form-based tabs pass a known intent; the free-text **Ask PayMind** box lets the supervisor agent route the request itself.
- **tools/** holds the deterministic layer: card config, SQLite helpers, reward engine and budget checks.
- Every run is wrapped in `@traceable` and traced in **LangSmith**.

| Folder | What it contains |
|---|---|
| `agents/` | `graph.py` (supervisor + routing), one file per agent |
| `tools/` | `rewards.py`, `db.py`, `card_config.py`, `budget.py`, `llm.py` |
| `data/` | `cards.json` (card and UPI rules), `paymind.db` (auto-created) |

## Screenshots

Add screenshots here

## How this demonstrates fintech AI engineering skills

- **Multi-agent orchestration.** A LangGraph supervisor routes natural-language requests to specialised agents with typed shared state, the same pattern used to split payments workflows into routing, ledger and analytics services.
- **Payment domain logic.** Choosing the best card for a transaction is a small version of payment gateway routing: evaluate every available rail against rules (merchant match, category, per-transaction caps) and pick the best outcome. The ranking is deterministic and testable; the LLM never does the maths.
- **LLM observability.** Every agent run is traced in LangSmith, so each routing decision, prompt and latency can be inspected and debugged.
- **Reliable data layer.** SQLite with a fixed schema, parameterised queries and transactional writes keeps every logged expense consistent.
- **Real India fintech context.** UPI and Indian credit cards with real-world reward structures (merchant multipliers, category cashback, per-transaction caps).
- **Graceful failure.** If the LLM is down or unconfigured, reward calculations still work and every agent returns a clear error instead of crashing.

## Future improvements

- Compare GPT, Gemini and Claude on routing accuracy and cost with a small eval set
- Parse bank SMS messages to log expenses automatically
- Budget alerts via WhatsApp
- Extract offers from app screenshots with a vision model, so the offer data stays current
- Extend Best deal to movies, bus and flights (same data model, new offer files)
- Monthly reward caps (e.g. "max ₹200/month") tracked across transactions