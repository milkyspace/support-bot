import chromadb
from chromadb.config import Settings
from openai import OpenAI

# подключаемся к локальной векторной базе
chroma = chromadb.Client(Settings(
    chroma_db_impl="duckdb+parquet",
    persist_directory="./vector_db"
))

kb = chroma.get_collection("support_kb")


async def generate_ai_reply_rag(user_message: str, config) -> str:
    """
    Достаёт лучшие фрагменты из базы знаний и формирует ответ.
    """

    # 1) ищем ближайшие куски
    results = kb.query(
        query_texts=[user_message],
        n_results=5,
    )
    context = "\n---\n".join(results["documents"][0])

    # 2) формируем финальный prompt
    prompt = f"""
Ты — сотрудник поддержки VPN Ducks.

Используй контекст ниже, он всегда имеет приоритет:

Контекст:
{context}

Сообщение клиента:
{user_message}

Ответь дружелюбно, кратко, по делу.
"""

    # 3) генерируем ответ
    client = OpenAI(api_key=config.bot.OPENAI_API_KEY)
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Ты — профессиональный сотрудник поддержки."},
            {"role": "user", "content": prompt}
        ]
    )

    return completion.choices[0].message.content
