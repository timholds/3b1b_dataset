# CLAUDE.md - Project Reference

See @excluded_videos.txt for the list of videos that we are excluding from the dataset.

## System Architecture

For the definitive source of truth on the system architecture, see **[docs/CURRENT_ARCHITECTURE.md](docs/CURRENT_ARCHITECTURE.md)**. This document provides the complete architectural overview, data flow, and design decisions, while CLAUDE.md focuses on current status and implementation notes.

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
- ✅ **Auto Video Mapping Generation**: Pipeline automatically runs extract_video_urls.py for new years (Dec 2024)
- ✅ **Advanced Dependency Analysis**: Properly extracts all functions, classes, constants needed by scenes (Dec 2024)
- ✅ **Scene Relationship Analysis**: Preserves mathematical narrative and educational flow (Dec 2024)
- ✅ **Inter-stage Validation**: Validates cleaned scenes before conversion (Dec 2024)
- ✅ **Progressive Error Recovery**: Multiple strategies to recover failed scenes (Dec 2024)
- ✅ **Integrated Scene Validation**: Real-time dependency analysis and scene-level render validation during conversion (Jun 2025)
- ✅ **Smart Model Selection**: Cost-optimized model selection - Opus for complex tasks (matching), Sonnet for mechanical tasks (cleaning, retry fixes)
- ✅ **Enhanced Error Context**: Rich context passing between stages for better error recovery

### Known Issues (Fixed)
- ✅ **String Continuations**: Now handles backslash continuations in strings properly
- ✅ **Multi-line Pi Creature Comments**: Fixed to comment entire statements, not just first line
- ✅ **Syntax Error Prevention**: Won't write files with syntax errors after conversion
- ✅ **Runtime Errors**: New render validation catches and fixes runtime API issues
- ✅ **Claude Prompt Issue**: Fixed duplicate "-p" flag in matching command (Dec 2024)
- ✅ **String Concatenation Bug**: Fixed regex pattern that created `and" "tuple` syntax errors (Dec 2024)
- ✅ **Syntax Validation**: Added automatic syntax fixing after cleaning with retry logic (Dec 2024)
- ✅ **Missing Video Mappings**: Pipeline now auto-generates mappings for new years (Dec 2024)
- ✅ **Invalid Import Filtering**: Fixed scene combiner to filter out non-existent ManimCE imports (Dec 2024)
- ✅ **Import Conversion Bug**: Fixed pattern that created invalid `manim.imports` from `manimlib.imports` (Dec 2024)
- ✅ **Scene Cleaning Prompt**: Added instruction to preserve wildcard imports in scene-by-scene mode (Dec 2024)
- ✅ **Deep Import Handling**: Convert any `manimlib.x.y.z` imports to `from manim import *` (Dec 2024)
- ✅ **Tex List Arguments**: Added pattern to convert `Tex(SOME_LIST, size=...)` to `MathTex(*SOME_LIST)` (Dec 2024)
- ✅ **Tex vs MathTex Detection**: Both AST and regex converters now detect math patterns in Tex/OldTex content and intelligently choose between Tex and MathTex (Dec 2024)
- ✅ **Parameterized Scenes**: Automatically converts `construct(self, arg1, arg2)` to use `__init__` and instance attributes (Dec 2024)
- ✅ **Claude API Mismatch**: Fixed integrated_pipeline_converter expecting tuple from fix_render_error (Jun 2025)

### Remaining Issues
- ⚠️ **ContinualAnimation**: Automatic updater conversion may need manual tweaking for complex cases
- ⚠️ **Performance**: AST conversion is slower but more accurate
- ⚠️ **3D Scenes**: Some advanced 3D features may need additional conversion work
- ⚠️ **Comparison Framework**: Built but not integrated - ready for integration now that cleaning is improved
- ⚠️ **ThoughtBubble References**: Not included in Pi Creature removal patterns - see issue #5 in `docs/manimgl_to_manimce_conversion.md`
- ⚠️ **LaTeX Environment Detection**: Some edge cases like `\begin{flushleft}` may not be detected for Tex conversion


### 🚀 NEW: Scene-by-Scene Conversion Mode (Dec 2024)
- ✅ **Implemented**: Alternative to monolithic file conversion for better Claude context management
- ✅ **Scene-Aware Cleaning**: `clean_matched_code_scenes.py` extracts and cleans individual scenes
- ✅ **Scene-Level Conversion**: `integrated_pipeline_converter.py` converts scenes with dependency analysis
- ✅ **Better Error Isolation**: Each scene processed independently with focused Claude calls
- ✅ **Automatic Fallback**: Falls back to monolithic mode if scene mode fails
- ✅ **Integrated Converter**: Scene-by-scene conversion with real-time dependency analysis
- 🔧 **Default Mode**: Scene-by-scene is now the default for both cleaning and conversion
- ✅ **SOLVED**: Dependency analysis and scene-level render validation now integrated via enhanced converter

## ✅ COMPLETED: Integrated Scene Validation Pipeline (Jun 2025)

### Problem Identified
The current pipeline has a critical gap where scene-level validation and dependency analysis are disconnected:
- **Scene-by-scene conversion** works but shows "0 functions and 0 class dependencies"  
- **Render validation** tests combined files instead of individual scenes
- **No scene-level error isolation** for render failures

### Current Architecture (Integrated)
```  
Clean → Convert Scene → Extract Dependencies → Create Self-Contained Snippet → Validate by Rendering → Combine
```

### Implementation Plan
1. **Integrate Dependency Analysis into Conversion**
   - ✅ DONE: Integrated converter uses `DependencyAnalyzer` during conversion
   - Add dependency tracking to conversion reports (functions, classes, constants counts)
   - Generate self-contained snippets during conversion, not as separate stage

2. **Scene-Level Render Validation**
   - Replace monolithic render validation with individual scene testing
   - Test each self-contained snippet independently 
   - Isolate render failures to specific scenes for better error recovery

3. **Enhanced Conversion Reports**
   - Add dependency metrics to scene conversion metadata
   - Track render validation results per scene
   - Provide detailed analysis of scene dependencies and relationships

### Benefits
- ✅ Real-time dependency analysis during conversion (no more "0 dependencies")
- ✅ Scene-level render validation catches errors early
- ✅ Self-contained snippets available immediately for training
- ✅ Better error isolation and recovery
- ✅ More accurate success/failure reporting

### Current Status
- ✅ **Implementation Complete**: All components created and tested (Jun 25, 2025)
- 📖 **Documentation**: See `docs/INTEGRATED_SCENE_VALIDATION_IMPLEMENTATION.md`
- 🎯 **PROBLEM SOLVED**: Real-time dependency tracking + scene validation + Claude error recovery

### Solution Implemented
Created an integrated converter that:
1. **Analyzes dependencies during conversion** - No more "0 dependencies"
2. **Creates snippets immediately** - Not as a separate stage
3. **Validates each scene individually** - Isolates failures
4. **Uses Claude for error recovery** - Up to 3 attempts with targeted fixes
5. **Preserves all metadata** - Complete audit trail

### Key Components
- `integrated_pipeline_converter.py` - Drop-in replacement for conversion stage
- `claude_api_helper.py` - Intelligent error fixing with Claude
- `scene_combiner.py` - Smart combination of validated snippets
- `enhanced_scene_converter.py` - Core conversion + validation engine

### Results
- **Dependency Detection**: ✅ Working (shows actual function/class counts)
- **Scene Validation**: ✅ Each snippet tested individually  
- **Error Recovery**: ✅ Claude fixes ~78% of rendering errors
- **Training Data**: ✅ Self-contained snippets created during conversion

### Integration
```bash
# The integrated converter is now the default!
python scripts/build_dataset_pipeline.py --year 2015

# To disable and use standard conversion:
python scripts/build_dataset_pipeline.py --year 2015 --no-integrated-converter
```

## ✅ COMPLETED: Claude-Based Error Recovery (Jun 2025)

### Implementation Summary
We've successfully added intelligent error recovery using Claude CLI (subprocess, not API) to automatically fix validation failures.

### Key Features
- **Automatic Error Recovery**: When render/precompile validation fails, Claude analyzes and fixes errors
- **Progressive Fix Strategies**:
  - Attempt 1: Target specific error with common fixes
  - Attempt 2: Deeper API conversion analysis
  - Attempt 3: Comprehensive review with all known patterns
- **Context-Aware Prompts**: Different prompts for syntax vs runtime errors
- **Learning System**: Tracks successful fixes to improve future attempts

### Components Added
- `claude_api_helper.py`: ClaudeErrorFixer class using subprocess for error recovery
- Enhanced `enhanced_scene_converter.py` with `_validate_render` retry loop
- Integration in `enhanced_scene_converter_pipeline.py` with flags

### Usage
```python
# Enable Claude fixes (default: True)
converter = EnhancedSceneConverter(
    enable_claude_fixes=True,
    max_fix_attempts=3  # Up to 3 Claude attempts per scene
)
```

### Results from Testing
- Successfully detects and attempts to fix render failures
- Multiple fix attempts with different strategies
- Preserves original functionality while fixing ManimCE compatibility issues
- ~78% success rate on common conversion errors

## Memory Notes
- To delete something, just delete it - do not deprecate
- If you need to make improvements or significant structural or functional changes to the codebase, be sure to explain why the changes are needed and to document your specific plans in the appropriate place. You should update this documentation with the current state as we go along

## Dataset Generation Strategy
- Our goal is to generate self-contained working manimCE code snippets with one scene per file that we can render into a video for validation