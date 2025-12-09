import os
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(BASE_DIR, "..", "data", "kb.index")
TEXTS_PATH = os.path.join(BASE_DIR, "..", "data", "kb_texts.npy")

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
index = faiss.read_index(INDEX_PATH)
texts = np.load(TEXTS_PATH, allow_pickle=True)

def search_similar(query: str, top_k: int = 5):
    query_vec = model.encode([query], convert_to_numpy=True)
    D, I = index.search(query_vec, top_k)

    results = []
    for idx in I[0]:
        if idx < len(texts):
            results.append(texts[idx])

    return results
