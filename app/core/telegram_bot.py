"""
Telegram bot for remote approval workflow.
Runs in its own daemon thread with its own asyncio event loop.
Communicates with the UI thread via a thread-safe queue.
"""

import asyncio
import logging
import os
import queue
import threading

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from db.db import Database
from db.models import Status, format_status

logger = logging.getLogger(__name__)


class TelegramBot:
    """
    Telegram bot that handles approval workflows.
    Runs in a dedicated daemon thread with its own asyncio event loop.
    """

    def __init__(
        self,
        token: str,
        admin_id: int,
        db: Database,
        ui_queue: queue.Queue,
        pipeline=None,
    ) -> None:
        self._token = token
        self._admin_id = admin_id
        self._db = db
        self._ui_queue = ui_queue
        self._pipeline = pipeline  # Set after Pipeline is created
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._app: Application | None = None
        self._bot: Bot | None = None
        self._running = False

    def set_pipeline(self, pipeline) -> None:
        """Set the pipeline reference (resolves circular dependency)."""
        self._pipeline = pipeline

    def start(self) -> None:
        """Start the bot in a new daemon thread with its own asyncio loop."""
        if self._running:
            logger.warning("Telegram bot is already running")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._run_bot, name="telegram-bot", daemon=True
        )
        self._thread.start()
        logger.info("Telegram bot thread started")

    def stop(self) -> None:
        """Gracefully shut down the bot and its thread."""
        self._running = False
        if self._loop and self._app:
            asyncio.run_coroutine_threadsafe(
                self._shutdown(), self._loop
            )
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        logger.info("Telegram bot stopped")

    def _run_bot(self) -> None:
        """Entry point for the bot thread. Creates and runs the asyncio loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._start_bot())
        except Exception as e:
            logger.error("Telegram bot thread error: %s", e)
        finally:
            self._loop.close()

    async def _start_bot(self) -> None:
        """Build and start the telegram Application."""
        builder = Application.builder().token(self._token)
        self._app = builder.build()
        self._bot = self._app.bot

        # Register handlers
        self._app.add_handler(CommandHandler("start", self._handle_start))
        self._app.add_handler(CommandHandler("status", self._handle_status))
        self._app.add_handler(
            CallbackQueryHandler(self._handle_callback)
        )

        logger.info("Telegram bot initializing...")
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)
        logger.info("Telegram bot is polling for updates")

        # Keep running until stopped
        while self._running:
            await asyncio.sleep(1)

        await self._shutdown()

    async def _shutdown(self) -> None:
        """Clean shutdown of the bot."""
        try:
            if self._app and self._app.updater and self._app.updater.running:
                await self._app.updater.stop()
            if self._app and self._app.running:
                await self._app.stop()
                await self._app.shutdown()
        except Exception as e:
            logger.warning("Error during Telegram bot shutdown: %s", e)

    # ------------------------------------------------------------------ #
    #  Public methods (called from other threads via run_coroutine_threadsafe)
    # ------------------------------------------------------------------ #

    def send_topic_approval_threadsafe(self, item: dict) -> None:
        """Thread-safe wrapper to send topic approval message."""
        if self._loop and self._running:
            future = asyncio.run_coroutine_threadsafe(
                self.send_topic_approval(item), self._loop
            )
            try:
                future.result(timeout=30)
            except Exception as e:
                logger.error("Failed to send topic approval: %s", e)

    def send_preview_approval_threadsafe(self, item: dict) -> None:
        """Thread-safe wrapper to send preview approval message."""
        if self._loop and self._running:
            future = asyncio.run_coroutine_threadsafe(
                self.send_preview_approval(item), self._loop
            )
            try:
                future.result(timeout=30)
            except Exception as e:
                logger.error("Failed to send preview approval: %s", e)

    def send_notification_threadsafe(self, text: str) -> None:
        """Thread-safe wrapper to send a plain notification."""
        if self._loop and self._running:
            future = asyncio.run_coroutine_threadsafe(
                self.send_notification(text), self._loop
            )
            try:
                future.result(timeout=15)
            except Exception as e:
                logger.error("Failed to send notification: %s", e)

    def update_message_status_threadsafe(self, item: dict, decision: str) -> None:
        """Thread-safe wrapper to edit a Telegram message with the decision."""
        if self._loop and self._running:
            future = asyncio.run_coroutine_threadsafe(
                self.update_message_status(item, decision), self._loop
            )
            try:
                future.result(timeout=15)
            except Exception as e:
                logger.error("Failed to update Telegram message: %s", e)

    # ------------------------------------------------------------------ #
    #  Async message methods
    # ------------------------------------------------------------------ #

    async def send_topic_approval(self, item: dict) -> None:
        """Send topic text to admin with inline Approve/Reject buttons."""
        if not self._bot:
            return

        item_id = item["id"]
        text = (
            f"[Topic #{item_id}]\n\n"
            f"{item['topic']}\n\n"
            f"Approve or reject this topic."
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "Approve", callback_data=f"approve_topic:{item_id}"
                ),
                InlineKeyboardButton(
                    "Reject", callback_data=f"reject_topic:{item_id}"
                ),
            ]
        ])

        try:
            msg = await self._bot.send_message(
                chat_id=self._admin_id,
                text=text,
                reply_markup=keyboard,
            )
            self._db.set_telegram_msg(item_id, self._admin_id, msg.message_id)
            self._db.log_usage(
                provider="telegram",
                endpoint="sendMessage",
                success=True,
            )
            logger.info("Sent topic approval to Telegram for item_id=%d", item_id)
        except Exception as e:
            logger.error("Failed to send topic approval to Telegram: %s", e)
            self._db.log_usage(
                provider="telegram",
                endpoint="sendMessage",
                success=False,
                error_msg=str(e),
            )

    async def send_preview_approval(self, item: dict) -> None:
        """Send generated image + caption to admin with Approve/Reject buttons."""
        if not self._bot:
            return

        item_id = item["id"]
        caption = (
            f"[Preview #{item_id}]\n\n"
            f"{item.get('generated_title', '')}\n\n"
            f"{item.get('generated_description', '')}\n\n"
            f"{item.get('generated_hashtags', '')}\n\n"
            f"Approve or reject this post."
        )
        # Truncate caption if over Telegram's limit (1024 for photos)
        if len(caption) > 1024:
            caption = caption[:1020] + "..."

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "Approve", callback_data=f"approve_preview:{item_id}"
                ),
                InlineKeyboardButton(
                    "Reject", callback_data=f"reject_preview:{item_id}"
                ),
            ]
        ])

        try:
            image_path = item.get("image_local_path")
            if image_path and os.path.exists(image_path):
                with open(image_path, "rb") as img:
                    msg = await self._bot.send_photo(
                        chat_id=self._admin_id,
                        photo=img,
                        caption=caption,
                        reply_markup=keyboard,
                    )
            else:
                msg = await self._bot.send_message(
                    chat_id=self._admin_id,
                    text=f"{caption}\n\n[Image not available]",
                    reply_markup=keyboard,
                )

            self._db.set_telegram_msg(item_id, self._admin_id, msg.message_id)
            self._db.log_usage(
                provider="telegram",
                endpoint="sendPhoto",
                success=True,
            )
            logger.info("Sent preview approval to Telegram for item_id=%d", item_id)
        except Exception as e:
            logger.error("Failed to send preview to Telegram: %s", e)
            self._db.log_usage(
                provider="telegram",
                endpoint="sendPhoto",
                success=False,
                error_msg=str(e),
            )

    async def send_notification(self, text: str) -> None:
        """Send a plain text notification to the admin."""
        if not self._bot:
            return

        try:
            await self._bot.send_message(chat_id=self._admin_id, text=text)
            self._db.log_usage(
                provider="telegram", endpoint="sendMessage", success=True
            )
        except Exception as e:
            logger.error("Failed to send Telegram notification: %s", e)
            self._db.log_usage(
                provider="telegram",
                endpoint="sendMessage",
                success=False,
                error_msg=str(e),
            )

    async def update_message_status(self, item: dict, decision: str) -> None:
        """Edit the original Telegram message to show the decision, remove buttons."""
        if not self._bot:
            return

        chat_id = item.get("telegram_chat_id")
        msg_id = item.get("telegram_msg_id")
        if not chat_id or not msg_id:
            return

        status_text = f"[{decision.upper()}]"
        try:
            # Try to edit the reply markup (remove buttons)
            await self._bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=msg_id,
                reply_markup=None,
            )
        except Exception as e:
            # May fail if message is a photo (different edit method)
            logger.debug("Could not remove keyboard: %s", e)

        try:
            # Send a follow-up reply
            await self._bot.send_message(
                chat_id=chat_id,
                text=f"Topic #{item['id']} -- {status_text}",
                reply_to_message_id=msg_id,
            )
        except Exception as e:
            logger.debug("Could not send status reply: %s", e)

    # ------------------------------------------------------------------ #
    #  Command / callback handlers
    # ------------------------------------------------------------------ #

    async def _handle_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /start command."""
        if update.effective_user.id != self._admin_id:
            await update.message.reply_text("Unauthorized.")
            return
        await update.message.reply_text(
            "FB Content Automation Bot is active. "
            "You will receive content approval requests here."
        )

    async def _handle_status(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /status command — show counts by status."""
        if update.effective_user.id != self._admin_id:
            return

        lines = ["Current pipeline status:"]
        for status_val in [
            Status.PENDING_APPROVAL,
            Status.APPROVED,
            Status.GENERATING_CONTENT,
            Status.GENERATING_IMAGE,
            Status.PREVIEW_PENDING,
            Status.PUBLISHED,
            Status.FAILED,
        ]:
            items = self._db.get_items_by_status(status_val)
            if items:
                lines.append(f"  {format_status(status_val)}: {len(items)}")

        await update.message.reply_text("\n".join(lines))

    async def _handle_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle inline button callbacks for approve/reject actions."""
        query = update.callback_query
        if query.from_user.id != self._admin_id:
            await query.answer("Unauthorized.")
            return

        data = query.data
        await query.answer()

        if not self._pipeline:
            logger.error("Pipeline not set on Telegram bot")
            return

        try:
            action, item_id_str = data.split(":", 1)
            item_id = int(item_id_str)
        except (ValueError, AttributeError):
            logger.error("Invalid callback data: %s", data)
            return

        # Check current status to avoid double-actions
        item = self._db.get_content_item(item_id)
        if item is None:
            logger.warning("Item %d not found for callback", item_id)
            return

        if action == "approve_topic":
            if item["status"] != Status.PENDING_APPROVAL:
                await query.edit_message_reply_markup(reply_markup=None)
                return
            self._pipeline.approve_topic(item_id, source="telegram")

        elif action == "reject_topic":
            if item["status"] != Status.PENDING_APPROVAL:
                await query.edit_message_reply_markup(reply_markup=None)
                return
            self._pipeline.reject_topic(item_id, source="telegram")

        elif action == "approve_preview":
            if item["status"] != Status.PREVIEW_PENDING:
                await query.edit_message_reply_markup(reply_markup=None)
                return
            self._pipeline.approve_preview(item_id, source="telegram")

        elif action == "reject_preview":
            if item["status"] != Status.PREVIEW_PENDING:
                await query.edit_message_reply_markup(reply_markup=None)
                return
            self._pipeline.reject_preview(item_id, source="telegram")

        else:
            logger.warning("Unknown callback action: %s", action)
