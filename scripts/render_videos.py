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

class VideoRenderer:
    def __init__(self, base_dir: str, verbose: bool = False):
        self.base_dir = Path(base_dir)
        self.output_base_dir = self.base_dir / 'outputs'
        self.verbose = verbose
        
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
                          output_file: Path, quality: str = 'preview') -> Dict:
        """Render a single scene from a code file."""
        config = self.quality_configs[quality]
        
        # Construct manim command
        cmd = [
            'manim',
            'render',
            str(code_file),
            scene_name,
            '-o', output_file.name,  # Just the filename, not full path
            '--media_dir', str(output_file.parent.parent),  # Parent of scene output
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
                timeout=300  # 5 minute timeout per scene
            )
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                # Check if output file was created
                # Manim creates videos in a specific directory structure
                expected_output = output_file.parent.parent / 'videos' / output_file.parent.name / config['resolution'].replace(',', 'p') / output_file.name
                
                if expected_output.exists():
                    # Move to our desired location
                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    expected_output.rename(output_file)
                    
                    return {
                        'status': 'success',
                        'duration': duration,
                        'output_file': str(output_file),
                        'file_size': output_file.stat().st_size
                    }
                else:
                    return {
                        'status': 'failed',
                        'error': 'Output file not created',
                        'duration': duration,
                        'stdout': result.stdout,
                        'stderr': result.stderr
                    }
            else:
                return {
                    'status': 'failed',
                    'error': f'Manim exit code: {result.returncode}',
                    'duration': duration,
                    'stdout': result.stdout[-1000:] if result.stdout else '',  # Last 1000 chars
                    'stderr': result.stderr[-1000:] if result.stderr else ''
                }
                
        except subprocess.TimeoutExpired:
            return {
                'status': 'timeout',
                'error': 'Rendering timeout (5 minutes)',
                'duration': 300
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'duration': time.time() - start_time
            }
            
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
        # Save rendered videos in a subdirectory within the video's main directory
        output_dir = self.output_base_dir / str(year) / video_id / 'rendered_videos'
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
        
        for i, scene_name in enumerate(scenes):
            # Create output filename with title and scene
            output_filename = f"{safe_title}_{video_id}_{scene_name}.{self.quality_configs[quality]['format']}"
            output_path = output_dir / output_filename
            
            self.logger.info(f"Rendering scene {i+1}/{len(scenes)}: {scene_name}")
            
            scene_result = self.render_single_scene(
                code_file, scene_name, output_path, quality
            )
            
            scene_result['scene_name'] = scene_name
            results['total_duration'] += scene_result.get('duration', 0)
            
            if scene_result['status'] == 'success':
                results['rendered_scenes'].append(scene_result)
                self.logger.info(f"✓ Rendered {scene_name} successfully")
            else:
                results['failed_scenes'].append(scene_result) 
                self.logger.error(f"✗ Failed to render {scene_name}: {scene_result.get('error')}")
                
        # Calculate summary
        results['status'] = 'partial' if results['failed_scenes'] else 'success'
        results['success_rate'] = len(results['rendered_scenes']) / len(scenes) if scenes else 0
        
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
        log_file = video_dir / 'logs.json'
        
        # Load existing logs if file exists
        if log_file.exists():
            with open(log_file) as f:
                logs = json.load(f)
        else:
            logs = {}
        
        # Add rendering log
        logs['rendering'] = {
            'timestamp': datetime.now().isoformat(),
            'data': results
        }
        
        # Save updated logs
        with open(log_file, 'w') as f:
            json.dump(logs, f, indent=2)
            
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
        
    def render_year_videos(self, year: int, quality: str = 'preview',
                          limit: Optional[int] = None, 
                          scenes_limit: Optional[int] = None,
                          video_filter: Optional[List[str]] = None) -> Dict:
        """Render videos for an entire year."""
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
                
            # Prefer ManimCE code if available, otherwise use cleaned code
            manimce_file = video_dir / 'manimce_code.py'
            cleaned_file = video_dir / 'cleaned_code.py'
            
            code_file = manimce_file if manimce_file.exists() else cleaned_file
            
            if code_file.exists():
                videos_to_render.append({
                    'video_id': video_dir.name,
                    'code_file': code_file
                })
                
        if limit:
            videos_to_render = videos_to_render[:limit]
            
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
        
        for i, video_info in enumerate(videos_to_render):
            self.logger.info(f"\nRendering video {i+1}/{len(videos_to_render)}: {video_info['video_id']}")
            
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
            elif result.get('status') == 'partial':
                summary['partial_videos'] += 1
            else:
                summary['failed_videos'] += 1
                
            # Generate thumbnails for successfully rendered videos
            if self.verbose and result.get('rendered_scenes'):
                for scene_info in result['rendered_scenes'][:1]:  # Just first scene
                    video_path = Path(scene_info['output_file'])
                    if video_path.exists():
                        thumb = self.generate_thumbnail(video_path)
                        if thumb:
                            self.logger.info(f"Generated thumbnail: {thumb.name}")
                            
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
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create renderer
    base_dir = Path(__file__).parent.parent
    renderer = VideoRenderer(base_dir, verbose=args.verbose)
    
    if args.video:
        # Render single video
        year_output_dir = base_dir / 'outputs' / str(args.year) / args.video
        
        if not year_output_dir.exists():
            print(f"Video directory not found: {year_output_dir}")
            sys.exit(1)
            
        # Find code file
        manimce_file = year_output_dir / 'manimce_code.py'
        cleaned_file = year_output_dir / 'cleaned_code.py'
        code_file = manimce_file if manimce_file.exists() else cleaned_file
        
        if not code_file.exists():
            print(f"No code file found for video {args.video}")
            sys.exit(1)
            
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