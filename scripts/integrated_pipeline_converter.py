#!/usr/bin/env python3
"""
Integrated Pipeline Converter - Replaces the conversion stage in build_dataset_pipeline.py

This module provides a drop-in replacement for the conversion stage that:
1. Uses the enhanced scene converter with integrated dependency analysis
2. Creates self-contained snippets during conversion (not after)
3. Validates each snippet individually
4. Provides Claude feedback loops for fixing errors
5. Maintains compatibility with the existing pipeline structure
"""

import ast
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from enhanced_scene_converter import EnhancedSceneConverter
from clean_matched_code_scenes import SceneAwareCleaner, SceneInfo
from scene_combiner import SceneCombiner
from claude_api_helper import ClaudeAPIHelper
from conversion_error_collector import collect_conversion_error

logger = logging.getLogger(__name__)


def reset_conversion_status(base_dir: Path, year: int, video_filter: Optional[List[str]] = None):
    """
    Reset conversion status for all videos in a year when --force-convert is used.
    
    This ensures that if a previous conversion run was interrupted (e.g., by rate limiting),
    the next run will properly restart from the beginning rather than having mixed state.
    
    Args:
        base_dir: Base directory of the project
        year: Year to reset conversion status for
        video_filter: Optional list of specific videos to reset (if None, resets all)
    """
    output_dir = base_dir / 'outputs' / str(year)
    if not output_dir.exists():
        logger.warning(f"Output directory does not exist: {output_dir}")
        return
        
    videos_reset = 0
    
    for video_dir in output_dir.iterdir():
        if not video_dir.is_dir():
            continue
            
        # Apply video filter if specified
        if video_filter and video_dir.name not in video_filter:
            continue
            
        # Remove conversion outputs to reset status
        files_to_remove = [
            video_dir / 'manimce_code.py',
            video_dir / 'conversion_results.json',
            video_dir / 'validated_snippets'
        ]
        
        removed_any = False
        for file_path in files_to_remove:
            if file_path.exists():
                if file_path.is_dir():
                    # Remove directory and all contents
                    import shutil
                    shutil.rmtree(file_path)
                    logger.debug(f"Removed directory: {file_path}")
                else:
                    # Remove file
                    file_path.unlink()
                    logger.debug(f"Removed file: {file_path}")
                removed_any = True
                
        if removed_any:
            videos_reset += 1
            logger.debug(f"Reset conversion status for video: {video_dir.name}")
            
    logger.info(f"Reset conversion status for {videos_reset} videos")
    
    # Also remove year-level conversion summary to force regeneration
    summary_file = base_dir / 'outputs' / f'integrated_conversion_summary_{year}.json'
    if summary_file.exists():
        summary_file.unlink()
        logger.info(f"Removed year-level conversion summary: {summary_file.name}")


class IntegratedPipelineConverter:
    """
    Drop-in replacement for the conversion stage that integrates snippet extraction,
    dependency analysis, and validation into the conversion process.
    """
    
    def __init__(self, base_dir: Path, verbose: bool = False,
                 enable_render_validation: bool = True,
                 enable_precompile_validation: bool = True,
                 render_max_attempts: int = 3,
                 max_workers: int = 4):
        self.base_dir = base_dir
        self.verbose = verbose
        self.enable_render_validation = enable_render_validation
        self.enable_precompile_validation = enable_precompile_validation
        self.render_max_attempts = render_max_attempts
        self.max_workers = max_workers
        
        # Initialize components
        self.enhanced_converter = EnhancedSceneConverter(
            enable_render_validation=enable_render_validation,
            enable_precompile_validation=enable_precompile_validation,
            verbose=verbose
        )
        self.claude_helper = ClaudeAPIHelper(
            verbose=verbose,
            use_model_strategy=True  # Enable smart model selection
        )
        self.scene_combiner = SceneCombiner(verbose=verbose)
        
        # Track overall statistics
        self.stats = {
            'total_videos': 0,
            'total_scenes': 0,
            'successful_scenes': 0,
            'failed_scenes': 0,
            'videos_with_all_scenes_valid': 0,
            'claude_fixes_attempted': 0,
            'claude_fixes_successful': 0,
            'total_dependencies_found': 0
        }
        
    def convert_video(self, video_dir: Path) -> Dict[str, Any]:
        """
        Convert a single video's scenes with integrated validation and snippet creation.
        
        Args:
            video_dir: Path to the video directory containing cleaned scenes
            
        Returns:
            Dictionary with conversion results and created snippets
        """
        result = {
            'video_name': video_dir.name,
            'status': 'pending',
            'scenes': {},
            'snippets_created': 0,
            'all_scenes_valid': False,
            'combined_file': None,
            'errors': [],
            'metadata': {}
        }
        
        logger.info(f"Converting video: {video_dir.name}")
        
        # Check for cleaned scenes directory
        scenes_dir = video_dir / 'cleaned_scenes'
        if not scenes_dir.exists():
            # Try monolithic file
            cleaned_file = video_dir / 'monolith_manimgl.py'
            if cleaned_file.exists():
                # Extract scenes from monolithic file
                result_scenes = self._process_monolithic_file(cleaned_file, video_dir)
                result['scenes'] = result_scenes
            else:
                result['status'] = 'no_cleaned_code'
                result['errors'].append('No cleaned code found')
                return result
        else:
            # Process scene files
            result_scenes = self._process_scene_files(scenes_dir, video_dir)
            result['scenes'] = result_scenes
            
        # Update statistics
        total_scenes = len(result['scenes'])
        successful_scenes = sum(1 for s in result['scenes'].values() if s.get('success', False))
        
        result['snippets_created'] = successful_scenes
        result['all_scenes_valid'] = (total_scenes > 0 and successful_scenes == total_scenes)
        
        # Create combined file if all scenes are valid
        if result['all_scenes_valid']:
            combined_file = self._create_combined_file(video_dir, result['scenes'])
            if combined_file:
                result['combined_file'] = str(combined_file)
                result['status'] = 'success'
            else:
                result['status'] = 'combine_failed'
        else:
            result['status'] = 'partial_success' if successful_scenes > 0 else 'failed'
            
        # Save detailed results
        self._save_conversion_results(video_dir, result)
        
        # Update global stats
        self.stats['total_videos'] += 1
        self.stats['total_scenes'] += total_scenes
        self.stats['successful_scenes'] += successful_scenes
        self.stats['failed_scenes'] += (total_scenes - successful_scenes)
        if result['all_scenes_valid']:
            self.stats['videos_with_all_scenes_valid'] += 1
            
        return result
        
    def _process_monolithic_file(self, cleaned_file: Path, video_dir: Path) -> Dict[str, Any]:
        """Process a monolithic cleaned file by extracting and converting scenes."""
        logger.info(f"Processing monolithic file: {cleaned_file}")
        
        # Read the cleaned code
        with open(cleaned_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Parse AST for scene extraction
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            logger.error(f"Syntax error in cleaned file: {e}")
            return {}
            
        # Extract scenes using SceneAwareCleaner
        cleaner = SceneAwareCleaner(self.base_dir, self.verbose)
        scenes = {}
        
        # Find all scene classes in the AST
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.endswith('Scene'):
                scene_name = node.name
                # Get scene code
                scene_lines = content.splitlines()
                start_line = node.lineno - 1
                end_line = start_line
                
                # Find end of scene class
                for i in range(start_line + 1, len(scene_lines)):
                    if scene_lines[i] and not scene_lines[i].startswith((' ', '\t')):
                        end_line = i - 1
                        break
                else:
                    end_line = len(scene_lines) - 1
                
                scene_code = '\n'.join(scene_lines[start_line:end_line + 1])
                scenes[scene_name] = {
                    'content': scene_code,
                    'start_line': start_line,
                    'end_line': end_line
                }
        
        if not scenes:
            logger.warning("No scenes found in monolithic file")
            return {}
            
        # Process each scene
        results = {}
        for scene_name, scene_info in scenes.items():
            logger.info(f"Processing scene: {scene_name}")
            
            # Process with enhanced converter
            scene_result = self._process_single_scene(
                scene_name=scene_name,
                scene_content=scene_info['content'],
                full_ast=tree,
                video_name=video_dir.name,
                output_dir=video_dir
            )
            
            results[scene_name] = scene_result
            
        return results
        
    def _process_scene_files(self, scenes_dir: Path, video_dir: Path) -> Dict[str, Any]:
        """Process individual scene files from cleaned_scenes directory."""
        scene_files = list(scenes_dir.glob('*.py'))
        
        if not scene_files:
            logger.warning(f"No scene files found in {scenes_dir}")
            return {}
            
        # First, we need to build a combined AST for dependency analysis
        combined_ast = self._build_combined_ast(scene_files)
        
        # Process scenes in parallel
        results = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_scene = {}
            
            for scene_file in scene_files:
                # Extract scene name from filename
                scene_name = self._extract_scene_name(scene_file)
                
                # Read scene content
                with open(scene_file, 'r', encoding='utf-8') as f:
                    scene_content = f.read()
                    
                # Submit processing task
                future = executor.submit(
                    self._process_single_scene,
                    scene_name=scene_name,
                    scene_content=scene_content,
                    full_ast=combined_ast,
                    video_name=video_dir.name,
                    output_dir=video_dir
                )
                future_to_scene[future] = scene_name
                
            # Collect results
            for future in as_completed(future_to_scene):
                scene_name = future_to_scene[future]
                try:
                    result = future.result()
                    results[scene_name] = result
                except Exception as e:
                    logger.error(f"Failed to process scene {scene_name}: {e}")
                    results[scene_name] = {
                        'scene_name': scene_name,
                        'success': False,
                        'errors': [str(e)]
                    }
                    
        return results
        
    def _process_single_scene(self, scene_name: str, scene_content: str,
                             full_ast: ast.Module, video_name: str,
                             output_dir: Path) -> Dict[str, Any]:
        """Process a single scene with Claude feedback loop for errors."""
        
        # Initial processing with enhanced converter
        result = self.enhanced_converter.process_scene(
            scene_name=scene_name,
            scene_content=scene_content,
            full_module_ast=full_ast,
            video_name=video_name,
            output_dir=output_dir / 'validation'
        )
        
        # If initial render failed, try Claude fixes
        if (self.enable_render_validation and 
            not result['validation']['render']['success'] and 
            self.render_max_attempts > 1):
            
            snippet = result['snippet']
            error_msg = result['validation']['render'].get('error', 'Unknown render error')
            
            for attempt in range(1, self.render_max_attempts):
                logger.info(f"Attempting Claude fix for {scene_name} (attempt {attempt}/{self.render_max_attempts - 1})")
                
                # Build rich context for Claude
                additional_context = {
                    'video_name': video_name,
                    'original_scene_content': scene_content,  # Original cleaned code
                    'conversion_metadata': result.get('metadata', {}),
                    'dependencies': result.get('dependencies', {}),
                    'validation_errors': result.get('validation', {}).get('precompile', {}).get('errors', []),
                    'environment': {
                        'python_version': sys.version.split()[0],
                        'output_dir': str(output_dir)
                    }
                }
                
                # Get Claude fix
                fix_result = self.claude_helper.fix_render_error(
                    scene_name=scene_name,
                    snippet_content=snippet,
                    error_message=error_msg,
                    attempt_number=attempt,
                    additional_context=additional_context
                )
                fixed_snippet = fix_result['fixed_content']
                was_fixed = fix_result['success']
                
                if was_fixed:
                    self.stats['claude_fixes_attempted'] += 1
                    
                    # Re-validate the fixed snippet
                    re_result = self.enhanced_converter._validate_render(
                        fixed_snippet, scene_name, output_dir / 'validation'
                    )
                    
                    if re_result['success']:
                        # Update the result with successful fix
                        result['snippet'] = fixed_snippet
                        result['validation']['render'] = re_result
                        result['success'] = True
                        result['claude_fixes'] = attempt
                        self.stats['claude_fixes_successful'] += 1
                        logger.info(f"✅ Claude fix successful for {scene_name}")
                        break
                    else:
                        # Update error for next iteration
                        error_msg = re_result.get('error', 'Unknown render error')
                        snippet = fixed_snippet
                else:
                    logger.warning(f"Claude unable to fix {scene_name}")
                    break
                    
        # Save the validated snippet
        if result['success']:
            snippet_path = self._save_snippet(
                output_dir, scene_name, result['snippet'], result
            )
            result['snippet_path'] = str(snippet_path)
            
        # Track dependencies
        if result.get('dependencies'):
            dep_count = (result['dependencies'].get('function_count', 0) +
                        result['dependencies'].get('class_count', 0) +
                        result['dependencies'].get('constant_count', 0))
            self.stats['total_dependencies_found'] += dep_count
            
        return result
        
    def _build_combined_ast(self, scene_files: List[Path]) -> ast.Module:
        """Build a combined AST from all scene files for dependency analysis."""
        combined_body = []
        
        for scene_file in scene_files:
            try:
                with open(scene_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                tree = ast.parse(content)
                combined_body.extend(tree.body)
            except Exception as e:
                logger.error(f"Failed to parse {scene_file}: {e}")
                
        return ast.Module(body=combined_body, type_ignores=[])
        
    def _extract_scene_name(self, scene_file: Path) -> str:
        """Extract scene name from filename."""
        # For files like DivergentSum.py, FinalSlide.py, etc.
        return scene_file.stem
        
    def _save_snippet(self, video_dir: Path, scene_name: str, 
                     snippet_content: str, metadata: Dict[str, Any]) -> Path:
        """Save a validated snippet with its metadata."""
        snippets_dir = video_dir / 'validated_snippets'
        snippets_dir.mkdir(exist_ok=True)
        
        # Save snippet code
        snippet_file = snippets_dir / f"{scene_name}.py"
        with open(snippet_file, 'w', encoding='utf-8') as f:
            f.write(snippet_content)
            
        # Save metadata
        meta_file = snippets_dir / f"{scene_name}_metadata.json"
        with open(meta_file, 'w', encoding='utf-8') as f:
            json.dump({
                'scene_name': scene_name,
                'dependencies': metadata.get('dependencies', {}),
                'validation': metadata.get('validation', {}),
                'claude_fixes': metadata.get('claude_fixes', 0),
                'processing_time': metadata.get('metadata', {}).get('processing_time', 0)
            }, f, indent=2)
            
        return snippet_file
        
    def _create_combined_file(self, video_dir: Path, scene_results: Dict[str, Any]) -> Optional[Path]:
        """Create a combined ManimCE file from all validated snippets."""
        try:
            # Use scene combiner to create the final file
            snippets = {}
            for scene_name, result in scene_results.items():
                if result.get('success') and result.get('snippet'):
                    snippets[scene_name] = result['snippet']
                    
            if not snippets:
                return None
                
            # Combine snippets
            combined_content = self.scene_combiner.combine_snippets(
                snippets, video_name=video_dir.name
            )
            
            # Save combined file
            output_file = video_dir / 'manimce_code.py'
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(combined_content)
                
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to create combined file: {e}")
            return None
            
    def _save_conversion_results(self, video_dir: Path, results: Dict[str, Any]):
        """Save detailed conversion results for the video."""
        results_file = video_dir / 'conversion_results.json'
        
        # Prepare serializable results
        save_results = {
            'video_name': results['video_name'],
            'status': results['status'],
            'snippets_created': results['snippets_created'],
            'all_scenes_valid': results['all_scenes_valid'],
            'combined_file': results['combined_file'],
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'scenes_summary': {}
        }
        
        # Add scene summaries
        for scene_name, scene_result in results['scenes'].items():
            save_results['scenes_summary'][scene_name] = {
                'success': scene_result.get('success', False),
                'dependencies': scene_result.get('dependencies', {}),
                'validation': {
                    'precompile': scene_result.get('validation', {}).get('precompile', {}).get('success', False),
                    'render': scene_result.get('validation', {}).get('render', {}).get('success', False)
                },
                'claude_fixes': scene_result.get('claude_fixes', 0),
                'errors': scene_result.get('errors', [])
            }
            
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(save_results, f, indent=2)
            
    def get_statistics(self) -> Dict[str, Any]:
        """Get current conversion statistics."""
        stats = self.stats.copy()
        
        # Calculate success rates
        if stats['total_scenes'] > 0:
            stats['scene_success_rate'] = stats['successful_scenes'] / stats['total_scenes']
        else:
            stats['scene_success_rate'] = 0
            
        if stats['total_videos'] > 0:
            stats['video_success_rate'] = stats['videos_with_all_scenes_valid'] / stats['total_videos']
        else:
            stats['video_success_rate'] = 0
            
        if stats['claude_fixes_attempted'] > 0:
            stats['claude_fix_success_rate'] = stats['claude_fixes_successful'] / stats['claude_fixes_attempted']
        else:
            stats['claude_fix_success_rate'] = 0
            
        if stats['successful_scenes'] > 0:
            stats['avg_dependencies_per_scene'] = stats['total_dependencies_found'] / stats['successful_scenes']
        else:
            stats['avg_dependencies_per_scene'] = 0
            
        return stats


def integrate_with_pipeline(pipeline_builder, year: int, video_filter: Optional[List[str]] = None,
                          force: bool = False) -> Dict[str, Any]:
    """
    Integration function to use with existing build_dataset_pipeline.py
    
    This function replaces the run_conversion_stage method functionality.
    """
    logger.info("=== Using Integrated Pipeline Converter ===")
    
    # Initialize the integrated converter
    converter = IntegratedPipelineConverter(
        base_dir=pipeline_builder.base_dir,
        verbose=pipeline_builder.verbose,
        enable_render_validation=pipeline_builder.enable_render_validation,
        enable_precompile_validation=pipeline_builder.enable_precompile_validation,
        render_max_attempts=pipeline_builder.render_max_attempts,
        max_workers=4
    )
    
    # If force=True, reset all conversion statuses for the year before starting
    if force:
        logger.info("Force conversion enabled - resetting all video conversion statuses...")
        reset_conversion_status(pipeline_builder.base_dir, year, video_filter)
    
    # Get list of videos to process
    year_dir = pipeline_builder.output_dir / str(year)
    if not year_dir.exists():
        logger.warning(f"No output directory for year {year}")
        return {'status': 'no_videos', 'stats': converter.get_statistics()}
        
    # Process each video
    video_dirs = [d for d in year_dir.iterdir() if d.is_dir()]
    if video_filter:
        video_dirs = [d for d in video_dirs if d.name in video_filter]
        
    logger.info(f"Processing {len(video_dirs)} videos")
    
    all_results = {}
    for i, video_dir in enumerate(video_dirs, 1):
        if converter.verbose:
            print(f"\n{'='*80}")
            print(f"📁 Video {i}/{len(video_dirs)}: {video_dir.name}")
            print(f"{'='*80}")
        logger.info(f"Converting video: {video_dir.name}")
        # Check if already converted (unless forcing)
        if not force:
            manimce_file = video_dir / 'manimce_code.py'
            snippets_dir = video_dir / 'validated_snippets'
            if manimce_file.exists() and snippets_dir.exists():
                logger.info(f"Skipping {video_dir.name} - already converted")
                continue
                
        # Convert the video
        result = converter.convert_video(video_dir)
        all_results[video_dir.name] = result
        
        # Log progress
        if converter.verbose:
            success_count = sum(1 for s in result.get('scenes', {}).values() 
                              if isinstance(s, dict) and s.get('success', False))
            total_scenes = len(result.get('scenes', {}))
            print(f"\n📊 Video {video_dir.name} Summary:")
            print(f"   ✅ {success_count}/{total_scenes} scenes successful")
            print(f"   📄 {result['snippets_created']} snippets created")
            print(f"   🎯 Status: {result['status']}")
            if result.get('errors'):
                print(f"   ⚠️  {len(result['errors'])} errors occurred")
            print(f"   📁 Combined file: {'✅' if result.get('combined_file') else '❌'}")
        
        logger.info(f"Converted {video_dir.name}: {result['snippets_created']} snippets created, "
                   f"status: {result['status']}")
        
    # Get final statistics
    stats = converter.get_statistics()
    
    # Clean all_results to remove non-serializable objects
    cleaned_results = {}
    for video_name, video_result in all_results.items():
        cleaned_video_result = {
            'video_name': video_result.get('video_name'),
            'status': video_result.get('status'),
            'snippets_created': video_result.get('snippets_created'),
            'all_scenes_valid': video_result.get('all_scenes_valid'),
            'combined_file': video_result.get('combined_file'),
            'errors': video_result.get('errors', []),
            'scene_count': len(video_result.get('scenes', {})),
            'scenes': {}
        }
        
        # Clean scene results
        for scene_name, scene_data in video_result.get('scenes', {}).items():
            if isinstance(scene_data, dict):
                cleaned_scene = {
                    'success': scene_data.get('success', False),
                    'snippet_path': scene_data.get('snippet_path'),
                    'validation': {
                        'precompile': scene_data.get('validation', {}).get('precompile', {}).get('success', False),
                        'render': scene_data.get('validation', {}).get('render', {}).get('success', False)
                    },
                    'dependencies': {
                        'functions': scene_data.get('dependencies', {}).get('functions', 0),
                        'classes': scene_data.get('dependencies', {}).get('classes', 0),
                        'constants': scene_data.get('dependencies', {}).get('constants', 0)
                    },
                    'claude_fixes_applied': scene_data.get('claude_fixes_applied', 0)
                }
                cleaned_video_result['scenes'][scene_name] = cleaned_scene
                
        cleaned_results[video_name] = cleaned_video_result
    
    # Create summary
    summary = {
        'year': year,
        'stats': stats,
        'videos': cleaned_results,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Save summary
    summary_file = pipeline_builder.output_dir / f'integrated_conversion_summary_{year}.json'
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
        
    logger.info(f"""
Integrated Conversion Complete:
- Videos processed: {stats['total_videos']}
- Total scenes: {stats['total_scenes']}
- Successful scenes: {stats['successful_scenes']} ({stats['scene_success_rate']:.1%})
- Videos with all scenes valid: {stats['videos_with_all_scenes_valid']} ({stats['video_success_rate']:.1%})
- Claude fixes: {stats['claude_fixes_successful']}/{stats['claude_fixes_attempted']} ({stats['claude_fix_success_rate']:.1%})
- Average dependencies per scene: {stats['avg_dependencies_per_scene']:.1f}
""")
    
    return summary


if __name__ == "__main__":
    # Test the integrated converter
    import argparse
    
    parser = argparse.ArgumentParser(description="Test integrated pipeline converter")
    parser.add_argument("video_dir", help="Path to video directory to convert")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    converter = IntegratedPipelineConverter(
        base_dir=Path(args.video_dir).parent.parent,
        verbose=args.verbose
    )
    
    result = converter.convert_video(Path(args.video_dir))
    
    print(f"\nConversion result: {result['status']}")
    print(f"Snippets created: {result['snippets_created']}")
    print(f"All scenes valid: {result['all_scenes_valid']}")
    
    if result['errors']:
        print(f"Errors: {result['errors']}")