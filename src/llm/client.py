"""Anthropic Claude API client wrapper."""

import json
import time
from typing import Optional, TypeVar, Type

import anthropic
from pydantic import BaseModel

from src.config.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Async Claude API client with structured output support."""

    def __init__(self, api_key: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or settings.anthropic_api_key
        if not self.api_key:
            logger.warning("No ANTHROPIC_API_KEY configured, LLM features disabled")
            self.client = None
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = settings.llm_model
        self.max_tokens = settings.llm_max_tokens

    @property
    def is_available(self) -> bool:
        return self.client is not None

    def complete(
        self,
        prompt: str,
        system: str = "",
        response_schema: Optional[Type[T]] = None,
    ) -> tuple[Optional[T | str], int, int, int]:
        """
        Call Claude API with optional structured output.

        Returns: (response, input_tokens, output_tokens, latency_ms)
        """
        if not self.is_available:
            logger.warning("LLM not available, returning None")
            return None, 0, 0, 0

        start_time = time.time()

        try:
            messages = [{"role": "user", "content": prompt}]

            # Add JSON schema instruction if response_schema provided
            if response_schema:
                schema_json = json.dumps(response_schema.model_json_schema(), indent=2)
                system = f"{system}\n\nRespond with valid JSON matching this schema:\n{schema_json}"

            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system if system else None,
                messages=messages,
            )

            latency_ms = int((time.time() - start_time) * 1000)
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            content = response.content[0].text

            # Parse structured output if schema provided
            if response_schema:
                try:
                    # Extract JSON from response (handle markdown code blocks)
                    json_str = content
                    if "```json" in content:
                        json_str = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        json_str = content.split("```")[1].split("```")[0]

                    parsed = response_schema.model_validate_json(json_str.strip())
                    return parsed, input_tokens, output_tokens, latency_ms
                except Exception as e:
                    logger.error(f"Failed to parse structured output: {e}")
                    logger.debug(f"Raw response: {content}")
                    return None, input_tokens, output_tokens, latency_ms

            return content, input_tokens, output_tokens, latency_ms

        except anthropic.APIError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Anthropic API error: {e}")
            return None, 0, 0, latency_ms
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"LLM client error: {e}")
            return None, 0, 0, latency_ms


# Singleton instance
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get the global LLM client instance."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
