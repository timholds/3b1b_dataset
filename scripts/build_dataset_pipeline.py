#!/usr/bin/env python3
"""
Orchestration script for building the 3Blue1Brown dataset.
This script coordinates the entire pipeline:
1. Match videos to code files
2. Clean and inline the matched code
3. Convert from ManimGL to ManimCE (optional)
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
from convert_manimgl_to_manimce import ManimConverter
from render_videos import VideoRenderer

class DatasetPipelineBuilder:
    def __init__(self, base_dir: str, verbose: bool = False):
        self.base_dir = Path(base_dir)
        self.output_dir = self.base_dir / 'output'
        self.verbose = verbose
        
        # Initialize components
        self.matcher = ClaudeVideoMatcher(base_dir, verbose)
        self.cleaner = CodeCleaner(base_dir, verbose)
        self.renderer = VideoRenderer(base_dir, verbose)
        # ManimConverter will be initialized when needed with proper paths
        
        # Setup pipeline logging
        self.log_dir = self.output_dir / 'pipeline_logs'
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure logger
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = self.log_dir / f"pipeline_{timestamp}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler() if verbose else logging.NullHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Pipeline state tracking
        self.pipeline_state = {
            'start_time': None,
            'end_time': None,
            'stages': {
                'matching': {'status': 'pending', 'stats': {}},
                'cleaning': {'status': 'pending', 'stats': {}},
                'conversion': {'status': 'pending', 'stats': {}},
                'rendering': {'status': 'pending', 'stats': {}}
            }
        }
        
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
        
    def run_matching_stage(self, year: int, video_filter: Optional[List[str]] = None) -> Dict:
        """Run the video matching stage."""
        self.logger.info("=" * 60)
        self.logger.info("STAGE 1: Video Matching")
        self.logger.info("=" * 60)
        
        self.pipeline_state['stages']['matching']['status'] = 'running'
        self.pipeline_state['stages']['matching']['start_time'] = datetime.now().isoformat()
        
        # Check if matching has already been done
        summary_file = self.output_dir / f'matching_summary_{year}.json'
        if summary_file.exists():
            self.logger.info(f"Found existing matching results at {summary_file}")
            with open(summary_file) as f:
                existing_summary = json.load(f)
                
            # Ask if we should re-run
            if not self.verbose:  # In non-verbose mode, skip re-running
                self.logger.info("Using existing matching results. Use --force-match to re-run.")
                self.pipeline_state['stages']['matching']['status'] = 'skipped'
                self.pipeline_state['stages']['matching']['stats'] = existing_summary.get('stats', {})
                return existing_summary.get('results', {})
                
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
        
    def run_cleaning_stage(self, year: int, force: bool = False, video_filter: Optional[List[str]] = None) -> Dict:
        """Run the code cleaning stage."""
        self.logger.info("=" * 60)
        self.logger.info("STAGE 2: Code Cleaning")
        self.logger.info("=" * 60)
        
        self.pipeline_state['stages']['cleaning']['status'] = 'running'
        self.pipeline_state['stages']['cleaning']['start_time'] = datetime.now().isoformat()
        
        # Check if cleaning has already been done
        summary_file = self.output_dir / f'cleaning_summary_{year}.json'
        if summary_file.exists() and not force:
            self.logger.info(f"Found existing cleaning results at {summary_file}")
            with open(summary_file) as f:
                existing_summary = json.load(f)
                
            self.pipeline_state['stages']['cleaning']['status'] = 'skipped'
            self.pipeline_state['stages']['cleaning']['stats'] = existing_summary.get('stats', {})
            return existing_summary
            
        # Run cleaning
        self.logger.info(f"Running code cleaning for year {year}")
        if video_filter:
            self.logger.info(f"Filtering to videos: {video_filter}")
        summary = self.cleaner.clean_all_matched_videos(year=year, video_filter=video_filter)
        
        self.pipeline_state['stages']['cleaning']['status'] = 'completed'
        self.pipeline_state['stages']['cleaning']['end_time'] = datetime.now().isoformat()
        self.pipeline_state['stages']['cleaning']['stats'] = summary.get('stats', {})
        
        return summary
        
    def run_conversion_stage(self, year: int, force: bool = False, video_filter: Optional[List[str]] = None) -> Dict:
        """Run the ManimGL to ManimCE conversion stage."""
        self.logger.info("=" * 60)
        self.logger.info("STAGE 3: ManimCE Conversion")
        self.logger.info("=" * 60)
        
        self.pipeline_state['stages']['conversion']['status'] = 'running'
        self.pipeline_state['stages']['conversion']['start_time'] = datetime.now().isoformat()
        
        # Get list of cleaned files to convert
        cleaned_files = []
        year_dir = self.output_dir / 'v5' / str(year)
        
        if not year_dir.exists():
            self.logger.warning(f"No cleaned files found for year {year}")
            self.pipeline_state['stages']['conversion']['status'] = 'skipped'
            return {}
            
        # Load excluded videos
        excluded_videos = self.load_excluded_videos()
        
        # Find all cleaned code files
        for video_dir in year_dir.iterdir():
            if video_dir.is_dir():
                # Apply video filter if specified
                if video_filter and video_dir.name not in video_filter:
                    continue
                    
                cleaned_file = video_dir / 'cleaned_code.py'
                match_file = video_dir / 'matches.json'
                
                if cleaned_file.exists() and match_file.exists():
                    # Check if this video should be processed
                    with open(match_file) as f:
                        match_data = json.load(f)
                        
                    should_process, reason = self.should_process_video(
                        video_dir.name, match_data, excluded_videos
                    )
                    
                    if should_process:
                        # Check if already converted
                        manimce_file = video_dir / 'manimce_code.py'
                        if not manimce_file.exists() or force:
                            cleaned_files.append(cleaned_file)
                    else:
                        self.logger.info(f"Skipping conversion for {video_dir.name}: {reason}")
                        
        self.logger.info(f"Found {len(cleaned_files)} files to convert")
        
        if not cleaned_files:
            self.logger.info("No files need conversion")
            self.pipeline_state['stages']['conversion']['status'] = 'skipped'
            return {}
            
        # Create conversion output directory
        conversion_dir = self.output_dir / 'manimce_conversion' / str(year)
        conversion_dir.mkdir(parents=True, exist_ok=True)
        
        # Run conversion on each file
        conversion_results = {
            'total_files': len(cleaned_files),
            'converted': 0,
            'failed': 0,
            'errors': []
        }
        
        for cleaned_file in cleaned_files:
            video_dir = cleaned_file.parent
            manimce_file = video_dir / 'manimce_code.py'
            
            try:
                self.logger.info(f"Converting {video_dir.name}")
                
                # Create converter instance for this file
                converter = ManimConverter(
                    source_dir=str(cleaned_file.parent),
                    output_dir=str(manimce_file.parent)
                )
                
                # Convert the file
                converted_content, was_converted = converter.convert_file(cleaned_file)
                
                # Write the converted code if successful
                if was_converted:
                    with open(manimce_file, 'w') as f:
                        f.write(converted_content)
                else:
                    raise Exception("Conversion failed")
                
                # Validate the converted file
                if manimce_file.exists():
                    with open(manimce_file) as f:
                        content = f.read()
                        
                    if len(content) > 100:  # Basic check
                        conversion_results['converted'] += 1
                        self.logger.info(f"Successfully converted {video_dir.name}")
                    else:
                        conversion_results['failed'] += 1
                        conversion_results['errors'].append({
                            'file': str(cleaned_file),
                            'error': 'Converted file is too small'
                        })
                else:
                    conversion_results['failed'] += 1
                    conversion_results['errors'].append({
                        'file': str(cleaned_file),
                        'error': 'Converted file not created'
                    })
                    
            except Exception as e:
                self.logger.error(f"Failed to convert {video_dir.name}: {e}")
                conversion_results['failed'] += 1
                conversion_results['errors'].append({
                    'file': str(cleaned_file),
                    'error': str(e)
                })
                
            # Small delay to avoid overwhelming the system
            time.sleep(0.5)
            
        # Save conversion summary
        conversion_summary = {
            'year': year,
            'timestamp': datetime.now().isoformat(),
            'results': conversion_results
        }
        
        summary_file = conversion_dir / 'conversion_summary.json'
        with open(summary_file, 'w') as f:
            json.dump(conversion_summary, f, indent=2)
            
        self.pipeline_state['stages']['conversion']['status'] = 'completed'
        self.pipeline_state['stages']['conversion']['end_time'] = datetime.now().isoformat()
        self.pipeline_state['stages']['conversion']['stats'] = conversion_results
        
        self.logger.info(f"Conversion complete: {conversion_results['converted']} succeeded, "
                        f"{conversion_results['failed']} failed")
        
        return conversion_summary
        
    def run_rendering_stage(self, year: int, quality: str = 'preview', 
                           limit: Optional[int] = None, scenes_limit: Optional[int] = None,
                           video_filter: Optional[List[str]] = None) -> Dict:
        """Run the video rendering stage."""
        self.logger.info("=" * 60)
        self.logger.info("STAGE 4: Video Rendering")
        self.logger.info("=" * 60)
        
        self.pipeline_state['stages']['rendering']['status'] = 'running'
        self.pipeline_state['stages']['rendering']['start_time'] = datetime.now().isoformat()
        
        # Check if rendering has already been done
        summary_file = self.output_dir / 'rendered_videos' / str(year) / f'rendering_summary_{quality}.json'
        if summary_file.exists() and not self.verbose:
            self.logger.info(f"Found existing rendering results at {summary_file}")
            with open(summary_file) as f:
                existing_summary = json.load(f)
                
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
        
    def generate_final_report(self, year: int):
        """Generate a comprehensive report of the entire pipeline run."""
        self.pipeline_state['end_time'] = datetime.now().isoformat()
        
        # Calculate total duration
        if self.pipeline_state['start_time']:
            start = datetime.fromisoformat(self.pipeline_state['start_time'])
            end = datetime.fromisoformat(self.pipeline_state['end_time'])
            duration = (end - start).total_seconds()
            self.pipeline_state['duration_seconds'] = duration
            
        # Save pipeline state
        report_file = self.output_dir / f'pipeline_report_{year}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(report_file, 'w') as f:
            json.dump(self.pipeline_state, f, indent=2)
            
        # Generate human-readable report
        report_text = f"""
3Blue1Brown Dataset Pipeline Report
===================================
Year: {year}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Stage 1: Video Matching
-----------------------
Status: {self.pipeline_state['stages']['matching']['status']}
Stats: {json.dumps(self.pipeline_state['stages']['matching']['stats'], indent=2)}

Stage 2: Code Cleaning
----------------------
Status: {self.pipeline_state['stages']['cleaning']['status']}
Stats: {json.dumps(self.pipeline_state['stages']['cleaning']['stats'], indent=2)}

Stage 3: ManimCE Conversion
---------------------------
Status: {self.pipeline_state['stages']['conversion']['status']}
Stats: {json.dumps(self.pipeline_state['stages']['conversion']['stats'], indent=2)}

Stage 4: Video Rendering
------------------------
Status: {self.pipeline_state['stages']['rendering']['status']}
Stats: {json.dumps(self.pipeline_state['stages']['rendering']['stats'], indent=2)}

Total Duration: {self.pipeline_state.get('duration_seconds', 0):.1f} seconds

Output Locations:
- Matched files: {self.output_dir}/v5/{year}/*/matches.json
- Cleaned code: {self.output_dir}/v5/{year}/*/cleaned_code.py
- ManimCE code: {self.output_dir}/v5/{year}/*/manimce_code.py
- Rendered videos: {self.output_dir}/rendered_videos/{year}/*/
- Logs: {self.log_dir}/
"""
        
        report_text_file = self.output_dir / f'pipeline_report_{year}.txt'
        with open(report_text_file, 'w') as f:
            f.write(report_text)
            
        print(report_text)
        self.logger.info(f"Pipeline report saved to {report_file}")
        
    def run_full_pipeline(self, year: int = 2015, skip_matching: bool = False,
                         skip_cleaning: bool = False, skip_conversion: bool = False,
                         skip_rendering: bool = False, force_clean: bool = False, 
                         force_convert: bool = False, render_quality: str = 'preview',
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
        
        try:
            # Stage 1: Matching
            if not skip_matching:
                self.run_matching_stage(year, video_filter=video_filter)
            else:
                self.logger.info("Skipping matching stage")
                self.pipeline_state['stages']['matching']['status'] = 'skipped'
                
            # Stage 2: Cleaning
            if not skip_cleaning:
                self.run_cleaning_stage(year, force=force_clean, video_filter=video_filter)
            else:
                self.logger.info("Skipping cleaning stage")
                self.pipeline_state['stages']['cleaning']['status'] = 'skipped'
                
            # Stage 3: Conversion
            if not skip_conversion:
                self.run_conversion_stage(year, force=force_convert, video_filter=video_filter)
            else:
                self.logger.info("Skipping conversion stage")
                self.pipeline_state['stages']['conversion']['status'] = 'skipped'
                
            # Stage 4: Rendering
            if not skip_rendering:
                self.run_rendering_stage(year, quality=render_quality, 
                                       limit=render_limit, scenes_limit=render_scenes_limit,
                                       video_filter=video_filter)
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
    parser.add_argument('--force-clean', action='store_true',
                        help='Force re-cleaning of already cleaned files')
    parser.add_argument('--force-convert', action='store_true',
                        help='Force re-conversion of already converted files')
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
    
    # Handle render preview shortcut
    if args.render_preview:
        args.render = True  # Enable rendering
        args.render_limit = args.render_limit or 5
        args.render_scenes_limit = args.render_scenes_limit or 2
    
    # Create pipeline builder
    base_dir = Path(__file__).parent.parent
    builder = DatasetPipelineBuilder(base_dir, verbose=args.verbose)
    
    # Run pipeline
    builder.run_full_pipeline(
        year=args.year,
        skip_matching=args.skip_matching,
        skip_cleaning=args.skip_cleaning,
        skip_conversion=args.skip_conversion,
        skip_rendering=not args.render,  # Invert the logic: render flag enables rendering
        force_clean=args.force_clean,
        force_convert=args.force_convert,
        render_quality=args.render_quality,
        render_limit=args.render_limit,
        render_scenes_limit=args.render_scenes_limit,
        video_filter=args.video
    )

if __name__ == '__main__':
    main()