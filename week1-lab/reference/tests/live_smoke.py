"""Make one paid Converse request to check model access in the configured Region.

Run from `reference/` with `uv run python -m tests.live_smoke`. The test uses the
course inference profile, records the attempt in the ledger and prints its
request identifier, token usage and cost. Output excludes the account number.
A failed request prints the error and exits with status 1.
"""

from __future__ import annotations

import json
import sys

from support_assistant import config
from support_assistant.bedrock import BedrockCallError, BedrockClient
from support_assistant.ledger import Ledger


def main() -> int:
    try:
        region = config.region()
    except config.ConfigurationError as error:
        print(f"Smoke test not run: {error}")
        return 1
    ledger = Ledger()
    client = BedrockClient(ledger=ledger)
    try:
        result = client.converse([{"role": "user", "content": [{"text": "Reply with the single word: ready"}]}],
                                 max_tokens=10, run_id="live-smoke")
    except BedrockCallError as error:
        print(f"Smoke test failed in {region} with {config.MODEL_ID}: {error.code}: {config.redact(error.message)}")
        return 1
    row = ledger.rows("live-smoke")[-1]
    print(json.dumps({"region": region, "model_id": config.MODEL_ID, "stop_reason": result.stop_reason,
                      "request_id": result.request_id, "usage": result.usage, "latency_ms": result.latency_ms,
                      "cost_usd": row["cost_usd"], "price_read_on": row["price_read_on"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
