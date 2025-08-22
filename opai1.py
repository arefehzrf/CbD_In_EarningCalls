# earnings_sentiment_pipeline.py
# End-to-end earnings-call sentiment pipeline (LSEG/StreetEvents style)
# - Parses speakers (CEO/CFO/Analyst/Operator)
# - Calls OpenAI (GPT-4o-mini) to classify sentiment for 5 dimensions
# - Saves results to earnings_sentiment.csv
#
# Usage:
#   1) Put .txt transcripts in ./transcripts
#   2) Set OPENAI_API_KEY env var  (or put the key in openai_key.txt)
#   3) python earnings_sentiment_pipeline.py

import os
import re
import json
import time
from typing import Dict, List, Optional

import pandas as pd
from openai import OpenAI


# =========================
# Config
# =========================
TRANSCRIPTS_DIR = "./transcripts"
OUTPUT_CSV = "earnings_sentiment.csv"
OPENAI_MODEL = "gpt-4o-mini"
TEMPERATURE = 0.0
MAX_CHARS_PER_BLOCK = 8000
SLEEP_BETWEEN_CALLS = 0.2  # gentle pacing


# =========================
# Filename metadata helper
# =========================
def extract_meta_from_filename(filename_no_ext: str) -> Dict[str, Optional[str]]:
    """Extracts meta for two common patterns:
    1) AAPL_Q1_2024
    2) 2025-Jul-31-AAPL.OQ-12345
    Falls back to keeping the raw filename in 'extra_id'.
    """
    meta = {"ticker": None, "quarter": None, "year": None, "date": None, "extra_id": None}

    parts_us = filename_no_ext.split("_")
    if len(parts_us) == 3 and parts_us[1].upper().startswith("Q"):
        meta["ticker"], meta["quarter"], meta["year"] = parts_us[0], parts_us[1], parts_us[2]
        return meta

    parts_dash = filename_no_ext.split("-")
    if len(parts_dash) >= 4:
        meta["date"] = "-".join(parts_dash[:3])
        meta["ticker"] = parts_dash[3]
        meta["extra_id"] = parts_dash[4] if len(parts_dash) >= 5 else None
        return meta

    meta["extra_id"] = filename_no_ext
    return meta


# =========================
# Transcript parser (LSEG/StreetEvents style)
# =========================
SEPARATOR_RE = re.compile(r'^\s*[-=]{3,}\s*$', re.IGNORECASE)

ROLE_MAP = {
    "CHIEF EXECUTIVE OFFICER": "CEO",
    "CHIEF FINANCIAL OFFICER": "CFO",
    "CEO": "CEO",
    "CFO": "CFO",
    "ANALYST": "ANALYST",
    "OPERATOR": "OPERATOR",
    "INVESTOR RELATIONS": "IR",
}

HEADER_RE = re.compile(
    r"""^\s*
        (?:                               # Operator-only line
            (?P<operator>Operator)\s*,?\s*(?:\[\d+\])?
          |                               
            (?P<name>.+?)\s*,\s*.+?       # "Name, Affiliation - Roles    [idx]"
            (?:-|—|–)\s*
            (?P<roles>[^[]+?)
            (?:\s+\[\d+\])?
        )
        \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

SECTION_RE = re.compile(r'^\s*(presentation|q[-\s]*and[-\s]*a)\s*$', re.IGNORECASE)


def _normalize_role(raw_roles: str) -> str:
    if not raw_roles:
        return "UNKNOWN"
    joined = raw_roles.upper()
    for key, short in ROLE_MAP.items():
        if key in joined:
            return short
    if "ANALYST" in joined:
        return "ANALYST"
    return "UNKNOWN"


def parse_transcript(text: str) -> List[Dict[str, str]]:
    """Parses LSEG/StreetEvents-style transcripts into speaker blocks."""
    # Pre-clean: remove the long participant lists (bullet points)
    cleaned_lines = []
    skip_mode = False
    for line in text.splitlines():
        if SECTION_RE.match(line):
            cleaned_lines.append(f"##SECTION::{SECTION_RE.match(line).group(1).lower()}")
            skip_mode = False
            continue

        if line.strip().startswith("* "):
            skip_mode = True
        if skip_mode:
            if line.strip() == "" or SEPARATOR_RE.match(line):
                skip_mode = False
            continue

        cleaned_lines.append(line)

    lines = cleaned_lines
    n = len(lines)

    # Find headers (speakers and sections)
    headers = []
    for i, line in enumerate(lines):
        if SEPARATOR_RE.match(line):
            continue
        if SECTION_RE.match(line):
            headers.append(("SECTION", i, None))
            continue
        m = HEADER_RE.match(line)
        if m:
            if m.group("operator"):
                role = "OPERATOR"
            else:
                role = _normalize_role(m.group("roles") or "")
            headers.append(("SPEAKER", i, role))

    # Build blocks
    blocks: List[Dict[str, str]] = []
    for idx, (kind, start_i, role) in enumerate(headers):
        if kind != "SPEAKER":
            continue

        body_start = start_i + 1
        if body_start < n and SEPARATOR_RE.match(lines[body_start]):
            body_start += 1

        if idx + 1 < len(headers):
            next_kind, next_i_kind, _ = headers[idx + 1]
            body_end = next_i_kind
        else:
            body_end = n

        while body_end > body_start and SEPARATOR_RE.match(lines[body_end - 1]):
            body_end -= 1

        body = "\n".join(
            l for l in lines[body_start:body_end]
            if not SEPARATOR_RE.match(l)
        ).strip()

        if not body:
            continue

        if len(body) > MAX_CHARS_PER_BLOCK:
            body = body[:MAX_CHARS_PER_BLOCK]

        blocks.append({"speaker_role": role or "UNKNOWN", "text": body})

    if not blocks:
        body = "\n".join([l for l in lines if not SEPARATOR_RE.match(l)]).strip()
        if body:
            blocks.append({"speaker_role": "UNKNOWN", "text": body[:MAX_CHARS_PER_BLOCK]})

    return blocks


# =========================
# OpenAI client + prompt
# =========================
def read_key_from_file() -> Optional[str]:
    """Optional convenience: read API key from ./openai_key.txt if present."""
    path = "openai_key.txt"
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return None
    return None


def get_openai_client() -> OpenAI:
    """Create OpenAI client from env var or openai_key.txt. Raises if missing."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        api_key = read_key_from_file()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set and openai_key.txt was not found.\n"
            "Set the environment variable or create an openai_key.txt with your key."
        )
    return OpenAI(api_key=api_key)


def build_prompt(block_text: str) -> str:
    return (
        "You are a financial analyst.\n"
        "Classify the following earnings call excerpt by sentiment toward:\n"
        "1. Revenue\n"
        "2. Expenses\n"
        "3. Profitability\n"
        "4. Guidance/Outlook\n"
        "5. Risks/Uncertainty\n\n"
        "Sentiment scale: Positive, Neutral, Negative.\n"
        "Return ONLY a compact JSON object with these exact keys: "
        '["Revenue","Expenses","Profitability","Guidance","Uncertainty"].\n\n'
        "Text:\n"
        f'"""{block_text}"""'
    )


def parse_model_json(text: str) -> Dict[str, str]:
    """Extract a JSON object from model output; return defaults on failure."""
    code_fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    raw = code_fence.group(1) if code_fence else text.strip()
    first_brace = raw.find("{")
    last_brace = raw.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        raw = raw[first_brace:last_brace + 1]
    try:
        obj = json.loads(raw)
        if "Risks" in obj and "Uncertainty" not in obj:
            obj["Uncertainty"] = obj.pop("Risks")
        for k in ["Revenue", "Expenses", "Profitability", "Guidance", "Uncertainty"]:
            obj.setdefault(k, "Neutral")
        return obj
    except Exception as e:
        return {"error": f"JSONParseError: {type(e).__name__}: {e}", "raw": text[:3000]}


def analyse_block(client: OpenAI, text: str) -> Dict[str, str]:
    prompt = build_prompt(text)
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=TEMPERATURE,
    )
    content = resp.choices[0].message.content
    return parse_model_json(content)


# =========================
# Main
# =========================
def main() -> None:
    if not os.path.isdir(TRANSCRIPTS_DIR):
        raise FileNotFoundError(f"Transcripts directory not found: {TRANSCRIPTS_DIR}")

    files = [f for f in os.listdir(TRANSCRIPTS_DIR) if f.lower().endswith(".txt")]
    print(f"Found {len(files)} transcript(s).")

    client = get_openai_client()

    rows: List[Dict[str, object]] = []
    for file in files:
        path = os.path.join(TRANSCRIPTS_DIR, file)
        filename_no_ext = os.path.splitext(file)[0]
        meta = extract_meta_from_filename(filename_no_ext)

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                raw_text = f.read().strip()
        except Exception as e:
            print(f"[READ ERROR] {file}: {e}")
            rows.append(
                {
                    "filename": filename_no_ext,
                    **meta,
                    "block_index": None,
                    "speaker_role": None,
                    "text": None,
                    "error": f"ReadError: {e}",
                }
            )
            continue

        blocks = parse_transcript(raw_text)
        print(f"{file}: parsed {len(blocks)} block(s).")

        for idx, b in enumerate(blocks, start=1):
            try:
                result = analyse_block(client, b["text"])
            except Exception as e:
                result = {"error": f"APICallError: {type(e).__name__}: {e}"}

            rows.append(
                {
                    "filename": filename_no_ext,
                    **meta,
                    "block_index": idx,
                    "speaker_role": b.get("speaker_role"),
                    "text": b.get("text"),
                    "sentiment_json": json.dumps(result, ensure_ascii=False),
                    "Revenue": result.get("Revenue"),
                    "Expenses": result.get("Expenses"),
                    "Profitability": result.get("Profitability"),
                    "Guidance": result.get("Guidance"),
                    "Uncertainty": result.get("Uncertainty"),
                    "error": result.get("error"),
                }
            )
            time.sleep(SLEEP_BETWEEN_CALLS)

    df = pd.DataFrame(rows)
    print(f"Total rows: {len(df)}")
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    print(f"Saved {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
