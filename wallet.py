"""Wallet parsing and hauling cost calculations."""

import math
import re
from dataclasses import dataclass


@dataclass
class PricingBreakdown:
    jita_total: float
    jumps: int
    isk_per_jump: float
    volume_m3: float
    isk_per_m3: float
    risk_pct: float
    jump_fee: float
    volume_fee: float
    subtotal_before_risk: float
    risk_fee: float
    final_total: float
    dst_capacity_m3: float
    dst_loads: int
    effective_markup_pct: float


def parse_wallet_cost(wallet_input: str) -> float:
    cost = 0.0
    for match in re.findall(r"-\s*([\d,]+(?:\.\d{1,2})?)\s*ISK", wallet_input or ""):
        cost += float(match.replace(",", ""))
    return cost


def calculate_pricing(
    jumps: int,
    volume_m3: float,
    risk_pct: float,
    base_cost: float,
    isk_per_jump: float = 1_000_000,
    isk_per_m3: float = 500,
    dst_capacity_m3: float = 62_500,
) -> PricingBreakdown:
    jump_fee = float(jumps) * float(isk_per_jump)
    volume_fee = float(volume_m3) * float(isk_per_m3)
    subtotal_before_risk = float(base_cost) + jump_fee + volume_fee
    risk_fee = subtotal_before_risk * (float(risk_pct) / 100.0)
    final_total = subtotal_before_risk + risk_fee
    dst_loads = max(1, math.ceil(float(volume_m3) / float(dst_capacity_m3))) if volume_m3 > 0 else 0
    effective_markup_pct = ((final_total - float(base_cost)) / float(base_cost) * 100.0) if base_cost > 0 else 0.0

    return PricingBreakdown(
        jita_total=float(base_cost),
        jumps=int(jumps),
        isk_per_jump=float(isk_per_jump),
        volume_m3=float(volume_m3),
        isk_per_m3=float(isk_per_m3),
        risk_pct=float(risk_pct),
        jump_fee=jump_fee,
        volume_fee=volume_fee,
        subtotal_before_risk=subtotal_before_risk,
        risk_fee=risk_fee,
        final_total=final_total,
        dst_capacity_m3=float(dst_capacity_m3),
        dst_loads=dst_loads,
        effective_markup_pct=effective_markup_pct,
    )


def calculate_fee(
    jumps: int,
    volume_m3: float,
    risk_pct: float,
    base_cost: float,
    isk_per_jump: float = 1_000_000,
    isk_per_m3: float = 500,
    dst_capacity_m3: float = 62_500,
) -> float:
    breakdown = calculate_pricing(
        jumps=jumps,
        volume_m3=volume_m3,
        risk_pct=risk_pct,
        base_cost=base_cost,
        isk_per_jump=isk_per_jump,
        isk_per_m3=isk_per_m3,
        dst_capacity_m3=dst_capacity_m3,
    )
    return breakdown.final_total - breakdown.jita_total
