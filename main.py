from agents.manager import run

def main():
    print("Unit 2 Enterprise RAG System")
    print("Type 'exit' to quit.\n")

    while True:
        query = input("Ask a question: ").strip()
        if query.lower() in {"exit", "quit"}:
            break
        if query:
            run(query)

if __name__ == "__main__":
    main()
