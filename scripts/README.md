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
2. **`clean_matched_code.py`** - Code cleaning and import inlining (monolithic mode)
3. **`clean_matched_code_scenes.py`** - Scene-aware cleaning with dependency analysis ✨
4. **`integrated_pipeline_converter.py`** - Integrated ManimCE converter with dependency analysis ✨
5. **`render_videos.py`** - Video rendering from ManimCE code

### Supporting Scripts
- **`manimce_conversion_utils.py`** - Utility functions for code conversion
- **`manimce_characters.py`** - Pi Creature replacements for ManimCE
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

2. CLEANING: Scene-aware cleaning with dependency analysis
   ├─> outputs/{year}/*/cleaned_scenes/*.py (individual scenes)
   └─> outputs/{year}/*/cleaned_code.py (combined file)

3. CONVERSION: Scene-level ManimGL to ManimCE conversion
   ├─> outputs/{year}/*/manimce_scenes/*.py (individual scenes)
   └─> outputs/{year}/*/manimce_code.py (combined file)

4. RENDERING: Render videos (optional)
   └─> outputs/{year}/*/rendered_videos/*.mp4

```

## 📋 Common Commands

### Process Everything
```bash
# Default: match, clean, convert (no rendering) - uses scene mode
python scripts/build_dataset_pipeline.py --year 2015

# With rendering
python scripts/build_dataset_pipeline.py --year 2015 --render

# Quick preview (5 videos, 2 scenes each)
python scripts/build_dataset_pipeline.py --year 2015 --render-preview

# Use monolithic mode for simple files
python scripts/build_dataset_pipeline.py --year 2015 --cleaning-mode monolithic --conversion-mode monolithic
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
    │       ├── matches.json              # Matching results
    │       ├── cleaned_code.py           # Combined cleaned code
    │       ├── cleaned_scenes/           # Individual cleaned scenes ✨
    │       │   └── *.py
    │       ├── manimce_code.py           # Combined converted code
    │       ├── manimce_scenes/           # Individual converted scenes ✨
    │       │   └── *.py
    │       ├── rendered_videos/          # Rendered videos
    │       │   └── *.mp4
    │       ├── snippets/                 # Self-contained scenes (created during conversion)
    │       │   └── *.py
    │       ├── logs.json                 # Processing logs
    │       └── scene_validation_report.txt # Validation report ✨
    ├── logs/
    │   ├── pipeline_history.jsonl        # Consolidated history
    │   ├── scene_validation_summary_{year}.json ✨
    │   └── cleaning/                     # Cleaning logs
    ├── pipeline_report_{year}_latest.json
    └── pipeline_report_{year}.txt
```

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