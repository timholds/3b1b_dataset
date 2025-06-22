# 3Blue1Brown Dataset Pipeline Scripts

This directory contains the core scripts for building the 3Blue1Brown dataset, including video matching, code cleaning, ManimGL to ManimCE conversion, and video rendering.

## 🚀 Quick Start

```bash
# Run the complete pipeline for a year
python scripts/build_dataset_pipeline.py --year 2015

# Process with video rendering
python scripts/build_dataset_pipeline.py --year 2015 --render

# Quick test with limited rendering
python scripts/build_dataset_pipeline.py --year 2015 --render-preview
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
2. **`clean_matched_code.py`** - Code cleaning and import inlining  
3. **`convert_manimgl_to_manimce.py`** - ManimGL to ManimCE converter
4. **`render_videos.py`** - Video rendering from ManimCE code

### Supporting Scripts
- **`manimce_conversion_utils.py`** - Utility functions for code conversion
- **`manimce_characters.py`** - Pi Creature replacements for ManimCE
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
   └─> output/v5/{year}/*/matches.json

2. CLEANING: Inline imports and create single files
   └─> output/v5/{year}/*/cleaned_code.py

3. CONVERSION: Convert ManimGL to ManimCE
   └─> output/v5/{year}/*/manimce_code.py

4. RENDERING: Render videos (optional)
   └─> output/rendered_videos/{year}/*/*.mp4
```

## 📋 Common Commands

### Process Everything
```bash
# Default: match, clean, convert (no rendering)
python scripts/build_dataset_pipeline.py --year 2015

# With rendering
python scripts/build_dataset_pipeline.py --year 2015 --render

# Quick preview (5 videos, 2 scenes each)
python scripts/build_dataset_pipeline.py --year 2015 --render-preview
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
├── output/
│   ├── v5/{year}/                      # Matched and cleaned code
│   │   └── {video-name}/
│   │       ├── matches.json            # Matching results
│   │       ├── cleaned_code.py         # Inlined imports
│   │       └── manimce_code.py         # Converted code
│   ├── rendered_videos/{year}/         # Rendered videos
│   ├── matching_summary_{year}.json    # Matching statistics
│   ├── cleaning_summary_{year}.json    # Cleaning statistics
│   └── pipeline_report_{year}.txt      # Full pipeline report
└── data/
    ├── youtube_metadata/               # Video mappings
    └── youtube_transcripts/            # Fetched transcripts
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

### Debug Options
- Add `--verbose` for detailed logging
- Check logs in `output/pipeline_logs/`
- Individual stage logs in respective output directories

## 📚 Requirements

- Python 3.8+
- ManimCE (for rendering)
- youtube-transcript-api (for transcript fetching)
- Other dependencies in requirements.txt