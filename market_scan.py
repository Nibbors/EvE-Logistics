"""Market scan helpers for EvE-Logistics."""

import asyncio
import aiohttp
import streamlit as st

from config import JITA_REGION_ID, JITA_STATION_ID, WATCHLIST


async def get_system_info(session, name: str):
    """Resolve a system name to system id + region id via ESI."""
    try:
        url = "https://esi.evetech.net/latest/universe/ids/?datasource=tranquility&language=en"
        async with session.post(url, json=[name.strip()]) as r:
            if r.status != 200:
                return None, None
            data = await r.json()
            sys_id = data.get("systems", [{}])[0].get("id")
            if not sys_id:
                return None, None

        sys_url = f"https://esi.evetech.net/latest/universe/systems/{sys_id}/?datasource=tranquility"
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
    import requests

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
