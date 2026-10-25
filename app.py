import html
from datetime import date, timedelta

from dotenv import load_dotenv

load_dotenv(override=True)  # .env wins over stale shell variables; must run before LangChain/LangSmith read the environment

import altair as alt
import streamlit as st

from agents.graph import run_graph
from tools.card_config import all_payment_options
from tools.db import VALID_CATEGORIES, get_transactions, init_db, insert_transaction
from tools.deals import (
    DAYS,
    add_household_card,
    add_offer,
    add_platform,
    find_best_deals,
    get_category,
    load_deal_data,
    remove_household_card,
    remove_offer,
    remove_platform,
)
from tools.llm import ask, get_api_key
from tools.rewards import calculate_cashback

AUTO_CATEGORY = "Auto-detect with AI"
BANK_COLORS = {
    "Axis": ("#97144D", "#5E0D31"),
    "ICICI": ("#B3541E", "#7A3612"),
    "SBI": ("#1F4E9E", "#123268"),
    "HDFC": ("#0B4F8C", "#06315A"),
    "Federal": ("#1D6B5A", "#0F4438"),
    "Kotak": ("#C8102E", "#7E0A1D"),
    "UPI": ("#3C4A44", "#222B27"),
}
DEFAULT_BANK_COLOR = ("#3D4E66", "#232E3E")
EXAMPLE_QUESTIONS = [
    "Am I over budget?",
    "How much did I spend on shopping this month?",
    "Which merchant do I spend most on?",
    "Best card for ₹3000 on Flipkart?",
    "Log 300 at Swiggy with SimplyCLICK",
]
SAMPLE_TRANSACTIONS = [
    (0, "Amazon", 2499.0, "shopping", "cc_sbi_simplyclick"),
    (1, "Swiggy", 640.0, "dining", "cc_sbi_simplyclick"),
    (2, "BigBasket", 1850.0, "groceries", "cc_icici_coral"),
    (3, "Indian Oil", 2000.0, "fuel", "upi_hdfc"),
    (4, "Flipkart", 3299.0, "shopping", "cc_axis_flipkart"),
    (5, "Zomato", 520.0, "dining", "cc_sbi_simplyclick"),
    (6, "Airtel", 799.0, "bills", "upi_icici"),
    (7, "Apollo Pharmacy", 460.0, "health", "upi_sbi"),
    (8, "BookMyShow", 700.0, "entertainment", "cc_icici_coral"),
    (9, "Myntra", 1599.0, "shopping", "cc_axis_flipkart"),
]
DEAL_PROMPT = (
    "You are PayMind. In 2 short sentences, tell the user how to pay and why it wins over the "
    "runner-up, using only the numbers given. Mention whose card it is. Amounts in ₹ with 2 decimals."
)

CSS = """
<style>
:root {
  --pm-ink: #16211C; --pm-muted: #5D6B64; --pm-line: #D9E2DC; --pm-surface: #FFFFFF;
  --pm-brand: #0B7A5E; --pm-brand-deep: #08503E; --pm-brand-soft: #E3F2EC;
  --pm-gold: #F2C14E; --pm-warn: #B4541A;
}
.block-container { max-width: 1180px; padding-top: 3.6rem; padding-bottom: 3rem; }
.stButton button, .stFormSubmitButton button { border-radius: 12px; min-height: 46px; font-weight: 600; }
h1, h2, h3 { letter-spacing: -0.01em; }

.pm-header { display:flex; flex-wrap:wrap; align-items:flex-end; justify-content:space-between; gap:12px;
  padding: 4px 0 14px; border-bottom: 1px solid var(--pm-line); margin-bottom: 6px; }
.pm-brand { font-size: 1.9rem; font-weight: 800; color: var(--pm-ink); line-height:1; }
.pm-brand span { color: var(--pm-brand); }
.pm-tag { color: var(--pm-muted); margin-top: 6px; font-size: 0.98rem; }
.pm-stats { display:flex; gap:8px; flex-wrap:wrap; }
.pm-stat { background: var(--pm-surface); border:1px solid var(--pm-line); border-radius: 999px;
  padding: 6px 12px; font-size: 0.85rem; color: var(--pm-muted); }
.pm-stat b { color: var(--pm-ink); }

.pm-best { background: linear-gradient(135deg, var(--pm-brand) 0%, var(--pm-brand-deep) 100%);
  color: #fff; border-radius: 18px; padding: 22px 22px 18px; margin-bottom: 12px; }
.pm-eyebrow { font-size: 0.75rem; letter-spacing: 0.12em; text-transform: uppercase; opacity: 0.8; }
.pm-best-title { font-size: 1.55rem; font-weight: 800; margin: 6px 0 2px; line-height: 1.2; }
.pm-best-title em { font-style: normal; opacity: 0.7; font-weight: 500; }
.pm-best-sub { opacity: 0.85; font-size: 0.95rem; }
.pm-figs { display:flex; flex-wrap:wrap; gap:10px; margin: 16px 0 12px; }
.pm-fig { background: rgba(255,255,255,0.12); border-radius: 12px; padding: 10px 14px; min-width: 120px; flex:1; }
.pm-fig small { display:block; opacity: 0.8; font-size: 0.78rem; }
.pm-fig b { font-size: 1.25rem; font-variant-numeric: tabular-nums; }
.pm-fig.save { background: var(--pm-gold); color: #2B2100; }
.pm-fig.save small { opacity: 0.75; }
.pm-chips { display:flex; flex-wrap:wrap; gap:6px; }
.pm-chip { background: rgba(255,255,255,0.16); border-radius: 999px; padding: 4px 10px; font-size: 0.8rem; }

.pm-card { background: var(--pm-surface); border: 1px solid var(--pm-line); border-radius: 14px; padding: 14px 16px; }
.pm-card h4 { margin: 0 0 8px; font-size: 0.95rem; color: var(--pm-ink); }
.pm-line { display:flex; justify-content:space-between; gap:12px; padding: 5px 0; font-size: 0.92rem;
  color: var(--pm-ink); border-bottom: 1px dashed var(--pm-line); font-variant-numeric: tabular-nums; }
.pm-line:last-child { border-bottom: none; }
.pm-line.minus span:last-child { color: var(--pm-brand); }
.pm-line.plus span:last-child { color: var(--pm-warn); }
.pm-line.total { font-weight: 700; }

.pm-rank { display:flex; align-items:center; gap:12px; background: var(--pm-surface); border:1px solid var(--pm-line);
  border-radius: 12px; padding: 10px 12px; margin-bottom: 8px; }
.pm-rank .n { width: 28px; height: 28px; border-radius: 50%; background: var(--pm-brand-soft); color: var(--pm-brand-deep);
  display:flex; align-items:center; justify-content:center; font-weight: 700; font-size: 0.85rem; flex:none; }
.pm-rank.first .n { background: var(--pm-brand); color: #fff; }
.pm-rank .who { flex:1; min-width:0; }
.pm-rank .who b { color: var(--pm-ink); font-size: 0.95rem; }
.pm-rank .who small { display:block; color: var(--pm-muted); font-size: 0.8rem; overflow:hidden; text-overflow: ellipsis; white-space: nowrap; }
.pm-rank .amt { text-align:right; font-variant-numeric: tabular-nums; color: var(--pm-ink); font-weight: 700; }
.pm-rank .amt small { display:block; color: var(--pm-brand); font-weight: 600; font-size: 0.78rem; }

.pm-empty { border: 2px dashed var(--pm-line); border-radius: 18px; padding: 40px 24px; text-align:center; color: var(--pm-muted); }
.pm-empty b { display:block; color: var(--pm-ink); font-size: 1.1rem; margin-bottom: 6px; }

.pm-wallet { display:grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 14px; margin: 6px 0 18px; }
.pm-cc { border-radius: 16px; padding: 16px; color: #fff; min-height: 128px; display:flex; flex-direction:column;
  justify-content:space-between; box-shadow: 0 6px 16px rgba(22,33,28,0.12); }
.pm-cc .top { display:flex; justify-content:space-between; font-size: 0.78rem; opacity: 0.85; text-transform: uppercase; letter-spacing: 0.08em; }
.pm-cc .name { font-size: 1.15rem; font-weight: 700; }
.pm-cc .bottom { display:flex; justify-content:space-between; font-size: 0.82rem; opacity: 0.9; }
.pm-owner { font-weight: 700; color: var(--pm-ink); margin: 10px 0 2px; }

.pm-badge { display:inline-block; background: var(--pm-brand-soft); color: var(--pm-brand-deep); border-radius: 999px;
  padding: 2px 9px; font-size: 0.76rem; margin: 0 4px 4px 0; }
.pm-badge.fee { background: #FBEEE4; color: var(--pm-warn); }
.pm-badge.mine { background: #FFF5D6; color: #6B5200; }
.pm-offer { font-size: 0.9rem; color: var(--pm-ink); padding: 3px 0; }
</style>
"""


def esc(value) -> str:
    return html.escape(str(value))


def money(value: float) -> str:
    return f"₹{value:,.2f}"


def category_label(category: dict) -> str:
    return f"{category['icon']} {category['name']}"


# ---------- header ----------

def render_header(data: dict) -> None:
    owners = sorted({card["owner"] for card in data["household_cards"] if card["owner"] != "Either"})
    apps = sum(len(category["platforms"]) for category in data["categories"])
    st.markdown(
        f"""
        <div class="pm-header">
          <div>
            <div class="pm-brand">Pay<span>Mind</span></div>
            <div class="pm-tag">Every bill, the cheapest way to pay. Apps × offers × your household's cards.</div>
          </div>
          <div class="pm-stats">
            <div class="pm-stat"><b>{len(data['household_cards'])}</b> cards &amp; UPI</div>
            <div class="pm-stat"><b>{esc(' & '.join(owners) or 'You')}</b></div>
            <div class="pm-stat"><b>{apps}</b> apps tracked</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------- best deal ----------

def run_deal_search(category: dict, amount: float, day: str, app_ids: list[str], card_ids: list[str], overrides: dict) -> None:
    prices = {pid: float(overrides.get(pid) or amount) for pid in app_ids}
    results = find_best_deals(category["id"], prices, day, card_ids)
    explanation = ""
    if results and get_api_key():
        runner = results[1] if len(results) > 1 else None
        try:
            explanation = ask(
                DEAL_PROMPT,
                f"Paying for: {category['name']}, {money(amount)} on {day}.\nBest: {results[0]}\nRunner-up: {runner}",
            )
        except Exception as error:
            explanation = f"(Couldn't generate the explanation: {error})"
    st.session_state.setdefault("deals", {})[category["id"]] = {
        "results": results, "amount": amount, "day": day, "explanation": explanation, "logged": False,
    }


def render_deal_form(category: dict, data: dict) -> None:
    platforms = category["platforms"]
    app_names = {p["id"]: p["name"] for p in platforms}
    card_names = {
        c["id"]: f"{c['name']} · {c['owner']}" for c in data["household_cards"]
    }
    with st.container(border=True):
        st.markdown(f"#### {category['icon']} {category['name']}")
        with st.form(f"deal_form_{category['id']}"):
            amount = st.number_input(
                f"{category['amount_label']} (₹)", min_value=1.0,
                value=float(category["default_amount"]), step=50.0, key=f"amount_{category['id']}",
            )
            day = st.selectbox("Day", DAYS, index=date.today().weekday(), key=f"day_{category['id']}")
            app_ids = st.multiselect(
                "Apps to compare", list(app_names), default=list(app_names),
                format_func=app_names.get, key=f"apps_{category['id']}",
            )
            overrides = {}
            if category.get("price_varies"):
                st.caption("Prices differ between apps. Enter what each app shows, or leave blank to use the fare above.")
                for platform in platforms:
                    overrides[platform["id"]] = st.number_input(
                        f"Price on {platform['name']} (₹)", min_value=0.0, value=None,
                        placeholder="Same as fare", step=50.0, key=f"price_{category['id']}_{platform['id']}",
                    )
            card_ids = st.multiselect(
                "Cards you can use", list(card_names), default=list(card_names),
                format_func=card_names.get, key=f"cards_{category['id']}",
            )
            submitted = st.form_submit_button("Find the best way to pay →", type="primary", width="stretch")
    if submitted:
        if not app_ids or not card_ids:
            st.error("Pick at least one app and one card.")
        else:
            with st.spinner("Comparing every app and card…"):
                run_deal_search(category, amount, day, app_ids, card_ids, overrides)


def render_best_hero(best: dict, deal: dict, compared: int) -> None:
    pct = best["savings"] / max(best["price"], best["savings"] + best["effective_cost"]) * 100 if best["savings"] > 0 else 0
    if best["card_type"] == "upi":
        sub = "Any UPI app"
    else:
        sub = f"{esc(best['owner'])}'s {esc(best['network'])} {esc(best['card_type'])} card"
    chips = []
    if best["platform_discount"]:
        chips.append(f"App discount {money(best['platform_discount'])}")
    if best["bank_offer"]:
        chips.append(f"🏷️ {esc(best['bank_offer'])}")
    if best["fee"]:
        chips.append(f"Fee {money(best['fee'])}")
    if best["rewards"]:
        chips.append(f"Rewards worth {money(best['rewards'])}")
    chips_html = "".join(f'<span class="pm-chip">{chip}</span>' for chip in chips)
    st.markdown(
        f"""
        <div class="pm-best">
          <div class="pm-eyebrow">Best way to pay · {esc(deal['day'])} · {compared} options compared</div>
          <div class="pm-best-title">{esc(best['platform'])} <em>with</em> {esc(best['card'])}</div>
          <div class="pm-best-sub">{sub}</div>
          <div class="pm-figs">
            <div class="pm-fig"><small>Pay now</small><b>{money(best['pay_now'])}</b></div>
            <div class="pm-fig"><small>After rewards</small><b>{money(best['effective_cost'])}</b></div>
            <div class="pm-fig save"><small>You save</small><b>{money(best['savings'])}</b> · {pct:.1f}%</div>
          </div>
          <div class="pm-chips">{chips_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_breakdown(best: dict) -> None:
    rows = [("", f"Price on {best['platform']}", best["price"])]
    if best["platform_discount"]:
        rows.append(("minus", f"{best['platform']} discount", -best["platform_discount"]))
    if best["bank_discount"]:
        rows.append(("minus", "Bank offer", -best["bank_discount"]))
    if best["fee"]:
        rows.append(("plus", "Convenience fee", best["fee"]))
    rows.append(("total", "Pay now", best["pay_now"]))
    if best["rewards"]:
        rows.append(("minus", "Card rewards (value)", -best["rewards"]))
        rows.append(("total", "Effective cost", best["effective_cost"]))
    lines = "".join(
        f'<div class="pm-line {kind}"><span>{esc(label)}</span><span>{"−" if value < 0 else ("+" if kind == "plus" else "")}{money(abs(value))}</span></div>'
        for kind, label, value in rows
    )
    st.markdown(f'<div class="pm-card"><h4>How the saving stacks up</h4>{lines}</div>', unsafe_allow_html=True)


def render_savings_chart(results: list[dict]) -> None:
    top = results[:8]
    rows = [
        {
            "Option": f"{item['platform']} · {item['card']}",
            "Savings": max(item["savings"], 0),
            "Label": money(item["savings"]),
            "Best": index == 0,
        }
        for index, item in enumerate(top)
    ]
    order = [row["Option"] for row in rows]
    base = alt.Chart(alt.Data(values=rows)).encode(
        y=alt.Y("Option:N", sort=order, title=None, axis=alt.Axis(labelLimit=220)),
        x=alt.X("Savings:Q", title="You save (₹)"),
    )
    bars = base.mark_bar(cornerRadiusEnd=5, height=18).encode(
        color=alt.condition("datum.Best", alt.value("#0B7A5E"), alt.value("#B9CCC2"))
    )
    labels = base.mark_text(align="left", dx=4, color="#16211C", fontSize=11).encode(text="Label:N")
    st.markdown("**Savings by option (top 8)**")
    st.altair_chart((bars + labels).properties(height=34 * len(rows) + 20), width="stretch")


def render_ranked_list(results: list[dict]) -> None:
    items = []
    for position, item in enumerate(results[:5], start=1):
        detail = item["bank_offer"] or ("No bank offer" if item["platform_discount"] == 0 else "App discount only")
        items.append(
            f"""<div class="pm-rank {'first' if position == 1 else ''}">
                  <div class="n">{position}</div>
                  <div class="who"><b>{esc(item['platform'])} · {esc(item['card'])}</b>
                    <small>{esc(item['owner'])} · {esc(detail)}</small></div>
                  <div class="amt">{money(item['effective_cost'])}<small>save {money(item['savings'])}</small></div>
                </div>"""
        )
    st.markdown("".join(items), unsafe_allow_html=True)


def log_deal(category: dict, best: dict) -> None:
    insert_transaction(
        date=date.today().isoformat(),
        merchant=f"{best['platform']} ({category['name']})",
        amount=best["pay_now"],
        category=category["log_category"],
        payment_method=f"{best['card']} ({best['owner']})",
        payment_id=best["card_id"],
        cashback_earned=round(best["price"] - best["effective_cost"], 2),
        notes="best-deal",
    )


def render_deal_results(category: dict) -> None:
    deal = st.session_state.get("deals", {}).get(category["id"])
    if not deal or not deal["results"]:
        st.markdown(
            f"""<div class="pm-empty"><b>{category['icon']} Find the cheapest way to pay</b>
            Enter the {esc(category['amount_label'].lower())}, pick the apps and cards you can use,
            and PayMind compares every combination with all offers stacked.</div>""",
            unsafe_allow_html=True,
        )
        return

    results = deal["results"]
    best = results[0]
    render_best_hero(best, deal, len(results))
    if deal["explanation"]:
        st.write(deal["explanation"])

    action_col, note_col = st.columns([1, 1])
    with action_col:
        if deal["logged"]:
            st.button("✓ Logged to Spending", disabled=True, width="stretch", key=f"logged_{category['id']}")
        elif st.button("Log this payment", width="stretch", key=f"log_{category['id']}"):
            log_deal(category, best)
            deal["logged"] = True
            st.toast(f"Logged {money(best['pay_now'])} on {best['card']}")
            st.rerun()
    with note_col:
        direct = [item for item in results if item["platform_discount"] == 0 and not item["bank_offer"]]
        if direct:
            plain = max(direct, key=lambda item: item["effective_cost"])
            st.caption(f"Without any offer: {money(plain['effective_cost'])} ({plain['platform']} · {plain['card']}).")

    left, right = st.columns([1, 1], gap="medium")
    with left:
        render_breakdown(best)
    with right:
        st.markdown("**Top 5 options**")
        render_ranked_list(results)

    render_savings_chart(results)

    with st.expander(f"All {len(results)} options"):
        st.dataframe(
            [
                {
                    "#": position,
                    "App": item["platform"],
                    "Card": f"{item['card']} ({item['owner']})",
                    "Price": money(item["price"]),
                    "Pay now": money(item["pay_now"]),
                    "After rewards": money(item["effective_cost"]),
                    "Save": money(item["savings"]),
                    "Offer used": item["bank_offer"] or "—",
                }
                for position, item in enumerate(results, start=1)
            ],
            width="stretch",
            hide_index=True,
        )
    missed = [(item, note) for item in results[:6] for note in item["missed_offers"]]
    if missed:
        with st.expander("Offers you just missed"):
            for item, note in missed:
                st.write(f"• **{item['platform']} · {item['card']}**: {note}")


def render_best_deal_tab(data: dict) -> None:
    categories = {category["id"]: category for category in data["categories"]}
    choice = st.pills(
        "What are you paying for?", list(categories), default="restaurant",
        format_func=lambda cid: category_label(categories[cid]), key="category_pick",
    ) or "restaurant"
    category = categories[choice]
    form_col, result_col = st.columns([5, 7], gap="large")
    with form_col:
        render_deal_form(category, data)
        st.caption(data.get("_note", ""))
    with result_col:
        render_deal_results(category)


# ---------- wallet ----------

def card_tile(card: dict) -> str:
    start, end = BANK_COLORS.get(card["bank"], DEFAULT_BANK_COLOR)
    kind = "UPI" if card["type"] == "upi" else f"{card['type']} card"
    reward = f"{card['reward_value_pct']:g}% back" if card["reward_value_pct"] else "No rewards"
    return f"""<div class="pm-cc" style="background: linear-gradient(135deg, {start}, {end});">
      <div class="top"><span>{esc(card['bank'])}</span><span>{esc(card.get('network', ''))}</span></div>
      <div class="name">{esc(card['name'])}</div>
      <div class="bottom"><span>{esc(kind)}</span><span>{esc(reward)}</span></div>
    </div>"""


def render_wallet_tab(data: dict) -> None:
    st.subheader("Household wallet")
    st.caption("Every card and UPI method your household can pay with. Offers are matched to the exact card and network.")
    owners: dict[str, list[dict]] = {}
    for card in data["household_cards"]:
        owners.setdefault(card["owner"], []).append(card)
    for owner, cards in owners.items():
        st.markdown(f'<div class="pm-owner">{esc(owner)}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="pm-wallet">{"".join(card_tile(card) for card in cards)}</div>', unsafe_allow_html=True)

    add_col, remove_col = st.columns([3, 2], gap="large")
    with add_col:
        with st.container(border=True):
            st.markdown("#### ➕ Add a card")
            with st.form("add_card_form", clear_on_submit=True):
                name = st.text_input("Exact card name", placeholder="e.g. HDFC Regalia Gold")
                bank_col, owner_col = st.columns(2)
                bank = bank_col.text_input("Bank", placeholder="e.g. HDFC")
                owner = owner_col.text_input("Owner", value="Hari")
                type_col, network_col = st.columns(2)
                card_type = type_col.selectbox("Type", ["credit", "debit"])
                network = network_col.selectbox("Network", ["Visa", "Mastercard", "RuPay", "Amex", "Diners"])
                reward = st.number_input("Reward value (% of spend)", min_value=0.0, max_value=20.0, value=1.0, step=0.25)
                if st.form_submit_button("Save card", type="primary", width="stretch"):
                    if not name.strip() or not bank.strip():
                        st.error("Enter the card name and bank.")
                    else:
                        try:
                            add_household_card(name.strip(), bank.strip(), card_type, network, owner.strip() or "Me", reward)
                            st.toast(f"Added {name.strip()}")
                            st.rerun()
                        except ValueError as error:
                            st.error(str(error))
    with remove_col:
        with st.container(border=True):
            st.markdown("#### Remove a card")
            names = {c["id"]: f"{c['name']} · {c['owner']}" for c in data["household_cards"]}
            to_remove = st.selectbox("Card", list(names), format_func=names.get, key="remove_card")
            if st.button("Remove card", width="stretch", key="remove_card_btn"):
                remove_household_card(to_remove)
                st.toast("Card removed")
                st.rerun()


# ---------- apps & offers ----------

def render_platform(category: dict, platform: dict) -> None:
    with st.container(border=True):
        badges = []
        if platform["discount_pct"]:
            cap = f" up to ₹{platform['discount_cap']:,.0f}" if platform.get("discount_cap") else ""
            badges.append(f'<span class="pm-badge">App discount {platform["discount_pct"]:g}%{cap}</span>')
        if platform.get("fee_pct"):
            badges.append(f'<span class="pm-badge fee">Fee {platform["fee_pct"]:g}%</span>')
        if platform.get("fee_flat"):
            badges.append(f'<span class="pm-badge fee">Fee ₹{platform["fee_flat"]:,.0f}</span>')
        if platform.get("user_added"):
            badges.append('<span class="pm-badge mine">Added by you</span>')
        st.markdown(f"**{esc(platform['name'])}**<br>{''.join(badges)}", unsafe_allow_html=True)
        offers = platform["bank_offers"]
        if not offers:
            st.caption("No bank offers yet.")
        for index, offer in enumerate(offers):
            text_col, button_col = st.columns([6, 1])
            text_col.markdown(f'<div class="pm-offer">🏷️ {esc(offer["label"])}</div>', unsafe_allow_html=True)
            if offer.get("user_added") and button_col.button("✕", key=f"del_{category['id']}_{platform['id']}_{index}", help="Remove this offer"):
                remove_offer(category["id"], platform["id"], index)
                st.rerun()
        if platform.get("user_added") and st.button("Remove app", key=f"del_app_{category['id']}_{platform['id']}"):
            remove_platform(category["id"], platform["id"])
            st.rerun()


def render_apps_tab(data: dict) -> None:
    categories = {category["id"]: category for category in data["categories"]}
    choice = st.pills(
        "Category", list(categories), default="restaurant",
        format_func=lambda cid: category_label(categories[cid]), key="apps_category_pick",
    ) or "restaurant"
    category = categories[choice]
    st.caption("Standard apps come with PayMind. Add the apps you use and the offers you see in them.")

    list_col, form_col = st.columns([7, 5], gap="large")
    with list_col:
        for platform in category["platforms"]:
            render_platform(category, platform)

    with form_col:
        with st.container(border=True):
            st.markdown("#### ➕ Add an app")
            with st.form(f"add_app_{category['id']}", clear_on_submit=True):
                name = st.text_input("App name", placeholder="e.g. Zomato Pay")
                pct_col, cap_col = st.columns(2)
                discount_pct = pct_col.number_input("App discount %", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
                discount_cap = cap_col.number_input("Max discount ₹", min_value=0.0, value=0.0, step=50.0, help="0 = no cap")
                fee_col, flat_col = st.columns(2)
                fee_pct = fee_col.number_input("Fee %", min_value=0.0, max_value=20.0, value=0.0, step=0.5)
                fee_flat = flat_col.number_input("Flat fee ₹", min_value=0.0, value=0.0, step=10.0)
                if st.form_submit_button("Add app", type="primary", width="stretch"):
                    if not name.strip():
                        st.error("Enter the app name.")
                    else:
                        try:
                            add_platform(category["id"], name.strip(), discount_pct, discount_cap, fee_pct, fee_flat)
                            st.toast(f"Added {name.strip()}")
                            st.rerun()
                        except ValueError as error:
                            st.error(str(error))

        with st.container(border=True):
            st.markdown("#### 🏷️ Add an offer")
            platform_names = {p["id"]: p["name"] for p in category["platforms"]}
            card_list = [c["name"] for c in data["household_cards"] if c["type"] != "upi"]
            banks = sorted({c["bank"] for c in data["household_cards"] if c["type"] != "upi"})
            with st.form(f"add_offer_{category['id']}", clear_on_submit=True):
                platform_id = st.selectbox("On app", list(platform_names), format_func=platform_names.get)
                bank_col, type_col = st.columns(2)
                bank = bank_col.selectbox("Bank", banks + ["any", "UPI"], help="'any' = offer for any bank, e.g. RuPay offers")
                card_type = type_col.selectbox("Card type", ["credit", "debit", "any", "upi"])
                other_bank = st.text_input("Bank not listed? Type it", placeholder="Optional")
                cards = st.multiselect("Only these cards (optional)", card_list)
                exclude = st.multiselect("Excluding these cards (optional)", card_list)
                networks = st.multiselect("Only these networks (optional)", ["Visa", "Mastercard", "RuPay", "Amex", "Diners"])
                kind = st.radio("Discount", ["% off", "₹ flat off"], horizontal=True)
                value_col, cap_col = st.columns(2)
                value = value_col.number_input("Value", min_value=0.0, value=10.0, step=1.0)
                cap = cap_col.number_input("Max discount ₹ (for %)", min_value=0.0, value=0.0, step=50.0, help="0 = no cap")
                min_col, days_col = st.columns(2)
                min_bill = min_col.number_input("Minimum amount ₹", min_value=0.0, value=0.0, step=100.0)
                days = days_col.multiselect("Only on days", DAYS)
                if st.form_submit_button("Add offer", type="primary", width="stretch"):
                    if value <= 0:
                        st.error("Enter a discount value.")
                    else:
                        offer = {
                            "bank": other_bank.strip() or bank, "card_type": card_type,
                            "cards": cards, "exclude_cards": exclude, "networks": networks,
                            "cap": cap, "min_bill": min_bill, "days": days,
                        }
                        offer["pct" if kind == "% off" else "flat"] = value
                        add_offer(category["id"], platform_id, offer)
                        st.toast("Offer added")
                        st.rerun()


# ---------- spending + assistant (agents) ----------

def add_sample_transactions() -> None:
    options_by_id = {option["id"]: option for option in all_payment_options()}
    today = date.today()
    for days_ago, merchant, amount, category, payment_id in SAMPLE_TRANSACTIONS:
        txn_date = max(today - timedelta(days=days_ago), today.replace(day=1))
        insert_transaction(
            date=txn_date.isoformat(), merchant=merchant, amount=amount, category=category,
            payment_method=options_by_id[payment_id]["name"], payment_id=payment_id,
            cashback_earned=calculate_cashback(payment_id, merchant, amount, category), notes="sample",
        )


def render_spending_tab() -> None:
    today = date.today()
    transactions = get_transactions(today.replace(day=1).isoformat(), today.isoformat())
    total = sum(item["amount"] for item in transactions)
    saved = sum(item["cashback_earned"] for item in transactions)

    title_col, budget_col = st.columns([3, 1])
    title_col.subheader(f"{today:%B %Y}")
    budget = budget_col.number_input("Monthly budget (₹)", min_value=1000.0, value=float(st.session_state.monthly_budget), step=1000.0)
    st.session_state.monthly_budget = budget

    columns = st.columns(3)
    columns[0].metric("Spent", money(total))
    columns[1].metric("Saved & cashback", money(saved))
    columns[2].metric("Transactions", len(transactions))
    st.progress(min(total / budget, 1.0), text=f"{total / budget * 100:.0f}% of {money(budget)} budget used")

    if not transactions:
        st.info("No transactions yet — log one first!")
        if st.button("Add 10 sample transactions", width="stretch"):
            add_sample_transactions()
            st.rerun()
    else:
        chart_col, list_col = st.columns([1, 1], gap="large")
        with chart_col:
            totals: dict[str, float] = {}
            for item in transactions:
                totals[item["category"]] = totals.get(item["category"], 0.0) + item["amount"]
            rows = [{"Category": key, "Amount": value} for key, value in totals.items()]
            chart = alt.Chart(alt.Data(values=rows)).mark_bar(cornerRadiusEnd=5, color="#0B7A5E").encode(
                y=alt.Y("Category:N", sort="-x", title=None), x=alt.X("Amount:Q", title="Spent (₹)")
            )
            st.altair_chart(chart.properties(height=36 * len(rows) + 20), width="stretch")
        with list_col:
            st.dataframe(
                [
                    {"Date": item["date"], "Merchant": item["merchant"], "Amount": money(item["amount"]), "Saved": money(item["cashback_earned"])}
                    for item in transactions
                ],
                width="stretch", hide_index=True, height=320,
            )

    with st.expander("📝 Log an expense"):
        options = {option["id"]: option["name"] for option in all_payment_options()}
        with st.form("expense_form", clear_on_submit=True):
            merchant = st.text_input("Merchant", placeholder="e.g. Zomato")
            amount = st.number_input("Amount (₹)", min_value=1.0, value=500.0, step=100.0)
            category = st.selectbox("Category", [AUTO_CATEGORY] + VALID_CATEGORIES)
            payment_id = st.selectbox("Paid with", list(options), format_func=options.get)
            submitted = st.form_submit_button("Log expense", type="primary", width="stretch")
        if submitted:
            if not merchant.strip():
                st.error("Enter a merchant name.")
            else:
                with st.spinner("Logging…"):
                    result = run_graph({
                        "messages": f"Log ₹{amount:.2f} at {merchant.strip()}",
                        "intent": "log", "merchant": merchant.strip(), "amount": float(amount),
                        "category": "" if category == AUTO_CATEGORY else category,
                        "payment_used": payment_id, "payment_ids": list(options), "monthly_budget": budget,
                    })
                show_result(result)


def show_result(result: dict) -> None:
    kind = result.get("type")
    if kind == "advise":
        if not result.get("recommended"):
            st.info(result.get("error") or result.get("reasoning") or "No recommendation.")
            return
        st.success(f"Pay with **{result['recommended']}** and earn **{money(result['cashback_earned'])}** cashback")
        if result.get("reasoning"):
            st.write(result["reasoning"])
        if result.get("error"):
            st.warning(result["error"])
        with st.expander("Compare all methods"):
            for position, option in enumerate(result.get("all_options", []), start=1):
                st.write(f"{position}. **{option['name']}**: {money(option['cashback'])} · {option['rule']}")
    elif kind == "log":
        (st.success if result.get("status") == "success" else st.error)(result.get("message", ""))
    elif kind == "analyze":
        if result.get("error") is True:
            st.error(result.get("answer"))
            return
        st.write(result.get("answer", ""))
        if result.get("category_totals"):
            st.bar_chart(result["category_totals"], color="#0B7A5E")
    elif kind == "offers":
        if result.get("overall_tip"):
            st.info(f"💡 {result['overall_tip']}")
        for card in result.get("cards", []):
            with st.container(border=True):
                st.markdown(f"**{card['name']}**")
                for offer in card["offers"]:
                    st.write(f"• {offer}")
                tip = result.get("tips", {}).get(card["name"])
                if tip:
                    st.caption(f"Tip: {tip}")
        if result.get("error"):
            st.warning(result["error"])
    else:
        st.error(result.get("error", "Something went wrong."))


def render_ask_tab() -> None:
    st.subheader("Ask PayMind")
    st.caption("A supervisor agent reads your question and routes it to the right agent: payment advice, logging, spending analysis or offers.")
    example = st.pills("Try one", EXAMPLE_QUESTIONS, key="ask_example")
    with st.form("ask_form"):
        question = st.text_area("Your question", value=example or "", placeholder="e.g. How much did I spend on dining this week?")
        asked = st.form_submit_button("Ask →", type="primary", width="stretch")
    if asked:
        if not question.strip():
            st.error("Type a question first.")
        else:
            payment_ids = [option["id"] for option in all_payment_options()]
            with st.spinner("Thinking…"):
                st.session_state.ask_result = run_graph({
                    "messages": question.strip(), "payment_ids": payment_ids,
                    "monthly_budget": st.session_state.monthly_budget,
                })
    if st.session_state.get("ask_result"):
        show_result(st.session_state.ask_result)


# ---------- app ----------

def main() -> None:
    st.set_page_config(page_title="PayMind", page_icon="💳", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    init_db()
    st.session_state.setdefault("monthly_budget", 30000.0)
    data = load_deal_data()

    render_header(data)
    if not get_api_key():
        st.warning("Add OPENROUTER_API_KEY to your .env to turn on AI explanations and Ask PayMind. Deal comparisons work without it.")

    deal_tab, wallet_tab, apps_tab, spending_tab, ask_tab = st.tabs(
        ["💸 Best deal", "👛 Wallet", "🏷️ Apps & offers", "📊 Spending", "🤖 Ask PayMind"]
    )
    with deal_tab:
        render_best_deal_tab(data)
    with wallet_tab:
        render_wallet_tab(data)
    with apps_tab:
        render_apps_tab(data)
    with spending_tab:
        render_spending_tab()
    with ask_tab:
        render_ask_tab()


main()