"""LLM client abstraction supporting multiple providers."""
import json
import httpx
from typing import Optional, Dict, Any, List
from anthropic import Anthropic

from .config import settings


class LLMClient:
    """
    Unified LLM client supporting Anthropic and OpenRouter.
    
    OpenRouter provides access to many models through an OpenAI-compatible API,
    which can be useful when Anthropic models are too restrictive for certain
    biosecurity-related analysis tasks.
    """
    
    def __init__(self):
        self.provider = settings.llm_provider
        self.model = settings.llm_model
        
        if self.provider == "anthropic":
            self.anthropic_client = Anthropic(api_key=settings.anthropic_api_key)
        elif self.provider == "openrouter":
            if not settings.openrouter_api_key:
                raise ValueError("OPENROUTER_API_KEY not set but llm_provider is 'openrouter'")
            self.http_client = httpx.Client(timeout=120.0)
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")
    
    def complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send a completion request to the configured LLM provider.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            system: Optional system prompt
            max_tokens: Maximum tokens in response
            json_schema: Optional JSON schema for structured output
            
        Returns:
            Dict with 'text' (response content), 'stop_reason', and 'raw_response'
        """
        if self.provider == "anthropic":
            return self._anthropic_complete(messages, system, max_tokens, json_schema)
        else:
            return self._openrouter_complete(messages, system, max_tokens, json_schema)
    
    def _anthropic_complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str],
        max_tokens: int,
        json_schema: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Anthropic API completion with structured outputs."""
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        
        if system:
            kwargs["system"] = system
        
        # Use structured outputs if schema provided
        if json_schema:
            kwargs["extra_headers"] = {"anthropic-beta": "structured-outputs-2025-11-13"}
            kwargs["extra_body"] = {
                "output_format": {
                    "type": "json_schema",
                    "schema": json_schema
                }
            }
        
        response = self.anthropic_client.messages.create(**kwargs)
        
        text = ""
        if response.content:
            text = response.content[0].text
        
        return {
            "text": text,
            "stop_reason": response.stop_reason,
            "model": response.model,
            "raw_response": response,
        }
    
    def _openrouter_complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str],
        max_tokens: int,
        json_schema: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """OpenRouter API completion (OpenAI-compatible)."""
        # Prepend system message if provided
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)
        
        payload = {
            "model": self.model,
            "messages": all_messages,
            "max_tokens": max_tokens,
        }
        
        # Add JSON mode if schema provided
        # OpenRouter supports response_format for JSON
        if json_schema:
            payload["response_format"] = {"type": "json_object"}
            # Add schema hint to the last message
            schema_hint = f"\n\nRespond with valid JSON matching this schema:\n```json\n{json.dumps(json_schema, indent=2)}\n```"
            if all_messages:
                all_messages[-1]["content"] += schema_hint
        
        response = self.http_client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "HTTP-Referer": "https://github.com/litmus-biosecurity",
                "X-Title": "Litmus Biosecurity Monitor",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        
        text = ""
        stop_reason = "stop"
        if data.get("choices"):
            choice = data["choices"][0]
            text = choice.get("message", {}).get("content", "")
            stop_reason = choice.get("finish_reason", "stop")
        
        return {
            "text": text,
            "stop_reason": stop_reason,
            "model": data.get("model", self.model),
            "raw_response": data,
        }


# Global client instance
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create the global LLM client."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client

