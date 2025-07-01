#!/usr/bin/env python3
"""
Orchestration script for building the 3Blue1Brown dataset.
This script coordinates the entire pipeline:
1. Match videos to code files
2. Clean and inline the matched code
3. Convert from ManimGL to ManimCE
4. Render videos (optional)
5. Compare with YouTube videos (future)
"""


# Automatically enable enhanced prompts for better performance
try:
    import auto_enable_enhanced_prompts
except ImportError:
    # Enhanced prompts not available, continue with standard prompts
    pass

import json
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional
import subprocess
import sys
import warnings
from io import StringIO
import contextlib

# Import the components
sys.path.append(str(Path(__file__).parent))
from claude_match_videos import ClaudeVideoMatcher
# Import hybrid cleaner (programmatic + Claude fallback)
from hybrid_cleaner import HybridCleaner
# Import parameterized scene converter for automatic conversion
from parameterized_scene_converter import ParameterizedSceneConverter
# ManimConverter removed - using integrated converter only
from render_videos import VideoRenderer
from manimce_precompile_validator import ManimCEPrecompileValidator
from conversion_error_collector import collect_conversion_error, get_error_collector
from generate_comparison_report import ComparisonReportGenerator
from scene_validator import SceneValidator

@contextlib.contextmanager
def capture_syntax_warnings():
    """Context manager to capture syntax warnings and return them."""
    captured_warnings = []
    
    def custom_warn(message, category=UserWarning, filename='', lineno=-1, file=None, line=None):
        if category == SyntaxWarning:
            captured_warnings.append(str(message))
        else:
            # Let other warnings through normally
            original_warn(message, category, filename, lineno, file, line)
    
    original_warn = warnings.showwarning
    warnings.showwarning = custom_warn
    
    try:
        yield captured_warnings
    finally:
        warnings.showwarning = original_warn

class DatasetPipelineBuilder:
    def __init__(self, base_dir: str, verbose: bool = False, timeout_multiplier: float = 1.0, 
                 max_retries: int = 3, enable_render_validation: bool = True, 
                 render_max_attempts: int = 3, use_advanced_converter: bool = True,
                 enable_precompile_validation: bool = True, auto_fix_precompile: bool = True,
                 cleaning_mode: str = 'hybrid', conversion_mode: str = 'scene',
                 parallel_render_workers: int = 1, use_systematic_converter: bool = True,
                 enable_unfixable_skipping: bool = True, monitor_unfixable_only: bool = False,
                 min_conversion_confidence: float = 0.8):
        self.base_dir = Path(base_dir)
        self.output_dir = self.base_dir / 'outputs'
        self.verbose = verbose
        self.timeout_multiplier = timeout_multiplier
        self.max_retries = max_retries
        self.enable_render_validation = enable_render_validation
        self.render_max_attempts = render_max_attempts
        self.use_advanced_converter = use_advanced_converter
        self.enable_precompile_validation = enable_precompile_validation
        self.auto_fix_precompile = auto_fix_precompile
        self.cleaning_mode = cleaning_mode
        self.conversion_mode = conversion_mode
        self.use_systematic_converter = use_systematic_converter
        self.enable_unfixable_skipping = enable_unfixable_skipping
        self.monitor_unfixable_only = monitor_unfixable_only
        self.min_conversion_confidence = min_conversion_confidence
        
        # Intelligent hybrid parsing strategy
        self.intelligent_parsing = True  # Always use smart hybrid approach
        
        # Initialize components
        self.matcher = ClaudeVideoMatcher(base_dir, verbose)
        self.cleaner = HybridCleaner(base_dir, verbose, timeout_multiplier=timeout_multiplier, max_retries=max_retries)
        self.param_converter = ParameterizedSceneConverter(verbose=verbose)
        self.renderer = VideoRenderer(base_dir, verbose, parallel_render_workers)
        self.validator = ManimCEPrecompileValidator(verbose=verbose)
        self.scene_validator = SceneValidator(verbose=verbose)
        self.comparison_generator = ComparisonReportGenerator(base_dir, verbose)
        # ManimConverter will be initialized when needed with proper paths
        
        # Setup organized logging structure
        self.logs_dir = self.output_dir / 'logs'
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Archive directory for old pipeline reports
        self.archive_dir = self.logs_dir / 'archive'
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure logger with lazy file creation
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file = self.logs_dir / f"pipeline_{self.timestamp}.log"
        self.log_file_created = False
        
        # Also create a consolidated log file for the year
        self.consolidated_log_file = self.logs_dir / 'pipeline_history.jsonl'
        
        # Setup basic logging without file handler initially
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler() if verbose else logging.NullHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.verbose = verbose
        
        # Override logger methods to ensure file creation when needed
        self._original_info = self.logger.info
        self._original_warning = self.logger.warning
        self._original_error = self.logger.error
        self._original_debug = self.logger.debug
        self._original_critical = self.logger.critical
        
        self.logger.info = lambda msg, *args, **kwargs: self._log_with_file_creation(self._original_info, msg, *args, **kwargs)
        self.logger.warning = lambda msg, *args, **kwargs: self._log_with_file_creation(self._original_warning, msg, *args, **kwargs)
        self.logger.error = lambda msg, *args, **kwargs: self._log_with_file_creation(self._original_error, msg, *args, **kwargs)
        self.logger.debug = lambda msg, *args, **kwargs: self._log_with_file_creation(self._original_debug, msg, *args, **kwargs)
        self.logger.critical = lambda msg, *args, **kwargs: self._log_with_file_creation(self._original_critical, msg, *args, **kwargs)
        
        # Pipeline state tracking
        self.pipeline_state = {
            'start_time': None,
            'end_time': None,
            'stages': {
                'matching': {'status': 'pending', 'stats': {}},
                'cleaning': {'status': 'pending', 'stats': {}},
                'conversion': {'status': 'pending', 'stats': {}},
                'rendering': {'status': 'pending', 'stats': {}},
            }
        }
        
        # Collect syntax warnings for cleaner output
        self.collected_warnings = []
        
    def _ensure_log_file(self):
        """Create log file handler only when we actually need to log something."""
        if not self.log_file_created:
            # Add file handler to existing logger
            file_handler = logging.FileHandler(self.log_file)
            file_handler.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            self.log_file_created = True
    
    def _log_with_file_creation(self, original_method, msg, *args, **kwargs):
        """Wrapper that ensures log file is created before logging."""
        self._ensure_log_file()
        return original_method(msg, *args, **kwargs)
    
    def save_video_log(self, video_dir: Path, stage: str, log_data: Dict):
        """Save stage-specific log data to the video's logs.json file."""
        log_file = video_dir / '.pipeline' / 'logs' / 'logs.json'
        
        # Ensure directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing logs if file exists
        logs = {}
        if log_file.exists():
            try:
                with open(log_file, 'r') as f:
                    content = f.read()
                    if content.strip():  # Only parse if file is not empty
                        logs = json.loads(content)
            except (json.JSONDecodeError, ValueError) as e:
                self.logger.warning(f"Corrupted logs.json for {video_dir.name}, creating new one: {e}")
                # Backup corrupted file
                backup_file = log_file.with_suffix('.json.corrupted')
                if log_file.exists():
                    log_file.rename(backup_file)
                logs = {}
        
        # Add or update the stage log
        logs[stage] = {
            'timestamp': datetime.now().isoformat(),
            'data': log_data
        }
        
        # Save updated logs with atomic write
        temp_file = log_file.with_suffix('.json.tmp')
        try:
            with open(temp_file, 'w') as f:
                json.dump(logs, f, indent=2)
            # Atomic rename
            temp_file.replace(log_file)
        except Exception as e:
            self.logger.error(f"Failed to save logs for {video_dir.name}: {e}")
            if temp_file.exists():
                temp_file.unlink()
            raise
    
    def load_excluded_videos(self) -> List[str]:
        """Load list of videos to exclude from processing."""
        excluded_file = self.base_dir / 'excluded-videos.txt'
        excluded_ids = []
        
        if not excluded_file.exists():
            self.logger.warning("No excluded-videos.txt file found.")
            return excluded_ids
        
        import re
        with open(excluded_file, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and header lines
                if not line or line.startswith('We should') or line.startswith('List of'):
                    continue
                
                # Extract video ID from lines like "- title https://..."
                if line.startswith('- '):
                    # Extract URL
                    url_match = re.search(r'https://[^\s]+', line)
                    if url_match:
                        url = url_match.group(0)
                        # Extract video ID from URL
                        video_id_match = re.search(r'[?&]v=([a-zA-Z0-9_-]+)', url)
                        if video_id_match:
                            video_id = video_id_match.group(1)
                            excluded_ids.append(video_id)
                        
        self.logger.info(f"Loaded {len(excluded_ids)} excluded video IDs")
        return excluded_ids
        
    def should_process_video(self, caption_dir: str, match_data: Dict, 
                           excluded_videos: List[str]) -> tuple[bool, str]:
        """Determine if a video should be processed through the pipeline."""
        video_id = match_data.get('video_id', '')
        
        # Check if video is excluded
        if video_id in excluded_videos or caption_dir in excluded_videos:
            return False, "Video is in excluded list"
            
        # Check match status
        status = match_data.get('status', '')
        if status == 'no_transcript':
            return False, "No transcript available"
            
        # Check confidence
        confidence = match_data.get('confidence_score', 0)
        if confidence < 0.8:
            return False, f"Low confidence score: {confidence}"
            
        # Check if files were found
        primary_files = match_data.get('primary_files', [])
        if not primary_files:
            return False, "No primary files found"
            
        return True, "Ready for processing"
    
    def preprocess_parameterized_scenes(self, year: int, video_filter: Optional[List[str]] = None) -> Dict[str, Any]:
        """Preprocess files to automatically convert parameterized scenes before cleaning."""
        self.logger.info("Preprocessing parameterized scenes...")
        
        preprocessing_stats = {
            'total_files_checked': 0,
            'parameterized_files_found': 0,
            'files_converted': 0,
            'conversion_failures': 0,
            'total_parameters_converted': 0,
            'converted_classes': []
        }
        
        year_dir = self.output_dir / str(year)
        if not year_dir.exists():
            self.logger.warning(f"No output directory found for year {year}")
            return preprocessing_stats
        
        for video_dir in year_dir.iterdir():
            if not video_dir.is_dir():
                continue
                
            # Apply video filter if specified
            if video_filter and video_dir.name not in video_filter:
                continue
            
            # Look for matched files to preprocess
            matches_file = video_dir / '.pipeline' / 'source' / 'matches.json'
            if not matches_file.exists():
                continue
                
            try:
                with open(matches_file) as f:
                    match_data = json.load(f)
            except (json.JSONDecodeError, ValueError) as e:
                self.logger.warning(f"Corrupted matches.json for {video_dir.name}, skipping: {e}")
                continue
                    
            primary_files = match_data.get('primary_files', [])
            try:
                for file_path_str in primary_files:
                    # Handle both string format and dict format for primary_files
                    if isinstance(file_path_str, dict):
                        file_path = Path(file_path_str['file_path'])
                    else:
                        # Convert relative path to absolute path from base_dir
                        file_path = self.base_dir / file_path_str
                    
                    if not file_path.exists():
                        continue
                        
                    preprocessing_stats['total_files_checked'] += 1
                        
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Check if file has parameterized scenes
                        if self.param_converter.is_parameterized_scene(content):
                            preprocessing_stats['parameterized_files_found'] += 1
                            
                            self.logger.info(f"Converting parameterized scenes in {file_path}")
                            
                            # Convert the file
                            converted_content, success, conversion_info = self.param_converter.convert_file_content(
                                content, str(file_path)
                            )
                            
                            if success:
                                # Validate the conversion
                                validation = self.param_converter.validate_conversion(content, converted_content)
                                
                                if validation['syntax_valid'] and not validation['issues']:
                                    # Save the converted file
                                    backup_path = file_path.with_suffix(f'{file_path.suffix}.original')
                                    if not backup_path.exists():
                                        # Create backup of original
                                        with open(backup_path, 'w', encoding='utf-8') as f:
                                            f.write(content)
                                    
                                    # Write converted content
                                    with open(file_path, 'w', encoding='utf-8') as f:
                                        f.write(converted_content)
                                    
                                    preprocessing_stats['files_converted'] += 1
                                    preprocessing_stats['total_parameters_converted'] += conversion_info.get('total_parameters', 0)
                                    preprocessing_stats['converted_classes'].extend(conversion_info.get('converted_classes', []))
                                    
                                    # Log the conversion details
                                    self.save_video_log(video_dir, 'parameterized_conversion', {
                                        'file_path': str(file_path),
                                        'converted_classes': conversion_info.get('converted_classes', []),
                                        'total_parameters': conversion_info.get('total_parameters', 0),
                                        'validation': validation
                                    })
                                    
                                    self.logger.info(f"Successfully converted {len(conversion_info.get('converted_classes', []))} classes")
                                else:
                                    self.logger.warning(f"Conversion validation failed for {file_path}: {validation['issues']}")
                                    preprocessing_stats['conversion_failures'] += 1
                            else:
                                self.logger.warning(f"Failed to convert parameterized scenes in {file_path}: {conversion_info}")
                                preprocessing_stats['conversion_failures'] += 1
                                
                    except Exception as e:
                        self.logger.error(f"Error processing {file_path}: {e}")
                        preprocessing_stats['conversion_failures'] += 1
            
            # This except should be at the video level, not inside the file loop
            except Exception as e:
                self.logger.error(f"Error processing video {video_dir.name}: {e}")
                continue
        # Log summary statistics
        self.logger.info(f"Parameterized scene preprocessing complete:")
        self.logger.info(f"  Files checked: {preprocessing_stats['total_files_checked']}")
        self.logger.info(f"  Parameterized files found: {preprocessing_stats['parameterized_files_found']}")
        self.logger.info(f"  Files successfully converted: {preprocessing_stats['files_converted']}")
        self.logger.info(f"  Conversion failures: {preprocessing_stats['conversion_failures']}")
        self.logger.info(f"  Total parameters converted: {preprocessing_stats['total_parameters_converted']}")
        
        if preprocessing_stats['converted_classes']:
            self.logger.info(f"  Converted classes: {', '.join(set(preprocessing_stats['converted_classes']))}")
        
        return preprocessing_stats
        
    def ensure_video_mappings(self, year: int) -> bool:
        """Ensure video mappings exist for the given year, creating them if needed."""
        mappings_file = self.base_dir / 'data' / 'youtube_metadata' / f'{year}_video_mappings.json'
        
        if mappings_file.exists():
            return True
            
        self.logger.info(f"Video mappings for {year} not found. Generating them now...")
        
        # Check if captions directory exists for this year
        captions_dir = self.base_dir / 'data' / 'captions' / str(year)
        if not captions_dir.exists():
            self.logger.error(f"No captions directory found for {year} at {captions_dir}")
            self.logger.error("Please ensure the captions repository is cloned and contains data for this year.")
            return False
            
        # Run extract_video_urls.py
        extract_script = self.base_dir / 'scripts' / 'extract_video_urls.py'
        cmd = [sys.executable, str(extract_script), '--year', str(year)]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.logger.info("Video mappings generated successfully")
            if self.verbose:
                self.logger.info(f"Output: {result.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to generate video mappings: {e}")
            if e.stderr:
                self.logger.error(f"Error output: {e.stderr}")
            return False

    def run_matching_stage(self, year: int, force: bool = False, video_filter: Optional[List[str]] = None) -> Dict:
        """Run the video matching stage."""
        if not self.verbose:
            print("[MATCH] Processing videos...", end='', flush=True)
        else:
            print("\n📊 Stage 1: Video Matching")
        self.logger.info("Starting video matching stage")
        
        self.pipeline_state['stages']['matching']['status'] = 'running'
        self.pipeline_state['stages']['matching']['start_time'] = datetime.now().isoformat()
        
        # Check if matching has already been done
        summary_file = self.output_dir / f'matching_summary_{year}.json'
        if summary_file.exists() and not force:
            self.logger.info(f"Found existing matching results at {summary_file}")
            try:
                with open(summary_file) as f:
                    existing_summary = json.load(f)
                    
                self.logger.info("Using existing matching results. Use --force-match to re-run.")
                self.pipeline_state['stages']['matching']['status'] = 'skipped'
                self.pipeline_state['stages']['matching']['stats'] = existing_summary.get('stats', {})
                return existing_summary.get('results', {})
            except (json.JSONDecodeError, ValueError) as e:
                self.logger.warning(f"Corrupted summary file {summary_file}, will re-run matching: {e}")
                # Continue with matching process
        
        # Ensure video mappings exist
        if not self.ensure_video_mappings(year):
            raise RuntimeError(f"Cannot proceed without video mappings for {year}")
                
        # Run matching
        self.logger.info(f"Running video matching for year {year}")
        if video_filter:
            self.logger.info(f"Filtering to videos: {video_filter}")
        results = self.matcher.match_all_videos(year=year, video_filter=video_filter)
        
        # Save results
        summary = self.matcher.save_final_results(results, year)
        
        self.pipeline_state['stages']['matching']['status'] = 'completed'
        self.pipeline_state['stages']['matching']['end_time'] = datetime.now().isoformat()
        self.pipeline_state['stages']['matching']['stats'] = {
            'total_videos': summary['total_videos'],
            'successful_matches': summary['successful_matches'],
            'low_confidence_matches': summary['low_confidence_matches'],
            'failed_matches': summary['failed_matches'],
            'skipped_videos': summary['skipped_videos']
        }
        
        # Print completion message
        if not self.verbose:
            print(f" ✓ ({summary['successful_matches']}/{summary['total_videos']} matched)")
        
        return results
        
    def validate_cleaned_files(self, year: int) -> Dict[str, bool]:
        """Validate syntax of all cleaned files after cleaning stage."""
        validation_results = {}
        year_dir = self.output_dir / str(year)
        
        if not year_dir.exists():
            return validation_results
            
        for video_dir in year_dir.iterdir():
            if video_dir.is_dir():
                cleaned_file = video_dir / '.pipeline' / 'intermediate' / 'monolith_manimgl.py'
                if cleaned_file.exists():
                    try:
                        with open(cleaned_file, 'r') as f:
                            code = f.read()
                        compile(code, str(cleaned_file), 'exec')
                        validation_results[video_dir.name] = True
                    except SyntaxError as e:
                        self.logger.error(f"Syntax error in cleaned file {video_dir.name}: {e}")
                        validation_results[video_dir.name] = False
                        # Log detailed error information
                        self.save_video_log(video_dir, 'cleaning_syntax_error', {
                            'error': str(e),
                            'line': e.lineno,
                            'text': e.text,
                            'offset': e.offset
                        })
        
        return validation_results
    
    def validate_cleaned_scenes(self, year: int) -> Dict[str, Dict]:
        """Validate all cleaned scenes before conversion stage."""
        validation_summary = {
            'total_videos': 0,
            'validated_videos': 0,
            'failed_videos': 0,
            'scene_validation_results': {}
        }
        
        year_dir = self.output_dir / str(year)
        if not year_dir.exists():
            return validation_summary
        
        self.logger.info("Validating cleaned scenes before conversion...")
        
        for video_dir in year_dir.iterdir():
            if not video_dir.is_dir():
                continue
                
            scenes_dir = video_dir / 'cleaned_scenes'
            if not scenes_dir.exists():
                # Check if monolithic cleaned file exists
                cleaned_file = video_dir / '.pipeline' / 'intermediate' / 'monolith_manimgl.py'
                if cleaned_file.exists():
                    # Validate monolithic file
                    result = self.scene_validator.validate_scene_file(cleaned_file)
                    validation_summary['scene_validation_results'][video_dir.name] = {
                        'mode': 'monolithic',
                        'is_valid': result.is_valid,
                        'issues': [{'severity': i.severity, 'type': i.issue_type, 'message': i.message} 
                                  for i in result.issues]
                    }
                    validation_summary['total_videos'] += 1
                    if result.is_valid:
                        validation_summary['validated_videos'] += 1
                    else:
                        validation_summary['failed_videos'] += 1
                continue
            
            # Validate scene-by-scene cleaned files
            self.logger.info(f"Validating scenes in {video_dir.name}...")
            scene_results = self.scene_validator.validate_scene_directory(scenes_dir)
            
            # Aggregate results
            all_valid = all(r.is_valid for r in scene_results.values())
            total_issues = sum(len(r.issues) for r in scene_results.values())
            
            validation_summary['scene_validation_results'][video_dir.name] = {
                'mode': 'scene',
                'total_scenes': len(scene_results),
                'valid_scenes': sum(1 for r in scene_results.values() if r.is_valid),
                'is_valid': all_valid,
                'total_issues': total_issues,
                'scene_details': {
                    name: {
                        'is_valid': result.is_valid,
                        'issues': [{'severity': i.severity, 'type': i.issue_type, 'message': i.message} 
                                  for i in result.issues]
                    }
                    for name, result in scene_results.items()
                }
            }
            
            validation_summary['total_videos'] += 1
            if all_valid:
                validation_summary['validated_videos'] += 1
            else:
                validation_summary['failed_videos'] += 1
                
            # Save validation report for this video
            if total_issues > 0:
                report = self.scene_validator.generate_validation_report(scene_results)
                report_file = video_dir / 'scene_validation_report.txt'
                with open(report_file, 'w') as f:
                    f.write(report)
                    
                self.logger.warning(f"{video_dir.name}: {total_issues} validation issues found, report saved")
        
        # Save overall validation summary
        summary_file = self.logs_dir / f'scene_validation_summary_{year}.json'
        temp_file = summary_file.with_suffix('.json.tmp')
        try:
            with open(temp_file, 'w') as f:
                json.dump(validation_summary, f, indent=2)
            temp_file.replace(summary_file)
        except Exception as e:
            self.logger.error(f"Failed to save validation summary: {e}")
            if temp_file.exists():
                temp_file.unlink()
            raise
            
        self.logger.info(f"Scene validation complete: {validation_summary['validated_videos']}/{validation_summary['total_videos']} videos passed")
        
        return validation_summary
    
    def optimize_cleaning_summary(self, summary: Dict) -> Dict:
        """Optimize cleaning summary by removing redundant data and adding useful metrics."""
        import re
        from collections import defaultdict
        
        # Initialize aggregate statistics
        aggregated_stats = {
            'total_cleaning_time': 0,
            'total_attempts': 0,
            'scene_count': 0,
            'complexity_distribution': defaultdict(int),
            'validation_errors': defaultdict(int),
            'scene_sizes': [],
            'avg_time_per_scene': 0
        }
        
        # Process results to remove redundant data and calculate metrics
        optimized_results = {}
        
        for video_name, video_data in summary.get('results', {}).items():
            if not isinstance(video_data, dict):
                optimized_results[video_name] = video_data
                continue
                
            # Create optimized video entry
            optimized_video = {
                'status': video_data.get('status', 'unknown'),
                'reason': video_data.get('reason', '')
            }
            
            # Process scene-by-scene results
            if 'scenes' in video_data:
                optimized_scenes = {}
                total_video_time = 0
                
                for scene_name, scene_data in video_data.get('scenes', {}).items():
                    if not isinstance(scene_data, dict):
                        optimized_scenes[scene_name] = scene_data
                        continue
                        
                    # Remove redundant file paths - they can be reconstructed
                    elapsed_time = scene_data.get('elapsed_time', 0)
                    optimized_scene = {
                        'status': scene_data.get('status', 'unknown'),
                        'time': round(elapsed_time, 2),
                        'attempts': scene_data.get('attempts', 1),
                        'validation': scene_data.get('validation', 'unknown')
                    }
                    
                    # Add validation error summary if present
                    if 'validation_error' in scene_data:
                        error_msg = scene_data['validation_error']
                        # Truncate long error messages
                        optimized_scene['error_summary'] = error_msg[:100] + '...' if len(error_msg) > 100 else error_msg
                        
                        # Categorize error type
                        error_type = 'other'
                        if 'syntax' in error_msg.lower():
                            error_type = 'syntax'
                        elif 'import' in error_msg.lower():
                            error_type = 'import'
                        elif 'name' in error_msg.lower() and 'not defined' in error_msg.lower():
                            error_type = 'undefined_name'
                        aggregated_stats['validation_errors'][error_type] += 1
                    
                    # Update aggregate statistics
                    aggregated_stats['total_cleaning_time'] += elapsed_time
                    aggregated_stats['total_attempts'] += optimized_scene['attempts']
                    aggregated_stats['scene_count'] += 1
                    total_video_time += elapsed_time
                    
                    # Try to calculate scene metrics if file exists
                    scene_file = self.output_dir / str(video_data.get('year', summary.get('year'))) / video_name / 'cleaned_scenes' / f'{scene_name}.py'
                    if scene_file.exists():
                        try:
                            with open(scene_file, 'r') as f:
                                content = f.read()
                            lines = len(content.splitlines())
                            size_kb = round(len(content) / 1024, 2)
                            
                            # Count animations and objects
                            animations = len(re.findall(r'\.animate\(|\.play\(|self\.play\(', content))
                            tex_objects = len(re.findall(r'(?:Tex|MathTex|Text)\s*\(', content))
                            mobjects = len(re.findall(r'(?:Circle|Square|Dot|Arrow|Line|Rectangle|Polygon)\s*\(', content))
                            
                            optimized_scene['metrics'] = {
                                'lines': lines,
                                'size_kb': size_kb,
                                'animations': animations,
                                'complexity': 'simple' if lines < 50 else 'medium' if lines < 150 else 'complex'
                            }
                            
                            aggregated_stats['complexity_distribution'][optimized_scene['metrics']['complexity']] += 1
                            aggregated_stats['scene_sizes'].append(lines)
                        except Exception:
                            pass
                    
                    optimized_scenes[scene_name] = optimized_scene
                
                optimized_video['scenes'] = optimized_scenes
                optimized_video['total_scenes'] = len(optimized_scenes)
                optimized_video['cleaned_scenes'] = video_data.get('cleaned_scenes', 0)
                optimized_video['failed_scenes'] = video_data.get('failed_scenes', 0)
                optimized_video['total_time'] = round(total_video_time, 2)
                optimized_video['combine_success'] = video_data.get('combine_success', False)
                
                # Add relationship summary if available
                if 'relationship_analysis' in video_data:
                    rel = video_data['relationship_analysis']
                    optimized_video['relationships'] = {
                        'total': rel.get('total_relationships', 0),
                        'shared_objects': rel.get('shared_objects', 0)
                    }
            
            optimized_results[video_name] = optimized_video
        
        # Calculate final aggregate statistics
        if aggregated_stats['scene_count'] > 0:
            aggregated_stats['avg_time_per_scene'] = round(
                aggregated_stats['total_cleaning_time'] / aggregated_stats['scene_count'], 2
            )
            aggregated_stats['avg_scene_size'] = round(
                sum(aggregated_stats['scene_sizes']) / len(aggregated_stats['scene_sizes'])
            ) if aggregated_stats['scene_sizes'] else 0
        
        # Clean up temporary data
        del aggregated_stats['scene_sizes']
        aggregated_stats['total_cleaning_time'] = round(aggregated_stats['total_cleaning_time'], 2)
        aggregated_stats['complexity_distribution'] = dict(aggregated_stats['complexity_distribution'])
        aggregated_stats['validation_errors'] = dict(aggregated_stats['validation_errors'])
        
        # Create optimized summary
        optimized_summary = {
            'year': summary.get('year'),
            'timestamp': summary.get('timestamp'),
            'stats': summary.get('stats', {}),
            'results': optimized_results,
            'aggregated_stats': aggregated_stats
        }
        
        # Add scene validation summary if present
        if 'scene_validation' in summary:
            optimized_summary['scene_validation'] = summary['scene_validation']
        
        return optimized_summary
    
    def generate_cleaning_report(self, summary: Dict, output_file: Optional[Path] = None) -> str:
        """Generate a human-readable cleaning report from the optimized summary."""
        agg_stats = summary.get('aggregated_stats', {})
        stats = summary.get('stats', {})
        
        report = f"""
Cleaning Summary Report - Year {summary.get('year')}
{'=' * 60}

Overall Statistics:
- Total videos matched: {stats.get('total_matched', 0)}
- Successfully cleaned: {stats.get('cleaned', 0)}
- Failed: {stats.get('failed', 0)}
- Skipped: {stats.get('skipped', 0)} (Low confidence: {stats.get('low_confidence', 0)}, No files: {stats.get('no_files', 0)})
"""
        
        if stats.get('total_matched', 0) > 0:
            success_rate = (stats.get('cleaned', 0) / stats['total_matched']) * 100
            report += f"- Overall success rate: {success_rate:.1f}%\n"
        
        if agg_stats:
            report += f"""
Performance Metrics:
- Total scenes processed: {agg_stats.get('scene_count', 0)}
- Total cleaning time: {agg_stats.get('total_cleaning_time', 0):.1f} seconds
- Average time per scene: {agg_stats.get('avg_time_per_scene', 0):.1f} seconds
- Average scene size: {agg_stats.get('avg_scene_size', 0)} lines
- Total retry attempts: {agg_stats.get('total_attempts', 0)}
"""
            
            if agg_stats.get('complexity_distribution'):
                report += "\nScene Complexity Distribution:\n"
                for complexity, count in sorted(agg_stats['complexity_distribution'].items()):
                    report += f"- {complexity.capitalize()}: {count} scenes\n"
            
            if agg_stats.get('validation_errors'):
                report += "\nValidation Errors:\n"
                for error_type, count in sorted(agg_stats['validation_errors'].items(), 
                                              key=lambda x: x[1], reverse=True):
                    report += f"- {error_type}: {count} occurrences\n"
        
        # Add problem videos section
        problem_videos = []
        for video_name, video_data in summary.get('results', {}).items():
            if isinstance(video_data, dict) and video_data.get('status') == 'error':
                problem_videos.append((video_name, video_data.get('reason', 'Unknown error')))
        
        if problem_videos:
            report += f"\nProblem Videos ({len(problem_videos)}):\n"
            for video, reason in problem_videos[:10]:  # Show first 10
                report += f"- {video}: {reason}\n"
            if len(problem_videos) > 10:
                report += f"... and {len(problem_videos) - 10} more\n"
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report)
        
        return report
    
    def run_cleaning_stage(self, year: int, force: bool = False, video_filter: Optional[List[str]] = None) -> Dict:
        """Run the code cleaning stage."""
        if not self.verbose:
            print("[CLEAN] Cleaning code...", end='', flush=True)
        else:
            print("\n📊 Stage 2: Code Cleaning")
        self.logger.info("Starting code cleaning stage")
        
        self.pipeline_state['stages']['cleaning']['status'] = 'running'
        self.pipeline_state['stages']['cleaning']['start_time'] = datetime.now().isoformat()
        
        # Check if cleaning has already been done (skip this check if force=True)
        summary_file = self.output_dir / f'cleaning_summary_{year}.json'
        if summary_file.exists() and not force:
            self.logger.info(f"Found existing cleaning results at {summary_file}")
            try:
                with open(summary_file) as f:
                    existing_summary = json.load(f)
                    
                self.logger.info("Using existing cleaning results. Use --force-clean to re-run.")
                self.pipeline_state['stages']['cleaning']['status'] = 'skipped'
                self.pipeline_state['stages']['cleaning']['stats'] = existing_summary.get('stats', {})
                
                # Show completion message for cached results too
                if not self.verbose:
                    stats = existing_summary.get('stats', {})
                    cleaned = stats.get('cleaned', 0)
                    total = stats.get('total_matched', 0)
                    
                    # Count scenes from existing cleaned results
                    scene_count = 0
                    for video_name, video_data in existing_summary.get('results', {}).items():
                        if isinstance(video_data, dict) and video_data.get('status') == 'completed':
                            # Try multiple ways to get scene count
                            if 'scenes' in video_data:
                                scene_count += len(video_data['scenes'])
                            elif 'cleaned_scenes' in video_data:
                                scene_count += video_data['cleaned_scenes']
                            elif 'total_scenes' in video_data:
                                scene_count += video_data['total_scenes']
                    print(f" ✓ (using cache: {cleaned}/{total} videos, {scene_count} scenes)")
                
                return existing_summary
            except (json.JSONDecodeError, ValueError) as e:
                self.logger.warning(f"Corrupted summary file {summary_file}, will re-run cleaning: {e}")
                # Continue with cleaning process
            
        # Preprocess parameterized scenes before cleaning
        self.logger.info("Step 2a: Parameterized Scene Preprocessing")
        preprocessing_stats = self.preprocess_parameterized_scenes(year, video_filter)
        
        # Run cleaning with warning capture
        self.logger.info(f"Step 2b: Running code cleaning for year {year}")
        self.logger.info(f"Cleaning mode: {self.cleaning_mode}")
        if video_filter:
            self.logger.info(f"Filtering to videos: {video_filter}")
        
        with capture_syntax_warnings() as warnings_list:
            summary = self.cleaner.clean_all_matched_videos(
                year=year, video_filter=video_filter, force=force, mode=self.cleaning_mode,
                resume=not force  # If forcing, don't resume from checkpoint
            )
        
        # Store warnings for later display
        self.collected_warnings.extend(warnings_list)
        
        # Add preprocessing stats to the summary
        summary['parameterized_preprocessing'] = preprocessing_stats
        
        # Validate cleaned files with warning capture
        self.logger.info("Validating syntax of cleaned files...")
        with capture_syntax_warnings() as validation_warnings:
            validation_results = self.validate_cleaned_files(year)
        
        # Store validation warnings
        self.collected_warnings.extend(validation_warnings)
        
        # Update stats with validation results
        valid_count = sum(1 for v in validation_results.values() if v)
        invalid_count = len(validation_results) - valid_count
        
        if invalid_count > 0:
            self.logger.warning(f"Found {invalid_count} cleaned files with syntax errors!")
            summary['stats']['syntax_errors'] = invalid_count
            summary['stats']['syntax_valid'] = valid_count
            
            # Mark files with syntax errors as failed
            for video_name, is_valid in validation_results.items():
                if not is_valid and video_name in summary.get('results', {}):
                    summary['results'][video_name]['validation'] = 'syntax_error'
                    summary['stats']['cleaned'] -= 1
                    summary['stats']['failed'] += 1
        
        # Run scene-level validation if using scene mode
        if self.cleaning_mode == 'scene':
            scene_validation_summary = self.validate_cleaned_scenes(year)
            summary['scene_validation'] = scene_validation_summary
            
            # Update stats with scene validation results
            if scene_validation_summary['failed_videos'] > 0:
                self.logger.warning(f"Scene validation found issues in {scene_validation_summary['failed_videos']} videos")
        
        # Optimize the summary to remove redundant data and add useful metrics
        summary = self.optimize_cleaning_summary(summary)
        
        # Save optimized summary
        summary_file = self.output_dir / f'cleaning_summary_{year}.json'
        temp_file = summary_file.with_suffix('.json.tmp')
        try:
            with open(temp_file, 'w') as f:
                json.dump(summary, f, indent=2)
            temp_file.replace(summary_file)
        except Exception as e:
            self.logger.error(f"Failed to save cleaning summary: {e}")
            if temp_file.exists():
                temp_file.unlink()
            raise
        self.logger.info(f"Saved optimized cleaning summary to {summary_file}")
        
        # Generate and save human-readable report
        report_file = self.logs_dir / f'cleaning_report_{year}.txt'
        report = self.generate_cleaning_report(summary, report_file)
        self.logger.info(f"Generated cleaning report at {report_file}")
        
        # Log key statistics
        if 'aggregated_stats' in summary:
            agg = summary['aggregated_stats']
            self.logger.info(f"Cleaning Statistics:")
            self.logger.info(f"  Total scenes processed: {agg['scene_count']}")
            self.logger.info(f"  Average time per scene: {agg['avg_time_per_scene']}s")
            self.logger.info(f"  Total cleaning time: {agg['total_cleaning_time']}s")
            if agg.get('complexity_distribution'):
                self.logger.info(f"  Complexity distribution: {dict(agg['complexity_distribution'])}")
            if agg.get('validation_errors'):
                self.logger.info(f"  Validation errors: {dict(agg['validation_errors'])}")
        
        # Log parameterized scene preprocessing statistics
        if 'parameterized_preprocessing' in summary:
            prep = summary['parameterized_preprocessing']
            self.logger.info(f"Parameterized Scene Preprocessing:")
            self.logger.info(f"  Files checked: {prep['total_files_checked']}")
            self.logger.info(f"  Parameterized scenes found: {prep['parameterized_files_found']}")
            self.logger.info(f"  Successfully converted: {prep['files_converted']}")
            self.logger.info(f"  Parameters converted: {prep['total_parameters_converted']}")
            if prep['conversion_failures'] > 0:
                self.logger.warning(f"  Conversion failures: {prep['conversion_failures']}")
        
        self.pipeline_state['stages']['cleaning']['status'] = 'completed'
        self.pipeline_state['stages']['cleaning']['end_time'] = datetime.now().isoformat()
        self.pipeline_state['stages']['cleaning']['stats'] = summary.get('stats', {})
        
        # Also add aggregated stats to pipeline state for final report
        if 'aggregated_stats' in summary:
            self.pipeline_state['stages']['cleaning']['aggregated_stats'] = summary['aggregated_stats']
        
        # Print completion message
        if not self.verbose:
            stats = summary.get('stats', {})
            cleaned = stats.get('cleaned', 0)
            total = stats.get('total_matched', 0)
            
            # Use accurate scene count: if we actually processed scenes in this run,
            # use the aggregated stats. If we skipped due to existing results, 
            # calculate scene count from the actual video results
            stage_status = self.pipeline_state['stages']['cleaning'].get('status', 'unknown')
            if stage_status == 'skipped':
                # Count scenes from existing cleaned results
                scene_count = 0
                for video_name, video_data in summary.get('results', {}).items():
                    if isinstance(video_data, dict) and video_data.get('status') == 'completed':
                        # Try multiple ways to get scene count
                        if 'scenes' in video_data:
                            scene_count += len(video_data['scenes'])
                        elif 'cleaned_scenes' in video_data:
                            scene_count += video_data['cleaned_scenes']
                        elif 'total_scenes' in video_data:
                            scene_count += video_data['total_scenes']
                print(f" ✓ (using cache: {cleaned}/{total} videos, {scene_count} scenes)")
            else:
                # Use aggregated stats from the actual run
                scene_count = summary.get('aggregated_stats', {}).get('scene_count', 0)
                print(f" ✓ ({cleaned}/{total} videos, {scene_count} scenes cleaned)")
        
        return summary
        
    def run_conversion_stage(self, year: int, force: bool = False, video_filter: Optional[List[str]] = None) -> Dict:
        """Run the ManimGL to ManimCE conversion stage."""
        if not self.verbose:
            print("[CONVERT] Converting to ManimCE...", end='', flush=True)
        else:
            print("\n📊 Stage 3: ManimCE Conversion")
        self.logger.info("Starting ManimCE conversion stage")
        
        if self.use_systematic_converter:
            # Use the enhanced systematic converter (DEFAULT)
            from systematic_pipeline_converter import convert_with_systematic_pipeline
            unfixable_mode = "MONITORING" if self.monitor_unfixable_only else ("ACTIVE" if self.enable_unfixable_skipping else "DISABLED")
            self.logger.info(f"Using Enhanced Systematic Converter (DEFAULT - automatic fixes + intelligent Claude fallback)")
            self.logger.info(f"Unfixable pattern detection: {unfixable_mode}")
            
            with capture_syntax_warnings() as conversion_warnings:
                result = convert_with_systematic_pipeline(self, year, video_filter, force)
            
            # Store conversion warnings
            self.collected_warnings.extend(conversion_warnings)
            return result
        else:
            # Use standard integrated converter (LEGACY)
            from integrated_pipeline_converter import integrate_with_pipeline
            self.logger.info("Using Integrated Converter (LEGACY - with dependency analysis and scene validation)")
            
            with capture_syntax_warnings() as conversion_warnings:
                result = integrate_with_pipeline(self, year, video_filter, force)
            
            # Store conversion warnings
            self.collected_warnings.extend(conversion_warnings)
            return result

    def run_rendering_stage(self, year: int, quality: str = 'preview', 
                           limit: Optional[int] = None, scenes_limit: Optional[int] = None,
                           video_filter: Optional[List[str]] = None, force: bool = False) -> Dict:
        """Run the video rendering stage."""
        if not self.verbose:
            print("[RENDER] Rendering videos...", end='', flush=True)
        else:
            print("\n📊 Stage 4: Video Rendering")
        self.logger.info("Starting video rendering stage")
        
        # ENHANCEMENT: Apply runtime fixes before rendering (unless disabled)
        if not hasattr(self, 'skip_runtime_fixes') or not self.skip_runtime_fixes:
            self.logger.info("Applying runtime conversion fixes before rendering...")
            self._apply_runtime_fixes(year, video_filter)
        else:
            self.logger.info("Skipping runtime fixes (--skip-runtime-fixes enabled)")
        
        self.pipeline_state['stages']['rendering']['status'] = 'running'
        self.pipeline_state['stages']['rendering']['start_time'] = datetime.now().isoformat()
        
        # Check if rendering has already been done
        # Check for existing rendering summary in the logs directory
        summary_file = self.logs_dir / f'rendering_summary_{year}_{quality}.json'
        if summary_file.exists() and not force:
            self.logger.info(f"Found existing rendering results at {summary_file}")
            try:
                with open(summary_file) as f:
                    existing_summary = json.load(f)
                    
                self.logger.info("Using existing rendering results. Use --force-render to re-run.")
                self.pipeline_state['stages']['rendering']['status'] = 'skipped'
                self.pipeline_state['stages']['rendering']['stats'] = {
                    'total_videos': existing_summary.get('total_videos', 0),
                    'successful_videos': existing_summary.get('successful_videos', 0),
                    'failed_videos': existing_summary.get('failed_videos', 0),
                    'partial_videos': existing_summary.get('partial_videos', 0),
                    'total_scenes_rendered': existing_summary.get('total_scenes_rendered', 0),
                    'total_render_time': existing_summary.get('total_render_time', 0),
                    'render_success_rate': (existing_summary.get('total_scenes_rendered', 0) / max(sum(len(v.get('rendered_scenes', [])) + len(v.get('failed_scenes', [])) for v in existing_summary.get('videos', [])), 1)) if existing_summary.get('videos') else 0
                }
                return existing_summary
            except (json.JSONDecodeError, ValueError) as e:
                self.logger.warning(f"Corrupted summary file {summary_file}, will re-run rendering: {e}")
                # Continue with rendering process
            
        # Run rendering
        self.logger.info(f"Running video rendering for year {year}")
        self.logger.info(f"Quality: {quality}, Limit: {limit}, Scenes limit: {scenes_limit}")
        if video_filter:
            self.logger.info(f"Filtering to videos: {video_filter}")
        
        try:
            summary = self.renderer.render_year_videos(
                year=year,
                quality=quality,
                limit=limit,
                scenes_limit=scenes_limit,
                video_filter=video_filter
            )
            
            self.pipeline_state['stages']['rendering']['status'] = 'completed'
            self.pipeline_state['stages']['rendering']['end_time'] = datetime.now().isoformat()
            self.pipeline_state['stages']['rendering']['stats'] = {
                'total_videos': summary.get('total_videos', 0),
                'successful_videos': summary.get('successful_videos', 0),
                'failed_videos': summary.get('failed_videos', 0),
                'partial_videos': summary.get('partial_videos', 0),
                'total_scenes_rendered': summary.get('total_scenes_rendered', 0),
                'total_render_time': summary.get('total_render_time', 0),
                'render_success_rate': (summary.get('total_scenes_rendered', 0) / max(sum(len(v.get('rendered_scenes', [])) + len(v.get('failed_scenes', [])) for v in summary.get('videos', [])), 1)) if summary.get('videos') else 0
            }
            
            # Print completion message
            if not self.verbose:
                # Show both video and scene counts for rendering
                total_scenes = sum(len(v.get('rendered_scenes', [])) + len(v.get('failed_scenes', [])) for v in summary.get('videos', []))
                rendered_scenes = summary.get('total_scenes_rendered', 0)
                print(f" ✓ ({summary.get('successful_videos', 0)}/{summary.get('total_videos', 0)} videos, {rendered_scenes}/{total_scenes} scenes rendered)")
            
        except Exception as e:
            self.logger.error(f"Rendering stage failed: {e}")
            self.pipeline_state['stages']['rendering']['status'] = 'failed'
            self.pipeline_state['stages']['rendering']['error'] = str(e)
            return {'error': str(e)}
            
        return summary
    
    def _apply_runtime_fixes(self, year: int, video_filter: Optional[List[str]] = None):
        """Apply runtime conversion fixes to validated snippets before rendering."""
        try:
            from fix_runtime_conversion_issues import RuntimeConversionFixer
            
            fixer = RuntimeConversionFixer(verbose=self.verbose)
            result = fixer.fix_video_snippets(year, self.base_dir, video_filter)
            
            if result.get('total_files_fixed', 0) > 0:
                self.logger.info(f"Applied runtime fixes to {result['total_files_fixed']} files")
            else:
                self.logger.info("No runtime fixes needed")
                
        except ImportError:
            self.logger.warning("Runtime fixer not available, skipping fixes")
        except Exception as e:
            self.logger.warning(f"Failed to apply runtime fixes: {e}")
    
    def archive_old_reports(self, year: int):
        """Archive old pipeline report JSON files, keeping only the latest."""
        # Find all existing pipeline report JSON files for this year
        existing_reports = list(self.output_dir.glob(f'pipeline_report_{year}_*.json'))
        
        if existing_reports:
            # Sort by modification time to find the most recent
            existing_reports.sort(key=lambda p: p.stat().st_mtime)
            
            # Archive all but the most recent
            for report in existing_reports[:-1]:
                archive_path = self.archive_dir / report.name
                report.rename(archive_path)
                self.logger.info(f"Archived old report: {report.name}")
                
    def generate_final_report(self, year: int):
        """Generate a comprehensive report of the entire pipeline run."""
        self.pipeline_state['end_time'] = datetime.now().isoformat()
        self.pipeline_state['year'] = year
        
        # Calculate total duration
        if self.pipeline_state['start_time']:
            start = datetime.fromisoformat(self.pipeline_state['start_time'])
            end = datetime.fromisoformat(self.pipeline_state['end_time'])
            duration = (end - start).total_seconds()
            self.pipeline_state['duration_seconds'] = duration
            
        # Archive old reports before creating new one
        self.archive_old_reports(year)
        
        # Save the latest pipeline state JSON (this will be the only one in main output dir)
        latest_report_file = self.output_dir / f'pipeline_report_{year}_latest.json'
        temp_file = latest_report_file.with_suffix('.json.tmp')
        try:
            with open(temp_file, 'w') as f:
                json.dump(self.pipeline_state, f, indent=2)
            temp_file.replace(latest_report_file)
        except Exception as e:
            self.logger.error(f"Failed to save pipeline report: {e}")
            if temp_file.exists():
                temp_file.unlink()
            raise
            
        # Also append to consolidated history log (one line per run)
        with open(self.consolidated_log_file, 'a') as f:
            f.write(json.dumps(self.pipeline_state) + '\n')
            
        # Generate human-readable report
        report_text = f"""
3Blue1Brown Dataset Pipeline Report
===================================
Year: {year}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Configuration:
- Cleaning Mode: {self.cleaning_mode}
- Conversion Mode: {self.conversion_mode}

Stage 1: Video Matching
-----------------------
Status: {self.pipeline_state['stages']['matching']['status']}
Stats: {json.dumps(self.pipeline_state['stages']['matching']['stats'], indent=2)}

Stage 2: Code Cleaning (Mode: {self.cleaning_mode})
----------------------
Status: {self.pipeline_state['stages']['cleaning']['status']}
Stats: {json.dumps(self.pipeline_state['stages']['cleaning']['stats'], indent=2)}"""
        
        # Add aggregated cleaning stats if available
        if 'aggregated_stats' in self.pipeline_state['stages']['cleaning']:
            agg = self.pipeline_state['stages']['cleaning']['aggregated_stats']
            report_text += f"""
Aggregated Cleaning Metrics:
  - Total scenes: {agg.get('scene_count', 0)}
  - Avg time/scene: {agg.get('avg_time_per_scene', 0):.1f}s
  - Complexity: {json.dumps(agg.get('complexity_distribution', {}), indent=4)}
  - Errors: {json.dumps(agg.get('validation_errors', {}), indent=4)}"""
        
        report_text += f"""

Stage 3: ManimCE Conversion (Mode: {self.conversion_mode})
---------------------------
Status: {self.pipeline_state['stages']['conversion']['status']}
Stats: {json.dumps(self.pipeline_state['stages']['conversion']['stats'], indent=2)}"""
        
        # Add unfixable pattern statistics if available
        conversion_stats = self.pipeline_state['stages']['conversion'].get('stats', {})
        if 'unfixable_patterns' in conversion_stats:
            unfixable = conversion_stats['unfixable_patterns']
            report_text += f"""

Unfixable Pattern Detection:
  - Mode: {"MONITORING" if unfixable.get('monitor_mode', True) else "ACTIVE"}
  - Claude calls that would be skipped: {unfixable.get('skipped', 0)}
  - Claude calls attempted: {unfixable.get('attempted', 0)}"""
            
            if unfixable.get('patterns'):
                report_text += "\n  - Top patterns detected:"
                for pattern, count in sorted(unfixable['patterns'].items(), 
                                           key=lambda x: x[1], reverse=True)[:3]:
                    report_text += f"\n    * {pattern}: {count} occurrences"
                    
            total_claude_candidates = unfixable.get('skipped', 0) + unfixable.get('attempted', 0)
            if total_claude_candidates > 0:
                skip_rate = unfixable.get('skipped', 0) / total_claude_candidates
                report_text += f"\n  - Potential API call reduction: {skip_rate:.1%}"
                report_text += f"\n  - Estimated cost savings: ${unfixable.get('skipped', 0) * 0.03:.2f}"

        report_text += f"""

Stage 4: Video Rendering
------------------------
Status: {self.pipeline_state['stages']['rendering']['status']}
Stats: {json.dumps(self.pipeline_state['stages']['rendering']['stats'], indent=2)}

Total Duration: {self.pipeline_state.get('duration_seconds', 0):.1f} seconds

Output Locations:
- Video directories: {self.output_dir}/{year}/"""
        
        # Add actual video names to the detailed report
        year_dir = self.output_dir / str(year)
        if year_dir.exists():
            processed_videos = [d.name for d in year_dir.iterdir() if d.is_dir()]
            if processed_videos:
                report_text += f"\n  Videos processed: {', '.join(processed_videos[:10])}"
                if len(processed_videos) > 10:
                    report_text += f" ... and {len(processed_videos) - 10} more"
        
        report_text += f"""
- Logs: {self.logs_dir}/
- Archive: {self.archive_dir}/

Each video directory contains:
  - matches.json: Matching results
  - .pipeline/intermediate/monolith_manimgl.py: Cleaned and inlined code
  - validated_snippets/: Final ManimCE snippets (individual files)
  - monolith_manimce.py: Final ManimCE code (monolithic file)
  - videos/: Rendered video files (if rendered)
  - .pipeline/logs/: Processing logs
"""
        
        report_text_file = self.output_dir / f'pipeline_report_{year}.txt'
        with open(report_text_file, 'w') as f:
            f.write(report_text)
            
        # Print clean formatted report
        if self.verbose:
            print("\n" + "="*60)
            print("🎯 PIPELINE COMPLETE")
            print("="*60)
            print(f"Year: {year}")
            print(f"Duration: {self.pipeline_state.get('duration_seconds', 0):.1f}s")
            
            # Print stage summaries
            for stage_name, stage_data in self.pipeline_state['stages'].items():
                status = stage_data.get('status', 'unknown')
                emoji = "✅" if status == 'completed' else "⏭️" if status == 'skipped' else "❌" if status == 'failed' else "⏸️"
                print(f"{emoji} {stage_name.upper()}: {status}")
                
                # Show key stats for each stage
                stats = stage_data.get('stats', {})
                if stage_name == 'matching' and stats:
                    print(f"   📊 {stats.get('total_videos', 0)} videos, {stats.get('successful_matches', 0)} matched")
                elif stage_name == 'cleaning' and stats:
                    cleaned = stats.get('cleaned', 0)
                    failed = stats.get('failed', 0)
                    
                    # Get scene count from aggregated stats
                    agg_stats = stage_data.get('aggregated_stats', {})
                    scene_count = agg_stats.get('scene_count', 0)
                    
                    # If no aggregated stats (e.g., when skipped), try to load from cleaning summary
                    if scene_count == 0 and cleaned > 0:
                        try:
                            summary_file = self.output_dir / f'cleaning_summary_{year}.json'
                            if summary_file.exists():
                                with open(summary_file) as f:
                                    cleaning_summary = json.load(f)
                                    scene_count = cleaning_summary.get('aggregated_stats', {}).get('scene_count', 0)
                        except:
                            pass  # Fallback to 0 if can't load summary
                    
                    print(f"   📊 {cleaned} videos cleaned, {scene_count} scenes processed")
                elif stage_name == 'conversion' and stats:
                    # Handle both old and new key formats from different converters
                    converted = stats.get('converted', stats.get('successful_videos', 0))
                    failed = stats.get('failed', stats.get('failed_videos', 0))
                    
                    # Calculate scene stats from video details if available
                    total_scenes = 0
                    successful_scenes = 0
                    if 'videos' in stats:
                        for video_name, video_data in stats['videos'].items():
                            if isinstance(video_data, dict):
                                total_scenes += video_data.get('total_scenes', 0)
                                successful_scenes += video_data.get('successful_scenes', 0)
                    
                    # Fallback to syntax_validation stats if video details not available
                    if total_scenes == 0 and 'syntax_validation' in stats:
                        successful_scenes = stats['syntax_validation']['syntax_valid_snippets']
                        total_scenes = stats['syntax_validation']['total_snippets_attempted']
                    
                    if total_scenes > 0:
                        print(f"   📊 {converted} videos converted, {successful_scenes}/{total_scenes} scenes")
                    else:
                        print(f"   📊 {converted} converted, {failed} failed")
                elif stage_name == 'rendering' and stats:
                    successful_videos = stats.get('successful_videos', 0)
                    total_scenes_rendered = stats.get('total_scenes_rendered', 0)
                    
                    # Calculate total scenes attempted from rendering summary if available
                    total_scenes_attempted = 0
                    try:
                        # Check for rendering summary file
                        render_summary_file = self.output_dir / f'logs/rendering_summary_{year}_preview.json'
                        if not render_summary_file.exists():
                            # Try alternate location
                            render_summary_file = self.output_dir / f'{year}/rendering_summary_preview.json'
                        
                        if render_summary_file.exists():
                            with open(render_summary_file) as f:
                                render_summary = json.load(f)
                                # Sum up total_scenes from all videos
                                for video in render_summary.get('videos', []):
                                    if isinstance(video, dict):
                                        total_scenes_attempted += video.get('total_scenes', 0)
                    except:
                        pass  # Fallback to stats only
                    
                    success_rate = stats.get('render_success_rate', 0)
                    if total_scenes_attempted > 0:
                        print(f"   📊 {successful_videos} videos rendered, {total_scenes_rendered}/{total_scenes_attempted} scenes ({success_rate:.1%} success)")
                    else:
                        print(f"   📊 {successful_videos} videos rendered, {total_scenes_rendered} scenes ({success_rate:.1%} success)")
            
            print(f"\n📁 Output: {self.output_dir}/{year}/")
            print(f"📄 Report: {latest_report_file}")
            print(f"📝 Logs: {self.logs_dir}/")
            print("="*60)
        else:
            # Compact completion summary for non-verbose
            print(f"\nCOMPLETE in {self.pipeline_state.get('duration_seconds', 0):.1f}s")
            
            # Quick stats summary
            conversion_stats = self.pipeline_state['stages'].get('conversion', {}).get('stats', {})
            if conversion_stats:
                systematic_eff = conversion_stats.get('systematic_efficiency', 0)
                if systematic_eff > 0:
                    print(f"  - {systematic_eff:.1%} handled systematically")
            
            print(f"Output: {self.output_dir}/{year}/")
            print(f"Report: {latest_report_file}")
        
        # Display collected warnings at the end (if any)
        self._display_collected_warnings()
        
        self.logger.info(f"Pipeline report saved to {latest_report_file}")
        
    def _display_collected_warnings(self):
        """Display collected syntax warnings in a clean, organized way."""
        if not self.collected_warnings:
            return
            
        # Deduplicate warnings
        unique_warnings = list(set(self.collected_warnings))
        if not unique_warnings:
            return
            
        if self.verbose:
            print(f"\n⚠️  SYNTAX WARNINGS ({len(unique_warnings)} unique)")
            print("=" * 50)
            for warning in unique_warnings[:10]:  # Show first 10
                print(f"  {warning}")
            if len(unique_warnings) > 10:
                print(f"  ... and {len(unique_warnings) - 10} more warnings")
            print("=" * 50)
        else:
            # Non-verbose: just show count
            if len(unique_warnings) > 0:
                print(f"⚠️  {len(unique_warnings)} syntax warnings (use --verbose to see details)")
        
    def run_full_pipeline(self, year: int = 2015, skip_matching: bool = False,
                         skip_cleaning: bool = False, skip_conversion: bool = False,
                         skip_rendering: bool = False,
                         force_match: bool = False, force_clean: bool = False, 
                         force_convert: bool = False, force_render: bool = False,
                         render_quality: str = 'preview',
                         render_limit: Optional[int] = None, render_scenes_limit: Optional[int] = None,
                         video_filter: Optional[List[str]] = None):
        """Run the complete dataset building pipeline."""
        self.pipeline_state['start_time'] = datetime.now().isoformat()
        
        # Print clean startup banner
        if self.verbose:
            print("\n" + "="*60)
            print("🚀 3BLUE1BROWN DATASET PIPELINE")
            print("="*60)
            print(f"📅 Year: {year}")
            print(f"🔧 Mode: {self.cleaning_mode} cleaning, {self.conversion_mode} conversion")
            
            # Show which stages will run
            stages = []
            if not skip_matching: stages.append("matching")
            if not skip_cleaning: stages.append("cleaning")
            if not skip_conversion: stages.append("conversion")
            if not skip_rendering: stages.append("rendering")
            
            print(f"⚙️  Stages: {' → '.join(stages)}")
            if video_filter:
                print(f"🎬 Videos: {', '.join(video_filter)}")
            print("="*60 + "\n")
        else:
            # Compact startup for non-verbose
            stages = []
            if not skip_matching: stages.append("match")
            if not skip_cleaning: stages.append("clean")
            if not skip_conversion: stages.append("convert")
            if not skip_rendering: stages.append("render")
            
            print(f"\n3BLUE1BROWN PIPELINE")
            print(f"Year: {year} | Stages: {' → '.join(stages)}")
            if video_filter:
                print(f"Videos: {', '.join(video_filter[:3])}{'...' if len(video_filter) > 3 else ''}")
            print("")
        
        self.logger.info(f"Starting pipeline for year {year} with stages: {', '.join(stages)}")
        
        # Count total stages to run
        stages_to_run = sum([
            not skip_matching,
            not skip_cleaning,
            not skip_conversion,
            not skip_rendering
        ])
        stages_completed = 0
        
        try:
            # Stage 1: Matching
            if not skip_matching:
                self.run_matching_stage(year, force=force_match, video_filter=video_filter)
                stages_completed += 1
            else:
                if self.verbose:
                    print("⏭️ Skipping matching stage (use --match-only to run)")
                self.pipeline_state['stages']['matching']['status'] = 'skipped'
                
            # Stage 2: Cleaning
            if not skip_cleaning:
                self.run_cleaning_stage(year, force=force_clean, video_filter=video_filter)
                stages_completed += 1
            else:
                if self.verbose:
                    print("⏭️ Skipping cleaning stage (use --clean-only to run)")
                self.pipeline_state['stages']['cleaning']['status'] = 'skipped'
                
            # Stage 3: Conversion
            if not skip_conversion:
                self.run_conversion_stage(year, force=force_convert, video_filter=video_filter)
                stages_completed += 1
            else:
                if self.verbose:
                    print("⏭️ Skipping conversion stage (use --convert-only to run)")
                self.pipeline_state['stages']['conversion']['status'] = 'skipped'
                
            # Stage 4: Rendering
            if not skip_rendering:
                self.run_rendering_stage(year, quality=render_quality, 
                                       limit=render_limit, scenes_limit=render_scenes_limit,
                                       video_filter=video_filter, force=force_render)
                stages_completed += 1
            else:
                if self.verbose:
                    print("⏭️ Skipping rendering stage (use --render or --render-only to run)")
                self.pipeline_state['stages']['rendering']['status'] = 'skipped'
                
        except Exception as e:
            self.logger.error(f"Pipeline failed: {e}")
            raise
            
        finally:
            # Generate final report
            self.generate_final_report(year)

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Build 3Blue1Brown dataset through matching, cleaning, and conversion pipeline'
    )
    parser.add_argument('--year', type=int, default=2015,
                        help='Year to process (default: 2015)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output')
    parser.add_argument('--skip-matching', action='store_true',
                        help='Skip the matching stage')
    parser.add_argument('--skip-cleaning', action='store_true',
                        help='Skip the cleaning stage')
    parser.add_argument('--skip-conversion', action='store_true',
                        help='Skip the ManimCE conversion stage')
    parser.add_argument('--render', action='store_true',
                        help='Enable video rendering stage (off by default)')
    parser.add_argument('--force-match', action='store_true',
                        help='Force re-matching of videos even if results exist')
    parser.add_argument('--force-clean', action='store_true',
                        help='Force re-cleaning of already cleaned files')
    parser.add_argument('--force-convert', action='store_true',
                        help='Force re-conversion of already converted files')
    parser.add_argument('--force-render', action='store_true',
                        help='Force re-rendering of videos even if results exist')
    parser.add_argument('--render-quality', choices=['preview', 'production'],
                        default='preview',
                        help='Video rendering quality (default: preview)')
    parser.add_argument('--render-limit', type=int,
                        help='Limit number of videos to render')
    parser.add_argument('--render-scenes-limit', type=int,
                        help='Limit number of scenes per video to render')
    parser.add_argument('--render-preview', action='store_true',
                        help='Shortcut for quick preview rendering (implies --render-limit 5 --render-scenes-limit 2)')
    parser.add_argument('--match-only', action='store_true',
                        help='Run only the matching stage')
    parser.add_argument('--clean-only', action='store_true',
                        help='Run only the cleaning stage')
    parser.add_argument('--convert-only', action='store_true',
                        help='Run only the conversion stage')
    parser.add_argument('--render-only', action='store_true',
                        help='Run only the rendering stage')
    parser.add_argument('--video', action='append',
                        help='Process only specific video(s) by caption directory name (can be specified multiple times)')
    parser.add_argument('--timeout-multiplier', type=float, default=1.0,
                        help='Multiply all cleaning timeouts by this factor (default: 1.0)')
    parser.add_argument('--max-retries', type=int, default=3,
                        help='Maximum number of retry attempts for timeouts in cleaning (default: 3)')
    parser.add_argument('--no-render-validation', action='store_true',
                        help='Disable render validation during conversion (not recommended)')
    parser.add_argument('--render-max-attempts', type=int, default=3,
                        help='Maximum attempts to fix render errors per file (default: 3)')
    parser.add_argument('--use-basic-converter', action='store_true',
                        help='Use basic regex converter instead of enhanced AST converter (not recommended - lower quality)')
    parser.add_argument('--no-precompile-validation', action='store_true',
                        help='Disable pre-compile validation (faster but may miss errors)')
    parser.add_argument('--precompile-only', action='store_true',
                        help='Run only pre-compile validation without rendering')
    parser.add_argument('--no-auto-fix', action='store_true',
                        help='Disable automatic fixes during pre-compile validation')
    parser.add_argument('--cleaning-mode', choices=['hybrid', 'programmatic', 'claude', 'monolithic', 'scene', 'simple'], default='hybrid',
                        help='Cleaning mode: hybrid (programmatic+fallback, DEFAULT), simple (just include all files), programmatic-only, claude-only, or legacy modes')
    parser.add_argument('--conversion-mode', choices=['monolithic', 'scene'], default='scene',
                        help='Conversion mode: scene-by-scene (default) or monolithic')
    parser.add_argument('--no-systematic-converter', action='store_true',
                        help='Disable enhanced systematic converter and use integrated converter only (NOT recommended - increases Claude API usage by ~500%%)')
    parser.add_argument('--use-systematic-converter', action='store_true',
                        help='Use enhanced systematic converter with automatic fixes (DEFAULT - reduces Claude API usage by ~85%%)')
    parser.add_argument('--parallel-render', type=int, default=1,
                        help='Number of parallel workers for rendering scenes (default: 1)')
    parser.add_argument('--disable-unfixable-skipping', action='store_true',
                        help='Disable active unfixable pattern detection (allow Claude calls for definitely unfixable issues)')
    parser.add_argument('--monitor-unfixable-only', action='store_true',
                        help='Monitor unfixable patterns without skipping Claude calls (log what would be skipped)')
    parser.add_argument('--min-conversion-confidence', type=float, default=0.8,
                        help='Minimum conversion confidence to attempt scene conversion (default: 0.8, range: 0.0-1.0)')
    parser.add_argument('--skip-runtime-fixes', action='store_true',
                        help='Skip automatic runtime fixes before rendering (not recommended)')
    parser.add_argument('--runtime-fixes-only', action='store_true',
                        help='Only apply runtime fixes, skip actual rendering')
    
    args = parser.parse_args()
    
    # Handle convenience flags
    if args.match_only:
        args.skip_cleaning = True
        args.skip_conversion = True
        args.render = False
    elif args.clean_only:
        args.skip_matching = True
        args.skip_conversion = True
        args.render = False
    elif args.convert_only:
        args.skip_matching = True
        args.skip_cleaning = True
        args.render = False
    elif args.render_only:
        args.skip_matching = True
        args.skip_cleaning = True
        args.skip_conversion = True
        args.render = True  # Force rendering on for render-only mode
    
    # Handle precompile-only flag
    if args.precompile_only:
        args.no_render_validation = True  # Disable render validation
        args.render = False  # Don't render videos
    
    # Handle render preview shortcut
    if args.render_preview:
        args.render = True  # Enable rendering
        args.render_limit = args.render_limit or 5
        args.render_scenes_limit = args.render_scenes_limit or 2
    
    # Handle runtime fixes only
    if args.runtime_fixes_only:
        args.skip_matching = True
        args.skip_cleaning = True
        args.skip_conversion = True
        args.render = False
    
    # Integrated converter is now always used
    use_integrated = True
    
    # Create pipeline builder
    base_dir = Path(__file__).parent.parent
    
    # Determine systematic converter usage - default True, disable with --no-systematic-converter
    use_systematic = not args.no_systematic_converter
    
    builder = DatasetPipelineBuilder(base_dir, verbose=args.verbose, 
                                    timeout_multiplier=args.timeout_multiplier,
                                    max_retries=args.max_retries,
                                    enable_render_validation=not args.no_render_validation,
                                    render_max_attempts=args.render_max_attempts,
                                    use_advanced_converter=not args.use_basic_converter,
                                    enable_precompile_validation=not args.no_precompile_validation,
                                    auto_fix_precompile=not args.no_auto_fix,
                                    cleaning_mode=args.cleaning_mode,
                                    conversion_mode=args.conversion_mode,
                                    parallel_render_workers=args.parallel_render,
                                    use_systematic_converter=use_systematic,
                                    enable_unfixable_skipping=not args.disable_unfixable_skipping,
                                    monitor_unfixable_only=args.monitor_unfixable_only,
                                    min_conversion_confidence=args.min_conversion_confidence)
    
    # Set runtime fixes preference
    builder.skip_runtime_fixes = args.skip_runtime_fixes
    
    # Handle runtime fixes only mode
    if args.runtime_fixes_only:
        from fix_runtime_conversion_issues import RuntimeConversionFixer
        fixer = RuntimeConversionFixer(verbose=args.verbose)
        result = fixer.fix_video_snippets(args.year, base_dir, args.video)
        
        print(f"Runtime fixes completed for {args.year}:")
        print(f"Videos processed: {result['videos_processed']}/{result['total_videos']}")
        print(f"Total files fixed: {result['total_files_fixed']}")
        
        for video_name, video_result in result['video_results'].items():
            if video_result.get('files_fixed', 0) > 0:
                print(f"  {video_name}: {video_result['files_fixed']} files fixed")
        return
    
    # Run pipeline
    builder.run_full_pipeline(
        year=args.year,
        skip_matching=args.skip_matching,
        skip_cleaning=args.skip_cleaning,
        skip_conversion=args.skip_conversion,
        skip_rendering=not args.render,  # Invert the logic: render flag enables rendering
        force_match=args.force_match,
        force_clean=args.force_clean,
        force_convert=args.force_convert,
        force_render=args.force_render,
        render_quality=args.render_quality,
        render_limit=args.render_limit,
        render_scenes_limit=args.render_scenes_limit,
        video_filter=args.video
    )

if __name__ == '__main__':
    main()