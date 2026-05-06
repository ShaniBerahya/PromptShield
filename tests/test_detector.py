import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engines.prompt_analyzer import analyze

DEFAULT_RULES_FILE = Path("data/promptshield_prompt_patterns.json")
DEFAULT_TESTS_FILE = Path("tests/test_cases/prompt_examples.json")
OUTPUT_DIR = Path("tests/output")


def load_json_file(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def run_tests(tests_path: Path, rules_path: Path):
    data = load_json_file(tests_path)
    config = load_json_file(rules_path)
    examples = data["examples"]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log_path = OUTPUT_DIR / "results.log"

    fp, fn, wl, passed = [], [], [], []

    for case in examples:
        result = analyze(case["text"], config)
        expected = case["risk"]
        actual = result["risk_level"]
        line = f"  {case['id']}: expected={expected}, got={actual} | score={result['score']} | patterns={result['matched_patterns']}"

        if expected == actual:
            passed.append(line)
        elif expected == "low" and actual != "low":
            fp.append(line + f"\n    prompt : {case['text']}")
        elif expected != "low" and actual == "low":
            fn.append(line + f"\n    prompt : {case['text']}")
        else:
            wl.append(line + f"\n    prompt : {case['text']}")

    failed = len(fp) + len(fn) + len(wl)
    lines = [
        f"{'='*40}",
        f"Total:           {len(examples)}",
        f"Failed:          {failed}",
        f"  False Positives: {len(fp)}",
        f"  False Negatives: {len(fn)}",
        f"  Wrong Level:     {len(wl)}",
        f"Passed:          {len(passed)}",
        f"{'='*40}",
    ]

    if fp:
        lines += ["\n── False Positives (benign flagged as risky) ──"] + fp
    if fn:
        lines += ["\n── False Negatives (malicious missed as low) ──"] + fn
    if wl:
        lines += ["\n── Wrong Level (detected but wrong severity) ──"] + wl
    if passed:
        lines += ["\n── Passed ──"] + passed

    log_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Log saved to: {log_path}")

    return failed == 0


def main(argv=None):
    argv = argv or sys.argv
    tests_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_TESTS_FILE
    rules_path = Path(argv[2]) if len(argv) > 2 else DEFAULT_RULES_FILE

    if not tests_path.exists():
        print(f"Tests file not found: {tests_path}")
        return 2
    if not rules_path.exists():
        print(f"Rules file not found: {rules_path}")
        return 3

    return 0 if run_tests(tests_path, rules_path) else 4


if __name__ == "__main__":
    sys.exit(main())
