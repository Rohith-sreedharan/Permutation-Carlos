from typing import List, Dict, Any

# OmniEdge AI stub: Enhance permutation results with adjusted confidence

def enhance_predictions(permutations: List[Dict[str, Any]], base_confidence: float) -> List[Dict[str, Any]]:
    enhanced: List[Dict[str, Any]] = []
    for p in permutations:
        score = p.get("score", 0.0)
        adjusted = round(min(1.0, base_confidence * 0.6 + score * 0.4), 3)
        enhanced.append({
            "combo": p["combo"],
            "base_score": score,
            "adjusted_confidence": adjusted,
        })
    return enhanced
