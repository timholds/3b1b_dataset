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

import json
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import subprocess
import sys

# Import the components
sys.path.append(str(Path(__file__).parent))
from claude_match_videos import ClaudeVideoMatcher
from clean_matched_code import CodeCleaner
# ManimConverter removed - using integrated converter only
from render_videos import VideoRenderer
from manimce_precompile_validator import ManimCEPrecompileValidator
from conversion_error_collector import collect_conversion_error, get_error_collector
from generate_comparison_report import ComparisonReportGenerator
from scene_validator import SceneValidator

class DatasetPipelineBuilder:
    def __init__(self, base_dir: str, verbose: bool = False, timeout_multiplier: float = 1.0, 
                 max_retries: int = 3, enable_render_validation: bool = True, 
                 render_max_attempts: int = 3, use_advanced_converter: bool = True,
                 enable_precompile_validation: bool = True, auto_fix_precompile: bool = True,
                 cleaning_mode: str = 'scene', conversion_mode: str = 'scene',
                 parallel_render_workers: int = 1):
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
        
        # Intelligent hybrid parsing strategy
        self.intelligent_parsing = True  # Always use smart hybrid approach
        
        # Initialize components
        self.matcher = ClaudeVideoMatcher(base_dir, verbose)
        self.cleaner = CodeCleaner(base_dir, verbose, timeout_multiplier=timeout_multiplier, max_retries=max_retries)
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
        log_file = video_dir / 'logs.json'
        
        # Load existing logs if file exists
        if log_file.exists():
            with open(log_file) as f:
                logs = json.load(f)
        else:
            logs = {}
        
        # Add or update the stage log
        logs[stage] = {
            'timestamp': datetime.now().isoformat(),
            'data': log_data
        }
        
        # Save updated logs
        with open(log_file, 'w') as f:
            json.dump(logs, f, indent=2)
    
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
        self.logger.info("=" * 60)
        self.logger.info("STAGE 1: Video Matching")
        self.logger.info("=" * 60)
        
        self.pipeline_state['stages']['matching']['status'] = 'running'
        self.pipeline_state['stages']['matching']['start_time'] = datetime.now().isoformat()
        
        # Check if matching has already been done
        summary_file = self.output_dir / f'matching_summary_{year}.json'
        if summary_file.exists() and not force:
            self.logger.info(f"Found existing matching results at {summary_file}")
            with open(summary_file) as f:
                existing_summary = json.load(f)
                
            self.logger.info("Using existing matching results. Use --force-match to re-run.")
            self.pipeline_state['stages']['matching']['status'] = 'skipped'
            self.pipeline_state['stages']['matching']['stats'] = existing_summary.get('stats', {})
            return existing_summary.get('results', {})
        
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
        
        return results
        
    def validate_cleaned_files(self, year: int) -> Dict[str, bool]:
        """Validate syntax of all cleaned files after cleaning stage."""
        validation_results = {}
        year_dir = self.output_dir / str(year)
        
        if not year_dir.exists():
            return validation_results
            
        for video_dir in year_dir.iterdir():
            if video_dir.is_dir():
                cleaned_file = video_dir / 'cleaned_code.py'
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
                cleaned_file = video_dir / 'cleaned_code.py'
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
        with open(summary_file, 'w') as f:
            json.dump(validation_summary, f, indent=2)
            
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
        self.logger.info("=" * 60)
        self.logger.info("STAGE 2: Code Cleaning")
        self.logger.info("=" * 60)
        
        self.pipeline_state['stages']['cleaning']['status'] = 'running'
        self.pipeline_state['stages']['cleaning']['start_time'] = datetime.now().isoformat()
        
        # Check if cleaning has already been done (skip this check if force=True)
        summary_file = self.output_dir / f'cleaning_summary_{year}.json'
        if summary_file.exists() and not force:
            self.logger.info(f"Found existing cleaning results at {summary_file}")
            with open(summary_file) as f:
                existing_summary = json.load(f)
                
            self.logger.info("Using existing cleaning results. Use --force-clean to re-run.")
            self.pipeline_state['stages']['cleaning']['status'] = 'skipped'
            self.pipeline_state['stages']['cleaning']['stats'] = existing_summary.get('stats', {})
            return existing_summary
            
        # Run cleaning
        self.logger.info(f"Running code cleaning for year {year}")
        self.logger.info(f"Cleaning mode: {self.cleaning_mode}")
        if video_filter:
            self.logger.info(f"Filtering to videos: {video_filter}")
        summary = self.cleaner.clean_all_matched_videos(
            year=year, video_filter=video_filter, force=force, mode=self.cleaning_mode,
            resume=not force  # If forcing, don't resume from checkpoint
        )
        
        # Validate cleaned files
        self.logger.info("Validating syntax of cleaned files...")
        validation_results = self.validate_cleaned_files(year)
        
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
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
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
        
        self.pipeline_state['stages']['cleaning']['status'] = 'completed'
        self.pipeline_state['stages']['cleaning']['end_time'] = datetime.now().isoformat()
        self.pipeline_state['stages']['cleaning']['stats'] = summary.get('stats', {})
        
        # Also add aggregated stats to pipeline state for final report
        if 'aggregated_stats' in summary:
            self.pipeline_state['stages']['cleaning']['aggregated_stats'] = summary['aggregated_stats']
        
        return summary
        
    def run_conversion_stage(self, year: int, force: bool = False, video_filter: Optional[List[str]] = None) -> Dict:
        """Run the ManimGL to ManimCE conversion stage."""
        self.logger.info("=" * 60)
        self.logger.info("STAGE 3: ManimCE Conversion")
        self.logger.info("=" * 60)
        
        # Always use integrated converter
        from integrated_pipeline_converter import integrate_with_pipeline
        self.logger.info("Using Integrated Converter (with dependency analysis and scene validation)")
        return integrate_with_pipeline(self, year, video_filter, force)

    def run_rendering_stage(self, year: int, quality: str = 'preview', 
                           limit: Optional[int] = None, scenes_limit: Optional[int] = None,
                           video_filter: Optional[List[str]] = None, force: bool = False) -> Dict:
        """Run the video rendering stage."""
        self.logger.info("=" * 60)
        self.logger.info("STAGE 4: Video Rendering")
        self.logger.info("=" * 60)
        
        self.pipeline_state['stages']['rendering']['status'] = 'running'
        self.pipeline_state['stages']['rendering']['start_time'] = datetime.now().isoformat()
        
        # Check if rendering has already been done
        # Check for existing rendering summary in the logs directory
        summary_file = self.logs_dir / f'rendering_summary_{year}_{quality}.json'
        if summary_file.exists() and not force:
            self.logger.info(f"Found existing rendering results at {summary_file}")
            with open(summary_file) as f:
                existing_summary = json.load(f)
                
            self.logger.info("Using existing rendering results. Use --force-render to re-run.")
            self.pipeline_state['stages']['rendering']['status'] = 'skipped'
            self.pipeline_state['stages']['rendering']['stats'] = {
                'total_videos': existing_summary.get('total_videos', 0),
                'successful_videos': existing_summary.get('successful_videos', 0),
                'failed_videos': existing_summary.get('failed_videos', 0),
                'total_scenes_rendered': existing_summary.get('total_scenes_rendered', 0)
            }
            return existing_summary
            
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
                'total_render_time': summary.get('total_render_time', 0)
            }
            
        except Exception as e:
            self.logger.error(f"Rendering stage failed: {e}")
            self.pipeline_state['stages']['rendering']['status'] = 'failed'
            self.pipeline_state['stages']['rendering']['error'] = str(e)
            return {'error': str(e)}
            
        return summary
    
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
        with open(latest_report_file, 'w') as f:
            json.dump(self.pipeline_state, f, indent=2)
            
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
Stats: {json.dumps(self.pipeline_state['stages']['conversion']['stats'], indent=2)}

Stage 4: Video Rendering
------------------------
Status: {self.pipeline_state['stages']['rendering']['status']}
Stats: {json.dumps(self.pipeline_state['stages']['rendering']['stats'], indent=2)}

Total Duration: {self.pipeline_state.get('duration_seconds', 0):.1f} seconds

Output Locations:
- Video directories: {self.output_dir}/{year}/[video_name]/
  - matches.json: Matching results
  - cleaned_code.py: Cleaned and inlined code
  - manimce_code.py: Converted ManimCE code
  - rendered_videos/: Rendered video files
  - logs.json: Video-specific processing logs
- Logs: {self.logs_dir}/
- Archive: {self.archive_dir}/
"""
        
        report_text_file = self.output_dir / f'pipeline_report_{year}.txt'
        with open(report_text_file, 'w') as f:
            f.write(report_text)
            
        print(report_text)
        self.logger.info(f"Pipeline report saved to {latest_report_file}")
        self.logger.info(f"Pipeline history appended to {self.consolidated_log_file}")
        
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
        
        self.logger.info("Starting 3Blue1Brown Dataset Pipeline")
        self.logger.info(f"Year: {year}")
        self.logger.info(f"Skip matching: {skip_matching}")
        self.logger.info(f"Skip cleaning: {skip_cleaning}")
        self.logger.info(f"Skip conversion: {skip_conversion}")
        self.logger.info(f"Skip rendering: {skip_rendering}")
        if video_filter:
            self.logger.info(f"Video filter: {video_filter}")
        
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
                if self.verbose and stages_to_run > 1:
                    print(f"\n\n🎯 Pipeline Progress: {stages_completed}/{stages_to_run} stages complete ({stages_completed/stages_to_run*100:.0f}%)\n")
            else:
                self.logger.info("Skipping matching stage")
                self.pipeline_state['stages']['matching']['status'] = 'skipped'
                
            # Stage 2: Cleaning
            if not skip_cleaning:
                self.run_cleaning_stage(year, force=force_clean, video_filter=video_filter)
                stages_completed += 1
                if self.verbose and stages_to_run > 1:
                    print(f"\n\n🎯 Pipeline Progress: {stages_completed}/{stages_to_run} stages complete ({stages_completed/stages_to_run*100:.0f}%)\n")
            else:
                self.logger.info("Skipping cleaning stage")
                self.pipeline_state['stages']['cleaning']['status'] = 'skipped'
                
            # Stage 3: Conversion
            if not skip_conversion:
                self.run_conversion_stage(year, force=force_convert, video_filter=video_filter)
                stages_completed += 1
                if self.verbose and stages_to_run > 1:
                    print(f"\n\n🎯 Pipeline Progress: {stages_completed}/{stages_to_run} stages complete ({stages_completed/stages_to_run*100:.0f}%)\n")
            else:
                self.logger.info("Skipping conversion stage")
                self.pipeline_state['stages']['conversion']['status'] = 'skipped'
                
            # Stage 4: Rendering
            if not skip_rendering:
                self.run_rendering_stage(year, quality=render_quality, 
                                       limit=render_limit, scenes_limit=render_scenes_limit,
                                       video_filter=video_filter, force=force_render)
                stages_completed += 1
                if self.verbose and stages_to_run > 1:
                    print(f"\n\n🎯 Pipeline Progress: {stages_completed}/{stages_to_run} stages complete ({stages_completed/stages_to_run*100:.0f}%)\n")
            else:
                self.logger.info("Skipping rendering stage")
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
    parser.add_argument('--cleaning-mode', choices=['monolithic', 'scene'], default='scene',
                        help='Cleaning mode: scene-by-scene (default) or monolithic')
    parser.add_argument('--conversion-mode', choices=['monolithic', 'scene'], default='scene',
                        help='Conversion mode: scene-by-scene (default) or monolithic')
    parser.add_argument('--parallel-render', type=int, default=1,
                        help='Number of parallel workers for rendering scenes (default: 1)')
    
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
    
    # Integrated converter is now always used
    use_integrated = True
    
    # Create pipeline builder
    base_dir = Path(__file__).parent.parent
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
                                    parallel_render_workers=args.parallel_render)
    
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