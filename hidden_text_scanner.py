"""
PromptShield PDF Hidden Text Scanner

Detects text in PDFs that may be visually hidden:
- white or near-white text
- very light (off-white) text
- very tiny text (optional)
- text outside the visible page area (optional)
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import fitz  # PyMuPDF
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: PyMuPDF. Install with:\n    pip install pymupdf\n"
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


def _int_color_to_rgb(color: Optional[int]) -> Optional[Tuple[int, int, int]]:
    if color is None:
        return None
    try:
        color = int(color)
    except (TypeError, ValueError):
        return None
    return (color >> 16) & 255, (color >> 8) & 255, color & 255


def _is_near_white(rgb: Optional[Tuple[int, int, int]], threshold: int) -> bool:
    return rgb is not None and all(c >= threshold for c in rgb)


def _extract_span_text(span: Dict[str, Any]) -> str:
    if "text" in span and isinstance(span["text"], str):
        return span["text"]
    return "".join(ch.get("c") or ch.get("text") or "" for ch in span.get("chars", []) if isinstance(ch, dict))


def _bbox_tuple(value: Any) -> Optional[Tuple[float, float, float, float]]:
    if not value or len(value) != 4:
        return None
    return tuple(float(x) for x in value)


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

    Returns:
        {
            "file": str,
            "has_hidden_text": bool,
            "total_findings": int,
            "findings": [HiddenTextFinding, ...]
        }
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    findings: List[HiddenTextFinding] = []

    with fitz.open(pdf_path) as doc:
        for page_num, page in enumerate(doc, start=1):
            page_rect = page.rect
            for block in page.get_text("rawdict").get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = _extract_span_text(span).strip()
                        if not text:
                            continue

                        rgb = _int_color_to_rgb(span.get("color"))
                        size = float(span.get("size") or 0)
                        bbox = _bbox_tuple(span.get("bbox"))

                        if _is_near_white(rgb, white_threshold):
                            findings.append(HiddenTextFinding(
                                page=page_num, text=text,
                                detection_type="white_text", severity="high",
                                reason="Text drawn in white or near-white color.",
                                color_rgb=rgb, font=span.get("font"), size=size, bbox=bbox,
                            ))
                        elif _is_near_white(rgb, light_threshold):
                            findings.append(HiddenTextFinding(
                                page=page_num, text=text,
                                detection_type="very_light_text", severity="medium",
                                reason="Text drawn in a very light color.",
                                color_rgb=rgb, font=span.get("font"), size=size, bbox=bbox,
                            ))
                        elif include_tiny_text and 0 < size <= tiny_text_size:
                            findings.append(HiddenTextFinding(
                                page=page_num, text=text,
                                detection_type="tiny_text", severity="medium",
                                reason=f"Text size is very small ({size:.2f}).",
                                color_rgb=rgb, font=span.get("font"), size=size, bbox=bbox,
                            ))
                        elif include_offpage_text and bbox and not fitz.Rect(bbox).intersects(page_rect):
                            findings.append(HiddenTextFinding(
                                page=page_num, text=text,
                                detection_type="offpage_text", severity="medium",
                                reason="Text bounding box is outside the visible page area.",
                                color_rgb=rgb, font=span.get("font"), size=size, bbox=bbox,
                            ))

    return {
        "file": str(pdf_path),
        "has_hidden_text": bool(findings),
        "total_findings": len(findings),
        "findings": [asdict(f) for f in findings],
    }
