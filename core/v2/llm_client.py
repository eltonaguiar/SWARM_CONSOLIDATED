from __future__ import annotations
import logging
from typing import Optional
from ..transport import call_openai_compat

logger = logging.getLogger(__name__)

class ConsolidatedLLMClient:
    """
    V2 LLM Client refactored to use the consolidated transport layer.
    Instead of managing its own providers, it routes all calls through 
    the LiteLLM proxy via `core.transport`.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 60.0,
    ) -> None:
        self.timeout = timeout
        # In the consolidated world, the 'provider' is the proxy, 
        # and the 'model' is the LiteLLM alias.
        self._alias = provider or model or "free-mode-fast"

    @property
    def available(self) -> bool:
        """
        Always available as long as the proxy is reachable.
        Actual liveness is checked at call-time by the transport.
        """
        return True

    def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.2,
    ) -> Optional[str]:
        """
        Run a chat completion via the consolidated transport.
        """
        # Construct a combined prompt for the transport layer 
        # (which takes a single prompt string)
        full_prompt = prompt
        if system:
            full_prompt = f"System: {system}\n\nUser: {prompt}"

        try:
            # Route through the consolidated transport
            # We use 'openrouter' as the provider because our proxy is OpenAI-compat
            content, meta = call_openai_compat(
                provider="openrouter", 
                prompt=full_prompt,
                model_override=self._alias,
                sampling={
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }
            )
            return content
        except Exception as e:
            logger.warning(
                "ConsolidatedLLMClient[%s]: request failed: %s",
                self._alias, e
            )
            return None
