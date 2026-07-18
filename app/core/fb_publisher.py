"""
Facebook Graph API publisher.
Posts image + caption to a Facebook Page via the /{page-id}/photos endpoint.
"""

import logging
import time

import requests

from db.db import Database
from db.models import Status

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_BACKOFF = 2
GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


class FacebookPublisher:
    """Publishes image+caption posts to a Facebook Page."""

    def __init__(
        self, page_access_token: str, page_id: str, db: Database
    ) -> None:
        self._token = page_access_token
        self._page_id = page_id
        self._db = db

    def publish(self, item_id: int) -> str:
        """
        POST /{page_id}/photos with the image file and caption.
        Caption = title + description + hashtags.
        Updates content_item status to 'published' and stores fb_post_id.
        On failure: status = 'failed', error_message stored.
        Returns the Facebook post ID.
        Retries up to 3 times with exponential backoff.
        """
        item = self._db.get_content_item(item_id)
        if item is None:
            raise ValueError(f"Content item {item_id} not found")

        self._db.update_status(item_id, Status.PUBLISHING)

        image_path = item.get("image_local_path")
        if not image_path:
            error_msg = "No image path found for publishing"
            self._db.update_status(
                item_id, Status.FAILED, error_message=error_msg
            )
            raise RuntimeError(error_msg)

        caption = self._build_caption(item)
        url = f"{GRAPH_API_BASE}/{self._page_id}/photos"
        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(
                    "Facebook publish attempt %d/%d for item_id=%d",
                    attempt, MAX_RETRIES, item_id,
                )

                with open(image_path, "rb") as img_file:
                    resp = requests.post(
                        url,
                        data={
                            "caption": caption,
                            "access_token": self._token,
                        },
                        files={"source": img_file},
                        timeout=60,
                    )

                resp.raise_for_status()
                data = resp.json()

                # Check for API-level errors
                if "error" in data:
                    raise RuntimeError(
                        f"Facebook API error: {data['error'].get('message', data['error'])}"
                    )

                fb_post_id = data.get("post_id") or data.get("id", "")

                self._db.update_status(
                    item_id, Status.PUBLISHED, fb_post_id=str(fb_post_id)
                )
                self._db.log_usage(
                    provider="facebook",
                    endpoint=f"POST /{self._page_id}/photos",
                    success=True,
                )

                logger.info(
                    "Published item_id=%d fb_post_id=%s", item_id, fb_post_id
                )
                return str(fb_post_id)

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "Facebook publish attempt %d failed: %s", attempt, last_error
                )
                self._db.log_usage(
                    provider="facebook",
                    endpoint=f"POST /{self._page_id}/photos",
                    success=False,
                    error_msg=last_error,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(BASE_BACKOFF ** attempt)

        error_msg = (
            f"Facebook publish failed after {MAX_RETRIES} attempts: {last_error}"
        )
        self._db.update_status(item_id, Status.FAILED, error_message=error_msg)
        raise RuntimeError(error_msg)

    def _build_caption(self, item: dict) -> str:
        """Compose the full caption from title + description + hashtags."""
        parts = []
        title = item.get("generated_title", "")
        if title:
            parts.append(title)

        description = item.get("generated_description", "")
        if description:
            parts.append(description)

        hashtags = item.get("generated_hashtags", "")
        if hashtags:
            parts.append(hashtags)

        return "\n\n".join(parts)
