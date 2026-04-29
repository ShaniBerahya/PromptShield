#!/usr/bin/env python3
"""
PromptShield PDF Hidden Text Scanner

Detects text in PDFs that may be visually hidden, especially:
- white or near-white text
- almost transparent text 
- very tiny text
- text placed outside the visible page area

Main use case:
    A PDF contains hidden prompt-injection text in white font.
    This scanner reports the page number and the hidden text.

Dependency:
    pip install pymupdf

CLI usage:
    python pdf_hidden_text_scanner.py suspicious.pdf
    python pdf_hidden_text_scanner.py suspicious.pdf --json
    python pdf_hidden_text_scanner.py suspicious.pdf --include-tiny --include-offpage
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import fitz  # PyMuPDF
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: PyMuPDF. Install it with:\n\n"
        "    pip install pymupdf\n"
    ) from exc


@dataclass
class HiddenTextFinding:
    page: int
    text: str
    detection_type: str
    severity: str
    reason: str
    color_rgb: Optional[Tuple[int, int, int]] = None
    font: Optional[str] = None
    size: Optional[float] = None
    bbox: Optional[Tuple[float, float, float, float]] = None


def int_color_to_rgb(color: Optional[int]) -> Optional[Tuple[int, int, int]]:
    """
    Convert a PyMuPDF integer color into an RGB tuple.

    PyMuPDF often stores text color as an integer:
        0xRRGGBB
    """
    if color is None:
        return None

    try:
        color = int(color)
    except (TypeError, ValueError):
        return None

    r = (color >> 16) & 255
    g = (color >> 8) & 255
    b = color & 255
    return r, g, b


def is_near_white(rgb: Optional[Tuple[int, int, int]], threshold: int = 245) -> bool:
    """
    Return True when all RGB channels are close to white.

    threshold=245 means:
        RGB(245,245,245) through RGB(255,255,255)
    are treated as near-white.
    """
    if rgb is None:
        return False
    return all(channel >= threshold for channel in rgb)


def is_very_light(rgb: Optional[Tuple[int, int, int]], threshold: int = 235) -> bool:
    """
    Slightly weaker version of near-white detection.
    Useful for off-white text that may still be hard to see.
    """
    if rgb is None:
        return False
    return all(channel >= threshold for channel in rgb)


def extract_span_text(span: Dict[str, Any]) -> str:
    """
    Extract readable text from a PyMuPDF span.

    Depending on extraction mode/version, a span may contain:
    - span["text"]
    - span["chars"], where each char has c/text
    """
    if "text" in span and isinstance(span["text"], str):
        return span["text"]

    chars = span.get("chars", [])
    output = []

    for ch in chars:
        if isinstance(ch, dict):
            output.append(ch.get("c") or ch.get("text") or "")

    return "".join(output)


def bbox_tuple(value: Any) -> Optional[Tuple[float, float, float, float]]:
    """
    Convert a bbox-like value into a clean tuple.
    """
    if not value or len(value) != 4:
        return None
    return tuple(float(x) for x in value)


def bbox_is_outside_page(
    bbox: Optional[Tuple[float, float, float, float]],
    page_rect: fitz.Rect,
) -> bool:
    """
    Return True when the text bounding box is completely outside the page.
    """
    if bbox is None:
        return False

    rect = fitz.Rect(bbox)
    return not rect.intersects(page_rect)


def scan_pdf_for_hidden_text(
    pdf_path: str | Path,
    *,
    white_threshold: int = 245,
    light_threshold: int = 235,
    include_tiny_text: bool = False,
    tiny_text_size: float = 2.0,
    include_offpage_text: bool = False,
) -> Dict[str, Any]:
    """
    Scan a PDF for potentially hidden text.

    Parameters:
        pdf_path:
            Path to the PDF file.

        white_threshold:
            RGB threshold for definite white/near-white text.

        light_threshold:
            RGB threshold for suspicious very-light text.

        include_tiny_text:
            If True, also report very small text.

        tiny_text_size:
            Text size at or below this value is reported when include_tiny_text=True.

        include_offpage_text:
            If True, also report text whose bbox is outside the page area.

    Returns:
        A dictionary:
        {
            "file": "...",
            "has_hidden_text": true/false,
            "total_findings": number,
            "findings": [...]
        }
    """
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    findings: List[HiddenTextFinding] = []

    with fitz.open(pdf_path) as doc:
        for page_index, page in enumerate(doc, start=1):
            page_rect = page.rect

            # rawdict gives structured blocks / lines / spans / chars.
            raw = page.get_text("rawdict")

            for block in raw.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = extract_span_text(span).strip()
                        if not text:
                            continue

                        rgb = int_color_to_rgb(span.get("color"))
                        size = float(span.get("size", 0) or 0)
                        font = span.get("font")
                        bbox = bbox_tuple(span.get("bbox"))

                        # 1. Main feature: white / near-white text
                        if is_near_white(rgb, white_threshold):
                            findings.append(
                                HiddenTextFinding(
                                    page=page_index,
                                    text=text,
                                    detection_type="white_text",
                                    severity="high",
                                    reason=(
                                        "The PDF draws this text in white or near-white color, "
                                        "which may hide it on a white background."
                                    ),
                                    color_rgb=rgb,
                                    font=font,
                                    size=size,
                                    bbox=bbox,
                                )
                            )
                            continue

                        # 2. Suspicious but weaker: very light gray/off-white
                        if is_very_light(rgb, light_threshold):
                            findings.append(
                                HiddenTextFinding(
                                    page=page_index,
                                    text=text,
                                    detection_type="very_light_text",
                                    severity="medium",
                                    reason=(
                                        "The PDF draws this text in a very light color, "
                                        "which may be difficult to see."
                                    ),
                                    color_rgb=rgb,
                                    font=font,
                                    size=size,
                                    bbox=bbox,
                                )
                            )
                            continue

                        # 3. Optional: tiny text
                        if include_tiny_text and 0 < size <= tiny_text_size:
                            findings.append(
                                HiddenTextFinding(
                                    page=page_index,
                                    text=text,
                                    detection_type="tiny_text",
                                    severity="medium",
                                    reason=(
                                        f"The text size is very small ({size:.2f}), "
                                        "which may be used to hide instructions."
                                    ),
                                    color_rgb=rgb,
                                    font=font,
                                    size=size,
                                    bbox=bbox,
                                )
                            )
                            continue

                        # 4. Optional: text outside visible page area
                        if include_offpage_text and bbox_is_outside_page(bbox, page_rect):
                            findings.append(
                                HiddenTextFinding(
                                    page=page_index,
                                    text=text,
                                    detection_type="offpage_text",
                                    severity="medium",
                                    reason=(
                                        "The text bounding box is outside the visible page area."
                                    ),
                                    color_rgb=rgb,
                                    font=font,
                                    size=size,
                                    bbox=bbox,
                                )
                            )
                            continue

    return {
        "file": str(pdf_path),
        "has_hidden_text": len(findings) > 0,
        "total_findings": len(findings),
        "findings": [asdict(item) for item in findings],
    }


def format_report(result: Dict[str, Any]) -> str:
    """
    Create a human-readable report for the CLI.
    """
    lines = []
    lines.append("PromptShield PDF Hidden Text Scan")
    lines.append("=" * 38)
    lines.append(f"File: {result['file']}")
    lines.append(f"Hidden text found: {result['has_hidden_text']}")
    lines.append(f"Total findings: {result['total_findings']}")
    lines.append("")

    if not result["findings"]:
        lines.append("No hidden white/near-white text was detected.")
        return "\n".join(lines)

    for index, finding in enumerate(result["findings"], start=1):
        lines.append(f"Finding #{index}")
        lines.append(f"Page: {finding['page']}")
        lines.append(f"Type: {finding['detection_type']}")
        lines.append(f"Severity: {finding['severity']}")
        lines.append(f"Text: {finding['text']}")
        lines.append(f"Reason: {finding['reason']}")

        if finding.get("color_rgb"):
            lines.append(f"RGB color: {tuple(finding['color_rgb'])}")
        if finding.get("font"):
            lines.append(f"Font: {finding['font']}")
        if finding.get("size") is not None:
            lines.append(f"Size: {finding['size']}")
        if finding.get("bbox"):
            lines.append(f"Bounding box: {tuple(finding['bbox'])}")

        lines.append("-" * 38)

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan a PDF for hidden white or near-white text."
    )
    parser.add_argument("pdf", help="Path to the PDF file")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print result as JSON instead of a text report",
    )
    parser.add_argument(
        "--white-threshold",
        type=int,
        default=245,
        help="RGB threshold for near-white text. Default: 245",
    )
    parser.add_argument(
        "--light-threshold",
        type=int,
        default=235,
        help="RGB threshold for suspicious very-light text. Default: 235",
    )
    parser.add_argument(
        "--include-tiny",
        action="store_true",
        help="Also report very tiny text",
    )
    parser.add_argument(
        "--tiny-size",
        type=float,
        default=2.0,
        help="Tiny text size threshold. Default: 2.0",
    )
    parser.add_argument(
        "--include-offpage",
        action="store_true",
        help="Also report text outside the visible page area",
    )

    args = parser.parse_args()

    result = scan_pdf_for_hidden_text(
        args.pdf,
        white_threshold=args.white_threshold,
        light_threshold=args.light_threshold,
        include_tiny_text=args.include_tiny,
        tiny_text_size=args.tiny_size,
        include_offpage_text=args.include_offpage,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_report(result))


if __name__ == "__main__":
    main()
