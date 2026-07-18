"""
Chat-style message feed — the primary view of the application.
Shows pipeline events as chronological message bubbles with inline images
and approve/reject controls. Includes region-selection buttons and
a Telegram connection status indicator.
"""

import logging
import os
import queue
import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageTk

from db.db import Database
from db.models import Status, format_status

logger = logging.getLogger(__name__)

# Color scheme: black and yellow
COLOR_BG = "#0D0D0D"
COLOR_SURFACE = "#1A1A1A"
COLOR_SURFACE_ALT = "#252525"
COLOR_ACCENT = "#FFD700"
COLOR_ACCENT_DIM = "#B8960F"
COLOR_TEXT = "#E8E8E8"
COLOR_TEXT_DIM = "#888888"
COLOR_SUCCESS = "#4CAF50"
COLOR_ERROR = "#E53935"
COLOR_BORDER = "#333333"
COLOR_SCHEDULED = "#2196F3"

# Bubble type → left border color
BUBBLE_COLORS = {
    "info": COLOR_ACCENT_DIM,
    "topic": COLOR_ACCENT,
    "preview": COLOR_ACCENT,
    "success": COLOR_SUCCESS,
    "error": COLOR_ERROR,
    "status_update": COLOR_TEXT_DIM,
    "exhausted": COLOR_ERROR,
    "scheduled": COLOR_SCHEDULED,
}

PREVIEW_IMAGE_SIZE = (400, 225)  # 16:9 aspect for previews

from ui.post_preview_card import PostPreviewCard

class ChatFeed(ctk.CTkFrame):
    """Scrollable chat-style feed showing all pipeline events."""

    def __init__(
        self,
        parent,
        pipeline,
        db: Database,
        ui_queue: queue.Queue,
        telegram=None,
    ) -> None:
        super().__init__(parent, fg_color=COLOR_BG, corner_radius=0)
        self._pipeline = pipeline
        self._db = db
        self._ui_queue = ui_queue
        self._telegram = telegram
        self._message_widgets: dict[int, dict] = {}  # item_id → widget refs
        self._image_refs: list = []  # Keep refs to prevent GC

        self._build_ui()
        self._load_history()
        self._poll_ui_queue()

    def _build_ui(self) -> None:
        """Build the chat feed layout."""
        # Header
        header = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, height=50, corner_radius=0)
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="Content Pipeline",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=COLOR_ACCENT,
        ).pack(side="left", padx=16, pady=10)

        # Telegram status indicator (right side of header)
        self._telegram_status_label = ctk.CTkLabel(
            header,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_DIM,
        )
        self._telegram_status_label.pack(side="right", padx=(0, 16), pady=10)
        self._update_telegram_indicator()

        # Generate button in header
        self._generate_btn = ctk.CTkButton(
            header,
            text="Generate Topics",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=COLOR_ACCENT,
            text_color="#000000",
            hover_color=COLOR_ACCENT_DIM,
            width=140,
            height=32,
            corner_radius=6,
            command=self._on_generate,
        )
        self._generate_btn.pack(side="right", padx=(0, 8), pady=10)

        # Scrollable feed area
        self._feed_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=COLOR_BG,
            corner_radius=0,
            scrollbar_button_color=COLOR_SURFACE_ALT,
            scrollbar_button_hover_color=COLOR_ACCENT_DIM,
        )
        self._feed_frame.pack(fill="both", expand=True, padx=0, pady=0)

    def _update_telegram_indicator(self) -> None:
        """Update the Telegram status indicator in the header."""
        if self._telegram and hasattr(self._telegram, "is_enabled"):
            if self._telegram.is_enabled:
                self._telegram_status_label.configure(
                    text="Telegram: Connected",
                    text_color=COLOR_SUCCESS,
                )
            else:
                self._telegram_status_label.configure(
                    text="Telegram: Not Connected",
                    text_color=COLOR_TEXT_DIM,
                )
        else:
            self._telegram_status_label.configure(
                text="Telegram: Not Connected",
                text_color=COLOR_TEXT_DIM,
            )

    def _load_history(self) -> None:
        """Load existing items from DB and display them in the feed."""
        items = self._db.get_all_items(limit=50)
        # Display oldest first
        for item in reversed(items):
            self._render_item_from_db(item)

    def _render_item_from_db(self, item: dict) -> None:
        """Render a content_item from the database into the feed."""
        item_id = item["id"]
        status = item["status"]

        if status == Status.PENDING_APPROVAL:
            self.add_message(
                text=f"[Topic #{item_id}]\n{item['topic']}",
                msg_type="topic",
                item_id=item_id,
                show_actions=True,
                action_type="topic_approval",
            )
        elif status == Status.PREVIEW_PENDING:
            card = PostPreviewCard(
                self._feed_frame,
                item=item,
                config=self._pipeline.get_config(),
                on_approve=lambda iid: self._on_approve(iid, "preview_approval"),
                on_reject=lambda iid: self._on_reject(iid, "preview_approval"),
                on_recreate_image=self._pipeline.regenerate_image,
                on_edit_caption=self._pipeline.update_caption,
            )
            self._message_widgets[item_id] = {
                "bubble_outer": card,
                "bubble": card,
                "action_frame": card.get_action_frame(),
                "accent_bar": card.get_accent_bar(),
                "preview_card": card,
            }
            self._feed_frame.after(50, self._scroll_to_bottom)
        elif status == Status.APPROVED:
            # Could be awaiting region selection (after preview approval)
            if item.get("image_local_path"):
                # This was a preview that was approved — show region selection
                sched_cfg = self._pipeline.get_config().get("scheduling", {})
                regions = list(sched_cfg.get("regions", {}).keys())
                if regions:
                    self.add_message(
                        text=f"[Preview #{item_id} Approved]\nSelect target region:",
                        msg_type="preview",
                        item_id=item_id,
                    )
                    self._add_region_buttons(item_id, regions)
                else:
                    self.add_message(
                        text=f"[Approved #{item_id}]\n{item['topic']}",
                        msg_type="info",
                        item_id=item_id,
                    )
            else:
                self.add_message(
                    text=f"[Approved #{item_id}]\n{item['topic']}",
                    msg_type="info",
                    item_id=item_id,
                )
        elif status == Status.SCHEDULED:
            self.add_message(
                text=f"[Scheduled #{item_id}]\n{item.get('generated_title', item['topic'])}",
                msg_type="scheduled",
                item_id=item_id,
            )
        elif status == Status.PUBLISHED:
            self.add_message(
                text=f"[Published #{item_id}]\n{item.get('generated_title', item['topic'])}\nFB Post: {item.get('fb_post_id', 'N/A')}",
                msg_type="success",
                item_id=item_id,
            )
        elif status == Status.FAILED:
            self.add_message(
                text=f"[Failed #{item_id}]\n{item['topic']}\nError: {item.get('error_message', 'Unknown')}",
                msg_type="error",
                item_id=item_id,
            )
        elif status == Status.REJECTED:
            self.add_message(
                text=f"[Rejected #{item_id}]\n{item['topic']}",
                msg_type="status_update",
                item_id=item_id,
            )
        elif status in (
            Status.GENERATING_CONTENT,
            Status.GENERATING_IMAGE,
            Status.PUBLISHING,
        ):
            self.add_message(
                text=f"[{format_status(status)} #{item_id}]\n{item['topic']}",
                msg_type="info",
                item_id=item_id,
            )

    def add_message(
        self,
        text: str,
        msg_type: str = "info",
        item_id: int | None = None,
        image_path: str | None = None,
        show_actions: bool = False,
        action_type: str | None = None,
    ) -> None:
        """
        Append a message bubble to the feed.

        msg_type: 'info' | 'topic' | 'preview' | 'success' | 'error' |
                  'status_update' | 'exhausted' | 'scheduled'
        If show_actions: render Approve/Reject buttons.
        If image_path: render inline image thumbnail.
        action_type: 'topic_approval' | 'preview_approval'
        """
        border_color = BUBBLE_COLORS.get(msg_type, COLOR_BORDER)

        # Outer container with left border accent
        bubble_outer = ctk.CTkFrame(
            self._feed_frame,
            fg_color=COLOR_BG,
            corner_radius=0,
        )
        bubble_outer.pack(fill="x", padx=12, pady=4)

        # Accent bar on the left
        accent_bar = ctk.CTkFrame(
            bubble_outer,
            fg_color=border_color,
            width=3,
            corner_radius=0,
        )
        accent_bar.pack(side="left", fill="y", padx=(0, 0), pady=0)

        # Bubble content
        bubble = ctk.CTkFrame(
            bubble_outer,
            fg_color=COLOR_SURFACE,
            corner_radius=8,
        )
        bubble.pack(side="left", fill="x", expand=True, padx=(6, 0), pady=0)

        # Text content
        text_label = ctk.CTkLabel(
            bubble,
            text=text,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=COLOR_TEXT,
            wraplength=550,
            justify="left",
            anchor="w",
        )
        text_label.pack(fill="x", padx=12, pady=(10, 4))

        # Image preview
        if image_path and os.path.exists(image_path):
            self._render_image(bubble, image_path)

        # Action buttons
        action_frame = None
        if show_actions and action_type:
            action_frame = ctk.CTkFrame(bubble, fg_color="transparent")
            action_frame.pack(fill="x", padx=12, pady=(4, 10))

            approve_btn = ctk.CTkButton(
                action_frame,
                text="Approve",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                fg_color=COLOR_ACCENT,
                text_color="#000000",
                hover_color=COLOR_ACCENT_DIM,
                width=100,
                height=30,
                corner_radius=6,
                command=lambda iid=item_id, at=action_type: self._on_approve(iid, at),
            )
            approve_btn.pack(side="left", padx=(0, 8))

            reject_btn = ctk.CTkButton(
                action_frame,
                text="Reject",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                fg_color=COLOR_SURFACE_ALT,
                text_color=COLOR_TEXT,
                hover_color="#3A3A3A",
                width=100,
                height=30,
                corner_radius=6,
                command=lambda iid=item_id, at=action_type: self._on_reject(iid, at),
            )
            reject_btn.pack(side="left")

        else:
            # Bottom padding when no buttons
            ctk.CTkFrame(bubble, fg_color="transparent", height=6).pack()

        # Track widget refs for later updates
        if item_id is not None:
            self._message_widgets[item_id] = {
                "bubble_outer": bubble_outer,
                "bubble": bubble,
                "text_label": text_label,
                "action_frame": action_frame,
                "accent_bar": accent_bar,
            }

        # Auto-scroll to bottom
        self._feed_frame.after(50, self._scroll_to_bottom)

    def _add_region_buttons(self, item_id: int, regions: list[str]) -> None:
        """Add region-selection buttons to the feed for an approved preview."""
        widget_refs = self._message_widgets.get(item_id)
        if not widget_refs:
            return

        bubble = widget_refs.get("bubble")
        if not bubble:
            return

        # Remove existing action frame if any
        old_action = widget_refs.get("action_frame")
        if old_action:
            old_action.destroy()

        action_frame = ctk.CTkFrame(bubble, fg_color="transparent")
        action_frame.pack(fill="x", padx=12, pady=(4, 10))

        for region in regions:
            btn = ctk.CTkButton(
                action_frame,
                text=region,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                fg_color=COLOR_ACCENT,
                text_color="#000000",
                hover_color=COLOR_ACCENT_DIM,
                width=80,
                height=30,
                corner_radius=6,
                command=lambda r=region, iid=item_id: self._on_region_select(iid, r),
            )
            btn.pack(side="left", padx=(0, 8))

        widget_refs["action_frame"] = action_frame
        self._feed_frame.after(50, self._scroll_to_bottom)

    def _add_upload_button(self, bubble) -> None:
        """Add an 'Upload New Topic File' button to an exhaustion bubble."""
        action_frame = ctk.CTkFrame(bubble, fg_color="transparent")
        action_frame.pack(fill="x", padx=12, pady=(4, 10))

        upload_btn = ctk.CTkButton(
            action_frame,
            text="Upload New Topic File",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=COLOR_ACCENT,
            text_color="#000000",
            hover_color=COLOR_ACCENT_DIM,
            width=180,
            height=30,
            corner_radius=6,
            command=self._on_upload_topic_file,
        )
        upload_btn.pack(side="left")

    def _on_upload_topic_file(self) -> None:
        """Open a file dialog to select a new topic xlsx file."""
        from tkinter import filedialog

        file_path = filedialog.askopenfilename(
            title="Select Topic Excel File",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
        )
        if not file_path:
            return

        # Validate the file
        from core.topic_source import TopicSource
        config = self._pipeline.get_config()
        ts = TopicSource(self._db, config)
        ok, msg = ts.validate_file(file_path)

        if not ok:
            self.add_message(
                text=f"File rejected: {msg}",
                msg_type="error",
            )
            return

        # Update config with new file path
        config.setdefault("topic_source", {})["active_file"] = file_path

        # Save to disk
        import json
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config",
            "prompt_templates.json",
        )
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            self._pipeline.reload_config()
        except Exception as e:
            logger.error("Failed to save config: %s", e)

        remaining = ts.get_remaining_count(file_path)
        self.add_message(
            text=f"Topic file loaded: \"{os.path.basename(file_path)}\" ({remaining} topics available)",
            msg_type="info",
        )

    def update_message(self, item_id: int, new_status: str, text: str = None) -> None:
        """Update an existing message bubble: disable buttons, show outcome."""
        widget_refs = self._message_widgets.get(item_id)
        if not widget_refs:
            # Item not in feed yet — add as a status update
            if text:
                self.add_message(text=text, msg_type="status_update", item_id=item_id)
            return

        # Remove action buttons
        action_frame = widget_refs.get("action_frame")
        if action_frame:
            action_frame.destroy()
            widget_refs["action_frame"] = None

        # Update accent color or disable card actions
        preview_card = widget_refs.get("preview_card")
        if preview_card:
            preview_card.disable_actions(new_status)
        else:
            accent_bar = widget_refs.get("accent_bar")
            if accent_bar:
                if new_status == Status.REJECTED:
                    accent_bar.configure(fg_color=COLOR_ERROR)
                elif new_status in (Status.APPROVED, Status.PUBLISHING):
                    accent_bar.configure(fg_color=COLOR_SUCCESS)
                elif new_status == Status.PUBLISHED:
                    accent_bar.configure(fg_color=COLOR_SUCCESS)
            elif new_status == Status.SCHEDULED:
                accent_bar.configure(fg_color=COLOR_SCHEDULED)
            elif new_status == Status.FAILED:
                accent_bar.configure(fg_color=COLOR_ERROR)

        # Add status badge
        bubble = widget_refs.get("bubble")
        if bubble and text:
            badge_color = COLOR_SUCCESS if new_status not in (
                Status.REJECTED, Status.FAILED
            ) else COLOR_ERROR
            if new_status == Status.SCHEDULED:
                badge_color = COLOR_SCHEDULED
            status_label = ctk.CTkLabel(
                bubble,
                text=f"  {format_status(new_status)}  ",
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color="#000000",
                fg_color=badge_color,
                corner_radius=4,
            )
            status_label.pack(padx=12, pady=(2, 8), anchor="w")

    def _render_image(self, parent_frame, image_path: str) -> None:
        """Load and display an image inline at preview size."""
        try:
            pil_image = Image.open(image_path)
            pil_image.thumbnail(PREVIEW_IMAGE_SIZE, Image.Resampling.LANCZOS)

            # Use a canvas/label approach compatible with customtkinter
            ctk_image = ctk.CTkImage(
                light_image=pil_image,
                dark_image=pil_image,
                size=pil_image.size,
            )
            img_label = ctk.CTkLabel(
                parent_frame,
                image=ctk_image,
                text="",
            )
            img_label.pack(padx=12, pady=(4, 4))

            # Keep reference to prevent garbage collection
            self._image_refs.append(ctk_image)

        except Exception as e:
            logger.error("Failed to render image %s: %s", image_path, e)
            ctk.CTkLabel(
                parent_frame,
                text=f"[Image load error: {image_path}]",
                text_color=COLOR_ERROR,
                font=ctk.CTkFont(size=11),
            ).pack(padx=12, pady=4)

    def _on_approve(self, item_id: int, action_type: str) -> None:
        """Handle approve button click."""
        if action_type == "topic_approval":
            self._pipeline.approve_topic(item_id, source="app")
        elif action_type == "preview_approval":
            self._pipeline.approve_preview(item_id, source="app")

    def _on_reject(self, item_id: int, action_type: str) -> None:
        """Handle reject button click."""
        if action_type == "topic_approval":
            self._pipeline.reject_topic(item_id, source="app")
        elif action_type == "preview_approval":
            self._pipeline.reject_preview(item_id, source="app")

    def _on_region_select(self, item_id: int, region: str) -> None:
        """Handle region selection button click."""
        self._pipeline.select_region(item_id, region, source="app")

    def _on_generate(self) -> None:
        """Handle Generate Topics button click."""
        self._pipeline.trigger_topic_generation()

    def _scroll_to_bottom(self) -> None:
        """Scroll the feed to the bottom."""
        try:
            self._feed_frame._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _format_caption(self, item: dict) -> str:
        """Format a content item's caption for display."""
        parts = []
        title = item.get("generated_title", "")
        if title:
            parts.append(f"Title: {title}")
        desc = item.get("generated_description", "")
        if desc:
            # Truncate long descriptions for feed display
            if len(desc) > 300:
                desc = desc[:297] + "..."
            parts.append(desc)
        hashtags = item.get("generated_hashtags", "")
        if hashtags:
            parts.append(hashtags)
        return "\n".join(parts)

    def poll_ui_queue(self) -> None:
        """Drain the ui_queue and process events. Called via after()."""
        self._poll_ui_queue()

    def _poll_ui_queue(self) -> None:
        """Internal: drain queue and schedule next poll."""
        try:
            while True:
                try:
                    msg = self._ui_queue.get_nowait()
                except queue.Empty:
                    break

                self._handle_queue_message(msg)
        except Exception as e:
            logger.error("Error polling UI queue: %s", e)

        # Schedule next poll (100ms interval)
        self.after(100, self._poll_ui_queue)

    def _handle_queue_message(self, msg: dict) -> None:
        """Process a single message from the ui_queue."""
        msg_type = msg.get("type", "info")

        if msg_type == "info":
            self.add_message(
                text=msg.get("text", ""),
                msg_type="info",
                item_id=msg.get("item_id"),
            )

        elif msg_type == "error":
            self.add_message(
                text=msg.get("text", ""),
                msg_type="error",
                item_id=msg.get("item_id"),
            )

        elif msg_type == "topic_approval":
            item = msg.get("item", {})
            self.add_message(
                text=f"[Topic #{item.get('id', '?')}]\n{item.get('topic', '')}",
                msg_type="topic",
                item_id=item.get("id"),
                show_actions=True,
                action_type="topic_approval",
            )

        elif msg_type == "preview_approval":
            item = msg.get("item", {})
            card = PostPreviewCard(
                self._feed_frame,
                item=item,
                config=self._pipeline.get_config(),
                on_approve=lambda iid: self._on_approve(iid, "preview_approval"),
                on_reject=lambda iid: self._on_reject(iid, "preview_approval"),
                on_recreate_image=self._pipeline.regenerate_image,
                on_edit_caption=self._pipeline.update_caption,
            )
            self._message_widgets[item.get("id")] = {
                "bubble_outer": card,
                "bubble": card,
                "action_frame": card.get_action_frame(),
                "accent_bar": card.get_accent_bar(),
                "preview_card": card,
            }
            self._feed_frame.after(50, self._scroll_to_bottom)

        elif msg_type == "image_regenerated":
            item_id = msg.get("item_id")
            widget_refs = self._message_widgets.get(item_id)
            if widget_refs and "preview_card" in widget_refs:
                widget_refs["preview_card"].update_image(msg.get("image_path"))
            
        elif msg_type == "caption_updated":
            item_id = msg.get("item_id")
            widget_refs = self._message_widgets.get(item_id)
            if widget_refs and "preview_card" in widget_refs:
                widget_refs["preview_card"].update_caption(
                    title=msg.get("title", ""),
                    description=msg.get("description", ""),
                    hashtags=msg.get("hashtags", "")
                )

        elif msg_type == "region_selection":
            item_id = msg.get("item_id")
            regions = msg.get("regions", [])
            text = msg.get("text", "")

            # Add the message bubble
            self.add_message(
                text=text,
                msg_type="preview",
                item_id=item_id,
            )
            # Add region buttons
            if regions:
                self._add_region_buttons(item_id, regions)

        elif msg_type == "content_generated":
            self.add_message(
                text=msg.get("text", ""),
                msg_type="info",
                item_id=msg.get("item", {}).get("id"),
            )

        elif msg_type == "status_update":
            item_id = msg.get("item_id")
            status = msg.get("status", "")
            text = msg.get("text", "")
            self.update_message(item_id, status, text)

        elif msg_type == "published":
            item_id = msg.get("item_id")
            self.update_message(item_id, Status.PUBLISHED, msg.get("text", ""))
            # Also add a success message
            self.add_message(
                text=msg.get("text", ""),
                msg_type="success",
                item_id=None,  # Don't track — it's a notification
            )

        elif msg_type == "topic_file_exhausted":
            # Show exhaustion message with upload button
            text = msg.get("text", "")
            border_color = BUBBLE_COLORS.get("exhausted", COLOR_ERROR)

            bubble_outer = ctk.CTkFrame(
                self._feed_frame, fg_color=COLOR_BG, corner_radius=0,
            )
            bubble_outer.pack(fill="x", padx=12, pady=4)

            accent_bar = ctk.CTkFrame(
                bubble_outer, fg_color=border_color, width=3, corner_radius=0,
            )
            accent_bar.pack(side="left", fill="y")

            bubble = ctk.CTkFrame(
                bubble_outer, fg_color=COLOR_SURFACE, corner_radius=8,
            )
            bubble.pack(side="left", fill="x", expand=True, padx=(6, 0))

            ctk.CTkLabel(
                bubble, text=text,
                font=ctk.CTkFont(family="Segoe UI", size=13),
                text_color=COLOR_TEXT, wraplength=550,
                justify="left", anchor="w",
            ).pack(fill="x", padx=12, pady=(10, 4))

            self._add_upload_button(bubble)
            self._feed_frame.after(50, self._scroll_to_bottom)
