import os
import re
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set.")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "database.sqlite"

if not DATABASE_PATH.is_file():
    raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")

DATABASE_URI = DATABASE_PATH.as_uri() + "?mode=ro"
client = genai.Client(api_key=API_KEY)

SCHEMA_CONTEXT = """
Available tables:
- sales(id, region, product, revenue, date, units_sold)
- customers(id, name, industry, churn_date, satisfaction_score)
- employees(id, department, satisfaction_score, tenure_years)
"""

BLOCKED_KEYWORDS = (
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER",
    "TRUNCATE", "CREATE", "ATTACH", "DETACH",
    "PRAGMA", "VACUUM",
)


def token_usage(response) -> tuple[int, int]:
    usage = response.usage_metadata
    return (
        getattr(usage, "prompt_token_count", 0) or 0,
        getattr(usage, "candidates_token_count", 0) or 0,
    )


def clean_sql(sql: str) -> str:
    sql = sql.strip()

    if sql.startswith("```"):
        lines = sql.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        sql = "\n".join(lines).strip()

    if sql.lower().startswith("sql"):
        sql = sql[3:].strip()

    return sql


def validate_sql(query: str) -> dict:
    candidate = query.strip()

    if not candidate:
        return {"valid": False, "reason": "The generated SQL query is empty"}

    normalized = candidate.upper()

    if not re.match(r"^(SELECT|WITH)\b", normalized):
        return {
            "valid": False,
            "reason": "Only SELECT queries are permitted",
        }

    for keyword in BLOCKED_KEYWORDS:
        if re.search(rf"\b{keyword}\b", normalized):
            return {"valid": False, "reason": f"Blocked keyword: {keyword}"}

    if ";" in candidate.rstrip().rstrip(";"):
        return {
            "valid": False,
            "reason": "Multiple SQL statements are not permitted",
        }

    return {"valid": True, "reason": "OK"}


def generate_sql(query: str) -> dict:
    prompt = f"""
{SCHEMA_CONTEXT}

Generate a read-only SQLite SQL query for the user's request.

User request:
{query}

Return ONLY the SQL query. Do not use Markdown fences or explanations.
""".strip()

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=256,
        ),
    )

    input_tokens, output_tokens = token_usage(response)

    return {
        "sql": clean_sql(response.text or ""),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def interpret_results(
    user_query: str,
    sql: str,
    columns: list[str],
    rows: list[tuple],
) -> dict:
    prompt = f"""
The user asked:
{user_query}

SQL query used:
{sql}

Results:
Columns: {columns}
Data: {rows[:20]}

Provide a clear, concise interpretation using only the results.
Do not invent facts that are not present in the results.
""".strip()

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=512,
        ),
    )

    input_tokens, output_tokens = token_usage(response)

    return {
        "answer": response.text or "Gemini returned an empty interpretation.",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def run(query: str) -> dict:
    sql_result = generate_sql(query)
    sql = sql_result["sql"]

    validation = validate_sql(sql)

    if not validation["valid"]:
        return {
            "answer": f"Query blocked: {validation['reason']}",
            "sql": sql,
            "rows": [],
            "validation": "FAILED",
            "input_tokens": sql_result["input_tokens"],
            "output_tokens": sql_result["output_tokens"],
        }

    try:
        with sqlite3.connect(DATABASE_URI, uri=True) as connection:
            cursor = connection.cursor()

            # The SQL has passed validate_sql immediately before execution.
            cursor.execute(sql)

            rows = cursor.fetchall()
            columns = [
                description[0]
                for description in cursor.description
            ]

        interpretation = interpret_results(query, sql, columns, rows)

        return {
            "answer": interpretation["answer"],
            "sql": sql,
            "columns": columns,
            "rows": rows,
            "validation": "PASSED",
            "input_tokens": (
                sql_result["input_tokens"]
                + interpretation["input_tokens"]
            ),
            "output_tokens": (
                sql_result["output_tokens"]
                + interpretation["output_tokens"]
            ),
        }

    except Exception as error:
        return {
            "answer": f"Query execution failed: {error}",
            "sql": sql,
            "rows": [],
            "validation": "ERROR",
            "input_tokens": sql_result["input_tokens"],
            "output_tokens": sql_result["output_tokens"],
        }
