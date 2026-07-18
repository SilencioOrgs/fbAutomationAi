"""
AI33PRO Imagen API integration.
Async task/poll pattern: submit generation → poll for completion → download image.
"""

import logging
import os
import time

import requests

from db.db import Database
from db.models import Status

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_BACKOFF = 2
POLL_INTERVAL = 4.0  # seconds between status checks
POLL_TIMEOUT = 300.0  # 5 minutes max


class ImageGenerator:
    """AI33PRO image generation with task/poll pattern."""

    def __init__(
        self,
        api_key: str,
        db: Database,
        base_url: str = "https://api.ai33.pro",
        images_dir: str = None,
    ) -> None:
        self._api_key = api_key
        self._db = db
        self._base_url = base_url.rstrip("/")
        self._headers = {"xi-api-key": api_key}
        if images_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            images_dir = os.path.join(base_dir, "data", "images")
        self._images_dir = images_dir
        os.makedirs(self._images_dir, exist_ok=True)
        self._models_cache: list[dict] | None = None

    def fetch_models(self) -> list[dict]:
        """
        GET /v1i/models — fetch and cache available models.
        Called at startup; cached for subsequent use.
        """
        if self._models_cache is not None:
            return self._models_cache

        url = f"{self._base_url}/v1i/models"
        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info("Fetching AI33PRO models, attempt %d/%d",
                            attempt, MAX_RETRIES)
                resp = requests.get(url, headers=self._headers, timeout=30)
                resp.raise_for_status()
                data = resp.json()

                self._db.log_usage(
                    provider="ai33pro", endpoint="GET /v1i/models", success=True
                )

                # The response may be a list directly or wrapped in a key
                if isinstance(data, list):
                    self._models_cache = data
                elif isinstance(data, dict):
                    # Try common wrapper keys
                    self._models_cache = (
                        data.get("models")
                        or data.get("data")
                        or data.get("results")
                        or [data]
                    )
                else:
                    self._models_cache = []

                logger.info("Fetched %d AI33PRO models", len(self._models_cache))
                return self._models_cache

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "AI33PRO models fetch attempt %d failed: %s", attempt, last_error
                )
                self._db.log_usage(
                    provider="ai33pro",
                    endpoint="GET /v1i/models",
                    success=False,
                    error_msg=last_error,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(BASE_BACKOFF ** attempt)

        logger.error("Failed to fetch AI33PRO models after %d attempts", MAX_RETRIES)
        return []

    def check_credits(self) -> dict:
        """GET /v1/credits — return remaining credits info."""
        url = f"{self._base_url}/v1/credits"
        try:
            resp = requests.get(url, headers=self._headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            self._db.log_usage(
                provider="ai33pro", endpoint="GET /v1/credits", success=True
            )
            return data
        except Exception as e:
            error_msg = str(e)
            self._db.log_usage(
                provider="ai33pro",
                endpoint="GET /v1/credits",
                success=False,
                error_msg=error_msg,
            )
            logger.error("Failed to check AI33PRO credits: %s", error_msg)
            return {"error": error_msg}

    def check_price(
        self,
        model_id: str,
        count: int = 1,
        params: dict | None = None,
    ) -> dict:
        """POST /v1i/task/price — estimate cost before generating."""
        url = f"{self._base_url}/v1i/task/price"
        body = {
            "model_id": model_id,
            "generations_count": count,
            "model_parameters": params or {},
            "assets": 0,
        }
        try:
            resp = requests.post(
                url, headers=self._headers, json=body, timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
            self._db.log_usage(
                provider="ai33pro", endpoint="POST /v1i/task/price", success=True
            )
            return data
        except Exception as e:
            error_msg = str(e)
            self._db.log_usage(
                provider="ai33pro",
                endpoint="POST /v1i/task/price",
                success=False,
                error_msg=error_msg,
            )
            return {"error": error_msg}

    def generate_image(
        self,
        item_id: int,
        prompt: str,
        model_id: str,
        params: dict | None = None,
        reference_image_path: str | None = None,
    ) -> str:
        """
        Full image generation flow:
        1. POST /v1i/task/generate-image → get task_id
        2. Poll GET /v1/task/{task_id} until done
        3. Download image to data/images/{task_id}.png
        4. Update content_item with image_local_path
        5. Change status to 'preview_pending' on success, 'failed' on error

        Returns the local image file path.
        """
        self._db.update_status(item_id, Status.GENERATING_IMAGE)

        # Step 1: Submit generation request
        task_id = self._submit_generation(
            item_id, prompt, model_id, params, reference_image_path
        )

        # Update the task_id in DB
        self._db.update_status(
            item_id, Status.GENERATING_IMAGE, ai33pro_task_id=task_id
        )

        # Step 2: Poll for completion
        result = self._poll_task(task_id)

        if result.get("status") == "error":
            error_msg = result.get("error_message", "Unknown AI33PRO error")
            self._db.update_status(
                item_id, Status.FAILED, error_message=error_msg
            )
            raise RuntimeError(f"AI33PRO image generation failed: {error_msg}")

        # Step 3: Extract image URL and download
        image_url = self._extract_image_url(result)
        if not image_url:
            error_msg = "No image URL found in AI33PRO task result"
            self._db.update_status(
                item_id, Status.FAILED, error_message=error_msg
            )
            raise RuntimeError(error_msg)

        local_path = self._download_image(image_url, task_id)

        # Step 4: Update DB
        self._db.update_status(
            item_id, Status.PREVIEW_PENDING, image_local_path=local_path
        )

        logger.info(
            "Image generated for item_id=%d task_id=%s path=%s",
            item_id, task_id, local_path,
        )
        return local_path

    def _submit_generation(
        self,
        item_id: int,
        prompt: str,
        model_id: str,
        params: dict | None,
        reference_image_path: str | None = None,
    ) -> str:
        """POST /v1i/task/generate-image — submit and return task_id."""
        import json as json_mod

        url = f"{self._base_url}/v1i/task/generate-image"
        form_data = {
            "prompt": prompt,
            "model_id": model_id,
            "generations_count": "1",
        }
        if params:
            form_data["model_parameters"] = json_mod.dumps(params)

        if reference_image_path and not os.path.isfile(reference_image_path):
            raise FileNotFoundError(
                f"Configured reference image was not found: {reference_image_path}"
            )

        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(
                    "AI33PRO generate attempt %d/%d for item_id=%d",
                    attempt, MAX_RETRIES, item_id,
                )
                if reference_image_path:
                    with open(reference_image_path, "rb") as reference_image:
                        resp = requests.post(
                            url,
                            headers=self._headers,
                            data=form_data,
                            files={
                                "assets": (
                                    os.path.basename(reference_image_path),
                                    reference_image,
                                    "image/png",
                                )
                            },
                            timeout=30,
                        )
                else:
                    resp = requests.post(
                        url, headers=self._headers, data=form_data, timeout=30
                    )
                resp.raise_for_status()
                data = resp.json()

                if not data.get("success"):
                    raise RuntimeError(
                        f"AI33PRO returned success=false: {data}"
                    )

                task_id = data["task_id"]
                credit_cost = 0
                try:
                    remaining = data.get("ec_remain_credits", "0")
                    credit_cost = float(remaining) if remaining else 0
                except (ValueError, TypeError):
                    pass

                self._db.log_usage(
                    provider="ai33pro",
                    endpoint="POST /v1i/task/generate-image",
                    credit_cost=credit_cost,
                    success=True,
                )
                return task_id

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "AI33PRO generate attempt %d failed: %s", attempt, last_error
                )
                self._db.log_usage(
                    provider="ai33pro",
                    endpoint="POST /v1i/task/generate-image",
                    success=False,
                    error_msg=last_error,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(BASE_BACKOFF ** attempt)

        error_msg = f"AI33PRO generation failed after {MAX_RETRIES} attempts: {last_error}"
        self._db.update_status(item_id, Status.FAILED, error_message=error_msg)
        raise RuntimeError(error_msg)

    def _poll_task(
        self,
        task_id: str,
        interval: float = POLL_INTERVAL,
        timeout: float = POLL_TIMEOUT,
    ) -> dict:
        """Poll GET /v1/task/{task_id} until status is 'done' or 'error'."""
        url = f"{self._base_url}/v1/task/{task_id}"
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                self._db.log_usage(
                    provider="ai33pro",
                    endpoint=f"GET /v1/task/{task_id}",
                    success=False,
                    error_msg="Polling timeout exceeded",
                )
                return {
                    "status": "error",
                    "error_message": f"Polling timeout after {timeout}s",
                }

            try:
                resp = requests.get(url, headers=self._headers, timeout=15)
                resp.raise_for_status()
                data = resp.json()

                status = data.get("status", "unknown")
                progress = data.get("progress", 0)
                logger.info(
                    "AI33PRO task %s: status=%s progress=%s",
                    task_id, status, progress,
                )

                if status == "done":
                    self._db.log_usage(
                        provider="ai33pro",
                        endpoint=f"GET /v1/task/{task_id}",
                        success=True,
                    )
                    return data

                if status == "error":
                    error_msg = data.get("error_message", "Unknown error")
                    self._db.log_usage(
                        provider="ai33pro",
                        endpoint=f"GET /v1/task/{task_id}",
                        success=False,
                        error_msg=error_msg,
                    )
                    return data

            except Exception as e:
                logger.warning("Poll request failed: %s", e)

            time.sleep(interval)

    def _extract_image_url(self, task_result: dict) -> str | None:
        """Extract the first image URL from the task result metadata."""
        # The image URL may be nested in various structures
        metadata = task_result.get("metadata", {})
        if isinstance(metadata, dict):
            # Check common patterns
            images = metadata.get("images", [])
            if images and isinstance(images, list):
                first = images[0]
                if isinstance(first, str):
                    return first
                if isinstance(first, dict):
                    return first.get("url") or first.get("image_url")

            # Direct URL in metadata
            url = metadata.get("url") or metadata.get("image_url")
            if url:
                return url

        # Check top-level result
        result = task_result.get("result", {})
        if isinstance(result, dict):
            images = result.get("images", [])
            if images and isinstance(images, list):
                first = images[0]
                if isinstance(first, str):
                    return first
                if isinstance(first, dict):
                    return first.get("url") or first.get("image_url")

        # Check output field
        output = task_result.get("output", [])
        if isinstance(output, list) and output:
            first = output[0]
            if isinstance(first, str):
                return first
            if isinstance(first, dict):
                return first.get("url") or first.get("image_url")

        logger.error("Could not extract image URL from task result: %s",
                      str(task_result)[:500])
        return None

    def _download_image(self, url: str, task_id: str) -> str:
        """Download image from URL, save locally, return the local path."""
        local_path = os.path.join(self._images_dir, f"{task_id}.png")

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info("Downloading image attempt %d/%d: %s",
                            attempt, MAX_RETRIES, url[:100])
                resp = requests.get(url, timeout=60, stream=True)
                resp.raise_for_status()

                with open(local_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)

                logger.info("Image saved to %s", local_path)
                return local_path

            except Exception as e:
                logger.warning("Image download attempt %d failed: %s", attempt, e)
                if attempt < MAX_RETRIES:
                    time.sleep(BASE_BACKOFF ** attempt)

        raise RuntimeError(f"Failed to download image from {url}")
