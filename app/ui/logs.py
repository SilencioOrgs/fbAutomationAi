"""
Logs panel: API usage history, credit balance, and error log.
"""

import logging
import threading

import customtkinter as ctk

from db.db import Database

logger = logging.getLogger(__name__)

# Color scheme
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


class LogsPanel(ctk.CTkFrame):
    """Logs screen showing API usage, credit balance, and errors."""

    def __init__(self, parent, db: Database, image_gen) -> None:
        super().__init__(parent, fg_color=COLOR_BG, corner_radius=0)
        self._db = db
        self._image_gen = image_gen

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the logs panel layout."""
        # Header
        header = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, height=50, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="Logs & Usage",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=COLOR_ACCENT,
        ).pack(side="left", padx=16, pady=10)

        # Buttons row
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right", padx=16)

        ctk.CTkButton(
            btn_frame,
            text="Refresh",
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_ACCENT,
            text_color="#000000",
            hover_color=COLOR_ACCENT_DIM,
            width=100,
            height=30,
            corner_radius=6,
            command=self.refresh_logs,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_frame,
            text="Check Credits",
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_SURFACE_ALT,
            text_color=COLOR_TEXT,
            hover_color="#3A3A3A",
            width=120,
            height=30,
            corner_radius=6,
            command=self.check_credits,
        ).pack(side="left")

        # Credits display
        self._credits_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=COLOR_ACCENT,
        )
        self._credits_label.pack(anchor="w", padx=16, pady=(8, 4))

        # Filter row
        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.pack(fill="x", padx=16, pady=(4, 8))

        ctk.CTkLabel(
            filter_frame, text="Filter by provider:",
            text_color=COLOR_TEXT_DIM, font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(0, 8))

        self._filter_var = ctk.StringVar(value="All")
        self._filter_menu = ctk.CTkOptionMenu(
            filter_frame,
            variable=self._filter_var,
            values=["All", "gemini", "ai33pro", "telegram", "facebook"],
            fg_color=COLOR_SURFACE_ALT,
            button_color=COLOR_ACCENT_DIM,
            button_hover_color=COLOR_ACCENT,
            text_color=COLOR_TEXT,
            width=150,
            command=lambda _: self.refresh_logs(),
        )
        self._filter_menu.pack(side="left")

        # Logs table header
        table_header = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, height=32, corner_radius=0)
        table_header.pack(fill="x", padx=16)
        table_header.pack_propagate(False)

        columns = [
            ("Timestamp", 170),
            ("Provider", 90),
            ("Endpoint", 200),
            ("Credits", 70),
            ("Status", 60),
            ("Error", 200),
        ]
        for col_name, col_width in columns:
            ctk.CTkLabel(
                table_header,
                text=col_name,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=COLOR_ACCENT_DIM,
                width=col_width,
                anchor="w",
            ).pack(side="left", padx=4)

        # Scrollable log entries
        self._log_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=COLOR_BG,
            scrollbar_button_color=COLOR_SURFACE_ALT,
            scrollbar_button_hover_color=COLOR_ACCENT_DIM,
        )
        self._log_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))

    def refresh_logs(self) -> None:
        """Reload usage_log entries and display in the scrollable list."""
        # Clear existing entries
        for widget in self._log_frame.winfo_children():
            widget.destroy()

        provider_filter = self._filter_var.get()
        provider = None if provider_filter == "All" else provider_filter

        logs = self._db.get_usage_logs(provider=provider, limit=200)

        if not logs:
            ctk.CTkLabel(
                self._log_frame,
                text="No log entries found.",
                text_color=COLOR_TEXT_DIM,
                font=ctk.CTkFont(size=12),
            ).pack(pady=20)
            return

        for i, log in enumerate(logs):
            bg = COLOR_SURFACE if i % 2 == 0 else COLOR_SURFACE_ALT
            row = ctk.CTkFrame(self._log_frame, fg_color=bg, height=28, corner_radius=0)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)

            # Timestamp
            ctk.CTkLabel(
                row,
                text=log.get("timestamp", ""),
                font=ctk.CTkFont(family="Consolas", size=11),
                text_color=COLOR_TEXT_DIM,
                width=170,
                anchor="w",
            ).pack(side="left", padx=4)

            # Provider
            provider_text = log.get("provider", "")
            provider_colors = {
                "gemini": "#4285F4",
                "ai33pro": "#FF6B35",
                "telegram": "#0088CC",
                "facebook": "#1877F2",
            }
            ctk.CTkLabel(
                row,
                text=provider_text,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=provider_colors.get(provider_text, COLOR_TEXT),
                width=90,
                anchor="w",
            ).pack(side="left", padx=4)

            # Endpoint
            endpoint = log.get("endpoint", "")
            if len(endpoint) > 30:
                endpoint = endpoint[:27] + "..."
            ctk.CTkLabel(
                row,
                text=endpoint,
                font=ctk.CTkFont(family="Consolas", size=11),
                text_color=COLOR_TEXT,
                width=200,
                anchor="w",
            ).pack(side="left", padx=4)

            # Credits
            credit = log.get("credit_cost", 0)
            credit_text = f"{credit:.1f}" if credit else "-"
            ctk.CTkLabel(
                row,
                text=credit_text,
                font=ctk.CTkFont(size=11),
                text_color=COLOR_TEXT_DIM,
                width=70,
                anchor="w",
            ).pack(side="left", padx=4)

            # Status
            success = log.get("success", 1)
            status_text = "OK" if success else "FAIL"
            status_color = COLOR_SUCCESS if success else COLOR_ERROR
            ctk.CTkLabel(
                row,
                text=status_text,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=status_color,
                width=60,
                anchor="w",
            ).pack(side="left", padx=4)

            # Error message
            error = log.get("error_msg", "") or ""
            if len(error) > 35:
                error = error[:32] + "..."
            ctk.CTkLabel(
                row,
                text=error,
                font=ctk.CTkFont(size=11),
                text_color=COLOR_ERROR if error else COLOR_TEXT_DIM,
                width=200,
                anchor="w",
            ).pack(side="left", padx=4)

    def check_credits(self) -> None:
        """Check AI33PRO credits in a background thread."""
        self._credits_label.configure(text="Checking credits...", text_color=COLOR_TEXT_DIM)

        def _fetch():
            try:
                result = self._image_gen.check_credits()
                if "error" in result:
                    text = f"Credits check failed: {result['error']}"
                    color = COLOR_ERROR
                else:
                    # Try to extract a credits value from the response
                    credits = (
                        result.get("credits")
                        or result.get("remaining")
                        or result.get("ec_remain_credits")
                        or result.get("balance")
                    )
                    if credits is not None:
                        text = f"AI33PRO Credits Remaining: {credits}"
                    else:
                        text = f"AI33PRO Credits: {result}"
                    color = COLOR_ACCENT

                self.after(0, lambda: self._credits_label.configure(
                    text=text, text_color=color
                ))

            except Exception as e:
                self.after(0, lambda: self._credits_label.configure(
                    text=f"Credits check error: {e}", text_color=COLOR_ERROR
                ))

        threading.Thread(target=_fetch, daemon=True).start()
