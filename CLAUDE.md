# CLAUDE.md - Project Reference

See @excluded_videos.txt for the list of videos that we are excluding from the dataset.

## 🚀 Quick Status

### What Works
- ✅ **Import Inlining (v5)**: 100% success rate - properly orders imports and inlined code
- ✅ **Matching**: v4 script successfully matches videos to code with good accuracy
- ✅ **Pi Creature Handling**: Cleanly commented out instead of broken replacements
- ✅ **Video Rendering**: Optional rendering stage works with ManimCE code
- ✅ **Render Validation**: Conversion now tests rendering and fixes errors with Claude
- ✅ **AST-Based Conversion**: New advanced converter uses Python AST for context-aware transformations
- ✅ **Pre-compile Validation**: Static analysis catches errors before expensive render attempts
- ✅ **Automatic Fixes**: Common validation errors are fixed automatically during conversion
- ✅ **Custom Animations**: FlipThroughNumbers and DelayByOrder implemented for ManimGL compatibility
- ✅ **Enhanced Scene Classes**: GraphScene, NumberLineScene, and RearrangeEquation fully functional
- ✅ **Extended Color Support**: All ManimGL color variants (BLUE_A-E, etc.) mapped to ManimCE
- ✅ **Path Functions**: clockwise_path, counterclockwise_path, and straight_path available
- ✅ **Automatic Imports**: Custom animations and utilities imported automatically when detected

### Known Issues (Fixed)
- ✅ **String Continuations**: Now handles backslash continuations in strings properly
- ✅ **Multi-line Pi Creature Comments**: Fixed to comment entire statements, not just first line
- ✅ **Syntax Error Prevention**: Won't write files with syntax errors after conversion
- ✅ **Runtime Errors**: New render validation catches and fixes runtime API issues
- ✅ **Claude Prompt Issue**: Fixed duplicate "-p" flag in matching command (Dec 2024)
- ✅ **String Concatenation Bug**: Fixed regex pattern that created `and" "tuple` syntax errors (Dec 2024)
- ✅ **Syntax Validation**: Added automatic syntax fixing after cleaning with retry logic (Dec 2024)

### Remaining Issues
- ⚠️ **ContinualAnimation**: Automatic updater conversion may need manual tweaking for complex cases
- ⚠️ **Performance**: AST conversion is slower but more accurate
- ⚠️ **3D Scenes**: Some advanced 3D features may need additional conversion work
- ⚠️ **Comparison Framework**: Built but not integrated - waiting for cleaning stage fixes (see docs/COMPARISON_FRAMEWORK.md)

### Next Step: Training Snippet Extraction
- 🎯 **Scene Dependencies**: Scenes currently share code and cannot run independently
- 📋 **Plan Ready**: See `docs/TRAINING_SNIPPETS_PLAN.md` for detailed extraction strategy
- 🔧 **Implementation Needed**: Create `extract_training_snippets.py` to make self-contained scenes

## 📋 Common Commands

### Most Common Commands

```bash
# Process everything WITHOUT rendering (default, fastest)
python scripts/build_dataset_pipeline.py --year 2015

# Process everything WITH rendering
python scripts/build_dataset_pipeline.py --year 2015 --render

# Quick test: render just 5 videos, 2 scenes each
python scripts/build_dataset_pipeline.py --year 2015 --render-preview

# Process specific videos only
python scripts/build_dataset_pipeline.py --year 2015 --video inventing-math
python scripts/build_dataset_pipeline.py --year 2015 --video inventing-math --video moser --render
```

### 📹 Rendering-Specific Commands

```bash
# ONLY render (skip matching, cleaning, conversion)
python scripts/build_dataset_pipeline.py --year 2015 --render-only

# Render with limits
python scripts/build_dataset_pipeline.py --year 2015 --render --render-limit 10 --render-scenes-limit 2

# High quality rendering (1080p instead of 480p)
python scripts/build_dataset_pipeline.py --year 2015 --render --render-quality production

# Render a specific video
python scripts/render_videos.py --year 2015 --video "inventing-math"
```

### 🔧 Other Pipeline Options

```bash
# Run only matching
python scripts/build_dataset_pipeline.py --year 2015 --match-only

# Run only cleaning
python scripts/build_dataset_pipeline.py --year 2015 --clean-only

# Run only conversion
python scripts/build_dataset_pipeline.py --year 2015 --convert-only

# Force re-processing
python scripts/build_dataset_pipeline.py --year 2015 --force-clean --force-convert

# Extract training snippets (FUTURE - see docs/TRAINING_SNIPPETS_PLAN.md)
python scripts/build_dataset_pipeline.py --year 2015 --extract-snippets
```

### 🔍 Conversion Stage Options (NEW!)

```bash
# Run conversion with render validation (default behavior)
python scripts/build_dataset_pipeline.py --year 2015 --convert-only

# Disable render validation (not recommended, but faster)
python scripts/build_dataset_pipeline.py --year 2015 --convert-only --no-render-validation

# Increase fix attempts for stubborn render errors
python scripts/build_dataset_pipeline.py --year 2015 --convert-only --render-max-attempts 5

# Use basic converter instead of advanced AST converter (faster but less accurate)
python scripts/build_dataset_pipeline.py --year 2015 --convert-only --use-basic-converter

# Run with pre-compile validation only (no rendering)
python scripts/build_dataset_pipeline.py --year 2015 --convert-only --precompile-only

# Disable automatic fixes during pre-compile validation
python scripts/build_dataset_pipeline.py --year 2015 --convert-only --no-auto-fix

# Disable pre-compile validation entirely (not recommended)
python scripts/build_dataset_pipeline.py --year 2015 --convert-only --no-precompile-validation
```

### 🔄 Cleaning Stage Options

```bash
# Handle large files that timeout (double all timeouts)
python scripts/build_dataset_pipeline.py --year 2015 --timeout-multiplier 2.0

# Increase retry attempts for unreliable systems
python scripts/build_dataset_pipeline.py --year 2015 --max-retries 5

# Clear checkpoint to restart interrupted cleaning from beginning
python scripts/clean_matched_code.py --year 2015 --clear-checkpoint

# Disable checkpoint resume (always start from beginning)
python scripts/clean_matched_code.py --year 2015 --no-resume
```

### 📊 Logging and History

```bash
# View pipeline run history
python scripts/view_pipeline_history.py           # Show all runs
python scripts/view_pipeline_history.py --last 10  # Show last 10 runs
python scripts/view_pipeline_history.py --detail 5 # Show details of run #5
python scripts/view_pipeline_history.py --stats    # Show overall statistics
python scripts/view_pipeline_history.py --days 7   # Show runs from last 7 days

# Migrate existing logs to new structure (one-time)
python scripts/migrate_logs.py
```

**Pipeline Behavior Without Flags:**
- Skips stages that have already completed (checks for summary files)
- Resumes cleaning from checkpoint if previous run was interrupted
- Skips individual videos marked as "already cleaned" in matches.json

**When to Use Each Flag:**
- `--force-*`: When you've made changes and need to regenerate everything
- `--clear-checkpoint`: When you want to retry failed videos from the beginning
- `--timeout-multiplier`: For slower systems or very large files
- `--no-resume`: To ignore checkpoints without clearing them

**Note**: Rendering is opt-in rather than opt-out, which makes sense since rendering is slow and you don't always need it!

## 📁 Main Scripts Reference

| Script | Purpose | Key Options |
|--------|---------|------------|
| `build_dataset_pipeline.py` | Orchestrates full pipeline | `--year`, `--render`, `--render-preview`, `--force-*`, `--video`, `--timeout-multiplier`, `--max-retries`, `--no-render-validation`, `--render-max-attempts`, `--use-basic-converter`, `--precompile-only`, `--no-precompile-validation`, `--no-auto-fix`, `--extract-snippets` (future) |
| `clean_matched_code.py` | Cleans and inlines matched code | `--year`, `--video`, `--no-resume`, `--clear-checkpoint`, `--timeout-multiplier`, `--max-retries` |
| `match_videos_to_code_v4.py` | Matches videos to code files | Used by pipeline |
| `convert_manimgl_to_manimce.py` | ManimGL→ManimCE conversion with render validation | Used by pipeline |
| `render_videos.py` | Renders ManimCE code to videos | `--year`, `--video`, `--limit` |
| `manimce_precompile_validator.py` | Pre-compile validation and automatic fixes | `--path`, `--output`, `--verbose` |
| `generate_comparison_report.py` | Compare YouTube vs rendered videos (NOT YET INTEGRATED) | `--year`, `--verbose` |
| `extract_training_snippets.py` | Extract self-contained scene snippets (FUTURE) | `--year`, `--video`, `--approach` |

## 🏗️ Pipeline Flow

```
1. MATCHING: match_videos_to_code_v4.py
   ↓ (saves to outputs/{year}/{video}/matches.json)
2. CLEANING: (inline imports, create single files)
   ↓ (saves to outputs/{year}/{video}/cleaned_code.py)  
3. CONVERSION: convert_manimgl_to_manimce.py
   ├─ AST-based analysis and transformation
   ├─ API mapping database lookups
   ├─ Pattern-based conversions
   ├─ Scene-specific implementations
   ├─ Pre-compile validation (syntax, imports, API usage)
   ├─ Automatic fixes for common errors
   ├─ Render validation (test render + fixes)
   └─ Creates compilable ManimCE code
   ↓ (saves to outputs/{year}/{video}/manimce_code.py)
4. RENDERING: render_videos.py (optional)
   ↓ (saves to outputs/{year}/{video}/rendered_videos/)
5. SNIPPET EXTRACTION: extract_training_snippets.py (FUTURE)
   ├─ Analyze scene dependencies
   ├─ Extract self-contained scenes
   └─ Validate snippet executability
   ↓ (saves to outputs/{year}/{video}/snippets/)
6. COMPARISON: generate_comparison_report.py (NOT YET INTEGRATED)
   ↓ (saves to outputs/comparison_reports/{year}/)
```

## 🔬 Render Validation (NEW!)

The conversion stage now includes automatic render validation:

1. **Test Render**: After conversion, tries to render the first scene
2. **Error Detection**: Captures specific runtime errors (not just syntax)
3. **Automatic Fixes**: Claude analyzes errors and fixes the code
4. **Retry Loop**: Attempts up to 3 times (configurable) to get working code

Benefits:
- ✅ Catches API mismatches that syntax checking misses
- ✅ Produces code that actually runs, not just parses
- ✅ Learns from specific errors rather than guessing
- ✅ Higher success rate for complex conversions

Control options:
- `--no-render-validation` - Skip validation (faster but less reliable)
- `--render-max-attempts N` - Set max fix attempts (default: 3)
- `-v` - See detailed progress during validation

## 🛠️ Development Practices

- Always use `uv pip` to handle any installations
- Run lint/typecheck after changes: `npm run lint`, `npm run typecheck` (ask user for exact commands)
- Write these commands to CLAUDE.md if provided

## 🔍 Troubleshooting Quick Reference

### Import Inlining Issues
- **Problem**: Import ordering errors → **Solution**: Use v5 scripts (already fixed)
- **Problem**: Missing imports → **Check**: Look for imports inside functions/CONFIG dicts

### ManimCE Conversion Issues
- **Problem**: `OldTex`/`OldTexText` errors → **Fix**: Replace with `Tex`/`Text` + raw strings
- **Problem**: Missing `from manim import *` → **Fix**: Add unified import at top
- **Problem**: Pi Creatures → **Status**: Already commented out properly

### Rendering Issues
- **Problem**: Scene not found → **Check**: Scene class names in the file
- **Problem**: Timeout → **Fix**: Use `--render-scenes-limit` to test fewer scenes

### Render Validation Issues (NEW!)
- **Problem**: Conversion fails render test → **Fix**: Automatic - Claude fixes errors up to 3 times
- **Problem**: Too many fix attempts → **Fix**: Use `--render-max-attempts 5` to increase
- **Problem**: Render validation too slow → **Fix**: Use `--no-render-validation` (not recommended)
- **Problem**: Want to see what's happening → **Fix**: Use `-v` for verbose output

## 📚 Key Documentation

Essential docs (high quality):
- `docs/IMPORT_INLINING.md` - Detailed import inlining process
- `docs/RENDERING.md` - Video rendering functionality  
- `docs/manimgl_to_manimce_conversion.md` - Conversion process details
- `docs/ERROR_COLLECTION_AND_PROMPTING.md` - Error pattern learning system
- `docs/PRECOMPILE_VALIDATION.md` - Pre-compile validation and automatic fixes
- `docs/TRAINING_SNIPPETS_PLAN.md` - Plan for extracting self-contained training snippets (NEW)
- `docs/COMPARISON_FRAMEWORK.md` - YouTube vs rendered video comparison (NOT YET INTEGRATED)

Other docs in `docs/` folder are mixed quality (some from LLM sessions). Treat with skepticism.

## 🗂️ Project Structure

```
3b1b_dataset/
├── scripts/                    # All main scripts
├── docs/                       # Mixed documentation
├── excluded_videos.txt         # Videos to skip
└── outputs/                    # All pipeline outputs
    ├── {year}/                 # Year-specific outputs
    │   └── {video-name}/       # Per-video directory containing:
    │       ├── matches.json    # Video-to-code matching results
    │       ├── cleaned_code.py # Inlined, cleaned ManimGL code
    │       ├── manimce_code.py # Converted ManimCE code
    │       ├── logs.json       # Processing logs for this video
    │       ├── rendered_videos/# Rendered .mp4 files (if rendered)
    │       └── snippets/       # Self-contained scene files (FUTURE)
    ├── comparison_reports/     # YouTube vs rendered comparisons (FUTURE)
    │   └── {year}/
    │       ├── comparison_dashboard.html
    │       ├── comparison_data.json
    │       └── comparison_summary.txt
    ├── logs/                   # Pipeline-level logging
    │   ├── archive/           # Old pipeline reports
    │   ├── cleaning/          # Cleaning stage logs
    │   ├── rendering_summary_{year}_{quality}.json
    │   └── pipeline_history.jsonl # Consolidated history
    ├── pipeline_report_{year}_latest.json  # Latest run report
    └── pipeline_report_{year}.txt         # Human-readable summary
```

## ⚠️ Important Notes

- Never commit unless explicitly asked by the user
- Do not deprecate software - fix it or migrate contents then delete
- Focus on defensive security tasks only
- Never create docs unless requested

## 🎯 Current Priorities

1. **Training Snippet Extraction**: Implement self-contained scene extraction for SFT dataset
2. **Render Validation Testing**: Test the new render validation on more videos
3. **Extend to Other Years**: Currently focused on 2015, need 2016-2024
4. **Performance Optimization**: AST converter is accurate but slower than regex

## 🏃 Quick Wins - Test Everything Works

```bash
# Fastest way to verify the pipeline works (< 2 minutes):
python scripts/build_dataset_pipeline.py --year 2015 --match-only

# If that works, test with ONE video render (< 5 minutes):
python scripts/build_dataset_pipeline.py --year 2015 --render --render-limit 1 --render-scenes-limit 1

# Check the outputs exist:
ls -la outputs/2015/ | head -5        # Should see video folders
ls outputs/2015/*/manimce_code.py    # Should see converted files
find outputs/2015 -name "*.mp4" | head -5  # Should see videos (if rendered)
```

## 🖥️ Environment Setup

- Use the source 3b1b-env/bin/activate for the environment