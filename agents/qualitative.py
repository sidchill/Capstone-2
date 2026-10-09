import os
import time

import chromadb
from dotenv import load_dotenv
from google import genai
from google.genai import types
from sentence_transformers import SentenceTransformer

load_dotenv()

CANNOT_FIND = "I cannot find this information in the provided documents."

MODEL_CANDIDATES = list(
    dict.fromkeys(
        [
            os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
            os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.8-flash"),
            "gemini-3.5-flash-lite",
        ]
    )
)

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY is not set in your .env file.")

client = genai.Client(api_key=api_key)
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

SYSTEM_INSTRUCTION = f"""
You are a helpful enterprise documentation assistant.

Answer the user's question using ONLY the retrieved context provided in the
user message. Do not use outside knowledge, assumptions, or invented facts.

If the answer is not directly supported by the retrieved context, respond
exactly with: "{CANNOT_FIND}"

Every factual answer must cite retrieved sources using labels such as
[Source 1]. Do not invent sources, policies, or facts. Keep the answer concise.
""".strip()


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    chroma = chromadb.PersistentClient(path="./data/chroma")
    collection = chroma.get_collection("enterprise-docs")
    embedding = embedding_model.encode([query]).tolist()

    results = collection.query(
        query_embeddings=embedding,
        n_results=top_k,
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    return [
        {
            "content": document,
            "source": (metadata or {}).get("source", "unknown"),
            "chunk": (metadata or {}).get("chunk", "unknown"),
        }
        for document, metadata in zip(documents, metadatas)
    ]


def build_prompt(query: str, chunks: list[dict]) -> str:
    context = "\n\n".join(
        f"[Source {index}]\n{chunk['content']}"
        for index, chunk in enumerate(chunks, start=1)
    )

    return f"""
Retrieved context:

{context or "(No relevant context was retrieved.)"}

User question:

{query}

Answer using only the retrieved context. Cite factual statements with the
exact source labels shown above, such as [Source 1].
""".strip()


def is_retryable(error: Exception) -> bool:
    message = str(error).upper()

    return any(
        marker in message
        for marker in (
            "429",
            "500",
            "502",
            "503",
            "504",
            "UNAVAILABLE",
            "RESOURCE_EXHAUSTED",
            "TIMEOUT",
        )
    )


def generate_answer(prompt: str):
    errors = []

    for model in MODEL_CANDIDATES:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        temperature=0,
                        max_output_tokens=1024,
                    ),
                )

                print(f"\n[Qualitative] Model used: {model}")
                return response

            except Exception as error:
                errors.append(f"{model}: {type(error).__name__}: {error}")

                if attempt == 0 and is_retryable(error):
                    wait_seconds = 2
                    print(
                        f"\n[Qualitative] {model} unavailable; "
                        f"retrying in {wait_seconds} seconds..."
                    )
                    time.sleep(wait_seconds)
                else:
                    print(
                        f"\n[Qualitative] Trying next model after "
                        f"{type(error).__name__}."
                    )
                    break

    raise RuntimeError(
        "All Gemini model attempts failed:\n" + "\n".join(errors)
    )


def run(query: str) -> dict:
    chunks = retrieve(query)
    prompt = build_prompt(query, chunks)
    response = generate_answer(prompt)

    usage = getattr(response, "usage_metadata", None)
    answer = (response.text or "").strip() or CANNOT_FIND

    return {
        "answer": answer,
        "chunks": chunks,
        "input_tokens": int(
            getattr(usage, "prompt_token_count", 0) or 0
        ),
        "output_tokens": int(
            getattr(usage, "candidates_token_count", 0) or 0
        ),
    }
