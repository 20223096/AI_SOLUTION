def non_dominated(candidates: list[dict]) -> list[dict]:
    out = []
    for candidate in candidates:
        x, y = candidate["resident_cost"], candidate["change_cost"]
        dominated = any((other["resident_cost"] <= x and other["change_cost"] <= y) and (other["resident_cost"] < x or other["change_cost"] < y) for other in candidates)
        if not dominated:
            out.append(candidate)
    return out
