"""
Gemini API client — async wrapper with rate limiting, retry logic,
and safety-filter toggling for red-team testing.
Uses the new google.genai SDK (v1.0+).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import settings


class GeminiClient:
    """Wrapper around the google.genai SDK."""

    def __init__(
        self,
        model_name: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._api_key = api_key or settings.gemini_api_key
        self._model_name = model_name or settings.gemini_model
        self._rpm = settings.gemini_rpm
        self._request_times: list[float] = []

        # Initialize the client
        self._client = genai.Client(api_key=self._api_key)

        # Build safety settings
        self._safety_settings = self._build_safety_settings()

    # ── Safety settings ─────────────────────────────────────────

    @staticmethod
    def _build_safety_settings() -> list[types.SafetySetting]:
        """
        When disable_safety_filters is True we set all thresholds to
        BLOCK_NONE so the *API* doesn't reject prompts before the model
        can respond.  This lets us test the model's own refusal behaviour.
        """
        threshold = (
            types.HarmBlockThreshold.BLOCK_NONE
            if settings.disable_safety_filters
            else types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
        )
        
        return [
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=threshold,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=threshold,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=threshold,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=threshold,
            ),
        ]

    # ── Rate limiting ───────────────────────────────────────────

    async def _wait_for_rate_limit(self) -> None:
        """Simple sliding-window rate limiter (requests per minute)."""
        now = time.monotonic()
        # Purge timestamps older than 60s
        self._request_times = [t for t in self._request_times if now - t < 60]
        if len(self._request_times) >= self._rpm:
            sleep_for = 60 - (now - self._request_times[0]) + 0.1
            await asyncio.sleep(sleep_for)
        self._request_times.append(time.monotonic())

    # ── Core API calls ──────────────────────────────────────────

    async def generate(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        temperature: float = 1.0,
        max_tokens: int = 8192,
    ) -> str:
        """Send a single-turn prompt and return the text response."""
        await self._wait_for_rate_limit()

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            safety_settings=self._safety_settings,
            system_instruction=system_instruction,
        )

        from tenacity import AsyncRetrying

        try:
            # Use AsyncRetrying to avoid blocking the event loop during backoff
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=2, max=30),
                reraise=True,
            ):
                with attempt:
                    try:
                        response = await self._client.aio.models.generate_content(
                            model=self._model_name,
                            contents=prompt,
                            config=config,
                        )
                    except Exception as e:
                        # Reraise to trigger retry logic, or handle if it's a fatal error
                        # For now, we assume simple network/server errors are retriable
                        raise e

            # Parsing logic after successful response
            if not response.text and response.candidates:
                first_candidate = response.candidates[0]
                if first_candidate.finish_reason != types.FinishReason.STOP:
                     return f"[BLOCKED BY API] Reason: {first_candidate.finish_reason}"
    
            if not response.text:
                 return "[BLOCKED BY API] Unknown reason"
    
            return response.text

        except Exception as e:
            # Final catch after retries exhausted
            return f"[BLOCKED BY API] Error: {str(e)}"

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        system_instruction: str | None = None,
        temperature: float = 1.0,
    ) -> str:
        """
        Multi-turn chat.  `messages` is a list of
        {"role": "user"|"model", "parts": "text"} dicts.
        """
        await self._wait_for_rate_limit()

        # Convert simple list of dicts to SDK types if needed, 
        # but the SDK often accepts list of dicts for history.
        # We need to ensure 'parts' is a list or formatted correctly if the SDK expects Content objects.
        # The google.genai SDK generally accepts:
        # contents=[types.Content(role="user", parts=[types.Part(text="...")]), ...]
        
        formatted_history = []
        for msg in messages[:-1]:
            formatted_history.append(
                types.Content(
                    role=msg["role"],
                    parts=[types.Part(text=msg["parts"])]
                )
            )

        config = types.GenerateContentConfig(
            temperature=temperature,
            safety_settings=self._safety_settings,
            system_instruction=system_instruction,
        )

        chat = self._client.chats.create(
            model=self._model_name,
            config=config,
            history=formatted_history
        )

        try:
            response = await chat.send_message_async(
                messages[-1]["parts"]
            )
        except Exception as e:
            return f"[BLOCKED BY API] Error: {str(e)}"

        if not response.text and response.candidates:
            first_candidate = response.candidates[0]
            if first_candidate.finish_reason != types.FinishReason.STOP:
                 return f"[BLOCKED BY API] Reason: {first_candidate.finish_reason}"
        
        if not response.text:
             return "[BLOCKED BY API] Unknown reason"

        return response.text

    # ── Utility ─────────────────────────────────────────────────

    @property
    def model_name(self) -> str:
        return self._model_name

    def __repr__(self) -> str:
        return f"GeminiClient(model={self._model_name!r})"
