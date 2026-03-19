"""Wallet parsing and hauling cost calculations."""

import re


def parse_wallet_cost(wallet_input: str) -> float:
    cost = 0.0
    for match in re.findall(r"-\s*([\d,]+(?:\.\d{1,2})?)\s*ISK", wallet_input or ""):
        cost += float(match.replace(",", ""))
    return cost


def calculate_fee(jumps: int, volume_m3: float, risk_pct: float, base_cost: float) -> float:
    return (jumps * 1_000_000) + (volume_m3 * 500) + (base_cost * (risk_pct / 100))
