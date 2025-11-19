from typing import List, Dict, Any

# Simple placeholder permutation engine to combine odds across bookmakers/markets
# Returns top-N combinations by naive score (product of normalized prices)

def score_combination(combo: List[Dict[str, Any]]) -> float:
    score = 1.0
    for leg in combo:
        price = leg.get("price")
        try:
            price = float(price)
        except (TypeError, ValueError):
            price = 1.0
        # Normalize decimal odds (e.g., 1.5..3.0) into ~0..1 space
        score *= max(0.1, min(price / 10.0, 1.0))
    return score


def run_permutations(odds: List[Dict[str, Any]], max_legs: int = 2, top_n: int = 5) -> List[Dict[str, Any]]:
    # naive O(n^2) for 2-leg combos; can be extended
    results: List[Dict[str, Any]] = []
    n = len(odds)
    if max_legs <= 1:
        for i in range(n):
            combo = [odds[i]]
            results.append({"combo": combo, "score": score_combination(combo)})
    else:
        for i in range(n):
            for j in range(i + 1, n):
                combo = [odds[i], odds[j]]
                results.append({"combo": combo, "score": score_combination(combo)})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_n]
