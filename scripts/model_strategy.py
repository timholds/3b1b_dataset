#!/usr/bin/env python3
"""
Model selection strategy for different Claude tasks.

This module defines which model to use for each type of task based on
complexity and accuracy requirements.
"""

from typing import Dict, Optional

# Model selection based on task type and context
MODEL_STRATEGY = {
    # Complex reasoning tasks - need Opus
    "match_videos": "opus",                    # Searching large codebases
    "initial_conversion": "opus",              # First attempt at ManimGL->CE conversion
    "complex_render_fix": "opus",              # Fixing complex render errors
    
    # Mechanical/pattern-based tasks - Sonnet is fine
    "clean_code": "claude-3-5-sonnet-20241022",             # Code cleaning, import inlining
    "simple_syntax_fix": "claude-3-5-sonnet-20241022",      # Basic syntax errors
    "precompile_fix": "claude-3-5-sonnet-20241022",         # Import/attribute fixes
    "retry_render_fix": "claude-3-5-sonnet-20241022",       # Subsequent fix attempts
}

def get_model_for_task(task_type: str, context: Optional[Dict] = None) -> str:
    """
    Get the appropriate model for a given task.
    
    Args:
        task_type: Type of task (e.g., "clean_code", "match_videos")
        context: Optional context dict with additional info like:
            - attempt_number: Which retry attempt (1, 2, 3)
            - error_complexity: Simple/complex error assessment
            - file_size: Size of file being processed
            
    Returns:
        Model name to use (e.g., "opus", "sonnet")
    """
    # Handle render fix attempts - use Opus for first attempt, Sonnet for retries
    if task_type == "fix_render_error" and context:
        attempt = context.get("attempt_number", 1)
        if attempt == 1:
            return MODEL_STRATEGY.get("initial_conversion", "opus")
        else:
            return MODEL_STRATEGY.get("retry_render_fix", "claude-3-5-sonnet-20241022")
    
    # Large files might need Opus even for simple tasks
    if context and context.get("file_size", 0) > 100000:  # 100KB
        return "opus"
    
    # Default to strategy or Opus if unknown task
    return MODEL_STRATEGY.get(task_type, "opus")

def estimate_cost_savings(task_counts: Dict[str, int]) -> Dict[str, float]:
    """
    Estimate cost savings from using Sonnet where appropriate.
    
    Rough pricing (per 1M tokens):
    - Opus: $15 input, $75 output
    - Sonnet: $3 input, $15 output
    """
    # Rough estimates of tokens per task
    TOKENS_PER_TASK = {
        "clean_code": 15000,      # Medium-sized file cleaning
        "match_videos": 25000,    # Large context search
        "fix_render_error": 8000, # Focused error fix
    }
    
    savings = {
        "current_cost": 0,
        "optimized_cost": 0,
        "savings": 0
    }
    
    for task, count in task_counts.items():
        tokens = TOKENS_PER_TASK.get(task, 10000) * count
        
        # Current (all Opus)
        opus_cost = (tokens / 1_000_000) * 45  # Average of input/output
        savings["current_cost"] += opus_cost
        
        # Optimized
        model = get_model_for_task(task)
        if "sonnet" in model.lower():
            optimized_cost = (tokens / 1_000_000) * 9  # Sonnet average
        else:
            optimized_cost = opus_cost
        savings["optimized_cost"] += optimized_cost
    
    savings["savings"] = savings["current_cost"] - savings["optimized_cost"]
    savings["savings_percent"] = (savings["savings"] / savings["current_cost"] * 100) if savings["current_cost"] > 0 else 0
    
    return savings