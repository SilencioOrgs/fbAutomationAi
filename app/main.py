"""
Application entry point.
Wires all components together and starts the CustomTkinter UI.
"""

import json
import logging
import os
import queue
import sys

import customtkinter as ctk
from dotenv import load_dotenv

# Add the app directory to sys.path for clean imports
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from core.content_gen import ContentGenerator
from core.fb_publisher import FacebookPublisher
from core.image_gen import ImageGenerator
from core.scheduler import Pipeline
from core.telegram_bot import TelegramBot
from core.topic_source import TopicSource
from db.db import Database
from ui.chat_feed import ChatFeed
from ui.logs import LogsPanel
from ui.settings import SettingsPanel

# ------------------------------------------------------------------ #
#  Logging setup
# ------------------------------------------------------------------ #

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
os.makedirs(os.path.join(APP_DIR, "data"), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(APP_DIR, "data", "app.log"),
            encoding="utf-8",
        ),
    ],
)
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


class App(ctk.CTk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()

        # Window setup
        self.title("FB Content Automation")
        self.geometry("950x680")
        self.minsize(800, 550)
        ctk.set_appearance_mode("dark")

        # Load environment
        env_path = os.path.join(APP_DIR, ".env")
        load_dotenv(env_path)
        self._validate_env()

        # Load config
        self._config = self._load_config()

        # Ensure data directories exist
        os.makedirs(os.path.join(APP_DIR, "data", "images"), exist_ok=True)

        # Thread-safe queue for UI updates
        self._ui_queue: queue.Queue = queue.Queue()

        # Initialize components
        self._init_components()

        # Build UI
        self._build_ui()

        # Start Telegram bot (no-ops if disabled)
        self._telegram.start()

        # Always start the scheduler (it runs the scheduled posts checker)
        self._pipeline.start_scheduler()

        # Handle close
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        logger.info("Application started")

    def _validate_env(self) -> None:
        """Validate that required environment variables are set.
        
        TELEGRAM_BOT_TOKEN is no longer required — Telegram is optional.
        GEMINI_API_KEY is no longer used.
        """
        required = [
            "AI33PRO_API_KEY",
            "FB_PAGE_ACCESS_TOKEN",
            "FB_PAGE_ID",
        ]
        missing = [var for var in required if not os.getenv(var)]
        if missing:
            msg = (
                f"Missing required environment variables: {', '.join(missing)}\n"
                f"Please create a .env file in {APP_DIR} with all required values.\n"
                f"See .env.example for reference."
            )
            logger.error(msg)
            # Don't crash — show a dialog at startup
            self._env_error = msg
        else:
            self._env_error = None

    def _load_config(self) -> dict:
        """Load prompt_templates.json."""
        config_path = os.path.join(APP_DIR, "config", "prompt_templates.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Could not load config: %s", e)
            return {}

    def _init_components(self) -> None:
        """Initialize all core modules."""
        # Database
        self._db = Database()
        self._db.initialize()

        # Core modules
        self._topic_source = TopicSource(
            db=self._db,
            config=self._config,
        )
        self._content_gen = ContentGenerator(
            db=self._db,
        )
        self._image_gen = ImageGenerator(
            api_key=os.getenv("AI33PRO_API_KEY", ""),
            db=self._db,
        )
        self._publisher = FacebookPublisher(
            page_access_token=os.getenv("FB_PAGE_ACCESS_TOKEN", ""),
            page_id=os.getenv("FB_PAGE_ID", ""),
            db=self._db,
        )

        # Telegram bot (pipeline set after Pipeline creation)
        admin_id = 0
        try:
            admin_id = int(os.getenv("TELEGRAM_ADMIN_ID", "0"))
        except ValueError:
            logger.error("TELEGRAM_ADMIN_ID must be an integer")

        self._telegram = TelegramBot(
            token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            admin_id=admin_id,
            db=self._db,
            ui_queue=self._ui_queue,
        )

        # Pipeline orchestrator
        self._pipeline = Pipeline(
            db=self._db,
            topic_source=self._topic_source,
            content_gen=self._content_gen,
            image_gen=self._image_gen,
            publisher=self._publisher,
            telegram=self._telegram,
            ui_queue=self._ui_queue,
            config=self._config,
        )

        # Set pipeline on telegram bot (resolves circular dependency)
        self._telegram.set_pipeline(self._pipeline)

    def _build_ui(self) -> None:
        """Build the main application layout: sidebar + content area."""
        # Configure grid
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self._sidebar = ctk.CTkFrame(
            self, fg_color=COLOR_SURFACE, width=180, corner_radius=0
        )
        self._sidebar.grid(row=0, column=0, sticky="nsew")
        self._sidebar.grid_propagate(False)

        # App title in sidebar
        title_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        title_frame.pack(fill="x", padx=12, pady=(16, 24))

        ctk.CTkLabel(
            title_frame,
            text="FB",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COLOR_ACCENT,
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_frame,
            text="Content Automation",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w")

        # Navigation buttons
        self._nav_buttons = {}
        nav_items = [
            ("Feed", self.show_feed),
            ("Settings", self.show_settings),
            ("Logs", self.show_logs),
        ]
        for name, command in nav_items:
            btn = ctk.CTkButton(
                self._sidebar,
                text=name,
                font=ctk.CTkFont(family="Segoe UI", size=13),
                fg_color="transparent",
                text_color=COLOR_TEXT,
                hover_color=COLOR_SURFACE_ALT,
                anchor="w",
                height=38,
                corner_radius=6,
                command=command,
            )
            btn.pack(fill="x", padx=8, pady=2)
            self._nav_buttons[name] = btn

        # Version label at bottom of sidebar
        ctk.CTkLabel(
            self._sidebar,
            text="v1.1.0",
            font=ctk.CTkFont(size=10),
            text_color=COLOR_TEXT_DIM,
        ).pack(side="bottom", pady=12)

        # Content area
        self._content_frame = ctk.CTkFrame(
            self, fg_color=COLOR_BG, corner_radius=0
        )
        self._content_frame.grid(row=0, column=1, sticky="nsew")
        self._content_frame.grid_columnconfigure(0, weight=1)
        self._content_frame.grid_rowconfigure(0, weight=1)

        # Create all panels
        self._feed_panel = ChatFeed(
            self._content_frame, self._pipeline, self._db, self._ui_queue,
            telegram=self._telegram,
        )
        self._settings_panel = SettingsPanel(
            self._content_frame, self._pipeline, self._image_gen, self._config
        )
        self._logs_panel = LogsPanel(
            self._content_frame, self._db, self._image_gen
        )

        # Show feed by default
        self.show_feed()

        # Show env error if any
        if hasattr(self, "_env_error") and self._env_error:
            self._ui_queue.put({
                "type": "error",
                "text": self._env_error,
            })

    def _hide_all_panels(self) -> None:
        """Remove all panels from the grid."""
        for panel in (self._feed_panel, self._settings_panel, self._logs_panel):
            panel.grid_forget()

        # Reset button highlights
        for btn in self._nav_buttons.values():
            btn.configure(fg_color="transparent", text_color=COLOR_TEXT)

    def show_feed(self) -> None:
        """Show the chat feed panel."""
        self._hide_all_panels()
        self._feed_panel.grid(row=0, column=0, sticky="nsew")
        self._nav_buttons["Feed"].configure(
            fg_color=COLOR_SURFACE_ALT, text_color=COLOR_ACCENT
        )

    def show_settings(self) -> None:
        """Show the settings panel."""
        self._hide_all_panels()
        self._settings_panel.grid(row=0, column=0, sticky="nsew")
        self._nav_buttons["Settings"].configure(
            fg_color=COLOR_SURFACE_ALT, text_color=COLOR_ACCENT
        )

    def show_logs(self) -> None:
        """Show the logs panel."""
        self._hide_all_panels()
        self._logs_panel.grid(row=0, column=0, sticky="nsew")
        self._logs_panel.refresh_logs()
        self._nav_buttons["Logs"].configure(
            fg_color=COLOR_SURFACE_ALT, text_color=COLOR_ACCENT
        )

    def on_closing(self) -> None:
        """Graceful shutdown."""
        logger.info("Application shutting down...")

        try:
            self._pipeline.stop_scheduler()
        except Exception as e:
            logger.warning("Scheduler shutdown error: %s", e)

        try:
            self._telegram.stop()
        except Exception as e:
            logger.warning("Telegram bot shutdown error: %s", e)

        self.destroy()


def main() -> None:
    """Application entry point."""
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
