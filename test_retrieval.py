import chromadb
from sentence_transformers import SentenceTransformer

CHROMA_PATH = "./data/chroma"
COLLECTION_NAME = "enterprise-docs"
TOP_K = 3

TEST_QUERIES = [
    "What is the employee satisfaction policy?",
    "How are sales reported by region?",
    "What is the customer churn process?",
]


def main() -> None:
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection(COLLECTION_NAME)
    model = SentenceTransformer("all-MiniLM-L6-v2")

    print(f"Indexed chunks: {collection.count()}")

    if collection.count() == 0:
        print("No chunks found. Run: python ingest.py")
        return

    for query in TEST_QUERIES:
        embedding = model.encode([query]).tolist()
        results = collection.query(
            query_embeddings=embedding,
            n_results=TOP_K,
            include=["documents", "metadatas", "distances"],
        )

        print(f"\nQUERY: {query}")

        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        for index, document in enumerate(documents, start=1):
            metadata = metadatas[index - 1]
            distance = distances[index - 1]

            print(f"\nResult {index}")
            print(f"Source: {metadata['source']}")
            print(f"Chunk: {metadata['chunk']}")
            print(f"Distance: {distance:.4f}")
            print(f"Content: {document[:500]}...")


if __name__ == "__main__":
    main()