# Validation Framework for Claude Video Matcher

This directory contains a validation framework to test the `claude_match_videos.py` script using known video-to-code mappings.

## Structure

- `validation_mappings.json` - Contains the ground truth mapping for test videos
- `test_results.json` - Generated after running tests, contains validation results
- `README.md` - This file

## Test Case

We use the "inventing-math" video from 2015 as our validation test case because:

1. **Clear correspondence**: The video transcript directly matches code elements
2. **Unique identifiers**: Contains specific mathematical expressions like "1 + 2 + 4 + 8 + ... = -1"  
3. **Multiple evidence points**: Has divergent sums, convergent sums, and p-adic metrics
4. **Well-structured code**: The `inventing_math.py` file has clear scene classes

## Running the Test

```bash
cd /Users/timholdsworth/code/3b1b_dataset
python scripts/test_claude_matcher.py
```

## Validation Criteria

The test checks for:

1. **File identification**: Does Claude find `inventing_math.py` as the primary file?
2. **Confidence score**: Is the confidence score >= 0.8? (Updated threshold)
3. **Evidence quality**: Are there at least 2 pieces of supporting evidence?
4. **Output creation**: Does Claude create the JSON output file at `output_v5/{year}/{video_id}/matches.json`?
5. **Cleaning phase**: For high confidence matches (>= 0.8), does Claude create `cleaned_code.py`?

## Expected Behavior

When the test runs successfully:

1. **Phase 1 - Matching**:
   - Claude reads the video transcript
   - Searches for matching code files in `data/videos/_2015/`
   - Identifies `inventing_math.py` based on matching content
   - Creates `output_v5/2015/inventing-math/matches.json`

2. **Phase 2 - Cleaning** (if confidence >= 0.8):
   - Claude reads the matched files
   - Consolidates code into a single script
   - Creates `output_v5/2015/inventing-math/cleaned_code.py`

3. The test script validates these results against expected values

## Interpreting Results

- ✅ **PASSED**: All validation criteria met
- ❌ **FAILED**: One or more criteria not met

Check `test_results.json` for detailed results including:
- Confidence scores
- Files identified
- Evidence count
- Any error messages