"""
Content generation from Excel-sourced fields.
Builds title, description, hashtags from data already stored on the
content_item row, using templates from prompt_templates.json.
No external API calls.
"""

import logging
import re

from db.db import Database
from db.models import Status

logger = logging.getLogger(__name__)


class ContentGenerator:
    """Generates Facebook post content (title, description, hashtags) from Excel fields."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def generate_content(
        self, item_id: int, template: dict | None = None, image_template: str = "{topic}"
    ) -> dict:
        """
        For an approved content_item, build title, description, hashtags
        from the Excel-sourced fields already on the row.

        Uses templates from config["content_generation"]:
          - title_template:       default "{headline}"
          - description_template: default "{fact_text}"
          - hashtags_template:    default "#DidYouKnow #{category} #{subject}"

        Updates the DB row. Changes status to 'generating_image' on success,
        'failed' on error. Returns updated content_item dict.
        """
        item = self._db.get_content_item(item_id)
        if item is None:
            raise ValueError(f"Content item {item_id} not found")

        # Mark as generating
        self._db.update_status(item_id, Status.GENERATING_CONTENT)

        template = template or {}

        try:
            # Gather Excel-sourced fields
            fields = {
                "topic": item.get("topic", ""),
                "subject": item.get("subject", ""),
                "headline": item.get("headline", ""),
                "fact_text": item.get("fact_text", ""),
                "highlight_1": item.get("highlight_1", ""),
                "highlight_2": item.get("highlight_2", ""),
                "category": item.get("category", ""),
            }

            # Build title from template
            title_tmpl = template.get("title_template", "{headline}")
            title = self._apply_template(title_tmpl, fields)
            if not title:
                title = fields["topic"]  # Fallback to topic

            # Build description from template
            desc_tmpl = template.get("description_template", "{fact_text}")
            description = self._apply_template(desc_tmpl, fields)

            # Build hashtags from template
            hashtags_tmpl = template.get("hashtags_template", "#DidYouKnow #{category} #{subject}")
            hashtags_raw = self._apply_template(hashtags_tmpl, fields)
            # Clean up hashtags: remove spaces within individual tags
            hashtags_str = self._clean_hashtags(hashtags_raw)

            # Build image prompt from the image template
            image_prompt = image_template
            image_values = {
                "topic": fields["topic"],
                "TOPIC": fields["topic"],
                "fact_text": fields["fact_text"],
                "FACT_TEXT": fields["fact_text"],
                "highlight_1": fields["highlight_1"],
                "HIGHLIGHT_1": fields["highlight_1"],
                "highlight_2": fields["highlight_2"],
                "HIGHLIGHT_2": fields["highlight_2"],
                "subject": fields["subject"],
                "SUBJECT": fields["subject"],
            }
            for k, v in image_values.items():
                image_prompt = image_prompt.replace(f"{{{k}}}", str(v))

            # Update the database
            self._db.update_status(
                item_id,
                Status.GENERATING_IMAGE,
                generated_title=title,
                generated_description=description,
                generated_hashtags=hashtags_str,
                image_prompt=image_prompt,
            )

            updated_item = self._db.get_content_item(item_id)
            logger.info(
                "Generated content for item_id=%d title='%s'",
                item_id, title[:60],
            )
            return updated_item

        except Exception as e:
            error_msg = f"Content generation failed for item #{item_id}: {e}"
            logger.error(error_msg)
            self._db.update_status(
                item_id, Status.FAILED, error_message=error_msg
            )
            raise RuntimeError(error_msg) from e

    def _apply_template(self, template: str, fields: dict) -> str:
        """Replace {key} placeholders in template with field values."""
        result = template
        for key, value in fields.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result

    def _clean_hashtags(self, raw: str) -> str:
        """
        Clean hashtag string: ensure each tag starts with #,
        remove spaces within tags, collapse duplicates.
        """
        # Split on spaces/newlines, filter empty
        tokens = raw.split()
        cleaned = []
        for token in tokens:
            token = token.strip()
            if not token:
                continue
            # Ensure starts with #
            if not token.startswith("#"):
                token = f"#{token}"
            # Remove any non-alphanumeric chars except # and _
            tag = "#" + re.sub(r"[^a-zA-Z0-9_]", "", token.lstrip("#"))
            if tag != "#" and tag not in cleaned:
                cleaned.append(tag)
        return " ".join(cleaned)
