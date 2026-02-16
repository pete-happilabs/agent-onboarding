# ============================================================================
# FILE: app/core/metrics.py
# ============================================================================
"""
Metrics - Track paid API usage.

Contains:
- TalkMetrics - Conversation/LLM metrics tracking
"""
from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class TalkMetrics:
    """
    Track ALL paid API usage during talk.

    All models tracked under single "models" dict.
    """

    # Per-model tracking
    models: Dict[str, Dict[str, int]] = field(default_factory=dict)

    def add(self, model: str, input_tokens: int, output_tokens: int = 0, cached_tokens: int = 0) -> None:
        """Add token usage for a model."""
        if not model:
            return

        if model not in self.models:
            self.models[model] = {"input_tokens": 0, "output_tokens": 0}

        self.models[model]["input_tokens"] += input_tokens
        self.models[model]["output_tokens"] += output_tokens

        # Only track cached_tokens for LLM models (not embeddings/vision)
        if cached_tokens > 0:
            if "cached_tokens" not in self.models[model]:
                self.models[model]["cached_tokens"] = 0
            self.models[model]["cached_tokens"] += cached_tokens

    # Convenience methods that route to add()
    def add_llm(self, model: str, input_tokens: int, output_tokens: int = 0, cached_tokens: int = 0) -> None:
        """Add LLM token usage with optional cached tokens."""
        self.add(model, input_tokens, output_tokens, cached_tokens)

    def add_embedding(self, input_tokens: int, model: str = "text-embedding-3-small") -> None:
        """Add embedding token usage."""
        self.add(model, input_tokens, 0)

    def add_vision(self, input_tokens: int, output_tokens: int, model: str = "gpt-4o") -> None:
        """Add vision token usage."""
        self.add(model, input_tokens, output_tokens)

    def merge(self, other_metrics: Dict[str, Any]) -> None:
        """Merge metrics from another source."""
        other_models = other_metrics.get("models", {})
        for model, tokens in other_models.items():
            self.add(
                model,
                tokens.get("input_tokens", 0),
                tokens.get("output_tokens", 0)
            )

    def to_dict(self) -> Dict[str, Any]:
        """Return metrics dict with only used models."""
        # Filter out models with no usage
        used_models = {
            model: tokens
            for model, tokens in self.models.items()
            if tokens["input_tokens"] > 0 or tokens["output_tokens"] > 0
        }
        return {"models": used_models}
