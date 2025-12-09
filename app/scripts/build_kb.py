import os
import json
import chromadb
from chromadb.config import Settings
from textwrap import wrap
from openai import OpenAI

# шаг 1 — читаем JSON
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB_PATH = os.path.join(BASE_DIR, "..", "data", "knowledge.json")
with open(KB_PATH, "r", encoding="utf8") as f:
    data = json.load(f)

# шаг 2 — инициализируем локальное хранилище vectordb
chroma = chromadb.Client(Settings(chroma_db_impl="duckdb+parquet", persist_directory="./vector_db"))

collection = chroma.get_or_create_collection(
    name="support_kb",
    metadata={"hnsw:space": "cosine"}
)

def chunk_text(text, size=800):
    return [t.strip() for t in wrap(text, size) if t.strip()]

# шаг 3 — нарезаем и загружаем векторы
documents = []
ids = []

i = 0
for chat in data["chats"]["list"]:
    for msg in chat["messages"]:
        if isinstance(msg.get("text"), str):
            chunks = chunk_text(msg["text"])
            for chunk in chunks:
                documents.append(chunk)
                ids.append(f"msg_{i}")
                i += 1

print(f"Загружаем {len(documents)} чанков...")

# шаг 4 — создаём embeddings и пишем в БД
collection.add(
    documents=documents,
    ids=ids
)

print("Готово! База знаний сохранена в ./vector_db")