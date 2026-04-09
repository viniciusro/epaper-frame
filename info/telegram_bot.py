import asyncio
import logging
import threading
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_CHAT_ID_FILE = Path('data/telegram_chat_id.txt')


class TelegramBot:
    def __init__(self, config: dict, upload_folder: Path, next_event: threading.Event):
        self._token = config.get('bot_token', '')
        self._upload_folder = Path(upload_folder)
        self._next_event = next_event
        self._last_chat_id: int | None = self._load_chat_id()

    def _load_chat_id(self) -> int | None:
        try:
            return int(_CHAT_ID_FILE.read_text().strip()) if _CHAT_ID_FILE.exists() else None
        except Exception:
            return None

    def _save_chat_id(self, chat_id: int):
        try:
            _CHAT_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
            _CHAT_ID_FILE.write_text(str(chat_id))
        except Exception:
            logger.warning('Failed to save Telegram chat ID', exc_info=True)

    def send_alert(self, text: str):
        """Send a text alert to the last known chat. No-op if bot not configured or no chat known."""
        if not self._token or not self._last_chat_id:
            return
        try:
            requests.post(
                f'https://api.telegram.org/bot{self._token}/sendMessage',
                json={'chat_id': self._last_chat_id, 'text': text},
                timeout=10,
            )
        except Exception:
            logger.warning('Failed to send Telegram alert', exc_info=True)

    def start(self):
        if not self._token:
            logger.info('Telegram bot_token not configured — bot disabled')
            return
        t = threading.Thread(target=self._run, daemon=True, name='telegram-bot')
        t.start()
        logger.info('Telegram bot started')

    def _run(self):
        try:
            from telegram.ext import Application, MessageHandler, filters
        except ImportError:
            logger.error('python-telegram-bot not installed — Telegram bot disabled')
            return

        async def _main():
            app = Application.builder().token(self._token).build()
            app.add_handler(MessageHandler(filters.PHOTO, self._handle_photo))
            app.add_handler(MessageHandler(~filters.PHOTO, self._handle_non_photo))
            # Manually manage the lifecycle to avoid signal handler issues in non-main thread
            async with app:
                await app.start()
                await app.updater.start_polling(drop_pending_updates=True)
                logger.info('Telegram bot polling started')
                # Run forever until the thread is killed (daemon)
                await asyncio.Event().wait()

        # Suppress httpx INFO logs — they print the full bot token URL
        import logging as _logging
        _logging.getLogger('httpx').setLevel(_logging.WARNING)
        try:
            asyncio.run(_main())
        except Exception as exc:
            logger.error('Telegram bot error: %s', exc)

    async def _handle_photo(self, update, context):
        chat_id = update.effective_chat.id
        if chat_id != self._last_chat_id:
            self._last_chat_id = chat_id
            self._save_chat_id(chat_id)
        await update.message.reply_text('Got it! Downloading...')
        try:
            photo = update.message.photo[-1]  # largest available size
            file = await context.bot.get_file(photo.file_id)
            self._upload_folder.mkdir(parents=True, exist_ok=True)
            dest = self._upload_folder / f'telegram_{photo.file_id}.jpg'
            await file.download_to_drive(str(dest))
            logger.info('Telegram photo saved: %s', dest)
            self._next_event.set()
            await update.message.reply_text('Queued! It will appear on the frame at the next refresh.')
        except Exception as exc:
            logger.error('Failed to save Telegram photo: %s', exc)
            await update.message.reply_text(f'Sorry, something went wrong: {exc}')

    async def _handle_non_photo(self, update, context):
        chat_id = update.effective_chat.id
        if chat_id != self._last_chat_id:
            self._last_chat_id = chat_id
            self._save_chat_id(chat_id)
        await update.message.reply_text(
            'Hi! Send me a photo and I will display it on the frame.'
        )
