import re
from pathlib import Path

from .rag import RAG


def parse_qa_pairs(content: str) -> list[tuple[str, str]]:
    """Parse Q&A pairs from content string"""
    # Split into pairs using regex
    pairs = re.findall(r'Q:\s*(.*?)\nA:\s*(.*?)(?=\n[QA]:|$)', content, re.DOTALL)
    # Clean up whitespace
    return [(q.strip(), a.strip()) for q, a in pairs]

def main():
    # Initialize RAG system
    rag = RAG()

    # Ensure schema exists
    print("Ensuring database schema...")
    rag.ensure_schema()

    # Load FAQ content
    data_dir = Path(__file__).parent.parent / 'data'
    faq_path = data_dir / 'sample_faq.txt'

    print(f"Reading FAQ from {faq_path}...")
    with open(faq_path, encoding='utf-8') as f:
        content = f.read()

    # Parse Q&A pairs
    qa_pairs = parse_qa_pairs(content)
    print(f"Found {len(qa_pairs)} Q&A pairs")

    # Store in database with embeddings
    print("Generating embeddings and storing documents...")
    docs = rag.upsert_docs(qa_pairs)
    print(f"Successfully stored {len(docs)} documents")

    # Test a query
    test_query = "What underlayment do you use?"
    print(f"\nTesting query: {test_query}")
    results = rag.query(test_query, k=1)
    if results:
        print("\nTop result:")
        _, text, score = results[0]
        print(f"Score: {score:.3f}")
        print(f"Text: {text}")

if __name__ == '__main__':
    main()
