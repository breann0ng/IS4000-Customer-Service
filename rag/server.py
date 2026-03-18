"""
rag/server.py

MCP-style tool for querying the processed knowledge base chunks (all_chunks.jsonl).
"""

import jsonlines
from pathlib import Path
from typing import List, Dict

DATA_FILE = Path(__file__).parent / "data" / "all_chunks.jsonl"

def search_knowledge_base(query: str, limit: int = 3) -> List[Dict]:
    """
    Simple keyword-based search for demo. 
    In the final app, this would use vector search (ChromaDB).
    """
    results = []
    if not DATA_FILE.exists():
        return [{"error": "Knowledge base file not found."}]

    query_words = query.lower().split()
    
    with jsonlines.open(DATA_FILE) as reader:
        for chunk in reader:
            text = chunk.get("text", "").lower()
            # Rank based on keyword matches
            score = sum(1 for word in query_words if word in text)
            if score > 0:
                results.append((score, chunk))

    # Sort by score descending
    results.sort(key=lambda x: x[0], reverse=True)
    return [r[1] for r in results[:limit]]

if __name__ == "__main__":
    # Test
    print(search_knowledge_base("Access App activation"))
