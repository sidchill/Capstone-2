import json
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

def read_rate(name: str) -> float | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    rate = float(value)
    if rate < 0:
        raise ValueError(f"{name} cannot be negative")
    return rate

INPUT_COST_PER_1M = read_rate("GEMINI_INPUT_COST_PER_1M")
OUTPUT_COST_PER_1M = read_rate("GEMINI_OUTPUT_COST_PER_1M")

def log(query: str, agent: str, input_tokens: int, output_tokens: int) -> dict:
    input_tokens = int(input_tokens or 0)
    output_tokens = int(output_tokens or 0)
    pricing_configured = (
        INPUT_COST_PER_1M is not None and OUTPUT_COST_PER_1M is not None
    )

    if pricing_configured:
        input_cost = input_tokens / 1_000_000 * INPUT_COST_PER_1M
        output_cost = output_tokens / 1_000_000 * OUTPUT_COST_PER_1M
        total_cost = round(input_cost + output_cost, 6)
        cost_per_1000_queries = round(total_cost * 1000, 2)
        cost_display = f"${total_cost:.6f}"
    else:
        total_cost = cost_per_1000_queries = None
        cost_display = "not configured"

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": MODEL_NAME,
        "query": query,
        "agent": agent,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": total_cost,
        "cost_per_1000_queries": cost_per_1000_queries,
        "pricing_configured": pricing_configured,
    }

    print(
        f"\n[TOKENOMICS] Agent: {agent} | Input: {input_tokens} | "
        f"Output: {output_tokens} | Cost: {cost_display}"
    )

    with open("tokenomics_log.jsonl", "a", encoding="utf-8") as file:
        file.write(json.dumps(entry) + "\n")

    return entry
