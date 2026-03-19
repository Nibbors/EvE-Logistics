"""Doctrine tracking helpers."""


def summarize_doctrine_needs(doctrines, saved_counts):
    to_buy_text = ""
    total_m3_needed = 0

    for ship in doctrines:
        current = saved_counts.get(ship["id"], 0)
        needed = max(0, ship["target"] - current)
        if needed > 0:
            to_buy_text += f"{ship['id']} {needed}\n"
            total_m3_needed += needed * ship["m3"]

    return to_buy_text, total_m3_needed
