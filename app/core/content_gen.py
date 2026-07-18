"""
Content generation via Google Gemini API (google.genai SDK).
Generates FB post title, description, and hashtags for an approved topic.
"""

import json
import logging
import re
import time

from google import genai
from google.genai import types

from db.db import Database
from db.models import Status

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_BACKOFF = 2


class ContentGenerator:
    """Generates Facebook post content (title, description, hashtags) using Gemini."""

    def __init__(self, api_key: str, db: Database) -> None:
        self._db = db
        self._api_key = api_key
        self._client = genai.Client(api_key=api_key)

    def generate_content(
        self, item_id: int, template: dict | None = None, image_template: str = "{topic}"
    ) -> dict:
        """
        For an approved content_item, call Gemini to produce title, description, hashtags.
        Updates the DB row. Changes status to 'generating_image' on success,
        'failed' on error. Returns updated content_item dict.
        """
        item = self._db.get_content_item(item_id)
        if item is None:
            raise ValueError(f"Content item {item_id} not found")

        # Mark as generating
        self._db.update_status(item_id, Status.GENERATING_CONTENT)

        topic = item["topic"]
        prompt = self._build_prompt(topic, template)
        system_prompt = ""
        if template and "system_prompt" in template:
            system_prompt = template["system_prompt"]

        response_text = None
        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(
                    "Content generation attempt %d/%d for item_id=%d",
                    attempt, MAX_RETRIES, item_id,
                )
                config = None
                if system_prompt:
                    config = types.GenerateContentConfig(
                        system_instruction=system_prompt,
                    )

                response = self._client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt,
                    config=config,
                )
                response_text = response.text.strip()

                self._db.log_usage(
                    provider="gemini",
                    endpoint="generateContent",
                    success=True,
                )
                break

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "Gemini content gen attempt %d failed: %s", attempt, last_error
                )
                self._db.log_usage(
                    provider="gemini",
                    endpoint="generateContent",
                    success=False,
                    error_msg=last_error,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(BASE_BACKOFF ** attempt)

        if response_text is None:
            error_msg = f"Content generation failed after {MAX_RETRIES} attempts: {last_error}"
            self._db.update_status(
                item_id, Status.FAILED, error_message=error_msg
            )
            raise RuntimeError(error_msg)

        # Parse the JSON response
        content = self._parse_content(response_text)
        if content is None:
            error_msg = f"Failed to parse content from Gemini response: {response_text[:200]}"
            self._db.update_status(
                item_id, Status.FAILED, error_message=error_msg
            )
            raise RuntimeError(error_msg)

        # Format image prompt
        image_prompt = image_template
        format_values = {
            "topic": topic,
            "TOPIC": topic,
            "fact_text": content.get("fact_text", ""),
            "FACT_TEXT": content.get("fact_text", ""),
            "highlight_1": content.get("highlight_1", ""),
            "HIGHLIGHT_1": content.get("highlight_1", ""),
            "highlight_2": content.get("highlight_2", ""),
            "HIGHLIGHT_2": content.get("highlight_2", ""),
            "subject": content.get("subject", ""),
            "SUBJECT": content.get("subject", ""),
        }
        for k, v in format_values.items():
            image_prompt = image_prompt.replace(f"{{{k}}}", str(v))

        # Update the database
        hashtags_str = " ".join(
            f"#{tag.lstrip('#')}" for tag in content.get("hashtags", [])
        )
        self._db.update_status(
            item_id,
            Status.GENERATING_IMAGE,
            generated_title=content.get("title", ""),
            generated_description=content.get("description", ""),
            generated_hashtags=hashtags_str,
            image_prompt=image_prompt,
        )

        updated_item = self._db.get_content_item(item_id)
        logger.info("Generated content for item_id=%d title='%s'",
                     item_id, content.get("title", "")[:60])
        return updated_item

    def _build_prompt(self, topic: str, template: dict | None) -> str:
        """Merge topic into the prompt template."""
        if template and "user_prompt" in template:
            return template["user_prompt"].format(topic=topic)
        return (
            f"Write a Facebook post for this topic: {topic}. "
            f"Return ONLY a valid JSON object with keys: "
            f'"title", "description", "hashtags" (array of strings).'
        )

    def _parse_content(self, text: str) -> dict | None:
        """Extract a JSON object with title, description, hashtags from response."""
        # Try direct parse
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and "title" in parsed:
                return parsed
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in the text
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
                if isinstance(parsed, dict) and "title" in parsed:
                    return parsed
            except json.JSONDecodeError:
                pass

        logger.error("Could not parse content from response: %s", text[:300])
        return None
