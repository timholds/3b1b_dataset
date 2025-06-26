# Claude Model Logging Update

## Summary
Updated the codebase to display which Claude model is being used in all logging statements.

## Changes Made

### 1. `clean_matched_code.py`
- Added import for `model_strategy`
- Modified `run_claude_cleaning` to:
  - Get the appropriate model using `get_model_for_task("clean_code", context={"file_size": file_size})`
  - Include model name in logging statements:
    - "Running Claude cleaning for scene 'X' in Y (model: sonnet, ...)"
    - "Claude cleaning completed for scene 'X' in Y (model: sonnet) in Z seconds"

### 2. `claude_match_videos.py`
- Added import for `model_strategy`
- Modified `run_claude_search` to:
  - Get the appropriate model using `get_model_for_task("match_videos")`
  - Include model name in logging: "🤖 Calling Claude (opus) for video: X"

### 3. `convert_manimgl_to_manimce.py`
- Added import for `model_strategy`
- Modified `run_claude_render_fix` to:
  - Get model based on attempt number context
  - Include model in logging: "Running Claude (opus/sonnet) to fix render errors..."
- Also updated the sanity check claude command to use model strategy

### 4. `claude_api_helper.py`
- Added import for `model_strategy`
- Modified `_run_claude_fix` to:
  - Determine model based on attempt number (extracted from prompt)
  - Include model in logging: "Running Claude (opus/sonnet) to fix render errors..."

## Model Strategy
Based on `model_strategy.py`, the system now uses:
- **Opus** for:
  - Video matching (complex reasoning)
  - Initial conversion attempts
  - First render fix attempt
  - Large files (>100KB)
- **Sonnet** for:
  - Code cleaning (mechanical task)
  - Simple syntax fixes
  - Precompile fixes
  - Retry render fix attempts (2nd and 3rd)

## Example Output
Now the pipeline will show output like:
```
Running Claude cleaning for scene 'ZoomInOnInterval' in inventing-math (model: sonnet, attempt 1/3, timeout: 600s, 1,042 chars)
Claude cleaning completed for scene 'ZoomInOnInterval' in inventing-math (model: sonnet) in 96.3 seconds
```

This makes it clear which model is being used for each operation, helping with cost tracking and optimization.