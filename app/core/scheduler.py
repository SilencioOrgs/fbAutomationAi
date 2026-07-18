"""
Central pipeline orchestrator and scheduler.
Owns all state machine transitions. Both UI and Telegram handlers
call into this module for approve/reject/generate actions.
Uses APScheduler for periodic topic generation and scheduled post checking.
"""

import json
import logging
import os
import queue
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

from core.content_gen import ContentGenerator
from core.fb_publisher import FacebookPublisher
from core.image_gen import ImageGenerator
from core.topic_source import TopicSource
from core import scheduling as scheduling_mod
from db.db import Database
from db.models import Status

logger = logging.getLogger(__name__)


class Pipeline:
    """
    Central orchestrator for the content automation pipeline.
    All state transitions go through this class.
    """

    def __init__(
        self,
        db: Database,
        topic_source: TopicSource,
        content_gen: ContentGenerator,
        image_gen: ImageGenerator,
        publisher: FacebookPublisher,
        telegram,  # TelegramBot — type hint omitted to avoid circular import
        ui_queue: queue.Queue,
        config: dict | None = None,
    ) -> None:
        self._db = db
        self._topic_source = topic_source
        self._content_gen = content_gen
        self._image_gen = image_gen
        self._publisher = publisher
        self._telegram = telegram
        self._ui_queue = ui_queue
        self._config = config or self._load_config()
        self._scheduler: BackgroundScheduler | None = None

    # ------------------------------------------------------------------ #
    #  Config
    # ------------------------------------------------------------------ #

    def _load_config(self) -> dict:
        """Load prompt_templates.json from config directory."""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config",
            "prompt_templates.json",
        )
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Could not load config: %s", e)
            return {}

    def reload_config(self) -> None:
        """Reload configuration from disk."""
        self._config = self._load_config()

    def get_config(self) -> dict:
        """Return current configuration."""
        return self._config

    # ------------------------------------------------------------------ #
    #  Topic generation (Excel-sourced)
    # ------------------------------------------------------------------ #

    def trigger_topic_generation(
        self, niche: str | None = None, count: int = 3
    ) -> None:
        """
        Trigger topic pulling from the active Excel file in a background thread.
        The niche parameter is kept for API compatibility but ignored
        (topics come from the Excel file now).
        """
        topic_config = self._config.get("topic_generation", {})
        count = topic_config.get("default_count", count)

        thread = threading.Thread(
            target=self._generate_topics_background,
            args=(count,),
            daemon=True,
        )
        thread.start()

    def _generate_topics_background(self, count: int) -> None:
        """Background thread: pull topics from Excel and send approvals."""
        try:
            # Resolve the active topic file
            active_file = self._resolve_topic_file()
            if not active_file:
                error_msg = (
                    "No topic file configured. Go to Settings and select "
                    "an Excel file, or place one in the app directory."
                )
                self._ui_queue.put({"type": "error", "text": error_msg})
                try:
                    self._telegram.send_notification_threadsafe(
                        f"[ERROR] {error_msg}"
                    )
                except Exception:
                    pass
                return

            self._ui_queue.put({
                "type": "info",
                "text": f"Pulling {count} topics from \"{os.path.basename(active_file)}\"...",
            })

            items = self._topic_source.get_next_topics(active_file, count)

            if not items:
                # File exhausted
                self._handle_file_exhausted(active_file)
                return

            for item in items:
                # Notify UI
                self._ui_queue.put({
                    "type": "topic_approval",
                    "item": item,
                })
                # Send to Telegram
                try:
                    self._telegram.send_topic_approval_threadsafe(item)
                except Exception as e:
                    logger.error("Failed to send topic to Telegram: %s", e)

            # Check if file is now exhausted after this pull
            remaining = self._topic_source.get_remaining_count(active_file)
            if remaining == 0:
                self._handle_file_exhausted(active_file)
            else:
                self._ui_queue.put({
                    "type": "info",
                    "text": f"{remaining} topics remaining in \"{os.path.basename(active_file)}\".",
                })

        except Exception as e:
            error_msg = f"Topic generation failed: {e}"
            logger.error(error_msg)
            self._ui_queue.put({
                "type": "error",
                "text": error_msg,
            })
            try:
                self._telegram.send_notification_threadsafe(
                    f"[ERROR] {error_msg}"
                )
            except Exception:
                pass

    def _resolve_topic_file(self) -> str | None:
        """Resolve the active topic file path from config."""
        ts_cfg = self._config.get("topic_source", {})
        active = ts_cfg.get("active_file", "")
        if not active:
            return None

        # If relative, resolve against the app directory
        if not os.path.isabs(active):
            app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            active = os.path.join(app_dir, active)

        if os.path.isfile(active):
            return active
        return None

    def _handle_file_exhausted(self, file_path: str) -> None:
        """Notify both channels that the topic file has been exhausted."""
        filename = os.path.basename(file_path)
        msg = (
            f"All topics used from \"{filename}\" — "
            f"upload a new topic file to continue."
        )
        self._ui_queue.put({
            "type": "topic_file_exhausted",
            "text": msg,
            "filename": filename,
        })
        try:
            self._telegram.send_notification_threadsafe(
                f"[NOTICE] {msg}"
            )
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    #  State machine actions
    # ------------------------------------------------------------------ #

    def approve_topic(self, item_id: int, source: str = "app") -> None:
        """
        Approve a topic:
        1. Update status to 'approved'
        2. Update the other channel (Telegram or app)
        3. Kick off content generation in background
        """
        item = self._db.get_content_item(item_id)
        if item is None or item["status"] != Status.PENDING_APPROVAL:
            logger.warning("Cannot approve item %d (status=%s)",
                           item_id, item.get("status") if item else "not found")
            return

        self._db.update_status(item_id, Status.APPROVED)
        item = self._db.get_content_item(item_id)

        # Notify the other channel
        if source != "telegram":
            try:
                self._telegram.update_message_status_threadsafe(item, "APPROVED")
            except Exception as e:
                logger.error("Telegram update error: %s", e)

        self._ui_queue.put({
            "type": "status_update",
            "item_id": item_id,
            "status": Status.APPROVED,
            "text": f"Topic #{item_id} approved. Starting content generation...",
        })

        # Start content generation in background
        thread = threading.Thread(
            target=self._process_approved_item,
            args=(item_id,),
            daemon=True,
        )
        thread.start()

    def reject_topic(self, item_id: int, source: str = "app") -> None:
        """Reject a topic. Updates both channels."""
        item = self._db.get_content_item(item_id)
        if item is None or item["status"] != Status.PENDING_APPROVAL:
            return

        self._db.update_status(item_id, Status.REJECTED)
        item = self._db.get_content_item(item_id)

        if source != "telegram":
            try:
                self._telegram.update_message_status_threadsafe(item, "REJECTED")
            except Exception as e:
                logger.error("Telegram update error: %s", e)

        self._ui_queue.put({
            "type": "status_update",
            "item_id": item_id,
            "status": Status.REJECTED,
            "text": f"Topic #{item_id} rejected.",
        })

    def approve_preview(self, item_id: int, source: str = "app") -> None:
        """
        Approve a final preview — now prompts for region selection
        instead of publishing immediately.

        1. Update status to APPROVED
        2. Send region-selection buttons to both channels
        """
        item = self._db.get_content_item(item_id)
        if item is None or item["status"] != Status.PREVIEW_PENDING:
            return

        self._db.update_status(item_id, Status.APPROVED)
        item = self._db.get_content_item(item_id)

        # Get available regions from config
        sched_cfg = self._config.get("scheduling", {})
        regions = list(sched_cfg.get("regions", {}).keys())
        if not regions:
            regions = ["Global"]

        # Notify the other channel
        if source != "telegram":
            try:
                self._telegram.update_message_status_threadsafe(item, "APPROVED")
                self._telegram.send_region_selection_threadsafe(item, regions)
            except Exception as e:
                logger.error("Telegram update error: %s", e)

        # Send region selection to UI
        self._ui_queue.put({
            "type": "region_selection",
            "item_id": item_id,
            "item": item,
            "regions": regions,
            "text": f"Preview #{item_id} approved. Select target region for scheduling:",
        })

    def select_region(self, item_id: int, region: str, source: str = "app") -> None:
        """
        Handle region selection after preview approval.
        1. Validate item is in APPROVED status.
        2. Call scheduling.schedule_post() to compute slot and insert row.
        3. Notify both channels with confirmation.
        """
        item = self._db.get_content_item(item_id)
        if item is None or item["status"] != Status.APPROVED:
            logger.warning(
                "Cannot schedule item %d (status=%s)",
                item_id, item.get("status") if item else "not found",
            )
            return

        try:
            result = scheduling_mod.schedule_post(
                content_item_id=item_id,
                region=region,
                db=self._db,
                config=self._config,
            )

            confirm_text = (
                f"Scheduled for {result['formatted_time']} "
                f"— targeting {region} audience."
            )

            # Notify UI
            self._ui_queue.put({
                "type": "status_update",
                "item_id": item_id,
                "status": Status.SCHEDULED,
                "text": confirm_text,
            })

            # Notify the other channel
            if source != "telegram":
                try:
                    self._telegram.send_notification_threadsafe(
                        f"Post #{item_id}: {confirm_text}"
                    )
                except Exception as e:
                    logger.error("Telegram notification error: %s", e)
            else:
                # Came from Telegram — push to UI
                self._ui_queue.put({
                    "type": "info",
                    "text": f"Post #{item_id}: {confirm_text}",
                    "item_id": item_id,
                })

        except Exception as e:
            error_msg = f"Scheduling failed for item #{item_id}: {e}"
            logger.error(error_msg)
            self._ui_queue.put({
                "type": "error",
                "text": error_msg,
                "item_id": item_id,
            })
            try:
                self._telegram.send_notification_threadsafe(
                    f"[ERROR] {error_msg}"
                )
            except Exception:
                pass

    def reject_preview(self, item_id: int, source: str = "app") -> None:
        """Reject a preview. Updates both channels."""
        item = self._db.get_content_item(item_id)
        if item is None or item["status"] != Status.PREVIEW_PENDING:
            return

        self._db.update_status(item_id, Status.REJECTED)
        item = self._db.get_content_item(item_id)

        if source != "telegram":
            try:
                self._telegram.update_message_status_threadsafe(item, "REJECTED")
            except Exception as e:
                logger.error("Telegram update error: %s", e)

        self._ui_queue.put({
            "type": "status_update",
            "item_id": item_id,
            "status": Status.REJECTED,
            "text": f"Preview #{item_id} rejected.",
        })

    # ------------------------------------------------------------------ #
    #  Background processing
    # ------------------------------------------------------------------ #

    def _process_approved_item(self, item_id: int) -> None:
        """
        Full processing pipeline for an approved topic:
        1. Generate content (title, description, hashtags) from Excel fields
        2. Generate image via AI33PRO
        3. Send preview for final approval
        """
        try:
            # Step 1: Generate content
            self._ui_queue.put({
                "type": "info",
                "text": f"Generating content for topic #{item_id}...",
                "item_id": item_id,
            })

            content_template = self._config.get("content_generation", {})
            image_config = self._config.get("image_generation", {})
            prompt_template = image_config.get("prompt_template", "{topic}")
            
            item = self._content_gen.generate_content(item_id, content_template, image_template=prompt_template)

            self._ui_queue.put({
                "type": "content_generated",
                "item": item,
                "text": (
                    f"Content generated for #{item_id}:\n"
                    f"Title: {item.get('generated_title', '')}\n"
                    f"Generating image..."
                ),
            })

            # Step 2: Generate image
            image_prompt = item.get("image_prompt", item["topic"])
            model_id = image_config.get("model_id", "bytedance-seedream-4.5")
            model_params = image_config.get("model_parameters", {})
            reference_image = image_config.get("reference_image")
            reference_image_path = self._resolve_reference_image(reference_image)

            local_path = self._image_gen.generate_image(
                item_id,
                image_prompt,
                model_id,
                model_params,
                reference_image_path=reference_image_path,
            )

            # Step 3: Send preview for approval
            item = self._db.get_content_item(item_id)

            self._ui_queue.put({
                "type": "preview_approval",
                "item": item,
                "image_path": local_path,
            })

            # Send to Telegram
            try:
                self._telegram.send_preview_approval_threadsafe(item)
            except Exception as e:
                logger.error("Failed to send preview to Telegram: %s", e)

        except Exception as e:
            error_msg = f"Processing failed for item #{item_id}: {e}"
            logger.error(error_msg)

            # Make sure status is set to failed
            current = self._db.get_content_item(item_id)
            if current and current["status"] != Status.FAILED:
                self._db.update_status(
                    item_id, Status.FAILED, error_message=str(e)
                )

            self._ui_queue.put({
                "type": "error",
                "text": error_msg,
                "item_id": item_id,
            })

            try:
                self._telegram.send_notification_threadsafe(
                    f"[ERROR] {error_msg}"
                )
            except Exception:
                pass

    def _build_image_prompt(self, template: str, item: dict) -> str:
        """Fill image-prompt placeholders without treating other braces as errors."""
        topic = item.get("topic", "")
        description = item.get("generated_description", "")
        title = item.get("generated_title", "")
        values = {
            "topic": topic,
            "TOPIC": topic,
            "FACT_TEXT": description,
            "fact_text": description,
            "HIGHLIGHT_1": title or topic,
            "highlight_1": title or topic,
            "HIGHLIGHT_2": topic,
            "highlight_2": topic,
            "SUBJECT": topic,
            "subject": topic,
        }
        for key, value in values.items():
            template = template.replace(f"{{{key}}}", value)
        return template

    def _resolve_reference_image(self, configured_path: str | None) -> str | None:
        """Resolve a configured template path relative to the app directory."""
        if not configured_path:
            return None
        if os.path.isabs(configured_path):
            return configured_path
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(app_dir, configured_path)

    def _publish_item(self, item_id: int) -> None:
        """Publish to Facebook and notify both channels."""
        try:
            fb_post_id = self._publisher.publish(item_id)

            self._ui_queue.put({
                "type": "published",
                "item_id": item_id,
                "text": f"Post #{item_id} published to Facebook. Post ID: {fb_post_id}",
            })

            try:
                self._telegram.send_notification_threadsafe(
                    f"Post #{item_id} published to Facebook.\nPost ID: {fb_post_id}"
                )
            except Exception as e:
                logger.error("Telegram notification error: %s", e)

        except Exception as e:
            error_msg = f"Publishing failed for item #{item_id}: {e}"
            logger.error(error_msg)

            self._ui_queue.put({
                "type": "error",
                "text": error_msg,
                "item_id": item_id,
            })

            try:
                self._telegram.send_notification_threadsafe(
                    f"[ERROR] {error_msg}"
                )
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    #  Scheduled posts checker
    # ------------------------------------------------------------------ #

    def _check_scheduled_posts(self) -> None:
        """
        Runs every minute via APScheduler.
        Finds scheduled_posts where scheduled_time_utc <= now and status = 'queued'.
        For each: calls _publish_item, then updates scheduled_posts status.
        """
        try:
            now_utc = datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S")
            due_posts = self._db.get_due_scheduled_posts(now_utc)

            for post in due_posts:
                post_id = post["id"]
                content_item_id = post["content_item_id"]

                logger.info(
                    "Executing scheduled post #%d for item #%d (region=%s)",
                    post_id, content_item_id, post.get("target_region"),
                )

                try:
                    # Update content_item status to PUBLISHING
                    self._db.update_status(content_item_id, Status.PUBLISHING)
                    # Reuse the existing publish path
                    self._publish_item(content_item_id)
                    # Mark scheduled post as posted
                    self._db.update_scheduled_post_status(post_id, "posted")
                except Exception as e:
                    logger.error(
                        "Scheduled publish failed for post #%d item #%d: %s",
                        post_id, content_item_id, e,
                    )
                    self._db.update_scheduled_post_status(post_id, "failed")
                    # _publish_item already notifies both channels on failure

        except Exception as e:
            logger.error("Error in _check_scheduled_posts: %s", e)

    # ------------------------------------------------------------------ #
    #  Scheduler
    # ------------------------------------------------------------------ #

    def start_scheduler(
        self,
        interval_hours: int | None = None,
    ) -> None:
        """Start APScheduler for periodic topic generation and scheduled post checking."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)

        self._scheduler = BackgroundScheduler()

        # Scheduled posts checker — always runs every minute
        self._scheduler.add_job(
            self._check_scheduled_posts,
            "interval",
            minutes=1,
            id="scheduled_posts_checker",
            replace_existing=True,
        )

        # Topic generation scheduler (optional, config-driven)
        schedule_config = self._config.get("schedule", {})
        if schedule_config.get("enabled", False) or interval_hours is not None:
            hours = interval_hours or schedule_config.get("interval_hours", 6)
            self._scheduler.add_job(
                self.trigger_topic_generation,
                "interval",
                hours=hours,
                id="topic_gen_job",
                replace_existing=True,
            )
            logger.info("Topic generation scheduled every %d hours", hours)

        self._scheduler.start()
        logger.info("Scheduler started (scheduled posts checker active)")

        self._ui_queue.put({
            "type": "info",
            "text": "Scheduler started: checking for scheduled posts every minute.",
        })

    def stop_scheduler(self) -> None:
        """Stop the APScheduler."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            logger.info("Scheduler stopped")
