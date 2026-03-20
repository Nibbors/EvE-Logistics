import asyncio

import pandas as pd
import streamlit as st

from config import DEFAULT_DST_CAPACITY_M3
from doctrine import parse_eve_fit, summarize_doctrine_needs
from market_scan import run_full_scan
from storage import (
    init_db,
    load_doctrine_fits,
    load_quote_history,
    load_stock,
    save_doctrine_fit,
    save_quote_history,
    save_stock,
)
from wallet import calculate_pricing, parse_wallet_cost


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

doctrines = load_doctrine_fits()
saved_counts = load_stock()
quote_history = load_quote_history()
to_buy_text, initial_total_m3_needed = summarize_doctrine_needs(doctrines, saved_counts)

tab1, tab2, tab3, tab4 = st.tabs(
    ["🛸 Doctrine Tracker", "💳 Contract Quote", "📜 Quote History", "💰 WH Exit Arbitrage"]
)

# --- TAB 1: DOCTRINE TRACKER ---
with tab1:
    st.title("📦 Doctrine Stock Control")
    st.caption("Track current doctrine readiness and import new doctrine fits directly from EVE fitting text.")

    with st.expander("➕ Import doctrine fit from EVE text"):
        fit_text = st.text_area("Paste fit export", height=220, key="doctrine_fit_text")
        import_col1, import_col2, import_col3 = st.columns(3)
        imported_target = import_col1.number_input("Target count", min_value=1, value=1, step=1)
        imported_m3 = import_col2.number_input("Estimated m3 per ship", min_value=0.0, value=0.0, step=500.0)
        imported_notes = import_col3.text_input("Notes / link", value="")

        if st.button("Save imported doctrine fit", use_container_width=True):
            try:
                parsed = parse_eve_fit(fit_text)
                parsed["target"] = imported_target
                parsed["m3"] = imported_m3
                parsed["notes"] = imported_notes
                save_doctrine_fit(parsed)
                st.success(f"Saved doctrine fit: {parsed['name']}")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    st.divider()

    total_m3_needed = 0
    current_inputs = {}

    for ship in doctrines:
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
        with col1:
            st.write(f"### {ship['name']}")
            extra_bits = []
            if ship.get("target"):
                extra_bits.append(f"Target: {ship['target']}")
            if ship.get("m3"):
                extra_bits.append(f"m3/ship: {ship['m3']:,.0f}")
            if ship.get("item_count"):
                extra_bits.append(f"Items in fit: {ship['item_count']}")
            if extra_bits:
                st.caption(" • ".join(extra_bits))
        with col2:
            if ship.get("notes", "").startswith("http"):
                st.link_button("🔗 Open Link", ship["notes"], use_container_width=True)
            else:
                st.write(ship.get("fit_name", ship["id"]))
        with col3:
            val = st.number_input(
                f"Stock ({ship['id']})",
                min_value=0,
                value=saved_counts.get(ship["id"], 0),
                key=f"s_{ship['id']}",
            )
            current_inputs[ship["id"]] = val
        with col4:
            needed = max(0, int(ship.get("target", 0)) - val)
            if needed > 0:
                st.error(f"Missing: {needed}")
                total_m3_needed += needed * float(ship.get("m3", 0))
            else:
                st.success("Stocked")

        if ship.get("fit_text"):
            with st.expander(f"View fit: {ship['name']}"):
                st.code(ship["fit_text"], language=None)

        st.divider()

    if st.button("💾 Save Progress", use_container_width=True):
        save_stock(current_inputs)
        st.toast("Doctrine stock saved.")
        st.rerun()

# --- TAB 2: CALCULATOR ---
with tab2:
    st.title("💳 Contract Quote")
    st.caption(
        "Build a fair wormhole import quote from Jita purchase cost, hauling effort, and risk."
    )

    input_col, output_col = st.columns([2, 1])

    with input_col:
        st.subheader("Purchase Input")
        wallet_input = st.text_area("Paste wallet rows", height=180)
        quote_note = st.text_input("Quote note / corpmate / route", value="")

        st.subheader("Hauling Settings")
        c1, c2, c3 = st.columns(3)
        j_count = int(c1.number_input("Jumps", min_value=0, value=1, step=1))
        v_count = float(
            c2.number_input(
                "Total m3",
                min_value=0.0,
                value=float(total_m3_needed or initial_total_m3_needed),
                step=100.0,
            )
        )
        r_pct = float(c3.number_input("Risk %", min_value=0.0, value=3.0, step=0.5))

        c4, c5 = st.columns(2)
        isk_per_jump = float(
            c4.number_input("ISK per jump", min_value=0.0, value=1_000_000.0, step=100_000.0, format="%.0f")
        )
        isk_per_m3 = float(c5.number_input("ISK per m3", min_value=0.0, value=500.0, step=50.0, format="%.0f"))

    cost = parse_wallet_cost(wallet_input)
    pricing = calculate_pricing(
        jumps=j_count,
        volume_m3=v_count,
        risk_pct=r_pct,
        base_cost=cost,
        isk_per_jump=isk_per_jump,
        isk_per_m3=isk_per_m3,
        dst_capacity_m3=dst_capacity_m3,
    )
    contract_price_text = f"{pricing.final_total:,.0f}".replace(",", "")
    summary_text = (
        f"Jita {pricing.jita_total:,.0f} + jumps {pricing.jump_fee:,.0f} + volume {pricing.volume_fee:,.0f} "
        f"+ risk {pricing.risk_fee:,.0f} = {pricing.final_total:,.0f} ISK"
    )

    with output_col:
        st.subheader("Quote Summary")
        st.metric("Final Quote", f"{pricing.final_total:,.0f} ISK")
        st.metric("Markup vs Jita", f"{pricing.final_total - pricing.jita_total:,.0f} ISK")
        st.metric("Effective Markup", f"{pricing.effective_markup_pct:.1f}%")

    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Jita Total", f"{pricing.jita_total:,.0f} ISK")
    b2.metric("Jump Fee", f"{pricing.jump_fee:,.0f} ISK")
    b3.metric("Volume Fee", f"{pricing.volume_fee:,.0f} ISK")
    b4.metric("Risk Fee", f"{pricing.risk_fee:,.0f} ISK")

    d1, d2 = st.columns([2, 1])
    d1.text_input(
        "Contract Price for EVE",
        value=contract_price_text,
        help="Plain ISK amount without commas for fast copy/paste into contracts.",
    )
    d2.metric("DST Loads", pricing.dst_loads)

    st.text_area("Breakdown", value=summary_text, height=80)

    if st.button("Save quote to history", use_container_width=True):
        save_quote_history(pricing, note=quote_note, pricing_mode="per_m3")
        st.success("Quote saved to history.")
        st.rerun()

# --- TAB 3: HISTORY ---
with tab3:
    st.title("📜 Quote History")
    st.caption("Recent saved logistics quotes with the actual settings used.")

    if not quote_history:
        st.info("No saved quotes yet. Save one from the Contract Quote tab.")
    else:
        df = pd.DataFrame(quote_history)
        display_cols = [
            "timestamp",
            "note",
            "total",
            "jita_total",
            "jump_fee",
            "volume_fee",
            "risk_fee",
            "jumps",
            "volume_m3",
            "risk_pct",
            "dst_loads",
        ]
        existing_cols = [col for col in display_cols if col in df.columns]
        df = df[existing_cols].copy()
        for col in ["total", "jita_total", "jump_fee", "volume_fee", "risk_fee"]:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: f"{x:,.0f} ISK")
        if "volume_m3" in df.columns:
            df["volume_m3"] = df["volume_m3"].apply(lambda x: f"{x:,.0f}")
        if "risk_pct" in df.columns:
            df["risk_pct"] = df["risk_pct"].apply(lambda x: f"{x:.1f}%")
        st.dataframe(df, use_container_width=True, hide_index=True)

# --- TAB 4: WH EXIT ARBITRAGE (ASYNC) ---
with tab4:
    st.title("💰 WH Exit Arbitrage Scanner")
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
st.sidebar.metric("Doctrine import volume", f"{total_m3_needed or initial_total_m3_needed:,.0f} m³")
st.sidebar.code(to_buy_text or "All doctrine stock targets currently met.")
