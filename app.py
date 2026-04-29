from fastapi import FastAPI
import json
from detector import analyze

app = FastAPI()

RULES_FILE = "rules.json"

with open(RULES_FILE) as f:
    config = json.load(f)


@app.post("/analyze")
def analyze_text(data: dict):
    text = data["text"]
    return analyze(text, config)