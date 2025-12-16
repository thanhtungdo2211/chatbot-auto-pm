"""
Run chat API test cases listed in tests/chat_api_cases.txt and write results.

Configuration (env):
CHAT_API_BASE_URL (default: http://localhost:8000)
CHAT_API_ENDPOINT (default: /chat)
CHAT_API_CASES_FILE (default: tests/chat_api_cases.txt)
CHAT_API_RESULTS_FILE (default: tests/chat_api_results.txt)
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any

import requests


def load_cases(path: Path) -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.strip().startswith("#"):
            continue
        cases.append(json.loads(line))
    return cases


def run_cases(
    base_url: str,
    endpoint: str,
    cases: List[Dict[str, Any]],
    results_path: Path,
) -> None:
    session = requests.Session()
    rows = []

    for case in cases:
        name = case.get("name")
        payload = case.get("payload", {})
        url = f"{base_url.rstrip('/')}{endpoint}"
        try:
            resp = session.post(url, json=payload, timeout=15)
            body_text = resp.text
            try:
                body_json = resp.json()
            except ValueError:
                body_json = None

            rows.append(
                {
                    "name": name,
                    "status_code": resp.status_code,
                    "response_json": body_json,
                    "response_text": body_text,
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "name": name,
                    "status_code": None,
                    "response_json": None,
                    "response_text": f"ERROR: {exc}",
                }
            )

    results = []
    for row in rows:
        results.append(f"=== {row['name']} ===")
        results.append(f"status: {row['status_code']}")
        if row["response_json"] is not None:
            results.append("response (json):")
            results.append(json.dumps(row["response_json"], ensure_ascii=False, indent=2))
        else:
            results.append("response (text):")
            results.append(row["response_text"])
        results.append("")

    results_path.write_text("\n".join(results), encoding="utf-8")


def main():
    base_url = os.getenv("CHAT_API_BASE_URL", "http://localhost:8000")
    endpoint = os.getenv("CHAT_API_ENDPOINT", "/chat")
    cases_file = Path(os.getenv("CHAT_API_CASES_FILE", "tests/chat_api_cases.txt"))
    results_file = Path(os.getenv("CHAT_API_RESULTS_FILE", "tests/chat_api_results.txt"))

    cases = load_cases(cases_file)
    run_cases(base_url, endpoint, cases, results_file)
    print(f"Ran {len(cases)} cases against {base_url}{endpoint}")
    print(f"Results written to {results_file}")


if __name__ == "__main__":
    main()
