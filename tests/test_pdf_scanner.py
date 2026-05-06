import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engines.hidden_text_scanner import scan_pdf_for_hidden_text

MANIFEST = Path("tests/test_cases/promptshield_pdf_test_bank_manifest.json")
PDF_DIR  = Path("tests/test_cases")
OUTPUT   = Path("tests/output/pdf_results.log")


def run_tests(manifest_path: Path, pdf_dir: Path):
    manifest = json.loads(manifest_path.read_text())
    cases = manifest["files"]

    fp, fn, wl, passed = [], [], [], []

    for case in cases:
        pdf_path = pdf_dir / case["filename"]
        if not pdf_path.exists():
            fn.append(f"  {case['id']}: FILE NOT FOUND — {case['filename']}")
            continue

        result = scan_pdf_for_hidden_text(pdf_path)

        expected_found = case["expected_hidden_text_found"]
        expected_count = case["expected_hidden_text_count"]
        actual_found   = result["has_hidden_text"]
        actual_count   = result["total_findings"]

        found_texts = [f["text"] for f in result["findings"]]
        line = (
            f"  {case['id']}: expected_found={expected_found} got={actual_found} | "
            f"expected_count={expected_count} got={actual_count}"
        )

        if expected_found == actual_found and expected_count == actual_count:
            passed.append(line + (f"\n    detected: {found_texts}" if found_texts else ""))
        elif not expected_found and actual_found:
            fp.append(line + f"\n    detected: {found_texts}")
        elif expected_found and not actual_found:
            fn.append(line + f"\n    expected: {case['expected_hidden_text']}")
        else:
            wl.append(line + f"\n    expected: {case['expected_hidden_text']}\n    detected: {found_texts}")

    failed = len(fp) + len(fn) + len(wl)
    lines = [
        "=" * 40,
        f"Total:           {len(cases)}",
        f"Failed:          {failed}",
        f"  False Positives: {len(fp)}  (clean PDF flagged)",
        f"  False Negatives: {len(fn)}  (hidden text missed)",
        f"  Wrong Count:     {len(wl)}  (detected but wrong count)",
        f"Passed:          {len(passed)}",
        "=" * 40,
    ]

    if fp:
        lines += ["\n── False Positives ──"] + fp
    if fn:
        lines += ["\n── False Negatives ──"] + fn
    if wl:
        lines += ["\n── Wrong Count ──"] + wl
    if passed:
        lines += ["\n── Passed ──"] + passed

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Log saved to: {OUTPUT}")
    return failed == 0


def main(argv=None):
    argv = argv or sys.argv
    manifest = Path(argv[1]) if len(argv) > 1 else MANIFEST
    pdf_dir  = Path(argv[2]) if len(argv) > 2 else PDF_DIR

    if not manifest.exists():
        print(f"Manifest not found: {manifest}")
        return 2

    return 0 if run_tests(manifest, pdf_dir) else 4


if __name__ == "__main__":
    sys.exit(main())
