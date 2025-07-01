# 3Blue1Brown Dataset Pipeline Scripts

This directory contains the core scripts for building the 3Blue1Brown dataset, including video matching, code cleaning, ManimGL to ManimCE conversion, and video rendering.

## 🚀 Quick Start

```bash
# Run the complete pipeline for a year (uses scene-by-scene mode by default)
python scripts/build_dataset_pipeline.py --year 2015

# Process with video rendering
python scripts/build_dataset_pipeline.py --year 2015 --render

# Quick test with limited rendering
python scripts/build_dataset_pipeline.py --year 2015 --render-preview

# Force reprocess everything for a video
python scripts/build_dataset_pipeline.py --year 2015 --video inventing-math --force-clean --force-convert
```

## 📁 Core Scripts

### Pipeline Orchestrator
- **`build_dataset_pipeline.py`** - Main pipeline that coordinates all stages
  ```bash
  python build_dataset_pipeline.py --year 2015 [options]
  ```
  Options include: `--render`, `--force-clean`, `--force-convert`, `--skip-matching`, etc.

### Core Pipeline Components
1. **`claude_match_videos.py`** - AI-powered video-to-code matching
2. **`hybrid_cleaner.py`** - ✨ NEW: Intelligent hybrid cleaning (programmatic + Claude fallback)
3. **`simple_file_includer.py`** - ✨ ENHANCED: Simple file concatenation with import organization, duplicate removal, and syntax validation
4. **`programmatic_cleaner.py`** - ✨ NEW: Fast AST-based mechanical cleaning (80-90% of cases)
5. **`clean_matched_code.py`** - Legacy monolithic Claude-based cleaning
6. **`clean_matched_code_scenes.py`** - Legacy scene-aware Claude-based cleaning
7. **`integrated_pipeline_converter.py`** - Integrated ManimCE converter with dependency analysis ✨
8. **`render_videos.py`** - Video rendering from ManimCE code

### Supporting Scripts
- **`manimce_conversion_utils.py`** - Utility functions for code conversion
- **`manimce_characters.py`** - Pi Creature replacements for ManimCE
- **`manimce_constants_helpers.py`** - ✨ NEW: Constants and helper functions for ManimGL compatibility
- **`manimce_custom_animations.py`** - ✨ NEW: Custom animation implementations (DelayByOrder, ShimmerIn, etc.)
- **`validation_failure_recovery.py`** - ✨ NEW: Auto-recovery system for validation errors (90% success)
- **`scene_dependency_analyzer.py`** - Advanced AST-based dependency extraction ✨
- **`scene_relationship_analyzer.py`** - Analyzes relationships between scenes ✨
- **`scene_validator.py`** - Validates cleaned scenes before conversion ✨
- **`manimce_precompile_validator.py`** - Pre-compile validation with auto-fixes
- **`extract_video_urls.py`** - Extract YouTube metadata from captions
  ```bash
  python extract_video_urls.py --year 2015
  ```
- **`fetch_youtube_transcripts.py`** - Fetch transcripts from YouTube
  ```bash
  python fetch_youtube_transcripts.py --year 2015
  ```

### Test Scripts
- **`test_single_video_pipeline.py`** - Test pipeline on a single video
- **`test_video_rendering.py`** - Test video rendering functionality
- **`test_single_conversion.py`** - Test ManimGL to ManimCE conversion

## 🔄 Pipeline Flow

```
1. MATCHING: Match videos to code files using AI
   └─> outputs/{year}/*/matches.json

2. CLEANING: Hybrid cleaning (programmatic + Claude fallback)
   ├─> outputs/{year}/*/cleaned_scenes/*.py (individual ManimGL scenes)
   └─> outputs/{year}/*/monolith_manimgl.py (combined file)

3. CONVERSION: Scene-level ManimGL to ManimCE conversion
   ├─> outputs/{year}/*/validated_snippets/*.py (PRIMARY OUTPUT: self-contained snippets)
   ├─> outputs/{year}/*/validated_snippets/metadata.json (snippet metadata)
   └─> outputs/{year}/*/monolith_manimce.py (combined file for compatibility)

4. RENDERING: Render videos (optional)
   └─> outputs/{year}/*/rendered_videos/*.mp4 (renders from snippets preferentially)

```

## 📋 Common Commands

### Process Everything
```bash
# Default: match, clean, convert (no rendering) - uses hybrid cleaning
python scripts/build_dataset_pipeline.py --year 2015

# With rendering
python scripts/build_dataset_pipeline.py --year 2015 --render

# Quick preview (5 videos, 2 scenes each)
python scripts/build_dataset_pipeline.py --year 2015 --render-preview

# Use simple mode (DEFAULT - just concatenates files, no complex analysis)
python scripts/build_dataset_pipeline.py --year 2015 --cleaning-mode simple

# Force programmatic cleaning only (complex AST analysis, no Claude fallback)
python scripts/build_dataset_pipeline.py --year 2015 --cleaning-mode programmatic

# Use hybrid mode (programmatic first, Claude fallback - legacy complex mode)
python scripts/build_dataset_pipeline.py --year 2015 --cleaning-mode hybrid

# Force Claude cleaning only (skip programmatic)
python scripts/build_dataset_pipeline.py --year 2015 --cleaning-mode claude

# Legacy modes for compatibility
python scripts/build_dataset_pipeline.py --year 2015 --cleaning-mode scene --conversion-mode monolithic
```

### Process Specific Videos
```bash
# Single video
python scripts/build_dataset_pipeline.py --year 2015 --video inventing-math

# Multiple videos
python scripts/build_dataset_pipeline.py --year 2015 --video inventing-math --video moser
```

### Run Individual Stages
```bash
# Only matching
python scripts/build_dataset_pipeline.py --year 2015 --match-only

# Only cleaning
python scripts/build_dataset_pipeline.py --year 2015 --clean-only

# Only conversion
python scripts/build_dataset_pipeline.py --year 2015 --convert-only

# Only rendering
python scripts/build_dataset_pipeline.py --year 2015 --render-only
```

### Force Re-processing
```bash
# Force re-clean and re-convert
python scripts/build_dataset_pipeline.py --year 2015 --force-clean --force-convert
```

### Data Preparation
```bash
# Extract video URLs for a year
python scripts/extract_video_urls.py --year 2016

# Fetch YouTube transcripts
python scripts/fetch_youtube_transcripts.py --year 2016
```

## 🛠️ Testing Individual Components

### Test Single Video
```bash
python scripts/test_single_video_pipeline.py inventing-math
```

### Test Conversion
```bash
python scripts/test_single_conversion.py path/to/file.py
```

### Test Rendering
```bash
python scripts/test_video_rendering.py
```

## 📊 Output Structure

```
3b1b_dataset/
└── outputs/
    ├── {year}/
    │   └── {video-name}/
    │       ├── metadata.json              # Video metadata
    │       ├── monolith_manimgl.py       # Combined cleaned ManimGL code
    │       ├── cleaned_scenes/           # Individual cleaned ManimGL scenes ✨
    │       │   └── *.py
    │       ├── validated_snippets/       # [PRIMARY OUTPUT] Self-contained ManimCE snippets ✨NEW
    │       │   ├── Scene1.py            # Individual runnable scene
    │       │   ├── Scene2.py            # Individual runnable scene
    │       │   └── metadata.json        # Snippet metadata
    │       ├── monolith_manimce.py      # Combined ManimCE file (backwards compat)
    │       ├── conversion_results.json   # Conversion statistics
    │       ├── rendered_videos/          # Test renders for validation
    │       │   └── *.png
    │       └── logs.json                 # Processing logs
    ├── logs/
    │   ├── pipeline_history.jsonl        # Consolidated history
    │   ├── scene_validation_summary_{year}.json ✨
    │   └── cleaning/                     # Cleaning logs
    ├── pipeline_report_{year}_latest.json
    └── pipeline_report_{year}.txt
```

## 🧹 Cleaning Modes

The cleaning stage now supports multiple approaches for optimal speed and accuracy:

### Hybrid Mode (Default) ✨
- **Tries programmatic first**: Fast AST-based cleaning for 80-90% of cases
- **Claude fallback**: Only for complex scenarios that need AI reasoning
- **Best of both**: Speed + reliability for simple cases, intelligence for complex ones
- **Usage**: `--cleaning-mode hybrid` (default)

### Programmatic Mode ✨
- **Pure AST-based**: No Claude calls, purely deterministic
- **Fastest**: Processes files in seconds
- **Most reliable**: No AI variability
- **Limitations**: May fail on complex dependency scenarios
- **Usage**: `--cleaning-mode programmatic`

### Claude Mode
- **AI-powered**: Uses Claude for all cleaning decisions
- **Most flexible**: Handles any complexity level
- **Slower**: Requires API calls
- **Usage**: `--cleaning-mode claude`

### Legacy Modes
- **Scene mode**: Legacy scene-by-scene Claude cleaning
- **Monolithic mode**: Legacy single-file Claude cleaning  
- **Usage**: `--cleaning-mode scene` or `--cleaning-mode monolithic`

### When to Use Which Mode

| Mode | Use When | Speed | Accuracy | Complexity Handling |
|------|----------|-------|----------|-------------------|
| `hybrid` | **Default - recommended** ✅ Tested | Fast | High | Excellent |
| `programmatic` | Speed critical, simple files ✅ Tested | Fastest | High | Limited |
| `claude` | Complex files, educational flow matters | Slow | Variable | Excellent |
| `scene`/`monolithic` | Legacy compatibility needed | Slow | Variable | Good |

### ✅ Status: Implemented and Tested (Jun 2025)
The hybrid programmatic + Claude cleaning system has been successfully implemented and tested with real 3Blue1Brown data:
- **38 scenes** processed from `inventing_math.py`
- **48 dependencies** correctly detected and inlined
- **69KB output files** with valid syntax
- **Pipeline integration** verified and working

## ⚙️ Configuration

### Excluded Videos
Videos listed in `excluded-videos.txt` are automatically skipped during processing.

### Quality Thresholds
- Matching confidence: 0.8 (videos below this are skipped)
- Rendering quality: `preview` (480p) or `production` (1080p)

## 🐛 Troubleshooting

### Common Issues
1. **Import errors**: Check that all dependencies are installed
2. **Rendering timeouts**: Use `--render-scenes-limit` to test fewer scenes
3. **Memory issues**: Process fewer videos at once with `--video` filter
4. **Scene dependencies missing**: Check `scene_validation_report.txt` for details
5. **Cleaning failures**: Progressive recovery will attempt multiple strategies

### Debug Options
- Add `--verbose` or `-v` for detailed logging
- Check scene validation reports in video directories
- Review `outputs/logs/scene_validation_summary_{year}.json`
- Individual stage logs in respective output directories

### New Features (Dec 2024) ✨
- **Advanced Dependency Analysis**: Automatically extracts all required functions, classes, and constants
- **Scene Relationship Analysis**: Preserves mathematical flow between scenes
- **Inter-stage Validation**: Catches errors before expensive conversion
- **Progressive Error Recovery**: Multiple strategies to fix failed scenes

## 📚 Requirements

- Python 3.8+
- ManimCE (for rendering)
- youtube-transcript-api (for transcript fetching)
- Other dependencies in requirements.txt