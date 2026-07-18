import os
import customtkinter as ctk
from PIL import Image

from ui.chat_feed import (
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_ALT, COLOR_ACCENT, 
    COLOR_ACCENT_DIM, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_BORDER, COLOR_SUCCESS, COLOR_ERROR
)

class PostPreviewCard(ctk.CTkFrame):
    """
    Rich preview card mimicking a social media post (Facebook/Instagram).
    Includes Recreate Image and Edit Caption actions in addition to Approve/Reject.
    """

    def __init__(
        self,
        parent,
        item: dict,
        config: dict,
        on_approve: callable,
        on_reject: callable,
        on_recreate_image: callable,
        on_edit_caption: callable
    ):
        super().__init__(parent, fg_color=COLOR_BG, corner_radius=0)
        self._item = item
        self._config = config
        self._on_approve = on_approve
        self._on_reject = on_reject
        self._on_recreate_image = on_recreate_image
        self._on_edit_caption = on_edit_caption
        
        # Load aspect ratio from config to determine image size
        self._aspect_ratio = self._config.get("image_generation", {}).get("model_parameters", {}).get("aspect_ratio", "1:1")
        self._platform = "Facebook"
        self._image_ctk = None # Keep reference
        
        self._build_ui()
        
    def get_action_frame(self):
        """Returns the main action frame so ChatFeed can manage it if needed, though we handle actions internally mostly."""
        return self._action_frame
        
    def get_accent_bar(self):
        return self._accent_bar
        
    def _build_ui(self):
        # Outer container with left border accent
        self.pack(fill="x", padx=12, pady=4)
        
        # Accent bar on the left
        self._accent_bar = ctk.CTkFrame(
            self, fg_color=COLOR_ACCENT, width=3, corner_radius=0
        )
        self._accent_bar.pack(side="left", fill="y")
        
        # Main bubble content
        self._bubble = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, corner_radius=8)
        self._bubble.pack(side="left", fill="x", expand=True, padx=(6, 0), pady=0)
        
        # Top Header row (Platform Toggle)
        header_row = ctk.CTkFrame(self._bubble, fg_color="transparent")
        header_row.pack(fill="x", padx=12, pady=(8, 0))
        
        self._fb_tab = ctk.CTkButton(
            header_row, text="Facebook Preview", font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=COLOR_SURFACE_ALT, hover_color=COLOR_BORDER,
            width=130, height=24, corner_radius=12,
            command=lambda: self._toggle_platform("Facebook")
        )
        self._fb_tab.pack(side="left", padx=(0, 4))
        
        self._ig_tab = ctk.CTkButton(
            header_row, text="Instagram Preview", font=ctk.CTkFont(size=11),
            fg_color="transparent", hover_color=COLOR_SURFACE_ALT, text_color=COLOR_TEXT_DIM,
            width=130, height=24, corner_radius=12,
            command=lambda: self._toggle_platform("Instagram")
        )
        self._ig_tab.pack(side="left")
        
        # Card Body (The mock post)
        self._card_body = ctk.CTkFrame(self._bubble, fg_color=COLOR_BG, corner_radius=6)
        self._card_body.pack(fill="x", padx=12, pady=(12, 12))
        
        # Post Header (Avatar, Page Name, Timestamp)
        post_header = ctk.CTkFrame(self._card_body, fg_color="transparent")
        post_header.pack(fill="x", padx=12, pady=(12, 8))
        
        branding = self._config.get("branding", {})
        page_name = branding.get("page_name", "Content Page")
        avatar_initial = branding.get("page_avatar_initial", "P")
        
        avatar_lbl = ctk.CTkLabel(
            post_header, text=avatar_initial, width=32, height=32,
            fg_color=COLOR_ACCENT, text_color="#000", corner_radius=16,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        avatar_lbl.pack(side="left", padx=(0, 8))
        
        meta_frame = ctk.CTkFrame(post_header, fg_color="transparent")
        meta_frame.pack(side="left", fill="y")
        
        ctk.CTkLabel(
            meta_frame, text=page_name, font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLOR_TEXT
        ).pack(anchor="w", pady=(0, 0))
        ctk.CTkLabel(
            meta_frame, text="Just now • Public", font=ctk.CTkFont(size=10),
            text_color=COLOR_TEXT_DIM
        ).pack(anchor="w")
        
        # Image
        self._image_lbl = ctk.CTkLabel(self._card_body, text="")
        self._image_lbl.pack(fill="x", padx=0, pady=0)
        self._image_lbl.bind("<Button-1>", self._open_image_viewer)
        
        image_path = self._item.get("image_local_path")
        self._render_image(image_path)
        
        # Caption Block
        self._caption_frame = ctk.CTkFrame(self._card_body, fg_color="transparent")
        self._caption_frame.pack(fill="x", padx=12, pady=(12, 8))
        
        self._title_lbl = ctk.CTkLabel(
            self._caption_frame, text="", font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXT, justify="left", anchor="w", wraplength=480
        )
        self._title_lbl.pack(fill="x", pady=(0, 4))
        
        self._desc_lbl = ctk.CTkLabel(
            self._caption_frame, text="", font=ctk.CTkFont(size=13),
            text_color=COLOR_TEXT, justify="left", anchor="w", wraplength=480
        )
        self._desc_lbl.pack(fill="x", pady=(0, 8))
        
        self._tags_lbl = ctk.CTkLabel(
            self._caption_frame, text="", font=ctk.CTkFont(size=13),
            text_color=COLOR_ACCENT, justify="left", anchor="w", wraplength=480
        )
        self._tags_lbl.pack(fill="x")
        
        self.update_caption(
            self._item.get("generated_title", ""),
            self._item.get("generated_description", ""),
            self._item.get("generated_hashtags", "")
        )
        
        # Engagement Mockup
        eng_frame = ctk.CTkFrame(self._card_body, fg_color="transparent")
        eng_frame.pack(fill="x", padx=12, pady=(0, 12))
        
        # Divider
        ctk.CTkFrame(eng_frame, fg_color=COLOR_BORDER, height=1).pack(fill="x", pady=(0, 8))
        
        btns_frame = ctk.CTkFrame(eng_frame, fg_color="transparent")
        btns_frame.pack(fill="x")
        
        for text in ["Like", "Comment", "Share"]:
            ctk.CTkLabel(
                btns_frame, text=text, font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_TEXT_DIM
            ).pack(side="left", expand=True)
            
        # Action Row (Real actions)
        self._action_frame = ctk.CTkFrame(self._bubble, fg_color="transparent")
        self._action_frame.pack(fill="x", padx=12, pady=(4, 10))
        
        # Primary actions
        self._approve_btn = ctk.CTkButton(
            self._action_frame, text="Approve", font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_ACCENT, text_color="#000", hover_color=COLOR_ACCENT_DIM,
            width=90, height=30, corner_radius=6,
            command=lambda: self._on_approve(self._item["id"])
        )
        self._approve_btn.pack(side="left", padx=(0, 8))
        
        self._reject_btn = ctk.CTkButton(
            self._action_frame, text="Reject", font=ctk.CTkFont(size=12),
            fg_color=COLOR_SURFACE_ALT, text_color=COLOR_TEXT, hover_color="#3A3A3A",
            width=90, height=30, corner_radius=6,
            command=lambda: self._on_reject(self._item["id"])
        )
        self._reject_btn.pack(side="left", padx=(0, 16))
        
        # Secondary edit actions
        self._recreate_btn = ctk.CTkButton(
            self._action_frame, text="Recreate Image", font=ctk.CTkFont(size=12),
            fg_color="transparent", text_color=COLOR_TEXT, hover_color=COLOR_SURFACE_ALT,
            border_width=1, border_color=COLOR_BORDER,
            width=110, height=30, corner_radius=6,
            command=self._handle_recreate_image
        )
        self._recreate_btn.pack(side="left", padx=(0, 8))
        
        self._edit_cap_btn = ctk.CTkButton(
            self._action_frame, text="Edit Caption", font=ctk.CTkFont(size=12),
            fg_color="transparent", text_color=COLOR_TEXT, hover_color=COLOR_SURFACE_ALT,
            border_width=1, border_color=COLOR_BORDER,
            width=100, height=30, corner_radius=6,
            command=self._open_edit_modal
        )
        self._edit_cap_btn.pack(side="left")

    def _render_image(self, image_path: str):
        """Loads and scales the image based on aspect ratio."""
        if not image_path or not os.path.exists(image_path):
            self._image_lbl.configure(text="[ Image Generating or Missing ]", text_color=COLOR_TEXT_DIM)
            return
            
        try:
            pil_image = Image.open(image_path)
            
            # Target width is roughly 480
            target_w = 480
            
            # Determine target height based on aspect ratio config
            w_ratio, h_ratio = 1, 1
            if ":" in self._aspect_ratio:
                try:
                    w_r, h_r = map(int, self._aspect_ratio.split(":"))
                    w_ratio, h_ratio = w_r, h_r
                except ValueError:
                    pass
                    
            target_h = int(target_w * (h_ratio / w_ratio))
            
            pil_image.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
            
            self._image_ctk = ctk.CTkImage(
                light_image=pil_image, dark_image=pil_image, size=pil_image.size
            )
            self._image_lbl.configure(image=self._image_ctk, text="")
            self._image_lbl.configure(cursor="hand2")
            
        except Exception as e:
            self._image_lbl.configure(text=f"[ Image load error: {e} ]", text_color=COLOR_ERROR)

    def update_image(self, new_image_path: str) -> None:
        """Update the displayed image after regeneration."""
        self._item["image_local_path"] = new_image_path
        self._render_image(new_image_path)
        self._recreate_btn.configure(state="normal", text="Recreate Image")
        
    def update_caption(self, title: str, description: str, hashtags: str) -> None:
        """Refresh the caption block after an edit."""
        self._item["generated_title"] = title
        self._item["generated_description"] = description
        self._item["generated_hashtags"] = hashtags
        
        self._title_lbl.configure(text=title)
        self._desc_lbl.configure(text=description)
        self._tags_lbl.configure(text=hashtags)
        
    def disable_actions(self, new_status: str) -> None:
        """Disable buttons and update the accent bar color when the state changes."""
        self._action_frame.destroy()
        
        if new_status == Status.REJECTED:
            self._accent_bar.configure(fg_color=COLOR_ERROR)
        elif new_status == Status.APPROVED:
            self._accent_bar.configure(fg_color=COLOR_SUCCESS)

    def _handle_recreate_image(self):
        """Disables the recreate button and triggers the callback."""
        self._recreate_btn.configure(state="disabled", text="Generating...")
        self._image_lbl.configure(image="", text="[ Regenerating Image... ]", text_color=COLOR_ACCENT)
        self._on_recreate_image(self._item["id"])

    def _open_image_viewer(self, event=None):
        """Open full resolution image in a CTkToplevel."""
        image_path = self._item.get("image_local_path")
        if not image_path or not os.path.exists(image_path):
            return
            
        viewer = ctk.CTkToplevel(self)
        viewer.title("Image Viewer")
        viewer.geometry("800x800")
        viewer.attributes("-topmost", True)
        
        try:
            pil_image = Image.open(image_path)
            # Scale down to fit 750x750 max
            pil_image.thumbnail((750, 750), Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=pil_image.size)
            
            lbl = ctk.CTkLabel(viewer, image=ctk_img, text="")
            lbl.pack(expand=True, fill="both", padx=20, pady=20)
        except Exception as e:
            ctk.CTkLabel(viewer, text=f"Error loading image: {e}").pack(expand=True)
            
    def _open_edit_modal(self):
        """Open CTkToplevel to edit caption fields."""
        modal = ctk.CTkToplevel(self)
        modal.title("Edit Caption")
        modal.geometry("600x450")
        modal.attributes("-topmost", True)
        modal.grab_set() # Make modal
        
        # Frame
        frame = ctk.CTkFrame(modal, fg_color=COLOR_BG, corner_radius=0)
        frame.pack(expand=True, fill="both")
        
        ctk.CTkLabel(frame, text="Title / Headline:", text_color=COLOR_TEXT_DIM, anchor="w").pack(fill="x", padx=20, pady=(20, 5))
        title_entry = ctk.CTkEntry(frame, fg_color=COLOR_SURFACE, text_color=COLOR_TEXT, border_color=COLOR_BORDER)
        title_entry.pack(fill="x", padx=20)
        title_entry.insert(0, self._item.get("generated_title", ""))
        
        ctk.CTkLabel(frame, text="Description:", text_color=COLOR_TEXT_DIM, anchor="w").pack(fill="x", padx=20, pady=(15, 5))
        desc_box = ctk.CTkTextbox(frame, fg_color=COLOR_SURFACE, text_color=COLOR_TEXT, border_color=COLOR_BORDER, height=120)
        desc_box.pack(fill="x", padx=20)
        desc_box.insert("1.0", self._item.get("generated_description", ""))
        
        ctk.CTkLabel(frame, text="Hashtags:", text_color=COLOR_TEXT_DIM, anchor="w").pack(fill="x", padx=20, pady=(15, 5))
        tags_entry = ctk.CTkEntry(frame, fg_color=COLOR_SURFACE, text_color=COLOR_TEXT, border_color=COLOR_BORDER)
        tags_entry.pack(fill="x", padx=20)
        tags_entry.insert(0, self._item.get("generated_hashtags", ""))
        
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(25, 20))
        
        def on_save():
            title = title_entry.get().strip()
            desc = desc_box.get("1.0", "end-1c").strip()
            tags = tags_entry.get().strip()
            self._on_edit_caption(self._item["id"], title, desc, tags)
            modal.destroy()
            
        ctk.CTkButton(
            btn_frame, text="Save Changes", fg_color=COLOR_ACCENT, text_color="#000", hover_color=COLOR_ACCENT_DIM,
            command=on_save
        ).pack(side="right", padx=(10, 0))
        
        ctk.CTkButton(
            btn_frame, text="Cancel", fg_color=COLOR_SURFACE_ALT, text_color=COLOR_TEXT, hover_color="#3A3A3A",
            command=modal.destroy
        ).pack(side="right")
        
    def _toggle_platform(self, platform: str) -> None:
        """Switch between Facebook and Instagram layout styles (visual only)."""
        if platform == self._platform:
            return
            
        self._platform = platform
        if platform == "Facebook":
            self._fb_tab.configure(fg_color=COLOR_SURFACE_ALT, font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT)
            self._ig_tab.configure(fg_color="transparent", font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_DIM)
            # Expand caption block
            self._title_lbl.pack(fill="x", pady=(0, 4))
        else:
            self._ig_tab.configure(fg_color=COLOR_SURFACE_ALT, font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT)
            self._fb_tab.configure(fg_color="transparent", font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_DIM)
            # Condense caption block (IG style doesn't emphasize title as much)
            self._title_lbl.pack_forget()
