# CLAUDE.md - Project Reference

See @excluded_videos.txt for the list of videos that we are excluding from the dataset.

## 🚀 Quick Status

### What Works
- ✅ **Import Inlining (v5)**: 100% success rate - properly orders imports and inlined code
- ✅ **Matching**: v4 script successfully matches videos to code with good accuracy
- ✅ **Pi Creature Handling**: Cleanly commented out instead of broken replacements
- ✅ **Video Rendering**: Optional rendering stage works with ManimCE code

### Known Issues
- ⚠️ **ManimCE Conversion**: Basic replacements only - many API differences remain unhandled
- ⚠️ **Old Classes**: `OldTex`, `OldTexText`, `Mobject1D`, etc. still referenced after conversion
- ⚠️ **Import Statements**: Doesn't update ManimGL imports to unified `from manim import *`

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
```

**Note**: Rendering is opt-in rather than opt-out, which makes sense since rendering is slow and you don't always need it!

## 📁 Main Scripts Reference

| Script | Purpose | Key Options |
|--------|---------|------------|
| `build_dataset_pipeline.py` | Orchestrates full pipeline | `--year`, `--render`, `--render-preview`, `--force-*`, `--video` |
| `match_videos_to_code_v4.py` | Matches videos to code, inlines imports | Used by pipeline |
| `convert_manimgl_to_manimce.py` | Basic ManimGL→ManimCE conversion | Used by pipeline |
| `render_videos.py` | Renders ManimCE code to videos | `--year`, `--video`, `--limit` |

## 🏗️ Pipeline Flow

```
1. MATCHING: match_videos_to_code_v4.py
   ↓ (creates matched_videos/year/)
2. CLEANING: (inline imports, create single files)
   ↓ (creates cleaned_code/year/)  
3. CONVERSION: convert_manimgl_to_manimce.py
   ↓ (creates manimce_conversions/year/)
4. RENDERING: render_videos.py (optional)
   ↓ (creates rendered_videos/year/)
```

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

## 📚 Key Documentation

Essential docs (high quality):
- `docs/IMPORT_INLINING.md` - Detailed import inlining process
- `docs/RENDERING.md` - Video rendering functionality  
- `docs/manimgl_to_manimce_conversion.md` - Conversion process details

Other docs in `docs/` folder are mixed quality (some from LLM sessions). Treat with skepticism.

## 🗂️ Project Structure

```
3b1b_dataset/
├── scripts/                    # All main scripts
├── matched_videos/{year}/      # Raw matched video→code mappings
├── cleaned_code/{year}/        # Single files with inlined imports
├── manimce_conversions/{year}/ # Converted ManimCE code
├── rendered_videos/{year}/     # Optional rendered videos
├── docs/                       # Mixed documentation
└── excluded_videos.txt         # Videos to skip
```

## ⚠️ Important Notes

- Never commit unless explicitly asked by the user
- Do not deprecate software - fix it or migrate contents then delete
- Focus on defensive security tasks only
- Never create docs unless requested

## 🎯 Current Priorities

1. **ManimCE Conversion**: Needs improvement beyond basic text replacements
2. **Extend to Other Years**: Currently focused on 2015, need 2016-2024
3. **Quality Validation**: Run full test suite on converted code

## 🏃 Quick Wins - Test Everything Works

```bash
# Fastest way to verify the pipeline works (< 2 minutes):
python scripts/build_dataset_pipeline.py --year 2015 --match-only

# If that works, test with ONE video render (< 5 minutes):
python scripts/build_dataset_pipeline.py --year 2015 --render --render-limit 1 --render-scenes-limit 1

# Check the outputs exist:
ls -la matched_videos/2015/ | head -5  # Should see video folders
ls -la rendered_videos/2015/ | head -5  # Should see .mp4 files (if rendered)
```