import asyncio
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self, config: dict, upload_folder: Path, next_event: threading.Event):
        self._token = config.get('bot_token', '')
        self._upload_folder = Path(upload_folder)
        self._next_event = next_event

    def start(self):
        if not self._token:
            logger.info('Telegram bot_token not configured — bot disabled')
            return
        t = threading.Thread(target=self._run, daemon=True, name='telegram-bot')
        t.start()
        logger.info('Telegram bot started')

    def _run(self):
        # python-telegram-bot v20+ is async-first; create a fresh event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            from telegram.ext import Application, MessageHandler, filters
        except ImportError:
            logger.error('python-telegram-bot not installed — Telegram bot disabled')
            return
        try:
            app = Application.builder().token(self._token).build()
            app.add_handler(MessageHandler(filters.PHOTO, self._handle_photo))
            app.add_handler(MessageHandler(~filters.PHOTO, self._handle_non_photo))
            app.run_polling(drop_pending_updates=True)
        except Exception as exc:
            logger.error('Telegram bot error: %s', exc)

    async def _handle_photo(self, update, context):
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
        await update.message.reply_text(
            'Hi! Send me a photo and I will display it on the frame.'
        )
