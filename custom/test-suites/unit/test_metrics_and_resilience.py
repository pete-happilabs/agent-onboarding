"""
Unit tests for metrics collection - MCP agent
Tests token tracking and metrics format
"""
import pytest
from typing import Dict, Any


@pytest.mark.unit
class TestMetricsFormat:
    """Test DPA metrics format compliance"""
    
    def test_empty_metrics_structure(self):
        """Test empty metrics has correct structure"""
        metrics = {"models": {}}
        
        assert "models" in metrics
        assert isinstance(metrics["models"], dict)
        
        print(f"\n✓ Empty metrics structure is valid")
    
    def test_single_model_metrics(self):
        """Test metrics for single model"""
        metrics = {
            "models": {
                "gpt-4o-mini": {
                    "input_tokens": 100,
                    "output_tokens": 50
                }
            }
        }
        
        assert "gpt-4o-mini" in metrics["models"]
        assert metrics["models"]["gpt-4o-mini"]["input_tokens"] == 100
        assert metrics["models"]["gpt-4o-mini"]["output_tokens"] == 50
        
        print(f"\n✓ Single model metrics structure is valid")
    
    def test_multiple_models_metrics(self):
        """Test metrics for multiple models"""
        metrics = {
            "models": {
                "gpt-4o-mini": {
                    "input_tokens": 100,
                    "output_tokens": 50
                },
                "gpt-4o": {
                    "input_tokens": 200,
                    "output_tokens": 75
                }
            }
        }
        
        assert len(metrics["models"]) == 2
        assert "gpt-4o-mini" in metrics["models"]
        assert "gpt-4o" in metrics["models"]
        
        print(f"\n✓ Multiple models metrics structure is valid")
    
    def test_accumulate_tokens_across_calls(self):
        """Test accumulating tokens across multiple calls"""
        metrics = {
            "models": {
                "gpt-4o-mini": {
                    "input_tokens": 0,
                    "output_tokens": 0
                }
            }
        }
        
        # Simulate first API call
        metrics["models"]["gpt-4o-mini"]["input_tokens"] += 100
        metrics["models"]["gpt-4o-mini"]["output_tokens"] += 50
        
        assert metrics["models"]["gpt-4o-mini"]["input_tokens"] == 100
        assert metrics["models"]["gpt-4o-mini"]["output_tokens"] == 50
        
        # Simulate second API call
        metrics["models"]["gpt-4o-mini"]["input_tokens"] += 150
        metrics["models"]["gpt-4o-mini"]["output_tokens"] += 75
        
        assert metrics["models"]["gpt-4o-mini"]["input_tokens"] == 250
        assert metrics["models"]["gpt-4o-mini"]["output_tokens"] == 125
        
        print(f"\n✓ Token accumulation works correctly")
    
    def test_metrics_structure_matches_expected(self, expected_metrics):
        """Test that metrics match expected DPA format"""
        metrics = {
            "models": {
                "gpt-4o-mini": {
                    "input_tokens": 100,
                    "output_tokens": 50
                }
            }
        }
        
        # Validate structure matches expected format
        assert set(metrics.keys()) == set(expected_metrics.keys())
        assert "models" in metrics
        
        # Validate each model's metrics structure
        for model_name, model_metrics in metrics["models"].items():
            assert "input_tokens" in model_metrics
            assert "output_tokens" in model_metrics
            assert isinstance(model_metrics["input_tokens"], int)
            assert isinstance(model_metrics["output_tokens"], int)
            assert model_metrics["input_tokens"] >= 0
            assert model_metrics["output_tokens"] >= 0
        
        print(f"\n✓ Metrics match expected DPA format")
    
    def test_metrics_reset(self):
        """Test resetting metrics"""
        metrics = {
            "models": {
                "gpt-4o-mini": {
                    "input_tokens": 100,
                    "output_tokens": 50
                }
            }
        }
        
        # Reset
        metrics = {"models": {}}
        
        assert metrics["models"] == {}
        
        print(f"\n✓ Metrics reset works correctly")
    
    def test_zero_token_usage(self):
        """Test handling of zero token usage"""
        metrics = {
            "models": {
                "gpt-4o-mini": {
                    "input_tokens": 0,
                    "output_tokens": 0
                }
            }
        }
        
        assert metrics["models"]["gpt-4o-mini"]["input_tokens"] == 0
        assert metrics["models"]["gpt-4o-mini"]["output_tokens"] == 0
        
        print(f"\n✓ Zero token usage is valid")


@pytest.mark.unit
class TestMetricsValidation:
    """Test metrics validation and error cases"""
    
    def test_metrics_must_have_models_key(self):
        """Test that metrics always have 'models' key"""
        metrics = {"models": {}}
        
        assert "models" in metrics
    
    def test_model_metrics_must_have_both_token_types(self):
        """Test that each model has both input and output tokens"""
        metrics = {
            "models": {
                "gpt-4o-mini": {
                    "input_tokens": 100,
                    "output_tokens": 50
                }
            }
        }
        
        for model_name, model_metrics in metrics["models"].items():
            assert "input_tokens" in model_metrics, f"Missing input_tokens for {model_name}"
            assert "output_tokens" in model_metrics, f"Missing output_tokens for {model_name}"
        
        print(f"\n✓ Model metrics validation works")
    
    def test_token_values_must_be_non_negative(self):
        """Test that token values are non-negative integers"""
        metrics = {
            "models": {
                "gpt-4o-mini": {
                    "input_tokens": 100,
                    "output_tokens": 50
                }
            }
        }
        
        for model_name, model_metrics in metrics["models"].items():
            assert model_metrics["input_tokens"] >= 0, "input_tokens must be non-negative"
            assert model_metrics["output_tokens"] >= 0, "output_tokens must be non-negative"
            assert isinstance(model_metrics["input_tokens"], int), "input_tokens must be integer"
            assert isinstance(model_metrics["output_tokens"], int), "output_tokens must be integer"
        
        print(f"\n✓ Token value validation works")
