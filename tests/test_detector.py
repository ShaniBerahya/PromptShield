import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from detector import analyze

DEFAULT_RULES_FILE = Path("prompts/promptshield_prompt_patterns.json")
DEFAULT_TESTS_FILE = Path("tests/test_cases/examples.json")


def load_json_file(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def run_tests(tests_path: Path, rules_path: Path):
    data = load_json_file(tests_path)
    config = load_json_file(rules_path)
    examples = data["examples"]

    passed = failed = false_positives = false_negatives = 0
    for case in examples:
        result = analyze(case["text"], config)
        expected = case["risk"]
        actual = result["risk_level"]
        ok = expected == actual
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {case['id']}: expected={expected}, got={actual}")
        if ok:
            passed += 1
        else:
            failed += 1
            if expected == "low" and actual != "low":
                false_positives += 1
            elif expected != "low" and actual == "low":
                false_negatives += 1

    print(f"\n{'='*40}")
    print(f"Total:          {len(examples)}")
    print(f"Passed:         {passed}")
    print(f"Failed:         {failed}")
    print(f"False Positives: {false_positives}  (benign flagged as risky)")
    print(f"False Negatives: {false_negatives}  (malicious missed as low)")
    print(f"{'='*40}")
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
