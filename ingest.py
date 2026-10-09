import os

import chromadb
from sentence_transformers import SentenceTransformer


def chunk_document(
    text: str, chunk_size: int = 100, overlap: int = 20
) -> list[str]:
    words = text.split()

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    step = chunk_size - overlap
    return [
        " ".join(words[i : i + chunk_size])
        for i in range(0, len(words), step)
    ]


def ingest(docs_path: str) -> None:
    client = chromadb.PersistentClient(path="./data/chroma")
    collection = client.get_or_create_collection("enterprise-docs")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    for filename in os.listdir(docs_path):
        if not filename.endswith(".txt"):
            continue

        path = os.path.join(docs_path, filename)

        with open(path, encoding="utf-8") as file:
            text = file.read()

        chunks = chunk_document(text)

        if not chunks:
            continue

        embeddings = model.encode(chunks).tolist()
        ids = [f"{filename}-{i}" for i in range(len(chunks))]
        metadatas = [
            {"source": filename, "chunk": i}
            for i in range(len(chunks))
        ]

        collection.upsert(
            documents=chunks,
            embeddings=embeddings,
            ids=ids,
            metadatas=metadatas,
        )

        print(f"Ingested {len(chunks)} chunks from {filename}")


if __name__ == "__main__":
    ingest("./data/documents")
