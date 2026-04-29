import math
import re

# ─── Scoring Formula ────────────────────────────────────────────────────────
#
#   Final score S = WK * Skw + WR * Srx       S ∈ [0, 1]
#
#   WK = 0.4  (keyword contribution)
#   WR = 0.6  (regex contribution — weighted higher, more precise)
#
#   Each pattern has a JSON `score` (0–100) representing its strength.
#   Normalized to [0,1] by dividing by 100 → called `weight` (w).
#
#   Skw  — Keyword Score
#   ─────────────────────
#   For each pattern, if ANY of its keywords appear in the text,
#   that pattern's weight is added to the matched sum.
#   An exponential curve converts the sum to [0,1]:
#
#     Skw = 1 - e^(-ALPHA * Σ wi)
#
#     wi    = p.score / 100  for each pattern with a keyword hit
#     ALPHA = sharpness factor (ALPHA=4 means one strong match w=0.4
#             gives Skw ≈ 0.80; two matches push toward 1.0)
#
#   Srx  — Regex Score
#   ────────────────────
#   Same formula, but triggered by regex matches instead of keywords:
#
#     Srx = 1 - e^(-ALPHA * Σ wi)
#
#     wi = p.score / 100  for each pattern where ANY regex matches
#
#   Using exponential (not linear sum / total) avoids the dilution
#   problem where many patterns make each individual match near-zero.
#   A single high-score pattern still produces a meaningful result.
#
# ─── Risk Thresholds ────────────────────────────────────────────────────────
#   S >= 0.5  → high
#   S >= 0.2  → medium
#   S <  0.2  → low
# ────────────────────────────────────────────────────────────────────────────

WK = 0.4
WR = 0.6
ALPHA = 4


def normalize(text):
    return text.lower().strip()


def keyword_score(text, patterns):
    weights = [
        p["score"] / 100
        for p in patterns
        if any(kw.lower() in text for kw in p.get("keywords", []))
    ]
    if not weights:
        return 0.0
    return 1 - math.exp(-ALPHA * sum(weights))


def regex_score(text, patterns):
    weights = [
        p["score"] / 100
        for p in patterns
        if any(re.search(rx, text, re.IGNORECASE) for rx in p.get("regex", []))
    ]
    if not weights:
        return 0.0
    return 1 - math.exp(-ALPHA * sum(weights))


def get_risk_level(score):
    if score >= 0.5:
        return "high"
    elif score >= 0.2:
        return "medium"
    return "low"


def analyze(text, config):
    normalized = normalize(text)
    patterns = config["patterns"]

    skw = keyword_score(normalized, patterns)
    srx = regex_score(normalized, patterns)
    final = WK * skw + WR * srx

    matched = [
        p["id"] for p in patterns
        if any(kw.lower() in normalized for kw in p.get("keywords", []))
        or any(re.search(rx, normalized, re.IGNORECASE) for rx in p.get("regex", []))
    ]

    return {
        "score": round(final, 4),
        "skw": round(skw, 4),
        "srx": round(srx, 4),
        "risk_level": get_risk_level(final),
        "matched_patterns": matched,
        "matches_count": len(matched),
    }
