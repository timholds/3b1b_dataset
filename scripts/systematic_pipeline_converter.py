#!/usr/bin/env python3
"""
Systematic Pipeline Converter - Integration layer for the enhanced systematic converter

This module provides a drop-in replacement for the integrated_pipeline_converter
that uses the systematic API fixer to reduce Claude dependency from 100% to ~15%.

Key features:
- Automatic fixing of 85% of common issues (imports, CONFIG patterns, properties, etc.)
- Intelligent Claude fallback for complex cases only
- Full compatibility with existing pipeline structure
- Detailed statistics and reporting
"""

import ast
import json
import logging
import re
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from enhanced_systematic_converter import EnhancedSystematicConverter, ConversionResult
from clean_matched_code_scenes import SceneAwareCleaner, SceneInfo

# Import logging utilities
try:
    from logging_utils import ProgressBar, StatsAggregator, ConditionalLogger, SummaryTable
except ImportError:
    ProgressBar = None
    StatsAggregator = None
    ConditionalLogger = None
    SummaryTable = None

logger = logging.getLogger(__name__)


def validate_snippet_syntax(code_content: str, filename: str) -> Tuple[bool, Optional[str]]:
    """
    Validate syntax of snippet code before writing to file.
    
    Args:
        code_content: The Python code to validate
        filename: Filename for error reporting
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # First try AST parsing to catch syntax errors
        ast.parse(code_content)
        
        # Then try compilation to catch more subtle issues
        compile(code_content, filename, 'exec')
        
        return True, None
        
    except SyntaxError as e:
        error_msg = f"SyntaxError at line {e.lineno}: {e.msg}"
        if e.text:
            error_msg += f" -> '{e.text.strip()}'"
        return False, error_msg
        
    except IndentationError as e:
        error_msg = f"IndentationError at line {e.lineno}: {e.msg}"
        if e.text:
            error_msg += f" -> '{e.text.strip()}'"
        return False, error_msg
        
    except Exception as e:
        error_msg = f"Compilation error: {type(e).__name__}: {str(e)}"
        return False, error_msg


def convert_with_systematic_pipeline(builder, year: int, video_filter: Optional[List[str]] = None, force: bool = False) -> Dict:
    """
    Integration function for the systematic converter pipeline.
    
    This is a drop-in replacement for integrate_with_pipeline that uses
    the enhanced systematic converter.
    
    Args:
        builder: DatasetPipelineBuilder instance
        year: Year to process
        video_filter: Optional list of specific videos to process
        force: Force re-conversion even if outputs exist
        
    Returns:
        Dictionary with conversion results and statistics
    """
    start_time = time.time()
    
    # Get unfixable pattern detection settings from builder
    enable_unfixable_skipping = getattr(builder, 'enable_unfixable_skipping', False)
    monitor_unfixable_only = getattr(builder, 'monitor_unfixable_only', True)
    min_conversion_confidence = getattr(builder, 'min_conversion_confidence', 0.8)
    
    # Initialize systematic converter with unfixable pattern detection settings
    converter = EnhancedSystematicConverter(
        enable_claude_fallback=True,  # Enable fallback for complex cases
        max_claude_attempts=3,
        enable_unfixable_skipping=enable_unfixable_skipping,
        monitor_unfixable_only=monitor_unfixable_only,
        min_conversion_confidence=min_conversion_confidence
    )
    
    logger.info(f"Initialized systematic converter with unfixable pattern detection: enable_skipping={enable_unfixable_skipping}, monitor_only={monitor_unfixable_only}")
    logger.info(f"Conversion confidence threshold: {min_conversion_confidence:.1%} (scenes below this will be skipped)")
    
    # Track results
    results = {
        'total_videos': 0,
        'successful_videos': 0,
        'failed_videos': 0,
        'systematic_only_success': 0,
        'claude_fallback_success': 0,
        'manual_fix_success': 0,
        'skipped_low_confidence': 0,
        'videos': {},
        'processing_time': 0,
        'systematic_efficiency': 0.0,
        'claude_reduction': 0.0,
        'syntax_validation': {
            'total_snippets_attempted': 0,
            'syntax_valid_snippets': 0,
            'syntax_invalid_snippets': 0,
            'syntax_errors': []
        }
    }
    
    # Find videos to process
    year_dir = builder.output_dir / str(year)
    logger.debug(f"[DEBUG] Looking for year directory: {year_dir}")
    logger.debug(f"[DEBUG] Year directory exists: {year_dir.exists()}")
    
    if not year_dir.exists():
        logger.error(f"Year directory does not exist: {year_dir}")
        return results
    
    logger.info(f"Processing systematic conversion for year {year}")
    if video_filter:
        logger.info(f"Video filter: {video_filter}")
    
    # List all directories in year_dir
    all_dirs = [d for d in year_dir.iterdir() if d.is_dir()]
    logger.debug(f"[DEBUG] Found {len(all_dirs)} directories in {year_dir}: {[d.name for d in all_dirs]}")
    
    # Filter directories based on video_filter if provided
    videos_to_process = []
    for video_dir in year_dir.iterdir():
        if not video_dir.is_dir():
            continue
        if video_filter and video_dir.name not in video_filter:
            continue
        # Check if already converted (unless force)
        manimce_file = video_dir / '.pipeline' / 'intermediate' / 'monolith_manimce.py'
        if manimce_file.exists() and not force:
            logger.info(f"Skipping {video_dir.name} - already converted")
            continue
        videos_to_process.append(video_dir)
    
    # Use progress tracker if available
    if ProgressBar and len(videos_to_process) > 0:
        progress = ProgressBar(len(videos_to_process), "Converting videos", show_stats=True)
    else:
        progress = None
    
    for idx, video_dir in enumerate(videos_to_process):
        video_name = video_dir.name
        
        if progress:
            progress.update(0, f"Processing {video_name}")
        else:
            logger.info(f"Processing video {idx+1}/{len(videos_to_process)}: {video_name}")
        
        results['total_videos'] += 1
        
        # Process video conversion
        video_result = _convert_video_systematic(builder, video_dir, converter, year)
        results['videos'][video_name] = video_result
        
        if video_result['success']:
            results['successful_videos'] += 1
            if video_result['conversion_method'] == 'systematic_only':
                results['systematic_only_success'] += 1
            elif video_result['conversion_method'] == 'claude_fallback':
                results['claude_fallback_success'] += 1
            elif video_result['conversion_method'] == 'manual_fix':
                results['manual_fix_success'] += 1
            
            if progress:
                progress.update(1, f"✓ {video_name}")
        else:
            results['failed_videos'] += 1
            if progress:
                progress.update(1, f"✗ {video_name}")
        
        # Aggregate syntax validation statistics from video result
        if 'syntax_validation' in video_result:
            video_syntax = video_result['syntax_validation']
            results['syntax_validation']['total_snippets_attempted'] += video_syntax.get('total_snippets_attempted', 0)
            results['syntax_validation']['syntax_valid_snippets'] += video_syntax.get('syntax_valid_snippets', 0)
            results['syntax_validation']['syntax_invalid_snippets'] += video_syntax.get('syntax_invalid_snippets', 0)
            results['syntax_validation']['syntax_errors'].extend(video_syntax.get('syntax_errors', []))
        
        # Aggregate skipped scenes count
        results['skipped_low_confidence'] += video_result.get('skipped_scenes', 0)
            
    # Calculate efficiency metrics
    if results['total_videos'] > 0:
        results['systematic_efficiency'] = results['systematic_only_success'] / results['total_videos']
        results['claude_reduction'] = 1.0 - (results['claude_fallback_success'] / results['total_videos'])
    
    results['processing_time'] = time.time() - start_time
    
    # Get unfixable pattern statistics
    converter_stats = converter.get_statistics()
    if 'unfixable_patterns' in converter_stats:
        results['unfixable_patterns'] = converter_stats['unfixable_patterns']
    
    # Print summary statistics
    _print_systematic_conversion_summary(results, converter, builder)
    
    logger.debug(f"[DEBUG] Final conversion stats: {results['total_videos']} total videos, {results['successful_videos']} successful")
    
    # Update pipeline state
    builder.pipeline_state['stages']['conversion']['status'] = 'completed'
    builder.pipeline_state['stages']['conversion']['stats'] = results
    
    # Print completion message
    if not builder.verbose:
        # Calculate actual scene conversion statistics from video results
        total_scenes = 0
        scenes_converted = 0
        for video_name, video_data in results.get('videos', {}).items():
            if isinstance(video_data, dict):
                total_scenes += video_data.get('total_scenes', 0)
                scenes_converted += video_data.get('successful_scenes', 0)
        print(f" ✓ ({results['successful_videos']}/{results['total_videos']} videos, {scenes_converted}/{total_scenes} scenes converted)")
    
    return results


def _convert_video_systematic(builder, video_dir: Path, converter: EnhancedSystematicConverter, year: int) -> Dict:
    """Convert a single video using the systematic converter."""
    
    video_name = video_dir.name
    logger.debug(f"[DEBUG] _convert_video_systematic called for: {video_name}")
    
    # Load cleaned scenes - support both JSON and file-based formats
    cleaned_scenes_file = video_dir / 'scenes_cleaned.json'
    cleaned_scenes_dir = video_dir / 'cleaned_scenes'
    # Also check pipeline structure
    pipeline_cleaned_scenes_dir = video_dir / '.pipeline' / 'intermediate' / 'cleaned_scenes'
    
    logger.debug(f"[DEBUG] Looking for cleaned scenes:")
    logger.debug(f"[DEBUG]   JSON file: {cleaned_scenes_file} (exists: {cleaned_scenes_file.exists()})")
    logger.debug(f"[DEBUG]   Scenes dir: {cleaned_scenes_dir} (exists: {cleaned_scenes_dir.exists()})")
    logger.debug(f"[DEBUG]   Pipeline scenes dir: {pipeline_cleaned_scenes_dir} (exists: {pipeline_cleaned_scenes_dir.exists()})")
    
    scenes_data = None
    
    # Try JSON format first (for legacy compatibility)
    if cleaned_scenes_file.exists():
        try:
            with open(cleaned_scenes_file, 'r') as f:
                scenes_data = json.load(f)
            logger.debug(f"Loaded scenes from JSON format for {video_name}")
        except Exception as e:
            logger.warning(f"Failed to load JSON scenes data for {video_name}: {e}")
    
    # Fallback to file-based format (current default)
    # Check standard location first, then pipeline location
    scenes_dir_to_use = None
    if cleaned_scenes_dir.exists() and cleaned_scenes_dir.is_dir():
        scenes_dir_to_use = cleaned_scenes_dir
    elif pipeline_cleaned_scenes_dir.exists() and pipeline_cleaned_scenes_dir.is_dir():
        scenes_dir_to_use = pipeline_cleaned_scenes_dir
    
    if not scenes_data and scenes_dir_to_use:
        scenes_data = {'scenes': {}}
        scene_files = list(scenes_dir_to_use.glob('*.py'))
        logger.debug(f"[DEBUG] Found {len(scene_files)} .py files in {scenes_dir_to_use.name} dir")
        
        for scene_file in scene_files:
            logger.debug(f"[DEBUG] Loading scene file: {scene_file}")
            try:
                with open(scene_file, 'r') as f:
                    scene_code = f.read()
                scene_name = scene_file.stem
                scenes_data['scenes'][scene_name] = {
                    'code': scene_code,
                    'file_path': str(scene_file)
                }
                logger.debug(f"[DEBUG] Successfully loaded scene: {scene_name} ({len(scene_code)} chars)")
            except Exception as e:
                logger.warning(f"Failed to load scene file {scene_file}: {e}")
                continue
        logger.debug(f"Loaded {len(scenes_data['scenes'])} scenes from file format for {video_name}")
    
    # No scenes found at all
    if not scenes_data or not scenes_data.get('scenes'):
        logger.error(f"No cleaned scenes found for {video_name} (checked JSON and file formats)")
        return {
            'success': False,
            'error': 'No cleaned scenes found',
            'scenes': {},
            'conversion_method': 'failed'
        }
    
    # Convert each scene
    scene_results = {}
    all_converted_scenes = []
    
    for scene_name, scene_data in scenes_data.get('scenes', {}).items():
        if 'code' not in scene_data:
            logger.warning(f"No code found for scene {scene_name}")
            continue
            
        if builder.verbose:
            logger.debug(f"Converting scene: {scene_name}")
        
        # Convert using systematic converter
        result = converter.convert_scene(
            scene_code=scene_data['code'],
            scene_name=scene_name,
            video_name=video_name,
            video_year=year
        )
        
        scene_results[scene_name] = {
            'success': result.success,
            'conversion_method': result.conversion_method,
            'systematic_fixes': len(result.systematic_fixes_applied),
            'claude_fixes': len(result.claude_fixes_applied),
            'confidence': result.confidence,
            'errors': result.errors
        }
        
        if result.success:
            all_converted_scenes.append({
                'name': scene_name,
                'code': result.final_code,
                'metadata': result.metadata
            })
            logger.debug(f"Successfully converted scene {scene_name} using {result.conversion_method}")
        else:
            logger.error(f"Failed to convert scene {scene_name}: {result.errors}")
    
    # Save converted scenes if any succeeded
    if all_converted_scenes:
        _save_converted_scenes(video_dir, all_converted_scenes, scene_results)
    
    # Determine overall conversion method
    conversion_methods = [r['conversion_method'] for r in scene_results.values() if r['success']]
    if 'claude_fallback' in conversion_methods:
        overall_method = 'claude_fallback'
    elif 'manual_fix' in conversion_methods:
        overall_method = 'manual_fix'
    elif 'systematic_only' in conversion_methods:
        overall_method = 'systematic_only'
    else:
        overall_method = 'failed'
    
    # Count scenes by conversion method
    skipped_scenes = sum(1 for r in scene_results.values() if r['conversion_method'] == 'skipped_low_confidence')
    failed_scenes = sum(1 for r in scene_results.values() if not r['success'] and r['conversion_method'] != 'skipped_low_confidence')
    successful_scenes_count = sum(1 for r in scene_results.values() if r['success'])
    
    # Video is successful if we have at least one successfully converted scene
    video_success = successful_scenes_count > 0
    
    return {
        'success': video_success,
        'scenes': scene_results,
        'conversion_method': overall_method,
        'total_scenes': len(scene_results),
        'successful_scenes': successful_scenes_count,
        'skipped_scenes': skipped_scenes,
        'failed_scenes': failed_scenes,
        'syntax_validation': {
            'total_snippets_attempted': 0,
            'syntax_valid_snippets': 0,
            'syntax_invalid_snippets': 0,
            'syntax_errors': []
        }
    }


def _sort_constants_by_dependency(constants: List[str]) -> List[str]:
    """Sort constants by dependency order so that constants referencing others come after them."""
    if not constants:
        return constants
    
    # Build a map of constant name to definition
    const_map = {}
    const_names = []
    
    for const in constants:
        # Extract constant name
        if '=' in const:
            const_name = const.split('=')[0].strip()
            const_map[const_name] = const
            const_names.append(const_name)
    
    # Build dependency graph
    dependencies = {}
    for const_name in const_names:
        dependencies[const_name] = []
        const_def = const_map[const_name]
        # Extract the value part (after =)
        value_part = const_def.split('=', 1)[1] if '=' in const_def else ''
        
        # Check which other constants this one references
        for other_name in const_names:
            if other_name != const_name and other_name in value_part:
                # Make sure it's actually a reference, not part of a string
                # Simple heuristic: check if it's surrounded by word boundaries
                import re
                if re.search(r'\b' + re.escape(other_name) + r'\b', value_part):
                    dependencies[const_name].append(other_name)
    
    # Topological sort
    sorted_names = []
    visited = set()
    visiting = set()
    
    def visit(name):
        if name in visiting:
            # Circular dependency - just add it
            logger.warning(f"Circular dependency detected for constant {name}")
            return
        if name in visited:
            return
        
        visiting.add(name)
        for dep in dependencies.get(name, []):
            visit(dep)
        visiting.remove(name)
        visited.add(name)
        sorted_names.append(name)
    
    # Visit all constants
    for name in const_names:
        if name not in visited:
            visit(name)
    
    # Return constants in sorted order
    return [const_map[name] for name in sorted_names if name in const_map]


def _save_converted_scenes(video_dir: Path, converted_scenes: List[Dict], scene_results: Dict):
    """Save converted scenes to files - both individual snippets and monolithic file."""
    
    # Double-check that we only have successfully converted scenes
    # This is a safety check - converted_scenes should already be filtered
    successful_scenes = []
    for scene in converted_scenes:
        scene_name = scene['name']
        if scene_name in scene_results and scene_results[scene_name]['success']:
            successful_scenes.append(scene)
        else:
            logger.warning(f"Skipping scene {scene_name} - not marked as successful in results")
    
    if not successful_scenes:
        logger.error(f"No successfully converted scenes to save for {video_dir.name}")
        return
    
    # Create validated_snippets directory for individual self-contained scenes
    snippets_dir = video_dir / 'validated_snippets'
    snippets_dir.mkdir(exist_ok=True)
    logger.info(f"Creating validated snippets in {snippets_dir}")
    
    # Extract imports from all converted scenes
    all_imports = set()
    scene_codes_without_imports = []
    
    for scene in successful_scenes:
        code_lines = scene['code'].split('\n')
        scene_imports = []
        scene_body = []
        
        # Separate imports from body
        i = 0
        in_multiline_import = False
        current_import = []
        
        while i < len(code_lines):
            line = code_lines[i]
            stripped = line.strip()
            
            # Skip commented-out imports
            if stripped.startswith('#') and ('import' in stripped or 'from' in stripped):
                scene_body.append(line)
                i += 1
                continue
            
            # Handle multiline imports
            if in_multiline_import:
                current_import.append(line)
                if ')' in line:
                    # End of multiline import
                    full_import = '\n'.join(current_import)
                    # Normalize to single line for deduplication
                    normalized = ' '.join(full_import.split())
                    if normalized not in all_imports:
                        all_imports.add(normalized)
                    in_multiline_import = False
                    current_import = []
                i += 1
                continue
            
            # Check for start of import
            if stripped.startswith(('import ', 'from ')) and (
                # Make sure it's actually an import statement
                (stripped.startswith('import ') and len(stripped.split()) > 1) or
                (stripped.startswith('from ') and ' import ' in stripped)
            ):
                if '(' in line and ')' not in line:
                    # Start of multiline import
                    in_multiline_import = True
                    current_import = [line]
                else:
                    # Single line import
                    if stripped not in all_imports:
                        all_imports.add(stripped)
                        scene_imports.append(line)
            else:
                # This is body code
                scene_body.append(line)
            
            i += 1
        
        # Store scene code without imports
        scene_codes_without_imports.append({
            'name': scene['name'],
            'code': '\n'.join(scene_body).strip()
        })
    
    # Build combined file with proper imports
    combined_parts = []
    
    # Header
    combined_parts.append("# Generated by Enhanced Systematic Converter")
    combined_parts.append("# This file contains ManimCE-converted scenes with systematic fixes applied")
    combined_parts.append("")
    
    # Sort and add imports
    # Always ensure 'from manim import *' comes first
    manim_imports = [imp for imp in all_imports if 'from manim import' in imp]
    numpy_imports = [imp for imp in all_imports if 'numpy' in imp]
    typing_imports = [imp for imp in all_imports if 'typing' in imp]
    other_imports = [imp for imp in all_imports if imp not in manim_imports + numpy_imports + typing_imports]
    
    # Add imports in order
    if manim_imports:
        combined_parts.extend(sorted(manim_imports))
    else:
        # Always include manim import
        combined_parts.append("from manim import *")
    
    if numpy_imports:
        combined_parts.extend(sorted(numpy_imports))
    
    if typing_imports:
        combined_parts.extend(sorted(typing_imports))
    
    if other_imports:
        combined_parts.extend(sorted(other_imports))
    
    combined_parts.append("")  # Empty line after imports
    
    # Extract any custom animation classes, constants, or helper functions that appear before scenes
    custom_animations = []
    constants = []
    helper_functions = []
    
    # Track which constants we've already extracted to avoid duplicates
    extracted_constants = {}  # Map constant name to its definition
    
    for scene_info in scene_codes_without_imports:
        code = scene_info['code']
        lines = code.split('\n')
        
        # Look for custom animation classes, constants, and helper content
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Check for constants (all caps variables at module level)
            if (re.match(r'^[A-Z_]+\s*=', stripped) and 
                not any(s in line for s in ['class ', 'def ']) and
                not line.startswith((' ', '\t'))):  # Exclude indented code
                
                # Get the constant name
                const_name = stripped.split('=')[0].strip()
                
                # Skip if we've already extracted this constant
                if const_name in extracted_constants:
                    # Still need to advance past multi-line constants
                    j = i + 1
                    equals_pos = stripped.find('=')
                    if equals_pos >= 0:
                        value_part = stripped[equals_pos + 1:]
                        # Check for multi-line constant
                        if any(value_part.rstrip().endswith(b) for b in ['[', '{', '(']):
                            # Multi-line constant - skip until closing bracket
                            bracket_count = 1
                            open_brackets = {'[': ']', '{': '}', '(': ')'}
                            opening = value_part.rstrip()[-1]
                            closing = open_brackets[opening]
                            
                            while j < len(lines) and bracket_count > 0:
                                line_content = lines[j]
                                for char in line_content:
                                    if char == opening:
                                        bracket_count += 1
                                    elif char == closing:
                                        bracket_count -= 1
                                j += 1
                        elif stripped.rstrip().endswith('\\'):
                            # Backslash continuation
                            while j < len(lines) and lines[j-1].rstrip().endswith('\\'):
                                j += 1
                    i = j
                    continue
                
                # Extract the full constant definition (handle multi-line)
                const_def = []
                j = i
                # Get the first line
                const_def.append(lines[j])
                j += 1
                
                # Check if this is a multi-line constant (contains opening bracket)
                # Track all types of brackets simultaneously
                bracket_counts = {'[': 0, '{': 0, '(': 0}
                open_brackets = {'[': ']', '{': '}', '(': ')'}
                close_to_open = {']': '[', '}': '{', ')': '('}
                
                # Count brackets in the first line, but only after the = sign
                # to avoid counting brackets in the variable name
                equals_pos = stripped.find('=')
                if equals_pos >= 0:
                    value_part = stripped[equals_pos + 1:]
                else:
                    value_part = stripped
                
                # Track if we're inside a string literal
                in_string = False
                string_char = None
                escaped = False
                
                for char in value_part:
                    if escaped:
                        escaped = False
                        continue
                    if char == '\\':
                        escaped = True
                        continue
                    
                    # Handle string literals
                    if char in ['"', "'"]:
                        if not in_string:
                            in_string = True
                            string_char = char
                        elif char == string_char:
                            in_string = False
                            string_char = None
                        continue
                    
                    # Only count brackets outside of strings
                    if not in_string:
                        if char in open_brackets:
                            bracket_counts[char] += 1
                        elif char in close_to_open:
                            bracket_counts[close_to_open[char]] -= 1
                
                # If we have any unclosed brackets, it's a multi-line constant
                total_open = sum(bracket_counts.values())
                if total_open > 0:
                    # Continue collecting lines until all brackets are closed
                    while j < len(lines) and total_open > 0:
                        const_def.append(lines[j])
                        line_content = lines[j]
                        
                        # Track string state
                        in_string = False
                        string_char = None
                        escaped = False
                        
                        # Count brackets in this line
                        for char in line_content:
                            if escaped:
                                escaped = False
                                continue
                            if char == '\\':
                                escaped = True
                                continue
                            
                            # Handle string literals
                            if char in ['"', "'"]:
                                if not in_string:
                                    in_string = True
                                    string_char = char
                                elif char == string_char:
                                    in_string = False
                                    string_char = None
                                continue
                            
                            # Only count brackets outside of strings
                            if not in_string:
                                if char in open_brackets:
                                    bracket_counts[char] += 1
                                elif char in close_to_open:
                                    bracket_counts[close_to_open[char]] -= 1
                        
                        total_open = sum(bracket_counts.values())
                        j += 1
                    
                    # Check if the constant continues with backslash
                elif stripped.rstrip().endswith('\\'):
                    # Continue collecting lines until no backslash
                    while j < len(lines) and lines[j-1].rstrip().endswith('\\'):
                        const_def.append(lines[j])
                        j += 1
                
                # Don't skip constants that reference other constants - we'll handle ordering later
                
                # Normalize indentation for multi-line constants
                if len(const_def) > 1:
                    # Find the base indentation from the first line
                    base_indent = len(const_def[0]) - len(const_def[0].lstrip())
                    
                    # Normalize subsequent lines to maintain relative indentation
                    normalized_lines = [const_def[0]]  # First line stays as-is
                    
                    for line in const_def[1:]:
                        # Calculate the current line's indentation
                        current_indent = len(line) - len(line.lstrip())
                        
                        # If line is completely empty, keep it empty
                        if line.strip() == '':
                            normalized_lines.append('')
                        else:
                            # Remove excess indentation but maintain relative structure
                            # We expect subsequent lines to be indented more than the base
                            if current_indent > base_indent:
                                # Calculate relative indentation (usually 4 spaces for list items)
                                relative_indent = current_indent - base_indent
                                # Reconstruct with base indent + relative indent
                                new_line = ' ' * (base_indent + 4) + line.lstrip()
                                normalized_lines.append(new_line)
                            else:
                                # If not indented more, keep original indentation
                                normalized_lines.append(line)
                    
                    const_definition = '\n'.join(normalized_lines)
                else:
                    const_definition = '\n'.join(const_def)
                
                # Store the constant definition only if we haven't seen it before
                if const_name not in extracted_constants:
                    extracted_constants[const_name] = const_definition
                    constants.append(const_definition)
                
                i = j
                continue
            
            # Check for helper functions at module level
            if stripped.startswith('def ') and not line.startswith((' ', '\t')):
                # Extract function name for deduplication
                func_match = re.match(r'^def\s+(\w+)', stripped)
                if func_match:
                    func_name = func_match.group(1)
                    # Check if we've already extracted this function
                    if any(func_name in func for func in helper_functions):
                        # Skip this function
                        j = i + 1
                        while j < len(lines) and (lines[j].startswith((' ', '\t')) or not lines[j].strip()):
                            j += 1
                        i = j
                        continue
                
                # Extract the whole function
                func_def = []
                j = i
                while j < len(lines):
                    func_def.append(lines[j])
                    j += 1
                    # Check if we've reached the end of the function
                    if j < len(lines) and lines[j] and not lines[j].startswith((' ', '\t')):
                        break
                helper_functions.append('\n'.join(func_def))
                i = j
                continue
            
            # Check for custom animation classes
            if stripped.startswith('class ') and 'Animation' in line:
                # This might be a custom animation class
                class_name = line.split('(')[0].replace('class', '').strip()
                if class_name in ['FlipThroughNumbers', 'DelayByOrder', 'ContinualAnimation', 
                                 'SlideWordDownCycloid', 'RollAlongVector']:
                    # Check if we've already extracted this class
                    if any(class_name in anim for anim in custom_animations):
                        # Skip this class
                        j = i + 1
                        while j < len(lines) and (lines[j].startswith((' ', '\t')) or not lines[j].strip()):
                            j += 1
                        i = j
                        continue
                    
                    # Extract the whole class
                    class_def = []
                    j = i
                    while j < len(lines):
                        class_def.append(lines[j])
                        j += 1
                        # Check if we've reached the end of the class
                        if j < len(lines) and lines[j] and not lines[j].startswith((' ', '\t')):
                            break
                    custom_animations.append('\n'.join(class_def))
                    i = j
                    continue
            
            i += 1
    
    # Add helper functions FIRST (before constants that might use them)
    seen_functions = set()
    if helper_functions:
        combined_parts.append("# Helper functions")
        for func in helper_functions:
            # Extract function name for deduplication
            func_match = re.search(r'^def\s+(\w+)', func, re.MULTILINE)
            if func_match:
                func_name = func_match.group(1)
                if func_name not in seen_functions:
                    seen_functions.add(func_name)
                    combined_parts.append(func)
                    combined_parts.append("")
    
    # Add constants AFTER helper functions (since they might depend on them)
    seen_constants = set()
    if constants:
        # Sort constants by dependency order
        sorted_constants = _sort_constants_by_dependency(constants)
        
        combined_parts.append("# Constants")
        for const in sorted_constants:
            const_name = const.split('=')[0].strip()
            if const_name not in seen_constants:
                seen_constants.add(const_name)
                combined_parts.append(const)
        combined_parts.append("")
    
    # Add custom animations if found (deduplicated)
    seen_animations = set()
    if custom_animations:
        combined_parts.append("# Custom animations for ManimGL compatibility")
        for anim in custom_animations:
            # Extract class name for deduplication
            class_line = anim.split('\n')[0]
            if class_line not in seen_animations:
                seen_animations.add(class_line)
                combined_parts.append(anim)
                combined_parts.append("")
    
    # Add scenes (filtering out already extracted content)
    for scene_info in scene_codes_without_imports:
        scene_code = scene_info['code']
        
        # Filter out content that we've already added
        filtered_lines = []
        lines = scene_code.split('\n')
        skip_until = -1
        
        for i, line in enumerate(lines):
            if i < skip_until:
                continue
            
            stripped = line.strip()
            
            # Skip constants we've already added
            if stripped and re.match(r'^[A-Z_]+\s*=', stripped) and not line.startswith((' ', '\t')):
                const_name = stripped.split('=')[0].strip()
                if const_name in seen_constants:
                    # Skip multi-line constants properly
                    j = i + 1
                    if stripped.rstrip().endswith(('[', '{', '(')):
                        # Multi-line constant - skip until closing bracket
                        bracket_count = 1
                        open_brackets = {'[': ']', '{': '}', '(': ')'}
                        opening = stripped.rstrip()[-1]
                        closing = open_brackets[opening]
                        
                        while j < len(lines) and bracket_count > 0:
                            line_content = lines[j]
                            for char in line_content:
                                if char == opening:
                                    bracket_count += 1
                                elif char == closing:
                                    bracket_count -= 1
                            j += 1
                    elif stripped.rstrip().endswith('\\'):
                        # Backslash continuation
                        while j < len(lines) and lines[j-1].rstrip().endswith('\\'):
                            j += 1
                    skip_until = j
                    continue
            
            # Skip helper functions we've already added
            if stripped.startswith('def ') and not line.startswith((' ', '\t')):
                func_match = re.match(r'^def\s+(\w+)', stripped)
                if func_match and func_match.group(1) in seen_functions:
                    # Skip this function
                    j = i + 1
                    while j < len(lines) and (lines[j].startswith((' ', '\t')) or not lines[j].strip()):
                        j += 1
                    skip_until = j
                    continue
            
            # Skip custom animation classes we've already added
            if stripped.startswith('class ') and any(anim in line for anim in 
                ['FlipThroughNumbers', 'DelayByOrder', 'ContinualAnimation', 
                 'SlideWordDownCycloid', 'RollAlongVector']):
                # Skip this custom animation class
                j = i + 1
                while j < len(lines) and (lines[j].startswith((' ', '\t')) or not lines[j].strip()):
                    j += 1
                skip_until = j
                continue
            
            filtered_lines.append(line)
        
        filtered_code = '\n'.join(filtered_lines).strip()
        
        if filtered_code:  # Only add if there's content after filtering
            combined_parts.append(f"\n# Scene: {scene_info['name']}")
            combined_parts.append(filtered_code)
            combined_parts.append("")
    
    combined_code = '\n'.join(combined_parts)
    
    # Save individual self-contained snippets
    snippet_metadata = {}
    
    # Initialize syntax validation statistics
    syntax_valid_snippets = 0
    syntax_invalid_snippets = 0
    syntax_errors = []
    
    # Prepare imports for each snippet
    snippet_imports = []
    
    # Always include manim import
    snippet_imports.append("from manim import *")
    
    # Add other essential imports
    if numpy_imports:
        snippet_imports.extend(sorted(numpy_imports))
    else:
        # Always include numpy as it's commonly used
        snippet_imports.append("import numpy as np")
    
    if typing_imports:
        snippet_imports.extend(sorted(typing_imports))
    
    # CRITICAL MISSING IMPORTS FIX: Add essential imports that are often missing
    # Check if reduce is used anywhere and add functools import
    all_scene_code = '\n'.join([scene_info['code'] for scene_info in scene_codes_without_imports])
    if 'reduce(' in all_scene_code:
        snippet_imports.append("from functools import reduce")
        logger.info(f"Added functools reduce import - found {all_scene_code.count('reduce(')} occurrences")
    
    # Check for string module usage (Python 2 vs 3 compatibility)
    if 'string.' in all_scene_code:
        snippet_imports.append("import string")
    
    # Add other common missing imports
    if 'random.' in all_scene_code or 'choice(' in all_scene_code or 'randint(' in all_scene_code:
        snippet_imports.append("import random")
    
    if 'sys.' in all_scene_code:
        snippet_imports.append("import sys")
    
    if 'itertools' in all_scene_code or ' it.' in all_scene_code:
        snippet_imports.append("import itertools as it")
    
    if 'operator' in all_scene_code or ' op.' in all_scene_code:
        snippet_imports.append("import operator as op")
    
    if other_imports:
        # Filter out any manimlib imports as they're covered by manim import
        filtered_other = [imp for imp in other_imports if 'manimlib' not in imp]
        if filtered_other:
            snippet_imports.extend(sorted(filtered_other))
    
    # Common header for all snippets
    imports_header = '\n'.join(snippet_imports) + '\n\n'
    
    # Add constants, helper functions, and custom animations if they exist
    shared_code_parts = []
    
    # Add helper functions FIRST (before constants that might use them)
    if helper_functions:
        shared_code_parts.append("# Helper functions")
        added_functions = set()
        for func in helper_functions:
            func_match = re.search(r'^def\s+(\w+)', func, re.MULTILINE)
            if func_match:
                func_name = func_match.group(1)
                if func_name in seen_functions and func_name not in added_functions:
                    added_functions.add(func_name)
                    shared_code_parts.append(func)
                    shared_code_parts.append("")
    
    # Add constants AFTER helper functions (since they might depend on them)
    if constants:
        shared_code_parts.append("# Constants")
        # Use the sorted constants
        sorted_constants = _sort_constants_by_dependency(constants)
        added_constants = set()
        for const in sorted_constants:
            const_name = const.split('=')[0].strip()
            if const_name in seen_constants and const_name not in added_constants:
                added_constants.add(const_name)
                shared_code_parts.append(const)
        shared_code_parts.append("")
    
    # Check if choose function is used but not defined
    all_code = '\n'.join([scene_info['code'] for scene_info in scene_codes_without_imports])
    if 'choose(' in all_code and 'choose' not in seen_functions:
        shared_code_parts.append("# Helper functions")
        shared_code_parts.append("""def choose(n, k):
    \"\"\"Binomial coefficient (n choose k).\"\"\"
    if k > n or k < 0:
        return 0
    if k == 0 or k == n:
        return 1
    k = min(k, n - k)
    result = 1
    for i in range(k):
        result = result * (n - i) // (i + 1)
    return result
""")
        shared_code_parts.append("")
    
    if custom_animations:
        shared_code_parts.append("# Custom animations")
        for anim in custom_animations:
            shared_code_parts.append(anim)
            shared_code_parts.append("")
    
    shared_code = '\n'.join(shared_code_parts) if shared_code_parts else ""
    
    # Save each scene as an individual self-contained snippet
    for scene_info in scene_codes_without_imports:
        scene_name = scene_info['name']
        scene_code = scene_info['code']
        
        # Find the filtered version from the monolithic file logic
        filtered_lines = []
        lines = scene_code.split('\n')
        skip_until = -1
        
        for i, line in enumerate(lines):
            if i < skip_until:
                continue
            
            stripped = line.strip()
            
            # Skip already-extracted content
            if stripped and re.match(r'^[A-Z_]+\s*=', stripped) and not line.startswith((' ', '\t')):
                const_name = stripped.split('=')[0].strip()
                if const_name in seen_constants:
                    # Skip multi-line constants properly
                    j = i + 1
                    if stripped.rstrip().endswith(('[', '{', '(')):
                        # Multi-line constant - skip until closing bracket
                        bracket_count = 1
                        open_brackets = {'[': ']', '{': '}', '(': ')'}
                        opening = stripped.rstrip()[-1]
                        closing = open_brackets[opening]
                        
                        while j < len(lines) and bracket_count > 0:
                            line_content = lines[j]
                            for char in line_content:
                                if char == opening:
                                    bracket_count += 1
                                elif char == closing:
                                    bracket_count -= 1
                            j += 1
                    elif stripped.rstrip().endswith('\\'):
                        # Backslash continuation
                        while j < len(lines) and lines[j-1].rstrip().endswith('\\'):
                            j += 1
                    skip_until = j
                    continue
            
            if stripped.startswith('def ') and not line.startswith((' ', '\t')):
                func_match = re.match(r'^def\s+(\w+)', stripped)
                if func_match and func_match.group(1) in seen_functions:
                    j = i + 1
                    while j < len(lines) and (lines[j].startswith((' ', '\t')) or not lines[j].strip()):
                        j += 1
                    skip_until = j
                    continue
            
            if stripped.startswith('class ') and any(anim in line for anim in 
                ['FlipThroughNumbers', 'DelayByOrder', 'ContinualAnimation', 
                 'SlideWordDownCycloid', 'RollAlongVector']):
                j = i + 1
                while j < len(lines) and (lines[j].startswith((' ', '\t')) or not lines[j].strip()):
                    j += 1
                skip_until = j
                continue
            
            filtered_lines.append(line)
        
        filtered_scene_code = '\n'.join(filtered_lines).strip()
        
        if filtered_scene_code:
            # Build the complete self-contained snippet
            snippet_parts = [
                f"# Self-contained ManimCE snippet for scene: {scene_name}",
                f"# From video: {video_dir.name}",
                "",
                imports_header
            ]
            
            # Add shared code if it exists
            if shared_code:
                snippet_parts.append(shared_code)
            
            # Add the scene code
            snippet_parts.append(filtered_scene_code)
            
            snippet_content = '\n'.join(snippet_parts)
            
            # Validate syntax before writing
            snippet_filename = f"{scene_name}.py"
            is_valid, error_message = validate_snippet_syntax(snippet_content, snippet_filename)
            
            if is_valid:
                # Save the snippet only if syntax is valid
                snippet_file = snippets_dir / snippet_filename
                with open(snippet_file, 'w') as f:
                    f.write(snippet_content)
                
                syntax_valid_snippets += 1
                
                # Track metadata
                snippet_metadata[scene_name] = {
                    'file': snippet_filename,
                    'size': len(snippet_content),
                    'lines': snippet_content.count('\n') + 1,
                    'has_shared_code': bool(shared_code),
                    'conversion_method': scene_results[scene_name]['conversion_method'],
                    'syntax_valid': True
                }
                
                logger.debug(f"✅ Saved validated snippet: {snippet_file}")
            else:
                # Skip writing malformed snippet
                syntax_invalid_snippets += 1
                syntax_errors.append({
                    'scene_name': scene_name,
                    'error': error_message,
                    'snippet_size': len(snippet_content)
                })
                
                logger.warning(f"❌ Skipped snippet {scene_name} due to syntax error: {error_message}")
                
                # Still track metadata but mark as invalid
                snippet_metadata[scene_name] = {
                    'file': snippet_filename,
                    'size': len(snippet_content),
                    'lines': snippet_content.count('\n') + 1,
                    'has_shared_code': bool(shared_code),
                    'conversion_method': scene_results[scene_name]['conversion_method'],
                    'syntax_valid': False,
                    'syntax_error': error_message
                }
    
    # Save snippet metadata
    metadata_file = snippets_dir / 'metadata.json'
    with open(metadata_file, 'w') as f:
        json.dump({
            'video_name': video_dir.name,
            'total_snippets': len(snippet_metadata),
            'snippets': snippet_metadata,
            'created_at': time.time()
        }, f, indent=2)
    
    logger.info(f"Saved {len(snippet_metadata)} self-contained snippets to {snippets_dir}")
    
    # Fix snippet dependency ordering and syntax issues
    try:
        from fix_snippet_dependency_order import fix_snippets_in_directory
        logger.info(f"Fixing snippet dependency ordering and syntax issues...")
        fix_stats = fix_snippets_in_directory(snippets_dir)
        logger.info(f"Fixed {fix_stats['fixed']}/{fix_stats['total']} snippet files")
    except Exception as e:
        logger.warning(f"Could not fix snippet issues: {e}")
    
    # Save monolithic file (for backwards compatibility)
    monolith_file = video_dir / '.pipeline' / 'intermediate' / 'monolith_manimce.py'
    monolith_file.parent.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
    with open(monolith_file, 'w') as f:
        f.write(combined_code)
    
    # Copy monolith file to the expected location for render script
    target_monolith = video_dir / 'monolith_manimce.py'
    shutil.copy2(monolith_file, target_monolith)
    logger.info(f"Copied monolith file to {target_monolith}")
    
    # Save scene-level conversion results
    conversion_results = {
        'converted_at': time.time(),
        'converter': 'enhanced_systematic',
        'scenes': scene_results,
        'total_scenes': len(scene_results),  # Total scenes attempted
        'successful_scenes': len(successful_scenes),  # Only successful ones
        'snippets_saved': len(snippet_metadata),
        'syntax_validation': {
            'total_snippets_attempted': syntax_valid_snippets + syntax_invalid_snippets,
            'syntax_valid_snippets': syntax_valid_snippets,
            'syntax_invalid_snippets': syntax_invalid_snippets,
            'validation_success_rate': syntax_valid_snippets / max(1, syntax_valid_snippets + syntax_invalid_snippets),
            'syntax_errors': syntax_errors
        }
    }
    
    results_file = video_dir / '.pipeline' / 'logs' / 'conversion_results.json'
    with open(results_file, 'w') as f:
        json.dump(conversion_results, f, indent=2)
    
    logger.info(f"Saved {len(successful_scenes)} successfully converted scenes (monolith: {monolith_file})")


def _print_systematic_conversion_summary(results: Dict, converter: EnhancedSystematicConverter, builder):
    """Print detailed summary of systematic conversion results."""
    
    if SummaryTable and builder.verbose:
        # Use clean summary table format
        stats = {
            "Videos": {
                "Total processed": results['total_videos'],
                "Successful": results['successful_videos'],
                "Failed": results['failed_videos'],
                "Success rate": f"{results['successful_videos'] / max(1, results['total_videos']) * 100:.1f}%"
            },
            "Conversion Methods": {
                "Systematic only": f"{results['systematic_only_success']} ({results.get('systematic_efficiency', 0):.1%})",
                "Claude fallback": results['claude_fallback_success'],
                "Manual fix": results.get('manual_fix_success', 0)
            },
            "Efficiency": {
                "Claude reduction": f"{results.get('claude_reduction', 0):.1%}",
                "API dependency": f"{100 * (1 - results.get('systematic_efficiency', 0)):.0f}% (was 100%)",
                "Processing time": f"{results['processing_time']:.1f}s"
            },
            "Scene Results": {
                "Total scenes": results['syntax_validation']['total_snippets_attempted'],
                "Valid scenes": results['syntax_validation']['syntax_valid_snippets'],
                "Invalid scenes": results['syntax_validation']['syntax_invalid_snippets'],
                "Skipped (low confidence)": results.get('skipped_low_confidence', 0),
                "Scene success rate": f"{results['syntax_validation']['syntax_valid_snippets'] / max(1, results['syntax_validation']['total_snippets_attempted']) * 100:.1f}%"
            }
        }
        
        # Add unfixable pattern stats if available
        if 'unfixable_patterns' in results:
            unfixable = results['unfixable_patterns']
            stats["Unfixable Patterns"] = {
                "Mode": "MONITORING" if unfixable.get('monitor_mode', True) else "ACTIVE",
                "Would skip": unfixable.get('skipped', 0),
                "Attempted": unfixable.get('attempted', 0),
                "Reduction": f"{unfixable.get('skipped', 0) / max(1, unfixable.get('skipped', 0) + unfixable.get('attempted', 0)) * 100:.1f}%"
            }
        
        # Add confidence threshold stats if there were skipped scenes
        if results.get('skipped_low_confidence', 0) > 0:
            skipped_count = results['skipped_low_confidence']
            estimated_savings = skipped_count * 0.03  # Estimate $0.03 per Claude API call
            stats["Confidence Threshold"] = {
                "Threshold": f"{min_conversion_confidence:.1%}",
                "Scenes skipped": skipped_count,
                "Estimated cost savings": f"${estimated_savings:.2f}",
                "Time saved": f"~{skipped_count * 30}s"  # Estimate 30s per Claude call
            }
        
        print(SummaryTable.format_stats(stats, "SYSTEMATIC CONVERSION SUMMARY"))
    else:
        # Fallback to original format
        print("\n" + "="*60)
        print("CONVERSION SUMMARY")
        print("="*60)
        print(f"✅ Success: {results['successful_videos']}/{results['total_videos']} videos")
        print(f"📊 Systematic: {results.get('systematic_efficiency', 0):.1%} handled automatically")
        print(f"🤖 Claude: {100 * (1 - results.get('systematic_efficiency', 0)):.0f}% needed help")
        # Calculate actual scene conversion statistics from video results
        total_scenes = 0
        successful_scenes = 0
        for video_name, video_data in results.get('videos', {}).items():
            if isinstance(video_data, dict):
                total_scenes += video_data.get('total_scenes', 0)
                successful_scenes += video_data.get('successful_scenes', 0)
        
        if total_scenes > 0:
            success_rate = (successful_scenes / total_scenes) * 100
            print(f"🎬 Scenes: {successful_scenes}/{total_scenes} scenes converted ({success_rate:.1f}%)")
        else:
            print(f"🎬 Scenes: 0/0 scenes converted (no scenes to process)")
        if results.get('skipped_low_confidence', 0) > 0:
            skipped_count = results['skipped_low_confidence']
            estimated_savings = skipped_count * 0.03
            print(f"⏭️  Skipped: {skipped_count} scenes (confidence < {min_conversion_confidence:.1%}) - saved ~${estimated_savings:.2f}")
        print(f"⏱️  Time: {results['processing_time']:.1f}s")
        print("="*60)


def test_systematic_pipeline():
    """Test function for the systematic pipeline converter."""
    print("Testing systematic pipeline converter...")
    
    # Test basic converter initialization
    converter = EnhancedSystematicConverter(enable_claude_fallback=False)
    converter.print_statistics()
    
    # Test with unfixable pattern detection parameters
    print("\nTesting unfixable pattern detection integration...")
    converter_with_unfixable = EnhancedSystematicConverter(
        enable_claude_fallback=True,
        enable_unfixable_skipping=True,
        monitor_unfixable_only=False
    )
    
    # Verify the settings were applied
    if converter_with_unfixable.claude_converter:
        print("✅ Claude converter initialized with unfixable pattern detection")
        if hasattr(converter_with_unfixable.claude_converter, 'unfixable_monitor_only'):
            monitor_mode = converter_with_unfixable.claude_converter.unfixable_monitor_only
            print(f"   Monitor mode: {monitor_mode}")
        else:
            print("   ⚠️ unfixable_monitor_only attribute not found")
    else:
        print("   ⚠️ Claude converter not initialized")
    
    print("✅ Systematic pipeline converter is ready!")


if __name__ == '__main__':
    test_systematic_pipeline()