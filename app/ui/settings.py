"""
Settings panel: topic file selection, prompt templates,
posting schedule, and AI33PRO model selection.
"""

import json
import logging
import os
import threading

import customtkinter as ctk

logger = logging.getLogger(__name__)

# Color scheme
COLOR_BG = "#0D0D0D"
COLOR_SURFACE = "#1A1A1A"
COLOR_SURFACE_ALT = "#252525"
COLOR_ACCENT = "#FFD700"
COLOR_ACCENT_DIM = "#B8960F"
COLOR_TEXT = "#E8E8E8"
COLOR_TEXT_DIM = "#888888"
COLOR_BORDER = "#333333"

ASPECT_RATIO_OPTIONS = ["1:1", "4:5", "3:4", "4:3", "16:9", "9:16"]
RESOLUTION_OPTIONS = ["1K", "2K", "4K"]

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "prompt_templates.json",
)


class SettingsPanel(ctk.CTkFrame):
    """Settings screen for configuring the content pipeline."""

    def __init__(self, parent, pipeline, image_gen, config: dict) -> None:
        super().__init__(parent, fg_color=COLOR_BG, corner_radius=0)
        self._pipeline = pipeline
        self._image_gen = image_gen
        self._config = config
        self._models_list: list = []

        self._build_ui()
        self.load_config()

    def _build_ui(self) -> None:
        """Build the settings layout."""
        # Header
        header = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, height=50, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="Settings",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=COLOR_ACCENT,
        ).pack(side="left", padx=16, pady=10)

        # Scrollable content
        scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=COLOR_BG,
            scrollbar_button_color=COLOR_SURFACE_ALT,
            scrollbar_button_hover_color=COLOR_ACCENT_DIM,
        )
        scroll.pack(fill="both", expand=True, padx=16, pady=8)

        # --- Topic Source section ---
        self._add_section_label(scroll, "Topic Source (Excel)")

        ctk.CTkLabel(
            scroll, text="Active Topic File:",
            text_color=COLOR_TEXT_DIM, font=ctk.CTkFont(size=12),
        ).pack(anchor="w", pady=(4, 2))

        file_row = ctk.CTkFrame(scroll, fg_color="transparent")
        file_row.pack(fill="x", pady=(0, 8))

        self._topic_file_label = ctk.CTkLabel(
            file_row, text="No file selected",
            text_color=COLOR_TEXT, font=ctk.CTkFont(size=12),
            wraplength=350, anchor="w", justify="left",
        )
        self._topic_file_label.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            file_row,
            text="Browse...",
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_SURFACE_ALT,
            text_color=COLOR_TEXT,
            hover_color="#3A3A3A",
            width=100,
            height=30,
            corner_radius=6,
            command=self._browse_topic_file,
        ).pack(side="left")

        self._topic_file_status = ctk.CTkLabel(
            scroll, text="", text_color=COLOR_TEXT_DIM, font=ctk.CTkFont(size=11),
        )
        self._topic_file_status.pack(anchor="w", pady=(0, 4))

        ctk.CTkLabel(
            scroll, text="Topics Per Generation:",
            text_color=COLOR_TEXT_DIM, font=ctk.CTkFont(size=12),
        ).pack(anchor="w", pady=(4, 2))

        self._count_entry = ctk.CTkEntry(
            scroll, fg_color=COLOR_SURFACE_ALT, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT, width=100, height=34,
        )
        self._count_entry.pack(anchor="w", pady=(0, 8))

        # --- Content Generation section ---
        self._add_section_label(scroll, "Content Generation")

        ctk.CTkLabel(
            scroll, text="Title Template (use {headline}, {topic}, etc.):",
            text_color=COLOR_TEXT_DIM, font=ctk.CTkFont(size=12),
        ).pack(anchor="w", pady=(4, 2))

        self._title_template_entry = ctk.CTkEntry(
            scroll, fg_color=COLOR_SURFACE_ALT, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT, width=500, height=34,
        )
        self._title_template_entry.pack(anchor="w", pady=(0, 8))

        ctk.CTkLabel(
            scroll, text="Description Template:",
            text_color=COLOR_TEXT_DIM, font=ctk.CTkFont(size=12),
        ).pack(anchor="w", pady=(4, 2))

        self._desc_template_entry = ctk.CTkEntry(
            scroll, fg_color=COLOR_SURFACE_ALT, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT, width=500, height=34,
        )
        self._desc_template_entry.pack(anchor="w", pady=(0, 8))

        ctk.CTkLabel(
            scroll, text="Hashtags Template:",
            text_color=COLOR_TEXT_DIM, font=ctk.CTkFont(size=12),
        ).pack(anchor="w", pady=(4, 2))

        self._hashtags_template_entry = ctk.CTkEntry(
            scroll, fg_color=COLOR_SURFACE_ALT, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT, width=500, height=34,
        )
        self._hashtags_template_entry.pack(anchor="w", pady=(0, 12))

        # --- Image Generation section ---
        self._add_section_label(scroll, "Image Generation")

        ctk.CTkLabel(
            scroll, text="Image Prompt Template:",
            text_color=COLOR_TEXT_DIM, font=ctk.CTkFont(size=12),
        ).pack(anchor="w", pady=(4, 2))

        self._image_prompt = ctk.CTkTextbox(
            scroll, fg_color=COLOR_SURFACE_ALT, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT, width=500, height=60,
        )
        self._image_prompt.pack(anchor="w", pady=(0, 8))

        # Model selection
        model_row = ctk.CTkFrame(scroll, fg_color="transparent")
        model_row.pack(fill="x", pady=(4, 8))

        ctk.CTkLabel(
            model_row, text="AI33PRO Model:",
            text_color=COLOR_TEXT_DIM, font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(0, 8))

        self._model_var = ctk.StringVar(value="bytedance-seedream-4.5")
        self._model_dropdown = ctk.CTkOptionMenu(
            model_row,
            variable=self._model_var,
            values=["bytedance-seedream-4.5"],
            fg_color=COLOR_SURFACE_ALT,
            button_color=COLOR_ACCENT_DIM,
            button_hover_color=COLOR_ACCENT,
            text_color=COLOR_TEXT,
            width=250,
        )
        self._model_dropdown.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            model_row,
            text="Refresh Models",
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_SURFACE_ALT,
            text_color=COLOR_TEXT,
            hover_color="#3A3A3A",
            width=120,
            height=30,
            corner_radius=6,
            command=self.refresh_models,
        ).pack(side="left")

        # Aspect ratio and resolution
        params_row = ctk.CTkFrame(scroll, fg_color="transparent")
        params_row.pack(fill="x", pady=(4, 8))

        ctk.CTkLabel(
            params_row, text="Aspect Ratio:",
            text_color=COLOR_TEXT_DIM, font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(0, 4))

        self._aspect_var = ctk.StringVar(value="16:9")
        self._aspect_dropdown = ctk.CTkOptionMenu(
            params_row,
            variable=self._aspect_var,
            values=ASPECT_RATIO_OPTIONS,
            fg_color=COLOR_SURFACE_ALT,
            button_color=COLOR_ACCENT_DIM,
            button_hover_color=COLOR_ACCENT,
            text_color=COLOR_TEXT,
            width=90,
        )
        self._aspect_dropdown.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(
            params_row, text="Resolution:",
            text_color=COLOR_TEXT_DIM, font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(0, 4))

        self._resolution_var = ctk.StringVar(value="2K")
        self._resolution_dropdown = ctk.CTkOptionMenu(
            params_row,
            variable=self._resolution_var,
            values=RESOLUTION_OPTIONS,
            fg_color=COLOR_SURFACE_ALT,
            button_color=COLOR_ACCENT_DIM,
            button_hover_color=COLOR_ACCENT,
            text_color=COLOR_TEXT,
            width=90,
        )
        self._resolution_dropdown.pack(side="left")

        # --- Schedule section ---
        self._add_section_label(scroll, "Schedule")

        schedule_row = ctk.CTkFrame(scroll, fg_color="transparent")
        schedule_row.pack(fill="x", pady=(4, 8))

        self._schedule_enabled = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            schedule_row,
            text="Enable automatic topic generation",
            variable=self._schedule_enabled,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_DIM,
            text_color=COLOR_TEXT,
            border_color=COLOR_BORDER,
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(0, 16))

        ctk.CTkLabel(
            schedule_row, text="Interval (hours):",
            text_color=COLOR_TEXT_DIM, font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(0, 4))

        self._interval_entry = ctk.CTkEntry(
            schedule_row, fg_color=COLOR_SURFACE_ALT, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT, width=60, height=30,
        )
        self._interval_entry.pack(side="left")

        # --- Save button ---
        btn_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(20, 8))

        ctk.CTkButton(
            btn_frame,
            text="Save Settings",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=COLOR_ACCENT,
            text_color="#000000",
            hover_color=COLOR_ACCENT_DIM,
            width=160,
            height=36,
            corner_radius=6,
            command=self.save_config,
        ).pack(side="left", padx=(0, 12))

        self._save_status = ctk.CTkLabel(
            btn_frame, text="", text_color=COLOR_TEXT_DIM,
            font=ctk.CTkFont(size=12),
        )
        self._save_status.pack(side="left")

    def _add_section_label(self, parent, text: str) -> None:
        """Add a section header label."""
        ctk.CTkLabel(
            parent,
            text=text,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=COLOR_ACCENT,
        ).pack(anchor="w", pady=(16, 4))

        # Divider
        ctk.CTkFrame(
            parent, fg_color=COLOR_BORDER, height=1, corner_radius=0
        ).pack(fill="x", pady=(0, 8))

    def _browse_topic_file(self) -> None:
        """Open a file dialog to select a topic Excel file."""
        from tkinter import filedialog

        file_path = filedialog.askopenfilename(
            title="Select Topic Excel File",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
        )
        if not file_path:
            return

        # Validate
        from core.topic_source import TopicSource
        ts = TopicSource(self._pipeline._db, self._config)
        ok, msg = ts.validate_file(file_path)

        if ok:
            self._topic_file_label.configure(text=os.path.basename(file_path))
            self._config.setdefault("topic_source", {})["active_file"] = file_path
            remaining = ts.get_remaining_count(file_path)
            self._topic_file_status.configure(
                text=f"Valid. {remaining} topics available.",
                text_color="#4CAF50",
            )
        else:
            self._topic_file_status.configure(
                text=f"Invalid: {msg}",
                text_color="#E53935",
            )

    def load_config(self) -> None:
        """Load current values from config dict into UI fields."""
        # Topic source
        ts_cfg = self._config.get("topic_source", {})
        active_file = ts_cfg.get("active_file", "")
        if active_file:
            self._topic_file_label.configure(text=os.path.basename(active_file))
        else:
            self._topic_file_label.configure(text="No file selected")

        topic_cfg = self._config.get("topic_generation", {})
        self._count_entry.delete(0, "end")
        self._count_entry.insert(0, str(topic_cfg.get("default_count", 3)))

        # Content generation templates
        content_cfg = self._config.get("content_generation", {})
        self._title_template_entry.delete(0, "end")
        self._title_template_entry.insert(0, content_cfg.get("title_template", "{headline}"))

        self._desc_template_entry.delete(0, "end")
        self._desc_template_entry.insert(0, content_cfg.get("description_template", "{fact_text}"))

        self._hashtags_template_entry.delete(0, "end")
        self._hashtags_template_entry.insert(0, content_cfg.get("hashtags_template", "#DidYouKnow #{category} #{subject}"))

        # Image generation
        image_cfg = self._config.get("image_generation", {})
        self._image_prompt.delete("1.0", "end")
        self._image_prompt.insert("1.0", image_cfg.get("prompt_template", ""))

        self._model_var.set(image_cfg.get("model_id", "bytedance-seedream-4.5"))

        params = image_cfg.get("model_parameters", {})
        aspect_ratio = params.get("aspect_ratio", "16:9")
        resolution = params.get("resolution", "2K")
        self._aspect_var.set(
            aspect_ratio if aspect_ratio in ASPECT_RATIO_OPTIONS else "16:9"
        )
        self._resolution_var.set(
            resolution if resolution in RESOLUTION_OPTIONS else "2K"
        )

        # Schedule
        sched_cfg = self._config.get("schedule", {})
        self._schedule_enabled.set(sched_cfg.get("enabled", False))

        self._interval_entry.delete(0, "end")
        self._interval_entry.insert(0, str(sched_cfg.get("interval_hours", 6)))

    def save_config(self) -> None:
        """Persist changes to prompt_templates.json and update pipeline config."""
        try:
            count_val = int(self._count_entry.get().strip() or "3")
        except ValueError:
            count_val = 3

        try:
            interval_val = int(self._interval_entry.get().strip() or "6")
        except ValueError:
            interval_val = 6

        self._config["topic_generation"] = {
            "system_prompt": self._config.get("topic_generation", {}).get(
                "system_prompt", ""
            ),
            "user_prompt": self._config.get("topic_generation", {}).get(
                "user_prompt", ""
            ),
            "niche": self._config.get("topic_generation", {}).get(
                "niche", "technology and AI"
            ),
            "default_count": count_val,
        }

        self._config["content_generation"] = {
            "system_prompt": self._config.get("content_generation", {}).get(
                "system_prompt", ""
            ),
            "user_prompt": self._config.get("content_generation", {}).get(
                "user_prompt", ""
            ),
            "title_template": self._title_template_entry.get().strip() or "{headline}",
            "description_template": self._desc_template_entry.get().strip() or "{fact_text}",
            "hashtags_template": self._hashtags_template_entry.get().strip() or "#DidYouKnow #{category} #{subject}",
        }

        self._config["image_generation"] = {
            "prompt_template": self._image_prompt.get("1.0", "end").strip(),
            "model_id": self._model_var.get(),
            "model_parameters": {
                "aspect_ratio": self._aspect_var.get(),
                "resolution": self._resolution_var.get(),
            },
            "reference_image": self._config.get("image_generation", {}).get(
                "reference_image", "Template.png"
            ),
        }

        self._config["schedule"] = {
            "enabled": self._schedule_enabled.get(),
            "interval_hours": interval_val,
        }

        # Preserve topic_source and scheduling sections
        # (topic_source.active_file may have been set by browse)

        # Write to disk
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)

            # Reload pipeline config
            self._pipeline.reload_config()

            # Restart scheduler if settings changed
            if self._schedule_enabled.get():
                self._pipeline.start_scheduler(interval_hours=interval_val)
            else:
                self._pipeline.stop_scheduler()

            self._save_status.configure(text="Settings saved.", text_color="#4CAF50")
            logger.info("Settings saved to %s", CONFIG_PATH)

        except Exception as e:
            self._save_status.configure(
                text=f"Save failed: {e}", text_color="#E53935"
            )
            logger.error("Failed to save settings: %s", e)

    def refresh_models(self) -> None:
        """Fetch AI33PRO models in a background thread and populate dropdown."""
        self._model_dropdown.configure(values=["Loading..."])

        def _fetch():
            try:
                models = self._image_gen.fetch_models()
                model_ids = []
                for m in models:
                    if isinstance(m, dict):
                        mid = m.get("id") or m.get("model_id") or m.get("name", "")
                        if mid:
                            model_ids.append(str(mid))
                    elif isinstance(m, str):
                        model_ids.append(m)

                if not model_ids:
                    model_ids = ["bytedance-seedream-4.5"]

                self._models_list = model_ids
                self.after(0, lambda: self._model_dropdown.configure(values=model_ids))
                logger.info("Loaded %d AI33PRO models", len(model_ids))

            except Exception as e:
                logger.error("Failed to fetch models: %s", e)
                self.after(
                    0,
                    lambda: self._model_dropdown.configure(
                        values=["bytedance-seedream-4.5"]
                    ),
                )

        threading.Thread(target=_fetch, daemon=True).start()
