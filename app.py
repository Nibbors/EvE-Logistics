import asyncio

import pandas as pd
import streamlit as st

from config import DEFAULT_DST_CAPACITY_M3, DOCTRINES
from doctrine import summarize_doctrine_needs
from market_scan import run_full_scan
from storage import init_db, load_history, load_stock, save_stock
from wallet import calculate_fee, parse_wallet_cost


# --- UI SETUP ---
init_db()
st.set_page_config(page_title="BobVult Logistics Hub", layout="wide")

# Sidebar runtime config
st.sidebar.title("⚙️ Settings")
dst_capacity_m3 = st.sidebar.number_input(
    "DST capacity (m³)",
    min_value=1_000,
    max_value=200_000,
    value=int(DEFAULT_DST_CAPACITY_M3),
    step=500,
)

saved_counts = load_stock()
history_logs = load_history()
_, initial_total_m3_needed = summarize_doctrine_needs(DOCTRINES, saved_counts)

tab1, tab2, tab3, tab4 = st.tabs(
    ["🛸 Doctrine Tracker", "💳 Wallet Analyzer", "📜 Transaction History", "💰 WH Exit Arbitrage"]
)

# --- TAB 1: DOCTRINE TRACKER ---
with tab1:
    st.title("📦 Doctrine Stock Control")
    to_buy_text, total_m3_needed, current_inputs = "", 0, {}
    for ship in DOCTRINES:
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
        with col1:
            st.write(f"### {ship['name']}")
        with col2:
            st.link_button("🔗 View Fit", ship["link"], use_container_width=True)
        with col3:
            val = st.number_input(
                f"Stock ({ship['id']})",
                min_value=0,
                value=saved_counts.get(ship["id"], 0),
                key=f"s_{ship['id']}",
            )
            current_inputs[ship["id"]] = val
        with col4:
            needed = max(0, ship["target"] - val)
            if needed > 0:
                st.error(f"Missing: {needed}")
                to_buy_text += f"{ship['id']} {needed}\n"
                total_m3_needed += needed * ship["m3"]
            else:
                st.success("Stocked")
        st.divider()

    if st.button("💾 Save Progress"):
        save_stock(current_inputs)
        st.toast("Saved to SQLite!")

# --- TAB 2: CALCULATOR ---
with tab2:
    st.title("💳 Logistics Calculator")
    col_l, col_r = st.columns([2, 1])
    wallet_input = col_l.text_area("Paste Wallet Rows", height=150)
    c1, c2, c3 = st.columns(3)
    j_count = c1.number_input("Jumps", value=1)
    v_count = c2.number_input("Total m3", value=int(total_m3_needed or initial_total_m3_needed))
    r_pct = c3.number_input("Risk %", value=3.0)
    cost = parse_wallet_cost(wallet_input)
    fee = calculate_fee(j_count, v_count, r_pct, cost)
    col_r.metric("Total ISK", f"{cost + fee:,.0f}")

# --- TAB 3: HISTORY ---
with tab3:
    st.title("📜 Logs")
    for log in history_logs:
        st.write(f"**{log.get('timestamp')}**: {log.get('total', 0):,.0f} ISK")

# --- TAB 4: WH EXIT ARBITRAGE (ASYNC) ---
with tab4:
    st.title("💰 WH Exit Arbitrage Scanner (Async)")
    st.markdown(
        "Fills your DST from cheapest to most expensive local orders, comparing against Jita's best buy order."
    )

    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        target_sys = st.text_input("Enter WH Exit System", value="Odebeinn")
    with c2:
        min_profit_m = st.number_input("Min Profit per DST (Millions)", value=10.0)
    with c3:
        min_fill_pct = st.number_input("Min Hold Fill %", value=0.0)
    with c4:
        st.write("##")
        do_scan = st.button("🔍 Run Fast Scan", use_container_width=True)

    if do_scan and target_sys:
        bar = st.progress(0, text="Initializing Async Session...")

        results, err = asyncio.run(
            run_full_scan(target_sys, min_profit_m, dst_capacity_m3, min_fill_pct, bar)
        )
        bar.empty()

        if err:
            st.error(err)
        elif results:
            df = pd.DataFrame(results).sort_values("Total DST Profit", ascending=False)
            df["Total DST Profit"] = df["Total DST Profit"].apply(lambda x: f"{x:,.0f} ISK")
            st.table(df)
        else:
            st.warning("No spreads found that fit your criteria.")

# --- SIDEBAR ---
st.sidebar.title("🚛 Transport Plan")
st.sidebar.metric("Volume", f"{total_m3_needed or initial_total_m3_needed:,} m³")
st.sidebar.code(to_buy_text)
