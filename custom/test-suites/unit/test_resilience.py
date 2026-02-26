# ============================================================================
# FILE: custom/test-suites/unit/test_resilience.py
# ============================================================================
"""
Unit tests for app/core/resilience.py and app/core/metrics.py

Covers:
- AsyncCircuitBreaker state machine (CLOSED → OPEN → HALF_OPEN → CLOSED)
- CircuitBreakerOpen exception properties
- with_timeout() success and failure paths
- validate_dost_event() all validation rules
- TalkMetrics add, accumulate, merge, filter
"""
import asyncio
import pytest

from app.core.resilience import (
    AsyncCircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
    with_timeout,
)
from app.core.protocol import validate_dost_event, DOST_SPEC_VERSION
from app.core.metrics import TalkMetrics


# =============================================================================
# Circuit Breaker — Initial State
# =============================================================================

class TestCircuitBreakerInitialState:

    @pytest.mark.unit
    def test_circuit_starts_closed(self):
        cb = AsyncCircuitBreaker(name="test", failure_threshold=3)
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.unit
    def test_circuit_starts_with_zero_failures(self):
        cb = AsyncCircuitBreaker(name="test", failure_threshold=3)
        assert cb._failure_count == 0

    @pytest.mark.unit
    def test_circuit_name_is_stored(self):
        cb = AsyncCircuitBreaker(name="my-service", failure_threshold=3)
        assert cb.name == "my-service"


# =============================================================================
# Circuit Breaker — OPEN State
# =============================================================================

class TestCircuitBreakerOpenState:

    @pytest.mark.unit
    async def test_circuit_opens_after_threshold_failures(self):
        cb = AsyncCircuitBreaker(name="test", failure_threshold=3)

        async def fail():
            raise RuntimeError("service down")

        for _ in range(3):
            with pytest.raises(RuntimeError):
                await cb.call(fail)

        assert cb.state == CircuitState.OPEN

    @pytest.mark.unit
    async def test_circuit_rejects_calls_when_open(self):
        cb = AsyncCircuitBreaker(name="test", failure_threshold=2)

        async def fail():
            raise RuntimeError("service down")

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.call(fail)

        with pytest.raises(CircuitBreakerOpen) as exc_info:
            await cb.call(fail)

        assert exc_info.value.circuit_name == "test"

    @pytest.mark.unit
    async def test_circuit_open_exception_message_contains_name(self):
        cb = AsyncCircuitBreaker(name="my-api", failure_threshold=1)

        async def fail():
            raise RuntimeError("down")

        with pytest.raises(RuntimeError):
            await cb.call(fail)

        with pytest.raises(CircuitBreakerOpen) as exc_info:
            await cb.call(fail)

        assert "my-api" in str(exc_info.value)

    @pytest.mark.unit
    async def test_circuit_does_not_open_before_threshold(self):
        cb = AsyncCircuitBreaker(name="test", failure_threshold=5)

        async def fail():
            raise RuntimeError("service down")

        for _ in range(4):  # one below threshold
            with pytest.raises(RuntimeError):
                await cb.call(fail)

        assert cb.state == CircuitState.CLOSED


# =============================================================================
# Circuit Breaker — Recovery (HALF_OPEN → CLOSED / OPEN)
# =============================================================================

class TestCircuitBreakerRecovery:

    @pytest.mark.unit
    async def test_circuit_transitions_to_half_open_after_timeout(self):
        cb = AsyncCircuitBreaker(
            name="test", failure_threshold=2, recovery_timeout=0.1
        )

        async def fail():
            raise RuntimeError("down")

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.call(fail)

        assert cb.state == CircuitState.OPEN

        await asyncio.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    @pytest.mark.unit
    async def test_circuit_closes_on_successful_probe(self):
        cb = AsyncCircuitBreaker(
            name="test", failure_threshold=2, recovery_timeout=0.1
        )

        async def fail():
            raise RuntimeError("down")

        async def succeed():
            return "ok"

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.call(fail)

        await asyncio.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        result = await cb.call(succeed)
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.unit
    async def test_circuit_reopens_on_failed_probe(self):
        cb = AsyncCircuitBreaker(
            name="test", failure_threshold=2, recovery_timeout=0.1
        )

        async def fail():
            raise RuntimeError("down")

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.call(fail)

        await asyncio.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        with pytest.raises(RuntimeError):
            await cb.call(fail)

        assert cb.state == CircuitState.OPEN

    @pytest.mark.unit
    async def test_success_before_threshold_resets_failure_count(self):
        cb = AsyncCircuitBreaker(name="test", failure_threshold=5)

        async def fail():
            raise RuntimeError("down")

        async def succeed():
            return "ok"

        for _ in range(3):
            with pytest.raises(RuntimeError):
                await cb.call(fail)

        assert cb._failure_count == 3

        await cb.call(succeed)
        assert cb._failure_count == 0
        assert cb.state == CircuitState.CLOSED


# =============================================================================
# Circuit Breaker — Passthrough
# =============================================================================

class TestCircuitBreakerPassthrough:

    @pytest.mark.unit
    async def test_successful_call_returns_result(self):
        cb = AsyncCircuitBreaker(name="test", failure_threshold=3)

        async def call():
            return {"status": "ok"}

        result = await cb.call(call)
        assert result == {"status": "ok"}

    @pytest.mark.unit
    async def test_call_passes_positional_args(self):
        cb = AsyncCircuitBreaker(name="test", failure_threshold=3)

        async def add(a, b):
            return a + b

        result = await cb.call(add, 2, 3)
        assert result == 5

    @pytest.mark.unit
    async def test_call_passes_keyword_args(self):
        cb = AsyncCircuitBreaker(name="test", failure_threshold=3)

        async def greet(name="world"):
            return f"hello {name}"

        result = await cb.call(greet, name="pete")
        assert result == "hello pete"


# =============================================================================
# with_timeout
# =============================================================================

class TestWithTimeout:

    @pytest.mark.unit
    async def test_fast_coroutine_completes_normally(self):
        async def fast():
            return "done"

        result = await with_timeout(fast(), timeout=5.0, operation="test")
        assert result == "done"

    @pytest.mark.unit
    async def test_slow_coroutine_raises_timeout_error(self):
        async def slow():
            await asyncio.sleep(10)

        with pytest.raises(TimeoutError):
            await with_timeout(slow(), timeout=0.1, operation="test_op")

    @pytest.mark.unit
    async def test_timeout_error_message_contains_operation_name(self):
        async def slow():
            await asyncio.sleep(10)

        with pytest.raises(TimeoutError) as exc_info:
            await with_timeout(slow(), timeout=0.1, operation="agent.run")

        assert "agent.run" in str(exc_info.value)

    @pytest.mark.unit
    async def test_timeout_error_message_contains_duration(self):
        async def slow():
            await asyncio.sleep(10)

        with pytest.raises(TimeoutError) as exc_info:
            await with_timeout(slow(), timeout=0.5, operation="op")

        assert "0.5" in str(exc_info.value)

    @pytest.mark.unit
    async def test_coroutine_return_value_preserved(self):
        async def compute():
            return {"result": 42}

        result = await with_timeout(compute(), timeout=5.0, operation="compute")
        assert result == {"result": 42}


# =============================================================================
# validate_dost_event
# =============================================================================

class TestValidateDostEvent:

    @pytest.mark.unit
    def test_valid_event_passes(self):
        event = {
            "version": DOST_SPEC_VERSION,
            "sourceEntityId": "hum.user.123",
            "sessionId": "123e4567-e89b-12d3-a456-426614174000",
            "message": {"text": {"data": "hello"}},
        }
        validate_dost_event(event)  # must not raise

    @pytest.mark.unit
    def test_rejects_non_dict(self):
        with pytest.raises(ValueError, match="must be a dict"):
            validate_dost_event("not a dict")

    @pytest.mark.unit
    def test_rejects_none(self):
        with pytest.raises(ValueError):
            validate_dost_event(None)

    @pytest.mark.unit
    def test_rejects_missing_source_entity_id(self):
        event = {
            "sessionId": "123e4567-e89b-12d3-a456-426614174000",
            "message": {"text": {"data": "hello"}},
        }
        with pytest.raises(ValueError, match="sourceEntityId"):
            validate_dost_event(event)

    @pytest.mark.unit
    def test_rejects_empty_source_entity_id(self):
        event = {
            "sourceEntityId": "",
            "sessionId": "123e4567-e89b-12d3-a456-426614174000",
            "message": {"text": {"data": "hello"}},
        }
        with pytest.raises(ValueError, match="sourceEntityId"):
            validate_dost_event(event)

    @pytest.mark.unit
    def test_rejects_missing_session_id(self):
        event = {
            "sourceEntityId": "hum.user.123",
            "message": {"text": {"data": "hello"}},
        }
        with pytest.raises(ValueError, match="sessionId"):
            validate_dost_event(event)

    @pytest.mark.unit
    def test_rejects_empty_session_id(self):
        event = {
            "sourceEntityId": "hum.user.123",
            "sessionId": "",
            "message": {"text": {"data": "hello"}},
        }
        with pytest.raises(ValueError, match="sessionId"):
            validate_dost_event(event)

    @pytest.mark.unit
    def test_version_mismatch_does_not_raise(self):
        event = {
            "version": "99.99.99",
            "sourceEntityId": "hum.user.123",
            "sessionId": "123e4567-e89b-12d3-a456-426614174000",
            "message": {"text": {"data": "hello"}},
        }
        validate_dost_event(event)  # warns only, must not raise

    @pytest.mark.unit
    def test_missing_version_field_passes(self):
        event = {
            "sourceEntityId": "hum.user.123",
            "sessionId": "123e4567-e89b-12d3-a456-426614174000",
            "message": {"text": {"data": "hello"}},
        }
        validate_dost_event(event)  # version is optional


# =============================================================================
# TalkMetrics (Custom only — MCP/Generic use raw dict metrics)
# =============================================================================

class TestTalkMetrics:

    @pytest.mark.unit
    def test_empty_metrics_returns_empty_models(self):
        m = TalkMetrics()
        assert m.to_dict() == {"models": {}}

    @pytest.mark.unit
    def test_add_llm_tracks_tokens(self):
        m = TalkMetrics()
        m.add_llm("gpt-4o-mini", input_tokens=100, output_tokens=50)
        result = m.to_dict()
        assert result["models"]["gpt-4o-mini"]["input_tokens"] == 100
        assert result["models"]["gpt-4o-mini"]["output_tokens"] == 50

    @pytest.mark.unit
    def test_add_llm_accumulates_across_calls(self):
        m = TalkMetrics()
        m.add_llm("gpt-4o-mini", input_tokens=100, output_tokens=50)
        m.add_llm("gpt-4o-mini", input_tokens=200, output_tokens=30)
        result = m.to_dict()
        assert result["models"]["gpt-4o-mini"]["input_tokens"] == 300
        assert result["models"]["gpt-4o-mini"]["output_tokens"] == 80

    @pytest.mark.unit
    def test_multiple_models_tracked_separately(self):
        m = TalkMetrics()
        m.add_llm("gpt-4o-mini", input_tokens=100, output_tokens=50)
        m.add_llm("gpt-4o", input_tokens=200, output_tokens=100)
        result = m.to_dict()
        assert "gpt-4o-mini" in result["models"]
        assert "gpt-4o" in result["models"]

    @pytest.mark.unit
    def test_to_dict_filters_zero_usage_models(self):
        m = TalkMetrics()
        m.add_llm("gpt-4o-mini", input_tokens=0, output_tokens=0)
        assert m.to_dict() == {"models": {}}

    @pytest.mark.unit
    def test_merge_combines_from_another_dict(self):
        m = TalkMetrics()
        m.add_llm("gpt-4o-mini", input_tokens=100, output_tokens=50)
        m.merge({"models": {"gpt-4o-mini": {"input_tokens": 50, "output_tokens": 25}}})
        result = m.to_dict()
        assert result["models"]["gpt-4o-mini"]["input_tokens"] == 150
        assert result["models"]["gpt-4o-mini"]["output_tokens"] == 75

    @pytest.mark.unit
    def test_add_embedding_tracked_separately(self):
        m = TalkMetrics()
        m.add_embedding(input_tokens=500)
        result = m.to_dict()
        assert "text-embedding-3-small" in result["models"]
        assert result["models"]["text-embedding-3-small"]["input_tokens"] == 500

    @pytest.mark.unit
    def test_cached_tokens_tracked_when_provided(self):
        m = TalkMetrics()
        m.add_llm("gpt-4o-mini", input_tokens=100, output_tokens=50, cached_tokens=30)
        result = m.to_dict()
        assert result["models"]["gpt-4o-mini"].get("cached_tokens") == 30
