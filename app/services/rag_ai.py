import html
from openai import OpenAI

from app.services.rag_search import search_similar


async def generate_ai_reply_rag(user_message: str, config) -> str:
    """
    Использует FAISS для поиска похожих сообщений
    и формирует RAG-ответ.
    """

    # 1) Ищем релевантные фрагменты из базы
    top_chunks = search_similar(user_message, top_k=5)

    context = "\n---\n".join(top_chunks)

    # 2) Формируем RAG-промпт
    prompt = f"""
Ты — сотрудник поддержки VPN Ducks.

Используй контекст ниже. 
Если в контексте есть точная инструкция — следуй ей. 
Если контекст не подходит — отвечай как обычно, но опирайся на стиль ответов.
Если клиент пишет неполно — уточняй.

Контекст:
{context}

Сообщение клиента:
{user_message}

Ответь:
- кратко
- дружелюбно
- по делу
- дай чёткие шаги, если нужны
"""

    client = OpenAI(api_key=config.bot.OPENAI_API_KEY)

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Ты — опытный сотрудник поддержки VPN Ducks."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.25,
    )

    return completion.choices[0].message.content.strip()
