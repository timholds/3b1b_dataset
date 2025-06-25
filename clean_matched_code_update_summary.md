# Clean Matched Code Update Summary

## Changes Made

### File: `/Users/timholdsworth/code/3b1b_dataset/scripts/clean_matched_code.py`

1. **Model Change**: Updated Claude model from "opus" to "sonnet" on line 272
   - Changed: `claude_command = ["claude", "--dangerously-skip-permissions", "--model", "opus"]`
   - To: `claude_command = ["claude", "--dangerously-skip-permissions", "--model", "sonnet"]`

2. **Preserved Functionality**: All existing functionality remains intact:
   - Retry logic with exponential backoff
   - Timeout handling based on file sizes
   - Verbose logging
   - Checkpoint/resume capability
   - Syntax validation and fixing
   - Scene-by-scene mode support

## Impact

- The `clean_matched_code.py` script now uses the Sonnet model for all code cleaning operations
- The `clean_matched_code_scenes.py` script (which inherits from `CodeCleaner`) automatically uses Sonnet as well
- No changes to the API or usage - this is a drop-in replacement

## Note on claude_api_helper.py

While we initially considered using `claude_api_helper.py`, it turns out that:
- `ClaudeErrorFixer` is designed specifically for fixing render errors, not general code cleaning
- The existing subprocess approach in `clean_matched_code.py` is well-suited for the cleaning task
- We only needed to change the model parameter from "opus" to "sonnet"

## Other Files Using Opus

For reference, these files still use the opus model and may need updating depending on requirements:
- `claude_match_videos.py` - For video matching (may benefit from opus for large codebase searching)
- `convert_manimgl_to_manimce.py` - For conversion tasks
- `model_strategy.py` - Contains model selection strategy (could be updated if needed)