import asyncio
from typing import Optional

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.types import Message

from app.bot.manager import Manager
from app.bot.types.album import Album
from app.bot.utils.create_forum_topic import (
    create_forum_topic,
    get_or_create_forum_topic,
)
from app.bot.utils.redis import RedisStorage
from app.bot.utils.redis.models import UserData

router = Router()
router.message.filter(F.chat.type == "private", StateFilter(None))


@router.edited_message()
async def handle_edited_message(message: Message, manager: Manager) -> None:
    text = manager.text_message.get("message_edited")
    msg = await message.reply(text)
    await asyncio.sleep(5)
    await msg.delete()


@router.message(F.media_group_id)
@router.message(F.media_group_id.is_(None))
async def handle_incoming_message(
    message: Message,
    manager: Manager,
    redis: RedisStorage,
    user_data: UserData,
    album: Optional[Album] = None,
) -> None:

    if user_data.is_banned:
        return

    async def copy_message_to_topic():
        message_thread_id = await get_or_create_forum_topic(
            message.bot, redis, manager.config, user_data
        )

        # --- обычное копирование в топик ---
        if not album:
            await message.forward(
                chat_id=manager.config.bot.GROUP_ID,
                message_thread_id=message_thread_id,
            )
        else:
            await album.copy_to(
                chat_id=manager.config.bot.GROUP_ID,
                message_thread_id=message_thread_id,
            )

        # ------------ AI DRAFT (RAG) ------------
        import html
        from app.services.rag_ai import generate_ai_reply_rag

        async def safe_ai_call():
            client_message = message.text or message.caption or ""
            if not client_message.strip():
                return None

            try:
                # Таймаут на генерацию 6 сек
                return await asyncio.wait_for(
                    generate_ai_reply_rag(client_message, manager.config),
                    timeout=6
                )
            except asyncio.TimeoutError:
                print("AI timeout (6 sec)")
            except Exception as e:
                print("AI error:", e)
            return None

        ai_text = await safe_ai_call()

        if ai_text:
            try:
                escaped = html.escape(ai_text)
                preview = (
                    "🤖 <b>AI предлагает ответ:</b>\n\n"
                    f"<blockquote>{escaped}</blockquote>"
                )

                # Telegram limit 4096 → режем на безопасные куски
                if len(preview) > 3800:
                    chunks = [preview[i:i + 3500] for i in range(0, len(preview), 3500)]
                    for ch in chunks:
                        await message.bot.send_message(
                            chat_id=manager.config.bot.GROUP_ID,
                            text=ch,
                            message_thread_id=message_thread_id,
                            parse_mode="HTML",
                        )
                else:
                    await message.bot.send_message(
                        chat_id=manager.config.bot.GROUP_ID,
                        text=preview,
                        message_thread_id=message_thread_id,
                        parse_mode="HTML",
                    )

            except Exception as e:
                print("Failed to send AI preview:", e)
        # ------------ END AI BLOCK ------------

    # --- обработка ошибок по топикам ---
    try:
        await copy_message_to_topic()
    except TelegramBadRequest as ex:
        if "message thread not found" in ex.message:
            user_data.message_thread_id = await create_forum_topic(
                message.bot, manager.config, user_data.full_name
            )
            await redis.update_user(user_data.id, user_data)
            await copy_message_to_topic()
        else:
            raise

    # --- отправляем пользователю подтверждение ---
    text = manager.text_message.get("message_sent")
    msg = await message.reply(text)
    await asyncio.sleep(5)
    await msg.delete()