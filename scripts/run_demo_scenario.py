"""Run Nomi's deterministic detection -> verification -> alert demo."""

from __future__ import annotations

import argparse
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request(base_url: str, method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--senior-id", default="senior-1")
    parser.add_argument(
        "--outcome",
        choices=("no-response", "reassuring", "help-needed"),
        default="no-response",
    )
    args = parser.parse_args()

    try:
        detection = request(
            args.api_url,
            "GET",
            f"/api/v1/seniors/{args.senior_id}/detections/anomaly",
        )
        print(f"1. Detection: {detection['detected']} - {detection['summary']}")
        if not detection["detected"]:
            raise RuntimeError("The selected senior has no actionable demo detection.")

        started = request(
            args.api_url,
            "POST",
            "/api/v1/verifications",
            {
                "senior_id": args.senior_id,
                "senior_name": "Mdm Tan",
                "detection": detection,
            },
        )
        verification_id = started["verification"]["id"]
        print(f"2. Verification started: {verification_id}")

        if args.outcome == "no-response":
            result = request(
                args.api_url,
                "POST",
                f"/api/v1/verifications/{verification_id}/no-response",
                {},
            )
        else:
            outcome = "reassuring" if args.outcome == "reassuring" else "help_needed"
            result = request(
                args.api_url,
                "POST",
                f"/api/v1/verifications/{verification_id}/response",
                {"outcome": outcome, "response_text": "Demo response"},
            )

        print(f"3. Verification result: {result['verification']['status']}")
        if result["alert"]:
            print(f"4. Caregiver alert: {result['alert']['what_changed']}")
            print(f"5. Suggested action: {result['alert']['suggested_action']}")
        else:
            print("4. Concern resolved without a caregiver alert.")
        return 0
    except (HTTPError, URLError, RuntimeError) as error:
        print(f"Demo failed: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
