# CLAUDE.md — PayMind Project Instructions

## What you are building
A personal finance assistant called **PayMind** that helps a user in India maximize credit card/UPI rewards and track spending. This is a portfolio project demonstrating fintech AI engineering skills for a Senior AI Engineer job application.

## Non-negotiable rules
- Never use placeholder/mock LLM calls. Always use a real LLM API.
- LLM provider is configurable via environment variables — support OpenRouter, Anthropic, or any OpenAI-compatible endpoint. Default to OpenRouter.
- Every LangGraph agent call must be traced via LangSmith.
- SQLite is the only database. No Postgres, no Redis, no external DBs.
- Streamlit is the only UI framework. No Flask, no FastAPI, no React.
- All code in a single repo, flat structure (no src/ subdirectory).
- Mobile-friendly UI: max content width 420px, centered, large touch targets.
- Never use `st.experimental_*` — use stable Streamlit APIs only.

---

## Project structure to create

```
paymind/
├── CLAUDE.md               # this file
├── README.md               # portfolio readme (see spec below)
├── requirements.txt
├── app.py                  # Streamlit entry point
├── agents/
│   ├── __init__.py
│   ├── graph.py            # LangGraph supervisor + agent graph
│   ├── payment_advisor.py  # Agent 1
│   ├── expense_tracker.py  # Agent 2
│   ├── spend_analyst.py    # Agent 3
│   └── offer_fetcher.py    # Agent 4
├── tools/
│   ├── __init__.py
│   ├── card_config.py      # loads card/UPI config JSON
│   ├── db.py               # SQLite read/write helpers
│   ├── rewards.py          # cashback calculation logic
│   └── budget.py           # budget threshold checker
├── data/
│   ├── cards.json          # card/UPI offer config
│   └── paymind.db          # SQLite DB (auto-created)
└── .env.example            # shows required env vars
```

---

## cards.json — exact structure to use

```json
{
  "upi": [
    {
      "id": "upi_sbi",
      "name": "SBI UPI",
      "bank": "SBI",
      "cashback_rules": [
        {"category": "food", "cashback_pct": 1.0},
        {"category": "default", "cashback_pct": 0.5}
      ],
      "max_cashback_per_txn": 50
    },
    {
      "id": "upi_hdfc",
      "name": "HDFC UPI",
      "bank": "HDFC",
      "cashback_rules": [
        {"category": "fuel", "cashback_pct": 2.0},
        {"category": "default", "cashback_pct": 0.5}
      ],
      "max_cashback_per_txn": 75
    },
    {
      "id": "upi_icici",
      "name": "ICICI UPI",
      "bank": "ICICI",
      "cashback_rules": [
        {"category": "default", "cashback_pct": 1.5}
      ],
      "max_cashback_per_txn": 100
    }
  ],
  "credit_cards": [
    {
      "id": "cc_hdfc_millennia",
      "name": "HDFC Millennia",
      "cashback_rules": [
        {"merchant_keywords": ["amazon", "flipkart"], "cashback_pct": 5.0},
        {"category": "default", "cashback_pct": 1.0}
      ],
      "annual_fee": 1000,
      "active_offers": [
        "5% cashback on Amazon & Flipkart (max ₹200/month)",
        "1% cashback on all other spends"
      ]
    },
    {
      "id": "cc_axis_flipkart",
      "name": "Axis Flipkart",
      "cashback_rules": [
        {"merchant_keywords": ["flipkart", "myntra"], "cashback_pct": 5.0},
        {"category": "default", "cashback_pct": 1.5}
      ],
      "annual_fee": 500,
      "active_offers": [
        "5% cashback on Flipkart & Myntra",
        "4% on preferred merchants",
        "1.5% unlimited cashback on all others"
      ]
    },
    {
      "id": "cc_sbi_simplyclick",
      "name": "SBI SimplyCLICK",
      "cashback_rules": [
        {"merchant_keywords": ["amazon"], "cashback_pct": 10.0},
        {"merchant_keywords": ["swiggy", "zomato", "bookmyshow", "cleartrip"], "cashback_pct": 5.0},
        {"category": "default", "cashback_pct": 1.25}
      ],
      "annual_fee": 499,
      "active_offers": [
        "10X reward points on Amazon",
        "5X reward points on Swiggy, Zomato, BookMyShow, Cleartrip",
        "1X on all other spends"
      ]
    },
    {
      "id": "cc_icici_coral",
      "name": "ICICI Coral",
      "cashback_rules": [
        {"category": "dining", "cashback_pct": 2.0},
        {"category": "groceries", "cashback_pct": 1.0},
        {"category": "default", "cashback_pct": 0.5}
      ],
      "annual_fee": 500,
      "active_offers": [
        "2% cashback on dining",
        "1% on groceries",
        "Buy 1 Get 1 on BookMyShow (2x/month)"
      ]
    }
  ]
}
```

---

## SQLite schema — create on startup

```sql
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    merchant TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT NOT NULL,
    payment_method TEXT NOT NULL,
    payment_id TEXT NOT NULL,
    cashback_earned REAL DEFAULT 0.0,
    notes TEXT DEFAULT ''
);
```

Valid categories: `food`, `fuel`, `shopping`, `dining`, `groceries`, `travel`, `entertainment`, `bills`, `health`, `other`

---

## LangGraph agent graph — exact design

### State schema
```python
class PayMindState(TypedDict):
    messages: Annotated[list, add_messages]
    intent: str          # "advise" | "log" | "analyze" | "offers"
    merchant: str
    amount: float
    category: str
    payment_used: str
    recommendation: dict
    analysis: str
    transactions: list
```

### Supervisor node
- Reads the latest user message
- Classifies intent into one of: `advise`, `log`, `analyze`, `offers`
- Routes to the appropriate agent node
- Uses an LLM call with a short system prompt — do NOT hardcode routing logic

### Agent nodes (one function each)
1. `payment_advisor_node` — calls PaymentAdvisorAgent
2. `expense_tracker_node` — calls ExpenseTrackerAgent
3. `spend_analyst_node` — calls SpendAnalystAgent
4. `offer_fetcher_node` — calls OfferFetcherAgent

### Edges
```
START → supervisor → [payment_advisor | expense_tracker | spend_analyst | offer_fetcher] → END
```

---

## Agent specifications

### Agent 1: Payment Advisor
**Input**: merchant name, amount (₹), category
**Logic**:
1. Load all cards and UPI options from cards.json
2. Calculate cashback for each option using merchant name matching + category matching
3. Rank by cashback amount earned on this transaction
4. Return top recommendation with full reasoning

**Output format** (return as dict):
```python
{
    "recommended": "HDFC Millennia",
    "payment_id": "cc_hdfc_millennia",
    "cashback_earned": 45.0,
    "reasoning": "HDFC Millennia gives 5% on Amazon purchases. On ₹900 you earn ₹45 cashback. Next best is SBI SimplyCLICK at ₹90 (10% on Amazon — actually use this instead if available).",
    "all_options": [
        {"name": "SBI SimplyCLICK", "cashback": 90.0},
        {"name": "HDFC Millennia", "cashback": 45.0},
        ...
    ]
}
```

The LLM's job here is to write natural language reasoning, not to do the math. Do the math in Python (rewards.py), pass the ranked results to the LLM for explanation.

### Agent 2: Expense Tracker
**Input**: merchant, amount, category, payment_method, payment_id
**Logic**:
1. Auto-detect category from merchant name if category not provided (use LLM)
2. Calculate cashback_earned using rewards.py
3. Insert into SQLite
4. Return confirmation with summary

### Agent 3: Spend Analyst
**Input**: natural language question (e.g. "how much did I spend on food this month?")
**Logic**:
1. Parse the question to extract time range + category filter
2. Query SQLite
3. Pass results to LLM for natural language answer
4. Also return structured data for charts

**Must handle these question types**:
- "How much did I spend on [category] this [month/week]?"
- "What's my total spend this month?"
- "Which merchant do I spend most on?"
- "Am I over budget?" (compare against hardcoded monthly budget of ₹30,000)
- "Show me my spending breakdown"

### Agent 4: Offer Fetcher
**Input**: optional category filter
**Logic**:
1. Load cards.json
2. Filter active_offers by category if provided
3. Format and return all relevant offers
4. LLM adds a short tip on which offer to prioritize today

---

## Streamlit UI — exact layout

```python
st.set_page_config(page_title="PayMind", page_icon="💳", layout="centered")

# Center and constrain width
st.markdown("""
<style>
.block-container { max-width: 420px; margin: 0 auto; padding: 1rem; }
.stButton button { width: 100%; border-radius: 12px; height: 48px; font-size: 16px; }
.stSelectbox, .stNumberInput, .stTextInput { font-size: 16px; }
</style>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["💳 Pay smart", "📝 Log", "📊 Spending", "🎁 Offers"])
```

### Tab 1 — Pay smart
- Text input: merchant name
- Number input: amount (₹)
- Selectbox: category (the valid categories list)
- Big "Find best payment →" button
- Output: show recommended card/UPI in a green success box, cashback earned highlighted, full ranked list in an expander

### Tab 2 — Log expense
- Text input: merchant
- Number input: amount
- Selectbox: category
- Selectbox: payment method used (populated from cards.json)
- "Log transaction" button
- Show success message with cashback earned

### Tab 3 — My spending
- Show 3 metric cards at top: Total this month | Cashback earned | Transactions count
- Bar chart: spending by category (use st.bar_chart)
- Text area: "Ask anything about your spending" + Submit button
- Show LLM answer below

### Tab 4 — Offers
- Show all active offers as cards (use st.container with border=True)
- Each card shows: card name, offer text, a tip from the LLM

---

## LangSmith integration

```python
from langsmith import traceable

# Wrap the main graph invocation
@traceable(name="PayMind Agent Run")
def run_graph(input_dict):
    return graph.invoke(input_dict)
```

Set these env vars (show in .env.example):
```
# LLM provider — defaults to OpenRouter (OpenAI-compatible)
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openai/gpt-4o-mini        # change to any OpenRouter model string

# If switching to Anthropic directly, set this instead:
# ANTHROPIC_API_KEY=
# LLM_PROVIDER=anthropic

# LangSmith observability
LANGSMITH_API_KEY=
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=paymind
```

Wire the LLM like this so switching providers is one env var change:
```python
import os
from langchain_openai import ChatOpenAI

def get_llm():
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL", "openai/gpt-4o-mini"),
        openai_api_key=os.getenv("OPENROUTER_API_KEY"),
        openai_api_base=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    )
```

---

## requirements.txt — exact packages

```
langchain
langchain-openai
langgraph
langsmith
streamlit
python-dotenv
```

`langchain-openai` works with OpenRouter, OpenAI, and any OpenAI-compatible endpoint — no separate Anthropic package needed unless switching providers.

---

## README.md — must include these sections

1. **What is PayMind** — 2 sentences
2. **Setup** — clone, pip install, set env vars, streamlit run app.py
3. **Architecture** — brief description of LangGraph supervisor + 4 agents
4. **Screenshots** — placeholder text "Add screenshots here"
5. **How this demonstrates fintech AI engineering skills** — write this section targeting a Senior AI Engineer role at a payment orchestration company. Cover: multi-agent orchestration, payment domain logic (cashback routing mirrors payment gateway routing), LLM observability with LangSmith, production-ready SQLite data layer, real-world India fintech context (UPI + credit cards)
6. **Future improvements** — GPT/Gemini comparison, bank SMS parsing for auto-logging, budget alerts via WhatsApp

---

## Error handling rules
- Every agent must have try/except and return a user-friendly error string on failure
- If ANTHROPIC_API_KEY is missing, show a clear st.error() message — do not crash
- If DB is empty on Tab 3, show "No transactions yet — log one first!" instead of an empty chart
- All amounts display with ₹ symbol and 2 decimal places

---

## Build order
Build in this exact order so each piece is testable:
1. `data/cards.json`
2. `tools/db.py` + SQLite init
3. `tools/card_config.py` + `tools/rewards.py`
4. `agents/payment_advisor.py` (test independently first)
5. `agents/expense_tracker.py`
6. `agents/spend_analyst.py`
7. `agents/offer_fetcher.py`
8. `agents/graph.py` (wire all agents into LangGraph)
9. `app.py` (Streamlit UI)
10. `README.md` + `requirements.txt` + `.env.example`

After each file, confirm it is complete before moving to the next.
# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---
Project-specific rules override the above when they conflict.
