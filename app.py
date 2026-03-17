import streamlit as st
import sqlite3
import re
import aiohttp
import asyncio
import pandas as pd

# --- FILE SETUP ---
DB_FILE = "logistics.db"

# --- DEFAULTS (UI overrides below) ---
DEFAULT_DST_CAPACITY_M3 = 62_500
JITA_REGION_ID = 10000002
JITA_STATION_ID = 60003760

# --- THE MASSIVE WATCHLIST ---
WATCHLIST = {
    "Tritanium": 34,
    "Pyerite": 35,
    "Mexallon": 36,
    "Isogen": 37,
    "Nocxium": 38,
    "Zydrine": 39,
    "Megacyte": 40,
    "Morphite": 11399,
    "Compressed Veldspar": 28430,
    "Compressed Scordite": 28429,
    "Compressed Pyroxeres": 28424,
    "Compressed Plagioclase": 28422,
    "Compressed Omber": 28435,
    "Compressed Kernite": 28432,
    "Compressed Jaspet": 28421,
    "Compressed Hemorphite": 28418,
    "Compressed Hedbergite": 28415,
    "Compressed Gneiss": 28388,
    "Compressed Dark Ochre": 28394,
    "Compressed Spodumain": 28391,
    "Compressed Crokite": 28397,
    "Compressed Bistot": 28400,
    "Compressed Arkonor": 28403,
    "Compressed Mercoxit": 28385,
    "Compressed Clear Icicle": 28479,
    "Compressed Glacial Mass": 28481,
    "Compressed Blue Ice": 28476,
    "Compressed White Glaze": 28489,
    "Compressed Glare Crust": 28483,
    "Compressed Dark Glitter": 28485,
    "Cobalt": 16641,
    "Scandium": 16642,
    "Titanium": 16643,
    "Tungsten": 16644,
    "Cadmium": 16646,
    "Platinum": 16649,
    "Vanadium": 16647,
    "Chromium": 16648,
    "Technetium": 16650,
    "Hafnium": 16651,
    "Mercury": 16652,
    "Promethium": 16653,
    "Dysprosium": 16654,
    "Neodymium": 16655,
    "Thulium": 16656,
    "Coolant": 9832,
    "Robotics": 9848,
    "Mechanical Parts": 9840,
    "Enriched Uranium": 44,
    "Consumer Electronics": 9842,
    "Supercomputers": 9850,
    "Transmitters": 9838,
    "Melted Nanoribbons": 30375,
    "Intact Armor Plates": 25624,
    "Logic Circuit": 25606,
}

# --- DOCTRINE CONFIG ---
DOCTRINES = [
    {
        "name": "Sabre | Fastest Bubbles",
        "id": "Sabre",
        "link": "https://services.bobvult.space/fittings/fit/46/",
        "target": 5,
        "m3": 5000,
    },
    {
        "name": "Malediction | Tackle",
        "id": "Malediction",
        "link": "https://services.bobvult.space/fittings/fit/37/",
        "target": 4,
        "m3": 2500,
    },
    {
        "name": "Praxis | WH Roller",
        "id": "Praxis",
        "link": "https://services.bobvult.space/fittings/fit/41/",
        "target": 2,
        "m3": 50000,
    },
    {
        "name": "Cyclone | Armor DPS",
        "id": "Cyclone",
        "link": "https://services.bobvult.space/fittings/fit/1/",
        "target": 4,
        "m3": 15000,
    },
]

# --- DB SETUP & UTILITIES ---

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS stock (ship_id TEXT PRIMARY KEY, count INTEGER)"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, timestamp TEXT, total REAL)"""
    )
    conn.commit()
    conn.close()


def load_stock():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT ship_id, count FROM stock")
    res = {row[0]: row[1] for row in c.fetchall()}
    conn.close()
    return res


def save_stock(data):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    for k, v in data.items():
        c.execute(
            "INSERT OR REPLACE INTO stock (ship_id, count) VALUES (?, ?)", (k, v)
        )
    conn.commit()
    conn.close()


def load_history():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT timestamp, total FROM history ORDER BY id DESC LIMIT 10")
    res = [{"timestamp": row[0], "total": row[1]} for row in c.fetchall()]
    conn.close()
    return res


async def get_system_info(session, name: str):
    """Resolve a system name to system id + region id via ESI."""
    try:
        url = "https://esi.evetech.net/latest/universe/ids/?datasource=tranquility&language=en"
        # Avoid .title() here; EVE names can be weird and ESI doesn't require title casing.
        async with session.post(url, json=[name.strip()]) as r:
            if r.status != 200:
                return None, None
            data = await r.json()
            sys_id = data.get("systems", [{}])[0].get("id")
            if not sys_id:
                return None, None

        sys_url = (
            f"https://esi.evetech.net/latest/universe/systems/{sys_id}/?datasource=tranquility"
        )
        async with session.get(sys_url) as r:
            if r.status != 200:
                return None, None
            const_id = (await r.json()).get("constellation_id")
            if not const_id:
                return None, None

        const_url = f"https://esi.evetech.net/latest/universe/constellations/{const_id}/?datasource=tranquility"
        async with session.get(const_url) as r:
            if r.status != 200:
                return None, None
            region_id = (await r.json()).get("region_id")
            return sys_id, region_id
    except Exception:
        return None, None


async def fetch_market_page(session, region_id, item_id, page=1):
    url = f"https://esi.evetech.net/latest/markets/{region_id}/orders/?datasource=tranquility&order_type=all&type_id={item_id}&page={page}"
    for attempt in range(3):
        try:
            async with session.get(url, timeout=10) as r:
                if r.status == 200:
                    pages = int(r.headers.get("x-pages", 1))
                    return await r.json(), pages
                if r.status == 404:
                    return [], 1
                if r.status >= 500 or r.status == 420:
                    await asyncio.sleep(2**attempt)
        except asyncio.TimeoutError:
            pass
    return [], 1


async def get_market_data(session, item_id, region_id):
    data, pages = await fetch_market_page(session, region_id, item_id, 1)
    if pages > 1:
        tasks = [fetch_market_page(session, region_id, item_id, p) for p in range(2, pages + 1)]
        results = await asyncio.gather(*tasks)
        for res, _ in results:
            data.extend(res)
    return data


@st.cache_data(ttl=86400)
def get_item_vol_sync(item_id):
    import requests  # fallback for cached sync use

    url = f"https://esi.evetech.net/latest/universe/types/{item_id}/?datasource=tranquility"
    try:
        return requests.get(url, timeout=10).json().get("volume", 1.0)
    except Exception:
        return 1.0


async def scan_single_item(
    sem: asyncio.Semaphore,
    session,
    name,
    iid,
    sid,
    rid,
    min_profit_m,
    dst_capacity_m3,
    min_fill_pct,
):
    try:
        async with sem:
            j_data, l_data = await asyncio.gather(
                get_market_data(session, iid, JITA_REGION_ID),
                get_market_data(session, iid, rid),
            )

        vol = get_item_vol_sync(iid)

        j_buys = [
            o
            for o in j_data
            if o["is_buy_order"]
            and (o["location_id"] == JITA_STATION_ID or o["range"] == "region")
        ]
        l_sells = [o for o in l_data if (not o["is_buy_order"]) and o["system_id"] == sid]

        if not (j_buys and l_sells):
            return None

        best_j_price = max(j_buys, key=lambda x: x["price"])["price"]
        l_sells.sort(key=lambda x: x["price"])

        max_units_for_dst = int(dst_capacity_m3 / vol) if vol > 0 else 0
        if max_units_for_dst <= 0:
            return None

        units_bought, total_buy_cost = 0, 0.0

        for order in l_sells:
            if order["price"] >= best_j_price:
                break
            units_to_buy = min(order["volume_remain"], max_units_for_dst - units_bought)
            if units_to_buy <= 0:
                break
            units_bought += units_to_buy
            total_buy_cost += units_to_buy * order["price"]
            if units_bought >= max_units_for_dst:
                break

        if units_bought <= 0:
            return None

        fill_pct = (units_bought / max_units_for_dst) * 100
        if fill_pct < min_fill_pct:
            return None

        avg_buy_price = total_buy_cost / units_bought
        total_profit = (units_bought * best_j_price) - total_buy_cost

        if total_profit < (min_profit_m * 1_000_000):
            return None

        return {
            "Item": name,
            "Total DST Profit": total_profit,
            "Avg Local Buy": f"{avg_buy_price:,.2f} ISK",
            "Jita Sell At": f"{best_j_price:,.2f} ISK",
            "Qty Packed": f"{int(units_bought):,}",
            "Hold Fill %": f"{fill_pct:.1f}%",
        }

    except Exception:
        return None


async def run_full_scan(target_sys, min_profit_m, dst_capacity_m3, min_fill_pct, pbar):
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        sid, rid = await get_system_info(session, target_sys)
        if not sid or not rid:
            return None, "System or Region not found. Check spelling."

        # Keep ESI happy: limit concurrency.
        sem = asyncio.Semaphore(15)

        tasks = [
            scan_single_item(
                sem,
                session,
                name,
                iid,
                sid,
                rid,
                min_profit_m,
                dst_capacity_m3,
                min_fill_pct,
            )
            for name, iid in WATCHLIST.items()
        ]

        results, completed, total = [], 0, len(tasks)
        for f in asyncio.as_completed(tasks):
            res = await f
            completed += 1
            pbar.progress(
                completed / total,
                text=f"Scanned {completed}/{total} items... (Async via ESI)",
            )
            if res:
                results.append(res)

        return results, None


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
    v_count = c2.number_input("Total m3", value=int(total_m3_needed))
    r_pct = c3.number_input("Risk %", value=3.0)
    cost = 0.0
    if wallet_input:
        for m in re.findall(r"-\s*([\d,]+(?:\.\d{1,2})?)\s*ISK", wallet_input):
            cost += float(m.replace(",", ""))
    fee = (j_count * 1_000_000) + (v_count * 500) + (cost * (r_pct / 100))
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
st.sidebar.metric("Volume", f"{total_m3_needed:,} m³")
st.sidebar.code(to_buy_text)
