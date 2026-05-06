from fastapi import FastAPI, UploadFile, File
import json
import tempfile
from pathlib import Path

from engines.prompt_analyzer import analyze
from engines.hidden_text_scanner import scan_pdf_for_hidden_text

app = FastAPI()

RULES_FILE = Path("data/promptshield_prompt_patterns.json")

with RULES_FILE.open() as f:
    config = json.load(f)


@app.post("/analyze")
def analyze_text(data: dict):
    text = data.get("text", "")
    return analyze(text, config)


@app.post("/scan-pdf")
async def scan_pdf(
    file: UploadFile = File(...),
    include_tiny: bool = False,
    include_offpage: bool = False,
):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        result = scan_pdf_for_hidden_text(
            tmp_path,
            include_tiny_text=include_tiny,
            include_offpage_text=include_offpage,
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    return result
