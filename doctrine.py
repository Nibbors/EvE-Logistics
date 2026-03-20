"""Doctrine tracking and EVE fit parsing helpers."""

from __future__ import annotations

from typing import Dict, List


def summarize_doctrine_needs(doctrines, saved_counts):
    to_buy_text = ""
    total_m3_needed = 0

    for ship in doctrines:
        current = saved_counts.get(ship["id"], 0)
        needed = max(0, int(ship.get("target", 0)) - current)
        if needed > 0:
            to_buy_text += f"{ship['id']} {needed}\n"
            total_m3_needed += needed * float(ship.get("m3", 0))

    return to_buy_text, total_m3_needed


def parse_eve_fit(fit_text: str) -> Dict:
    """Parse standard EVE fitting text into a lightweight doctrine record."""
    lines = [line.rstrip() for line in (fit_text or "").splitlines()]
    non_empty = [line.strip() for line in lines if line.strip()]
    if not non_empty:
        raise ValueError("Fit text is empty.")

    header = non_empty[0]
    if not (header.startswith("[") and header.endswith("]") and "," in header):
        raise ValueError("First line must look like [Hull, Fit Name].")

    inner = header[1:-1]
    hull, fit_name = [part.strip() for part in inner.split(",", 1)]

    sections: List[List[str]] = []
    current: List[str] = []
    for raw_line in lines[1:]:
        line = raw_line.strip()
        if not line:
            if current:
                sections.append(current)
                current = []
            continue
        current.append(line)
    if current:
        sections.append(current)

    lows = sections[0] if len(sections) > 0 else []
    mids = sections[1] if len(sections) > 1 else []
    highs = sections[2] if len(sections) > 2 else []
    rigs = sections[3] if len(sections) > 3 else []
    subsystems = sections[4] if len(sections) > 4 else []
    drones = sections[5] if len(sections) > 5 else []
    cargo = sections[6] if len(sections) > 6 else []

    item_lines = lows + mids + highs + rigs + subsystems + drones + cargo

    return {
        "id": hull,
        "name": f"{hull} | {fit_name}",
        "fit_name": fit_name,
        "hull": hull,
        "fit_text": fit_text.strip(),
        "lows": lows,
        "mids": mids,
        "highs": highs,
        "rigs": rigs,
        "subsystems": subsystems,
        "drones": drones,
        "cargo": cargo,
        "item_count": len(item_lines),
    }
