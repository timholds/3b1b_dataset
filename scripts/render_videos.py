#!/usr/bin/env python3
"""
Video rendering module for the 3Blue1Brown dataset pipeline.
Renders ManimCE code files to video format for validation and preview.
"""

import ast
import json
import logging
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import logging utilities
try:
    from logging_utils import ProgressBar, BatchProgressTracker, ConditionalLogger
except ImportError:
    # Fallback if logging_utils not available
    ProgressBar = None
    BatchProgressTracker = None
    ConditionalLogger = None

# Import enhanced logging
from enhanced_logging_system import (
    EnhancedVideoLogger, StageType, ErrorCategory, 
    create_error_from_exception
)

class VideoRenderer:
    def __init__(self, base_dir: str, verbose: bool = False, parallel_workers: int = 1):
        self.base_dir = Path(base_dir)
        self.output_base_dir = self.base_dir / 'outputs'
        self.verbose = verbose
        self.parallel_workers = parallel_workers
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        if verbose:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)
            
        # Rendering configurations
        # ManimCE quality options: l (low), m (medium), h (high), p (production), k (4k)
        self.quality_configs = {
            'preview': {
                'quality': 'l',  # low quality for fast preview
                'resolution': '854,480',  # 480p
                'fps': 30,
                'format': 'mp4'
            },
            'production': {
                'quality': 'h',  # high quality
                'resolution': '1920,1080',  # 1080p
                'fps': 60,
                'format': 'mp4'
            }
        }
        
    def sanitize_title_for_filename(self, title: str, max_length: int = 50) -> str:
        """Convert video title to a safe filename."""
        # Remove special characters
        safe_title = re.sub(r'[^\w\s-]', '', title)
        # Replace spaces with underscores
        safe_title = re.sub(r'[-\s]+', '_', safe_title)
        # Remove leading/trailing underscores
        safe_title = safe_title.strip('_')
        # Limit length
        if len(safe_title) > max_length:
            safe_title = safe_title[:max_length].rstrip('_')
        # Convert to lowercase for consistency
        safe_title = safe_title.lower()
        
        return safe_title
        
    def get_video_title(self, year: int, video_id: str) -> str:
        """Get the video title from the caption data."""
        title_path = self.base_dir / 'data' / 'captions' / str(year) / video_id / 'english' / 'title.json'
        
        if not title_path.exists():
            self.logger.warning(f"Title file not found: {title_path}")
            # Fallback to video ID
            return video_id.replace('-', ' ').title()
            
        try:
            with open(title_path) as f:
                title_data = json.load(f)
                return title_data.get('input', video_id)
        except Exception as e:
            self.logger.error(f"Error reading title file: {e}")
            return video_id
            
    def extract_scene_classes(self, code_file: Path) -> List[str]:
        """Extract all Scene class names from a Python file."""
        scene_classes = []
        
        try:
            with open(code_file) as f:
                content = f.read()
                
            # First try AST parsing
            try:
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        # Check if this class inherits from Scene
                        for base in node.bases:
                            base_name = ""
                            if isinstance(base, ast.Name):
                                base_name = base.id
                            elif isinstance(base, ast.Attribute):
                                base_name = base.attr
                                
                            if 'Scene' in base_name:
                                scene_classes.append(node.name)
                                break
            except SyntaxError as e:
                # Fallback to regex parsing if AST fails
                self.logger.warning(f"AST parsing failed for {code_file}, using regex fallback: {e}")
                
                # Find class definitions that inherit from Scene
                class_pattern = r'class\s+(\w+)\s*\([^)]*Scene[^)]*\)\s*:'
                matches = re.findall(class_pattern, content, re.MULTILINE)
                scene_classes = list(set(matches))  # Remove duplicates
                
                if scene_classes:
                    self.logger.info(f"Found {len(scene_classes)} scenes using regex: {scene_classes}")
                            
        except Exception as e:
            self.logger.error(f"Error reading {code_file}: {e}")
            
        return scene_classes
        
    def render_single_scene(self, code_file: Path, scene_name: str, 
                          output_file: Path, quality: str = 'preview', 
                          video_logger: Optional[EnhancedVideoLogger] = None) -> Dict:
        """Render a single scene from a code file."""
        config = self.quality_configs[quality]
        
        # Initialize logging if not provided
        if video_logger is None:
            # Try to create from video directory structure
            video_dir = output_file.parent.parent
            video_id = video_dir.name
            # Create logs directory if it doesn't exist
            logs_dir = video_dir / '.pipeline' / 'logs'
            logs_dir.mkdir(parents=True, exist_ok=True)
            video_logger = EnhancedVideoLogger(video_dir, video_id)
        
        # Start performance monitoring
        perf_id = video_logger.log_stage_start(
            StageType.RENDERING,
            method=f'scene_{quality}',
            config={
                'scene_name': scene_name,
                'quality': quality,
                'resolution': config['resolution'],
                'fps': config['fps']
            }
        )
        
        # Use a shared media directory per video instead of per scene
        # This reduces directory creation and cleanup overhead
        video_media_dir = output_file.parent.parent / 'media'
        video_media_dir.mkdir(parents=True, exist_ok=True)
        
        # Construct manim command
        cmd = [
            'manim',
            'render',
            str(code_file),
            scene_name,
            '-o', output_file.name,  # Just the filename, not full path
            '--media_dir', str(video_media_dir),  # Shared media directory
            '--quality', config['quality'],
            '--resolution', config['resolution'],
            '--fps', str(config['fps']),
            '--format', config['format'],
            '--disable_caching',
            '--verbosity', 'WARNING'  # Reduce manim output noise
        ]
        
        if not self.verbose:
            cmd.append('--progress_bar=leave')
            
        self.logger.info(f"Rendering {scene_name} from {code_file.name}")
        if self.verbose:
            self.logger.debug(f"Command: {' '.join(cmd)}")
            
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.base_dir,
                timeout=900  # 15 minute timeout per scene
            )
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                # FIXED: Improved file detection with multiple possible paths
                # Manim can create videos in various subdirectory structures
                possible_outputs = [
                    # Standard ManimCE path
                    video_media_dir / 'videos' / scene_name / config['resolution'].replace(',', 'p') / output_file.name,
                    # Alternative path with video directory name
                    video_media_dir / 'videos' / output_file.parent.name / config['resolution'].replace(',', 'p') / output_file.name,
                    # Direct in videos directory
                    video_media_dir / 'videos' / output_file.name,
                    # Alternative resolution format
                    video_media_dir / 'videos' / scene_name / f"{config['resolution'].replace(',', 'x')}" / output_file.name,
                    # Just resolution directory
                    video_media_dir / 'videos' / config['resolution'].replace(',', 'p') / output_file.name,
                    # Fallback: search the entire videos directory
                ]
                
                found_output = None
                for expected_output in possible_outputs:
                    if expected_output.exists():
                        found_output = expected_output
                        break
                
                # If not found in standard locations, search recursively
                if not found_output:
                    videos_dir = video_media_dir / 'videos'
                    if videos_dir.exists():
                        for path in videos_dir.rglob(output_file.name):
                            found_output = path
                            break
                
                if found_output:
                    # Move to our desired location
                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    found_output.rename(output_file)
                    
                    # Clean up the specific video subdirectory to avoid accumulation
                    try:
                        import shutil
                        # Clean up parent directory of found file if it's now empty
                        cleanup_dir = found_output.parent
                        if cleanup_dir.exists() and not any(cleanup_dir.iterdir()):
                            cleanup_dir.rmdir()
                        # Also try cleaning the scene-specific directory
                        video_subdir = video_media_dir / 'videos' / scene_name
                        if video_subdir.exists() and not any(video_subdir.iterdir()):
                            shutil.rmtree(video_subdir)
                    except Exception as e:
                        self.logger.warning(f"Failed to clean up video subdirectory: {e}")
                    
                    result_data = {
                        'status': 'success',
                        'duration': duration,
                        'output_file': str(output_file),
                        'file_size': output_file.stat().st_size,
                        'scene_name': scene_name,
                        'quality': quality,
                        'found_at': str(found_output)  # Debug info
                    }
                    
                    # Log successful completion
                    video_logger.log_stage_complete(
                        StageType.RENDERING,
                        success=True,
                        result_data=result_data,
                        performance_id=perf_id
                    )
                    
                    return result_data
                else:
                    # FIXED: Better error detection - check if manim actually failed
                    # Even if file not found, if returncode is 0 and no stderr, it might be a path issue
                    error_msg = f'Output file not found. Manim succeeded (exit code 0) but file not at expected locations.'
                    if result.stderr.strip():
                        error_msg += f' Stderr: {result.stderr.strip()[:200]}'
                    
                    result_data = {
                        'status': 'path_not_found',  # Different status to distinguish from real failures
                        'error': error_msg,
                        'duration': duration,
                        'stdout': result.stdout,
                        'stderr': result.stderr,
                        'scene_name': scene_name,
                        'expected_paths': [str(p) for p in possible_outputs[:3]]  # Debug info
                    }
                    
                    # Log as warning, not error, since manim succeeded
                    self.logger.warning(f"File path issue for {scene_name}: {error_msg}")
                    video_logger.log_stage_complete(
                        StageType.RENDERING,
                        success=False,
                        result_data=result_data,
                        performance_id=perf_id
                    )
                    
                    return result_data
            else:
                # Clean up media directory on failure
                self._cleanup_media_directory(video_media_dir, output_file.parent.name)
                error_msg = f'Manim exit code: {result.returncode}'
                
                # Classify error based on output
                error_category = self._classify_rendering_error(result.stderr, result.stdout)
                
                result_data = {
                    'status': 'failed',
                    'error': error_msg,
                    'error_category': error_category.value,
                    'duration': duration,
                    'stdout': result.stdout[-1000:] if result.stdout else '',  # Last 1000 chars
                    'stderr': result.stderr[-1000:] if result.stderr else '',
                    'scene_name': scene_name,
                    'exit_code': result.returncode
                }
                
                # Create structured error
                error = create_error_from_exception(
                    Exception(f"Manim rendering failed: {error_msg}"),
                    'rendering'
                )
                error.category = error_category
                
                # Log validation attempt if this was a validation error
                if 'SyntaxError' in result.stderr or 'ImportError' in result.stderr:
                    video_logger.log_validation_attempt(
                        'render_validation',
                        success=False,
                        errors=[result.stderr[-500:] if result.stderr else error_msg]
                    )
                
                video_logger.log_stage_complete(
                    StageType.RENDERING,
                    success=False,
                    result_data=result_data,
                    error=error,
                    performance_id=perf_id
                )
                
                return result_data
                
        except subprocess.TimeoutExpired:
            # Clean up media directory on timeout
            self._cleanup_media_directory(video_media_dir, output_file.parent.name)
            result_data = {
                'status': 'timeout',
                'error': 'Rendering timeout (15 minutes)',
                'duration': 900,
                'scene_name': scene_name
            }
            
            # Log timeout error
            error = create_error_from_exception(
                TimeoutError("Rendering timeout after 15 minutes"),
                'rendering'
            )
            video_logger.log_stage_complete(
                StageType.RENDERING,
                success=False,
                result_data=result_data,
                error=error,
                performance_id=perf_id
            )
            
            return result_data
            
        except Exception as e:
            # Clean up media directory on exception
            self._cleanup_media_directory(video_media_dir, output_file.parent.name)
            result_data = {
                'status': 'error',
                'error': str(e),
                'duration': time.time() - start_time,
                'scene_name': scene_name
            }
            
            # Log unexpected error
            error = create_error_from_exception(e, 'rendering')
            video_logger.log_stage_complete(
                StageType.RENDERING,
                success=False,
                result_data=result_data,
                error=error,
                performance_id=perf_id
            )
            
            return result_data
    
    def _cleanup_media_directory(self, media_dir: Path, video_name: str):
        """Clean up media directory subdirectories for a specific video."""
        try:
            import shutil
            video_subdir = media_dir / 'videos' / video_name
            if video_subdir.exists():
                shutil.rmtree(video_subdir)
                self.logger.debug(f"Cleaned up media subdirectory: {video_subdir}")
        except Exception as e:
            self.logger.warning(f"Failed to clean up media directory for {video_name}: {e}")
    
    def _classify_rendering_error(self, stderr: str, stdout: str) -> ErrorCategory:
        """Classify rendering error based on output."""
        error_text = (stderr or '') + (stdout or '')
        error_text_lower = error_text.lower()
        
        if 'syntaxerror' in error_text_lower or 'invalid syntax' in error_text_lower:
            return ErrorCategory.SYNTAX_ERROR
        elif 'importerror' in error_text_lower or 'modulenotfounderror' in error_text_lower:
            return ErrorCategory.IMPORT_ERROR
        elif 'attributeerror' in error_text_lower:
            return ErrorCategory.RUNTIME_ERROR
        elif 'timeout' in error_text_lower or 'timed out' in error_text_lower:
            return ErrorCategory.TIMEOUT_ERROR
        elif 'memory' in error_text_lower or 'memoryerror' in error_text_lower:
            return ErrorCategory.RESOURCE_ERROR
        elif 'validation' in error_text_lower or 'validation failed' in error_text_lower:
            return ErrorCategory.VALIDATION_ERROR
        else:
            return ErrorCategory.UNKNOWN_ERROR
            
    def render_video(self, year: int, video_id: str, code_file: Path,
                    quality: str = 'preview', scenes_limit: Optional[int] = None) -> Dict:
        """Render all scenes from a video's code file."""
        # Get video title
        title = self.get_video_title(year, video_id)
        safe_title = self.sanitize_title_for_filename(title)
        
        # Extract scenes
        scenes = self.extract_scene_classes(code_file)
        
        if not scenes:
            self.logger.warning(f"No scenes found in {code_file}")
            return {
                'video_id': video_id,
                'title': title,
                'status': 'no_scenes',
                'code_file': str(code_file)
            }
            
        # Limit scenes if requested
        if scenes_limit:
            scenes = scenes[:scenes_limit]
            
        self.logger.info(f"Found {len(scenes)} scenes to render in {video_id}")
        
        # Create output directory
        # Save rendered videos in videos subdirectory for simplified structure
        output_dir = self.output_base_dir / str(year) / video_id / 'videos'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Render each scene
        results = {
            'video_id': video_id,
            'title': title,
            'safe_title': safe_title,
            'code_file': str(code_file),
            'total_scenes': len(scenes),
            'rendered_scenes': [],
            'failed_scenes': [],
            'total_duration': 0
        }
        
        if self.parallel_workers > 1 and len(scenes) > 1:
            # Parallel rendering with progress tracking
            self.logger.info(f"Rendering {len(scenes)} scenes in parallel with {self.parallel_workers} workers")
            
            # Use progress tracker if available
            if BatchProgressTracker:
                progress = BatchProgressTracker(len(scenes), "scenes")
            else:
                progress = None
            
            with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
                # Prepare all scene rendering tasks
                future_to_scene = {}
                
                for i, scene_name in enumerate(scenes):
                    output_filename = f"{safe_title}_{video_id}_{scene_name}.{self.quality_configs[quality]['format']}"
                    output_path = output_dir / output_filename
                    
                    future = executor.submit(
                        self.render_single_scene,
                        code_file, scene_name, output_path, quality
                    )
                    future_to_scene[future] = (i, scene_name)
                
                # Process completed renders as they finish
                for future in as_completed(future_to_scene):
                    i, scene_name = future_to_scene[future]
                    
                    try:
                        scene_result = future.result()
                        scene_result['scene_name'] = scene_name
                        results['total_duration'] += scene_result.get('duration', 0)
                        
                        if scene_result['status'] == 'success':
                            results['rendered_scenes'].append(scene_result)
                            if progress:
                                progress.complete_operation(success=True)
                            # Silent in non-verbose mode
                        else:
                            results['failed_scenes'].append(scene_result)
                            if progress:
                                progress.complete_operation(success=False)
                            else:
                                self.logger.error(f"Failed to render {scene_name}: {scene_result.get('error', 'Unknown error')[:50]}...")
                    except Exception as e:
                        results['failed_scenes'].append({
                            'scene_name': scene_name,
                            'status': 'error',
                            'error': str(e)
                        })
                        if progress:
                            progress.complete_operation(success=False)
                        else:
                            self.logger.error(f"Exception rendering {scene_name}: {str(e)[:50]}...")
            
            if progress:
                progress.finish()
        else:
            # Sequential rendering with progress bar
            if ProgressBar:
                progress = ProgressBar(len(scenes), f"Rendering {video_id}", show_stats=True)
            else:
                progress = None
                
            for i, scene_name in enumerate(scenes):
                # Create output filename with title and scene
                output_filename = f"{safe_title}_{video_id}_{scene_name}.{self.quality_configs[quality]['format']}"
                output_path = output_dir / output_filename
                
                if progress:
                    progress.update(0, f"Rendering {scene_name}")
                # Silent in non-verbose mode
                
                scene_result = self.render_single_scene(
                    code_file, scene_name, output_path, quality
                )
                
                scene_result['scene_name'] = scene_name
                results['total_duration'] += scene_result.get('duration', 0)
                
                if scene_result['status'] == 'success':
                    results['rendered_scenes'].append(scene_result)
                    if progress:
                        progress.update(1, f"✓ {scene_name}")
                    elif self.verbose:
                        self.logger.info(f"✓ Rendered {scene_name} successfully")
                else:
                    results['failed_scenes'].append(scene_result)
                    error_msg = str(scene_result.get('error', 'Unknown error'))[:50]
                    if progress:
                        progress.update(1, f"✗ {scene_name}: {error_msg}")
                    else:
                        self.logger.error(f"Failed to render {scene_name}: {error_msg}...")
                
        # Calculate summary - treat path_not_found as partial success since manim worked
        path_issues = [s for s in results['failed_scenes'] if s.get('status') == 'path_not_found']
        real_failures = [s for s in results['failed_scenes'] if s.get('status') != 'path_not_found']
        
        if path_issues:
            self.logger.warning(f"{len(path_issues)} scenes had path issues but may have rendered successfully")
        
        results['status'] = 'partial' if (real_failures or path_issues) else 'success'
        results['success_rate'] = len(results['rendered_scenes']) / len(scenes) if scenes else 0
        results['path_issues'] = path_issues  # Track separately for debugging
        
        # Save rendering metadata
        metadata_file = output_dir / 'render_metadata.json'
        with open(metadata_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'quality': quality,
                'results': results
            }, f, indent=2)
            
        # Also save to the video's main logs.json file
        video_dir = self.output_base_dir / str(year) / video_id
        # The logs.json file is in the root of the video directory
        log_file = video_dir / 'logs.json'
        
        # Ensure directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing logs if file exists
        logs = {}
        if log_file.exists():
            try:
                with open(log_file) as f:
                    logs = json.load(f)
            except (json.JSONDecodeError, ValueError) as e:
                self.logger.warning(f"Corrupted logs.json for {video_id}, creating new one: {e}")
                # Backup corrupted file
                backup_file = log_file.with_suffix('.json.corrupted')
                log_file.rename(backup_file)
                logs = {}
        
        # Add rendering log
        logs['rendering'] = {
            'timestamp': datetime.now().isoformat(),
            'data': results
        }
        
        # Save updated logs with atomic write
        temp_file = log_file.with_suffix('.json.tmp')
        try:
            with open(temp_file, 'w') as f:
                json.dump(logs, f, indent=2)
            # Atomic rename
            temp_file.replace(log_file)
        except Exception as e:
            self.logger.error(f"Failed to save logs for {video_id}: {e}")
            if temp_file.exists():
                temp_file.unlink()
            
        return results
        
    def generate_thumbnail(self, video_file: Path, timestamp: float = 2.0) -> Optional[Path]:
        """Extract a frame from the video as a thumbnail."""
        thumbnail_path = video_file.with_suffix('.png')
        
        cmd = [
            'ffmpeg',
            '-i', str(video_file),
            '-ss', str(timestamp),
            '-vframes', '1',
            '-y',  # Overwrite
            str(thumbnail_path)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            if result.returncode == 0 and thumbnail_path.exists():
                return thumbnail_path
        except:
            pass
            
        return None
        
    def render_video_from_snippets(self, year: int, video_id: str, snippets_dir: Path,
                                  snippet_files: List[Path], quality: str = 'preview',
                                  scenes_limit: int = None) -> Dict:
        """Render a video from individual snippet files."""
        
        # Convert video ID to title
        title = video_id.replace('-', ' ').title()
        safe_title = video_id
        
        # Apply scenes limit if specified
        if scenes_limit and len(snippet_files) > scenes_limit:
            self.logger.info(f"Limiting to {scenes_limit} scenes out of {len(snippet_files)}")
            snippet_files = snippet_files[:scenes_limit]
        
        # Save rendered videos in videos subdirectory for simplified structure
        output_dir = self.output_base_dir / str(year) / video_id / 'videos'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Render each snippet
        results = {
            'video_id': video_id,
            'title': title,
            'safe_title': safe_title,
            'render_mode': 'snippets',
            'snippets_dir': str(snippets_dir),
            'total_scenes': len(snippet_files),
            'rendered_scenes': [],
            'failed_scenes': [],
            'total_duration': 0
        }
        
        if self.parallel_workers > 1 and len(snippet_files) > 1:
            # Parallel rendering
            self.logger.info(f"Rendering {len(snippet_files)} snippets in parallel with {self.parallel_workers} workers")
            
            with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
                # Prepare all snippet rendering tasks
                future_to_snippet = {}
                
                for i, snippet_file in enumerate(snippet_files):
                    scene_name = snippet_file.stem  # Use filename without .py extension
                    output_filename = f"{safe_title}_{video_id}_{scene_name}.{self.quality_configs[quality]['format']}"
                    output_path = output_dir / output_filename
                    
                    # For snippets, we know there's only one scene per file with the same name
                    future = executor.submit(
                        self.render_single_scene,
                        snippet_file, scene_name, output_path, quality
                    )
                    future_to_snippet[future] = (i, scene_name, snippet_file)
                
                # Process completed renders as they finish
                for future in as_completed(future_to_snippet):
                    i, scene_name, snippet_file = future_to_snippet[future]
                    
                    try:
                        scene_result = future.result()
                        scene_result['scene_name'] = scene_name
                        scene_result['snippet_file'] = str(snippet_file.name)
                        results['total_duration'] += scene_result.get('duration', 0)
                        
                        if scene_result['status'] == 'success':
                            results['rendered_scenes'].append(scene_result)
                            self.logger.info(f"✓ [{i+1}/{len(snippet_files)}] Rendered {scene_name} successfully")
                        else:
                            results['failed_scenes'].append(scene_result)
                            self.logger.error(f"❌ [{i+1}/{len(snippet_files)}] Failed to render {scene_name}: {scene_result.get('error')}")
                    except Exception as e:
                        self.logger.error(f"❌ [{i+1}/{len(snippet_files)}] Exception rendering {scene_name}: {e}")
                        results['failed_scenes'].append({
                            'scene_name': scene_name,
                            'snippet_file': str(snippet_file.name),
                            'status': 'error',
                            'error': str(e)
                        })
        else:
            # Sequential rendering
            for i, snippet_file in enumerate(snippet_files):
                scene_name = snippet_file.stem
                output_filename = f"{safe_title}_{video_id}_{scene_name}.{self.quality_configs[quality]['format']}"
                output_path = output_dir / output_filename
                
                self.logger.info(f"Rendering snippet {i+1}/{len(snippet_files)}: {scene_name}")
                
                scene_result = self.render_single_scene(
                    snippet_file, scene_name, output_path, quality
                )
                
                scene_result['scene_name'] = scene_name
                scene_result['snippet_file'] = str(snippet_file.name)
                results['total_duration'] += scene_result.get('duration', 0)
                
                if scene_result['status'] == 'success':
                    results['rendered_scenes'].append(scene_result)
                    self.logger.info(f"✓ Rendered {scene_name} successfully")
                else:
                    results['failed_scenes'].append(scene_result) 
                    self.logger.error(f"✗ Failed to render {scene_name}: {scene_result.get('error')}")
                
        # Calculate summary
        results['status'] = 'partial' if results['failed_scenes'] else 'success'
        results['success_rate'] = len(results['rendered_scenes']) / len(snippet_files) if snippet_files else 0
        
        # Save rendering metadata
        metadata_file = output_dir / 'render_metadata.json'
        with open(metadata_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'quality': quality,
                'render_mode': 'snippets',
                'results': results
            }, f, indent=2)
            
        # Also save to the video's main logs.json file
        video_dir = self.output_base_dir / str(year) / video_id
        # The logs.json file is in the root of the video directory
        log_file = video_dir / 'logs.json'
        
        # Ensure directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing logs if file exists
        logs = {}
        if log_file.exists():
            try:
                with open(log_file) as f:
                    logs = json.load(f)
            except (json.JSONDecodeError, ValueError) as e:
                self.logger.warning(f"Corrupted logs.json for {video_id}, creating new one: {e}")
                # Backup corrupted file
                backup_file = log_file.with_suffix('.json.corrupted')
                log_file.rename(backup_file)
                logs = {}
            
        # Add render results to logs
        if 'rendering' not in logs:
            logs['rendering'] = []
            
        # Ensure 'rendering' is a list
        if isinstance(logs.get('rendering'), dict):
            # Convert old dict format to list
            logs['rendering'] = []
        
        logs['rendering'].append({
            'timestamp': datetime.now().isoformat(),
            'quality': quality,
            'render_mode': 'snippets',
            **results
        })
        
        # Save updated logs with atomic write
        temp_file = log_file.with_suffix('.json.tmp')
        try:
            with open(temp_file, 'w') as f:
                json.dump(logs, f, indent=2)
            # Atomic rename
            temp_file.replace(log_file)
        except Exception as e:
            self.logger.error(f"Failed to save logs for {video_id}: {e}")
            if temp_file.exists():
                temp_file.unlink()
            
        return results
        
    def render_year_videos(self, year: int, quality: str = 'preview',
                          limit: Optional[int] = None, 
                          scenes_limit: Optional[int] = None,
                          video_filter: Optional[List[str]] = None) -> Dict:
        """Render videos for an entire year."""
        if self.verbose:
            self.logger.info(f"Starting video rendering for year {year}")
            self.logger.info(f"Quality: {quality}, Video limit: {limit}, Scenes per video: {scenes_limit}")
            if video_filter:
                self.logger.info(f"Filtering to videos: {video_filter}")
        
        # Find all videos with cleaned or converted code
        year_output_dir = self.base_dir / 'outputs' / str(year)
        
        if not year_output_dir.exists():
            self.logger.error(f"No output directory found for year {year}")
            return {'error': 'No output directory'}
            
        # Collect videos to render
        videos_to_render = []
        
        for video_dir in year_output_dir.iterdir():
            if not video_dir.is_dir():
                continue
                
            # Apply video filter if specified
            if video_filter and video_dir.name not in video_filter:
                continue
                
            # Check for validated snippets first, then monolithic files
            snippets_dir = video_dir / 'validated_snippets'
            manimce_file = video_dir / 'monolith_manimce.py'
            cleaned_file = video_dir / 'monolith_manimgl.py'
            
            if snippets_dir.exists() and snippets_dir.is_dir():
                # Use individual snippets - preferred approach
                snippet_files = list(snippets_dir.glob('*.py'))
                if snippet_files:
                    videos_to_render.append({
                        'video_id': video_dir.name,
                        'render_mode': 'snippets',
                        'snippets_dir': snippets_dir,
                        'snippet_files': snippet_files
                    })
                    # Silent - no need to log snippet counts
            elif manimce_file.exists() or cleaned_file.exists():
                # Fallback to monolithic file
                code_file = manimce_file if manimce_file.exists() else cleaned_file
                videos_to_render.append({
                    'video_id': video_dir.name,
                    'render_mode': 'monolithic',
                    'code_file': code_file
                })
                # Silent - no need to log file type
                
        if limit:
            videos_to_render = videos_to_render[:limit]
            
        if self.verbose:
            self.logger.info(f"Found {len(videos_to_render)} videos to render")
        
        # Render each video
        summary = {
            'year': year,
            'quality': quality,
            'timestamp': datetime.now().isoformat(),
            'total_videos': len(videos_to_render),
            'successful_videos': 0,
            'failed_videos': 0,
            'partial_videos': 0,
            'total_scenes_rendered': 0,
            'total_render_time': 0,
            'videos': []
        }
        
        # Use batch progress tracker for overall video progress
        if BatchProgressTracker:
            video_progress = BatchProgressTracker(len(videos_to_render), "videos")
        else:
            video_progress = None
            
        for i, video_info in enumerate(videos_to_render):
            if video_progress:
                video_progress.start_operation(video_info['video_id'])
            else:
                self.logger.info(f"\nRendering video {i+1}/{len(videos_to_render)}: {video_info['video_id']}")
            
            if video_info['render_mode'] == 'snippets':
                # Render from individual snippets
                result = self.render_video_from_snippets(
                    year,
                    video_info['video_id'],
                    video_info['snippets_dir'],
                    video_info['snippet_files'],
                    quality,
                    scenes_limit
                )
            else:
                # Render from monolithic file
                result = self.render_video(
                    year, 
                    video_info['video_id'],
                    video_info['code_file'],
                    quality,
                    scenes_limit
                )
            
            summary['videos'].append(result)
            summary['total_render_time'] += result.get('total_duration', 0)
            summary['total_scenes_rendered'] += len(result.get('rendered_scenes', []))
            
            if result.get('status') == 'success':
                summary['successful_videos'] += 1
                if video_progress:
                    video_progress.complete_operation(success=True)
            elif result.get('status') == 'partial':
                summary['partial_videos'] += 1
                if video_progress:
                    video_progress.complete_operation(success=True)  # Partial is still a success
            else:
                summary['failed_videos'] += 1
                if video_progress:
                    video_progress.complete_operation(success=False)
                
            # Generate thumbnails for successfully rendered videos
            if self.verbose and result.get('rendered_scenes'):
                for scene_info in result['rendered_scenes'][:1]:  # Just first scene
                    video_path = Path(scene_info['output_file'])
                    if video_path.exists():
                        thumb = self.generate_thumbnail(video_path)
                        if thumb:
                            self.logger.debug(f"Generated thumbnail: {thumb.name}")
        
        if video_progress:
            video_progress.finish()
                            
        # Save summary
        summary_file = self.output_base_dir / str(year) / f'rendering_summary_{quality}.json'
        summary_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
            
        # Print summary
        self.logger.info("\n" + "="*60)
        self.logger.info("Rendering Summary")
        self.logger.info("="*60)
        self.logger.info(f"Total videos: {summary['total_videos']}")
        self.logger.info(f"Successful: {summary['successful_videos']}")
        self.logger.info(f"Partial: {summary['partial_videos']}")
        self.logger.info(f"Failed: {summary['failed_videos']}")
        self.logger.info(f"Total scenes rendered: {summary['total_scenes_rendered']}")
        self.logger.info(f"Total render time: {summary['total_render_time']:.1f} seconds")
        self.logger.info(f"Summary saved to: {summary_file}")
        
        return summary

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Render ManimCE videos from cleaned/converted code'
    )
    parser.add_argument('--year', type=int, default=2015,
                        help='Year to process (default: 2015)')
    parser.add_argument('--quality', choices=['preview', 'production'], 
                        default='preview',
                        help='Rendering quality (default: preview)')
    parser.add_argument('--limit', type=int,
                        help='Limit number of videos to render')
    parser.add_argument('--scenes-limit', type=int,
                        help='Limit number of scenes per video to render')
    parser.add_argument('--video', 
                        help='Render a specific video by ID')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output')
    parser.add_argument('--parallel-render', type=int, default=1,
                        help='Number of parallel workers for rendering scenes (default: 1)')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create renderer
    base_dir = Path(__file__).parent.parent
    renderer = VideoRenderer(base_dir, verbose=args.verbose, parallel_workers=args.parallel_render)
    
    if args.video:
        # Render single video
        year_output_dir = base_dir / 'outputs' / str(args.year) / args.video
        
        if not year_output_dir.exists():
            print(f"Video directory not found: {year_output_dir}")
            sys.exit(1)
            
        # Check for snippets first, then monolithic files
        snippets_dir = year_output_dir / 'validated_snippets'
        manimce_file = year_output_dir / 'monolith_manimce.py'
        cleaned_file = year_output_dir / 'monolith_manimgl.py'
        # Determine render mode
        if snippets_dir.exists() and snippets_dir.is_dir():
            snippet_files = list(snippets_dir.glob('*.py'))
            if snippet_files:
                print(f"Rendering from {len(snippet_files)} snippets...")
                result = renderer.render_video_from_snippets(
                    args.year, args.video, snippets_dir, snippet_files,
                    args.quality, args.scenes_limit
                )
            else:
                print(f"No snippet files found in {snippets_dir}")
                sys.exit(1)
        else:
            # Fallback to monolithic file
            code_file = manimce_file if manimce_file.exists() else cleaned_file
            
            if not code_file.exists():
                print(f"No code file found for video {args.video}")
                sys.exit(1)
                
            print(f"Rendering from monolithic file: {code_file.name}")
            result = renderer.render_video(
                args.year,
                args.video,
                code_file,
                args.quality,
                args.scenes_limit
            )
        
        print(json.dumps(result, indent=2))
    else:
        # Render all videos for year
        renderer.render_year_videos(
            args.year,
            args.quality,
            args.limit,
            args.scenes_limit
        )

if __name__ == '__main__':
    main()