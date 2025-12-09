
import json
import os
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "..", "data", "knowledge.json")  # наш JSON
INDEX_PATH = os.path.join(BASE_DIR, "..", "data", "kb.index")
TEXTS_PATH = os.path.join(BASE_DIR, "..", "data", "kb_texts.npy")

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

def extract_messages(json_path):
    with open(json_path, "r", encoding="utf8") as f:
        data = json.load(f)

    texts = []

    for chat in data["chats"]["list"]:
        for msg in chat["messages"]:
            if msg.get("text"):
                # Превращаем text в строку (в экспорте Telegram это может быть массив / dict)
                if isinstance(msg["text"], list):
                    text_part = "".join(
                        p["text"] if isinstance(p, dict) else str(p)
                        for p in msg["text"]
                    )
                else:
                    text_part = str(msg["text"])

                # сохраняем только полезные сообщения
                if len(text_part.strip()) > 2:
                    texts.append(text_part.strip())

    print(f"Всего сообщений собрано: {len(texts)}")
    return texts


def build_index():
    print("Загрузка сообщений...")
    texts = extract_messages(DATA_PATH)

    print("Создаём эмбеддинги...")
    embeddings = model.encode(texts, batch_size=64, convert_to_numpy=True, show_progress_bar=True)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)

    print("Сохранение индекса...")
    faiss.write_index(index, INDEX_PATH)
    np.save(TEXTS_PATH, np.array(texts, dtype=object))

    print("Готово!")
    print("Индекс:", INDEX_PATH)
    print("Тексты:", TEXTS_PATH)


if __name__ == "__main__":
    build_index()
