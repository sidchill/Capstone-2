import re


REFUSAL_PHRASES = (
    "cannot find this information",
    "not in the context",
    "not provided in the documents",
)


BLOCKED_SQL_KEYWORDS = (
    "DROP",
    "DELETE",
    "UPDATE",
    "INSERT",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "ATTACH",
    "DETACH",
    "PRAGMA",
    "VACUUM",
)


def validate_qualitative(answer: str, chunks: list[dict]) -> dict:
    sources_cited = []
    citation_errors = []

    numbered_citations = re.findall(
        r"\bSource\s+(\d+)\b",
        answer,
        re.IGNORECASE,
    )

    for number in numbered_citations:
        index = int(number)

        if 1 <= index <= len(chunks):
            source = str(
                chunks[index - 1].get("source", "unknown")
            ).strip()

            if source not in sources_cited:
                sources_cited.append(source)
        else:
            citation_errors.append(f"Unknown source number: {index}")

    structured_citations = re.findall(
        r"\[\s*Source:\s*([^,\]]+),\s*chunk:\s*([^\]]+)\]",
        answer,
        re.IGNORECASE,
    )

    for source, chunk_number in structured_citations:
        source = source.strip()
        chunk_number = chunk_number.strip()

        matches_context = any(
            str(chunk.get("source", "")).strip() == source
            and str(chunk.get("chunk", "")).strip() == chunk_number
            for chunk in chunks
        )

        if matches_context:
            if source not in sources_cited:
                sources_cited.append(source)
        else:
            citation_errors.append(
                f"Citation not found in context: "
                f"{source}, chunk {chunk_number}"
            )

    normalized = answer.lower()
    refused = any(phrase in normalized for phrase in REFUSAL_PHRASES)
    grounded = bool(sources_cited) and not citation_errors

    return {
        "is_grounded": grounded,
        "refused_to_answer": refused,
        "sources_cited": sources_cited,
        "citation_errors": citation_errors,
        "flag": not grounded and not refused,
        "warning": (
            "Response may not be grounded in source documents"
            if not grounded and not refused
            else None
        ),
    }


def is_read_only_sql(sql: str) -> bool:
    candidate = sql.strip()

    if not candidate:
        return False

    if not re.match(r"^(SELECT|WITH)\b", candidate, re.IGNORECASE):
        return False

    without_final_semicolon = (
        candidate[:-1].rstrip()
        if candidate.endswith(";")
        else candidate
    )

    if ";" in without_final_semicolon:
        return False

    normalized = candidate.upper()

    return not any(
        re.search(rf"\b{keyword}\b", normalized)
        for keyword in BLOCKED_SQL_KEYWORDS
    )


def validate_quantitative(
    answer: str,
    sql: str,
    validation_status: str,
) -> dict:
    answer_present = bool(answer.strip())
    sql_present = bool(sql.strip())
    sql_read_only = is_read_only_sql(sql)

    passed = (
        validation_status == "PASSED"
        and answer_present
        and sql_present
        and sql_read_only
    )

    if not sql_present:
        warning = "No SQL query was returned"
    elif not sql_read_only:
        warning = "SQL is not a permitted read-only SELECT or WITH query"
    elif validation_status == "FAILED":
        warning = "Generated SQL was blocked by validation"
    elif validation_status == "ERROR":
        warning = "SQL execution returned an error"
    elif not answer_present:
        warning = "No interpretation was returned"
    else:
        warning = None

    return {
        "sql_validated": passed,
        "sql_blocked": (
            validation_status == "FAILED"
            or (sql_present and not sql_read_only)
        ),
        "execution_error": validation_status == "ERROR",
        "flag": not passed,
        "warning": warning,
    }
