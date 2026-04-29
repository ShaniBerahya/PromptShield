import re


def normalize(text):
    return text.lower().strip()


def match_patterns(text, patterns):
    total_score = 0
    matched = []

    for pattern in patterns:
        kw_hit = any(kw.lower() in text for kw in pattern.get("keywords", []))
        rx_hit = any(re.search(rx, text, re.IGNORECASE) for rx in pattern.get("regex", []))

        if kw_hit or rx_hit:
            total_score += pattern["score"]
            matched.append(pattern["id"])

    return min(total_score, 100), matched


def get_risk_level(score):
    if score >= 70:
        return "high"
    elif score >= 30:
        return "medium"
    return "low"


def analyze(text, config):
    text = normalize(text)
    score, matched = match_patterns(text, config["patterns"])

    return {
        "score": score,
        "risk_level": get_risk_level(score),
        "matched_patterns": matched,
        "matches_count": len(matched)
    }
