"""
Topic generation via Google Gemini API (google.genai SDK).
Generates N content ideas for a configurable niche and stores them in SQLite.
"""

import json
import logging
import re
import time

from google import genai
from google.genai import types

from db.db import Database

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
BASE_BACKOFF = 2  # seconds


class TopicGenerator:
    """Generates Facebook content topic ideas using Google Gemini."""

    def __init__(self, api_key: str, db: Database) -> None:
        self._db = db
        self._api_key = api_key
        self._client = genai.Client(api_key=api_key)

    def generate_topics(
        self, niche: str, count: int = 3, template: dict | None = None
    ) -> list[dict]:
        """
        Call Gemini to produce `count` topic ideas for the given niche.
        Each topic is inserted into content_items with status 'pending_approval'.
        Returns list of created content_item dicts.
        Logs usage to usage_log.
        Retries up to 3 times with exponential backoff on API failure.
        """
        prompt = self._build_prompt(niche, count, template)
        system_prompt = ""
        if template and "system_prompt" in template:
            system_prompt = template["system_prompt"]

        response_text = None
        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(
                    "Topic generation attempt %d/%d for niche='%s' count=%d",
                    attempt, MAX_RETRIES, niche, count,
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
                    "Gemini topic gen attempt %d failed: %s", attempt, last_error
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
            raise RuntimeError(
                f"Topic generation failed after {MAX_RETRIES} attempts: {last_error}"
            )

        # Parse JSON array from response
        topics = self._parse_topics(response_text)
        if not topics:
            raise RuntimeError(
                f"Failed to parse topics from Gemini response: {response_text[:200]}"
            )

        # Store each topic in the database
        created_items = []
        for topic_text in topics[:count]:
            item_id = self._db.create_content_item(topic=topic_text.strip())
            item = self._db.get_content_item(item_id)
            created_items.append(item)

        logger.info("Generated %d topics for niche='%s'", len(created_items), niche)
        return created_items

    def _build_prompt(
        self, niche: str, count: int, template: dict | None
    ) -> str:
        """Merge niche and count into the prompt template."""
        if template and "user_prompt" in template:
            return template["user_prompt"].format(niche=niche, count=count)
        return (
            f"Generate {count} unique, engaging Facebook post topic ideas "
            f"for the niche: {niche}. Return ONLY a valid JSON array of strings."
        )

    def _parse_topics(self, text: str) -> list[str]:
        """Extract a JSON array of strings from the Gemini response."""
        # Try direct JSON parse first
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(t) for t in parsed if t]
        except json.JSONDecodeError:
            pass

        # Try to find JSON array in the text (Gemini sometimes wraps in markdown)
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
                if isinstance(parsed, list):
                    return [str(t) for t in parsed if t]
            except json.JSONDecodeError:
                pass

        logger.error("Could not parse topics from response: %s", text[:300])
        return []
