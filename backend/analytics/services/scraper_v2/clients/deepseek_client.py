"""DeepSeek AI client with proper resource management and cost tracking."""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import openai

from ..config import Settings, get_settings
from ..models import ScraperMetrics
from ..utils import async_retry, extract_json_from_text

logger = logging.getLogger(__name__)


class DeepSeekClient:
    """
    Client for DeepSeek API with resource management and cost tracking.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        metrics: Optional[ScraperMetrics] = None,
    ):
        """
        Initialize DeepSeek client.

        Args:
            settings: Configuration settings
            metrics: Metrics tracker
        """
        self.settings = settings or get_settings()
        self.metrics = metrics or ScraperMetrics()

        if not self.settings.DEEPSEEK_API_KEY:
            raise RuntimeError("DEEPSEEK_API_KEY must be configured")

        self.client = openai.AsyncOpenAI(
            api_key=self.settings.DEEPSEEK_API_KEY,
            base_url=self.settings.DEEPSEEK_API_URL,
        )

        self._semaphore = asyncio.Semaphore(self.settings.DEEPSEEK_MAX_CONCURRENT)

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the client."""
        if self.client:
            await asyncio.sleep(0.1)  # Allow pending tasks to complete
            await self.client.close()

    @async_retry(max_attempts=3, initial_delay=0.5, max_delay=6.0)
    async def complete(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Send completion request to DeepSeek.

        Args:
            prompt: User prompt
            temperature: Model temperature
            max_tokens: Maximum tokens in response

        Returns:
            Parsed JSON response
        """
        async with self._semaphore:
            payload = {
                "model": self.settings.DEEPSEEK_MODEL,
                "temperature": temperature or self.settings.DEEPSEEK_TEMPERATURE,
                "max_tokens": max_tokens or self.settings.DEEPSEEK_MAX_TOKENS,
                "messages": [{"role": "user", "content": prompt}],
            }

            try:
                response = await self.client.chat.completions.create(**payload)

                # Track metrics
                tokens_used = getattr(response.usage, "total_tokens", 0) if hasattr(response, "usage") else 0
                cost = (tokens_used / 1_000_000) * self.settings.DEEPSEEK_COST_PER_1M_TOKENS
                self.metrics.add_deepseek_call(tokens=tokens_used, cost=cost)

                # Extract response text
                text = self._extract_response_text(response)

                # Parse JSON
                parsed = extract_json_from_text(text)
                if not parsed:
                    logger.warning(f"Failed to parse JSON from DeepSeek response: {text[:500]}")
                    raise ValueError("Invalid JSON response from DeepSeek")

                return parsed

            except Exception as exc:
                logger.error(f"DeepSeek request failed: {exc}")
                self.metrics.add_error(f"DeepSeek error: {str(exc)}")
                raise

    async def complete_batch(
        self,
        prompts: List[str],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Send multiple completion requests in parallel.

        Args:
            prompts: List of prompts
            temperature: Model temperature
            max_tokens: Maximum tokens per response

        Returns:
            List of parsed JSON responses
        """
        tasks = [
            self.complete(prompt, temperature, max_tokens)
            for prompt in prompts
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to empty dicts
        return [
            result if not isinstance(result, Exception) else {}
            for result in results
        ]

    @staticmethod
    def _extract_response_text(response: Any) -> str:
        """
        Extract text content from OpenAI-compatible response.

        Args:
            response: API response object

        Returns:
            Response text content
        """
        if hasattr(response, 'choices') and len(response.choices) > 0:
            return response.choices[0].message.content.strip()
        elif isinstance(response, str):
            return response.strip()
        elif isinstance(response, dict):
            if 'choices' in response and len(response['choices']) > 0:
                return response['choices'][0]['message']['content'].strip()
            elif 'content' in response:
                return str(response['content']).strip()
        return str(response).strip()
