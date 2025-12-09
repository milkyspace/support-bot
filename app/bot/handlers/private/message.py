import asyncio
from distutils.command.config import config
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
    """
    Handle edited messages.

    :param message: The edited message.
    :param manager: Manager object.
    :return: None
    """
    # Get the text for the edited message
    text = manager.text_message.get("message_edited")
    # Reply to the edited message with the specified text
    msg = await message.reply(text)
    # Wait for 5 seconds before deleting the reply
    await asyncio.sleep(5)
    # Delete the reply to the edited message
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
    """
    Handles incoming messages and copies them to the forum topic.
    If the user is banned, the messages are ignored.

    :param message: The incoming message.
    :param manager: Manager object.
    :param redis: RedisStorage object.
    :param user_data: UserData object.
    :param album: Album object or None.
    :return: None
    """
    # Check if the user is banned
    if user_data.is_banned:
        return

    async def copy_message_to_topic():
        """
        Copies the message or album to the forum topic.
        If no album is provided, the message is copied. Otherwise, the album is copied.
        """
        message_thread_id = await get_or_create_forum_topic(
            message.bot,
            redis,
            manager.config,
            user_data,
        )

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

        # ------ AI DRAFT BLOCK ------
        from app.services.ai import generate_ai_reply
        import html

        async def safe_ai_call():
            client_message = message.text or message.caption or ""
            if not client_message.strip():
                return None  # нет текста → нечего анализировать

            try:
                # Таймаут 6 сек
                from app.services.rag_ai import generate_ai_reply_rag
                try:
                    return await asyncio.wait_for(
                        generate_ai_reply_rag(client_message, manager.config),
                        timeout=10
                    )
                except asyncio.TimeoutError:
                    return None
            except asyncio.TimeoutError:
                print("AI timeout: exceeded 6 seconds")
            except Exception as e:
                print("AI error:", e)

            return None

        ai_text = await safe_ai_call()

        if ai_text:
            try:
                # Экранируем HTML, чтобы не сломать разметку
                safe_ai = html.escape(ai_text)

                preview = f"🤖 <b>AI предлагает ответ:</b>\n\n<blockquote>{safe_ai}</blockquote>"

                # Telegram ограничивает 4096 символов
                if len(preview) > 3800:
                    chunks = [preview[i:i + 3500] for i in range(0, len(preview), 3500)]
                    for chunk in chunks:
                        await message.bot.send_message(
                            chat_id=manager.config.bot.GROUP_ID,
                            text=chunk,
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
        # ------ END AI BLOCK ------
    try:
        await copy_message_to_topic()
    except TelegramBadRequest as ex:
        if "message thread not found" in ex.message:
            user_data.message_thread_id = await create_forum_topic(
                message.bot,
                manager.config,
                user_data.full_name,
            )
            await redis.update_user(user_data.id, user_data)
            await copy_message_to_topic()
        else:
            raise

    # Send a confirmation message to the user
    text = manager.text_message.get("message_sent")
    # Reply to the edited message with the specified text
    msg = await message.reply(text)
    # Wait for 5 seconds before deleting the reply
    await asyncio.sleep(5)
    # Delete the reply to the edited message
    await msg.delete()
