#!/usr/bin/env python3
"""
Clean and inline matched code files for 3Blue1Brown videos.
This script reads the matched files from claude_match_videos.py output
and creates self-contained, cleaned versions with all local imports inlined.
"""

import json
import time
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime

class CodeCleaner:
    def __init__(self, base_dir: str, verbose: bool = False):
        self.base_dir = Path(base_dir)
        self.output_dir = self.base_dir / 'output'
        self.data_dir = self.base_dir / 'data'
        self.verbose = verbose
        
        # Setup logging
        self.log_dir = self.output_dir / 'cleaning_logs'
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure logger
        log_file = self.log_dir / f"cleaning_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler() if verbose else logging.NullHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def load_match_results(self, year: int) -> Dict[str, Dict]:
        """Load all match results for a given year."""
        results = {}
        year_dir = self.output_dir / 'v5' / str(year)
        
        if not year_dir.exists():
            self.logger.warning(f"No match results found for year {year}")
            return results
            
        # Iterate through all video directories
        for video_dir in year_dir.iterdir():
            if video_dir.is_dir():
                match_file = video_dir / 'matches.json'
                if match_file.exists():
                    with open(match_file) as f:
                        match_data = json.load(f)
                        results[video_dir.name] = match_data
                        
        self.logger.info(f"Loaded {len(results)} match results for year {year}")
        return results
        
    def should_clean_video(self, match_data: Dict) -> Tuple[bool, str]:
        """Determine if a video should be cleaned based on match data."""
        # Check if status indicates a successful match
        status = match_data.get('status', '')
        if status == 'no_transcript':
            return False, "No transcript available"
        
        # Check confidence score
        confidence = match_data.get('confidence_score', 0)
        if confidence < 0.8:
            return False, f"Low confidence score: {confidence}"
            
        # Check if primary files exist
        primary_files = match_data.get('primary_files', [])
        if not primary_files:
            return False, "No primary files identified"
            
        # Check if it's already been cleaned
        # This allows re-running without reprocessing
        if match_data.get('cleaning_status') == 'completed':
            return False, "Already cleaned"
            
        return True, "Ready for cleaning"
        
    def create_cleaning_prompt(self, video_id: str, caption_dir: str, 
                             match_data: Dict, year: int) -> str:
        """Create a prompt for Claude to clean and inline code."""
        primary_files = match_data.get('primary_files', [])
        supporting_files = match_data.get('supporting_files', [])
        all_files = primary_files + supporting_files
        
        output_path = self.output_dir / 'v5' / str(year) / caption_dir / 'cleaned_code.py'
        
        return f"""You are an expert in cleaning and inlining Manim code for the 3Blue1Brown dataset.

Video Information:
- YouTube ID: {video_id}
- Caption Directory: {caption_dir}
- Year: {year}
- Confidence Score: {match_data.get('confidence_score', 0)}

The following files were identified as generating this video:
Primary files: {json.dumps(primary_files, indent=2)}
Supporting files: {json.dumps(supporting_files, indent=2)}

Your task:
1. Read ALL these files from data/videos/_{year}/
2. Create a single, self-contained Python script that includes all necessary code
3. Inline all local imports while preserving external imports (numpy, manim, etc.)
4. Remove any unused code or imports
5. Ensure the final script is syntactically valid and can run independently

CRITICAL INSTRUCTION - DO NOT CONVERT MANIM VERSIONS:
- Keep the ORIGINAL ManimGL code as-is
- DO NOT convert from manimlib to manim imports
- DO NOT change TextMobject to Text, TexMobject to MathTex, etc.
- DO NOT modernize or update any Manim syntax
- Preserve the exact Manim version used in the original files
- If you see "from manimlib import *" or "from manim_imports_ext import *", keep it exactly as is

Important guidelines:
- Preserve the original scene classes and their functionality
- Keep all animation logic intact
- Inline helper functions and classes from supporting files
- Add clear comments showing where inlined code came from
- The output should be a complete, runnable ManimGL script (NOT ManimCE)

Save the cleaned code to: {output_path}

Include this header:
```python
# Video: [Title if available]
# YouTube ID: {video_id}
# Generated from: {', '.join(all_files)}
# Cleaned on: {datetime.now().isoformat()}
# Manim version: ManimGL (original 3b1b version)
```

If you cannot create a valid cleaned file (e.g., files don't exist, code is incomplete), 
create a file with comments explaining what went wrong."""
        
    def run_claude_cleaning(self, prompt: str, video_id: str, caption_dir: str) -> Dict:
        """Execute Claude to clean a single video's code."""
        prompt_file = self.log_dir / f"{video_id}_cleaning_prompt.txt"
        with open(prompt_file, 'w') as f:
            f.write(prompt)
            
        try:
            self.logger.info(f"Running Claude cleaning for {caption_dir}")
            
            # Run Claude with the cleaning prompt
            result = subprocess.run(
                ["claude", "--continue", "--dangerously-skip-permissions", 
                 "--model", "sonnet", "-p", prompt],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                error_msg = f"Claude returned non-zero exit code: {result.returncode}"
                self.logger.error(f"{caption_dir}: {error_msg}")
                return {
                    "status": "error",
                    "error": error_msg,
                    "stderr": result.stderr
                }
                
            # Save Claude's response
            response_file = self.log_dir / f"{video_id}_cleaning_response.txt"
            with open(response_file, 'w') as f:
                f.write(result.stdout)
                
            return {
                "status": "completed",
                "prompt_file": str(prompt_file),
                "response_file": str(response_file)
            }
            
        except subprocess.TimeoutExpired:
            error_msg = "Claude cleaning timed out after 5 minutes"
            self.logger.error(f"{caption_dir}: {error_msg}")
            return {"status": "error", "error": error_msg}
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.error(f"{caption_dir}: {error_msg}")
            return {"status": "error", "error": error_msg}
            
    def validate_cleaned_code(self, file_path: Path) -> Tuple[bool, Optional[str]]:
        """Validate that the cleaned code is syntactically correct."""
        if not file_path.exists():
            return False, "File does not exist"
            
        try:
            with open(file_path) as f:
                code = f.read()
                
            # Check if it's just an error message
            if code.strip().startswith("#") and "error" in code.lower():
                return False, "File contains error message instead of code"
                
            # Try to compile the code
            compile(code, str(file_path), 'exec')
            return True, None
            
        except SyntaxError as e:
            return False, f"Syntax error: {e}"
        except Exception as e:
            return False, f"Validation error: {e}"
            
    def clean_all_matched_videos(self, year: int = 2015, video_filter: Optional[List[str]] = None) -> Dict:
        """Clean all successfully matched videos for a given year."""
        # Load match results
        match_results = self.load_match_results(year)
        
        if not match_results:
            self.logger.warning(f"No match results found for year {year}")
            return {}
            
        # Apply video filter if specified
        if video_filter:
            filtered_results = {k: v for k, v in match_results.items() if k in video_filter}
            self.logger.info(f"Filtering to {len(filtered_results)} videos: {video_filter}")
            match_results = filtered_results
            
        cleaning_results = {}
        stats = {
            'total_matched': len(match_results),
            'cleaned': 0,
            'skipped': 0,
            'failed': 0,
            'low_confidence': 0,
            'no_files': 0
        }
        
        self.logger.info(f"Starting cleaning process for {len(match_results)} matched videos")
        
        for caption_dir, match_data in match_results.items():
            video_id = match_data.get('video_id', 'unknown')
            
            # Check if we should clean this video
            should_clean, reason = self.should_clean_video(match_data)
            
            if not should_clean:
                self.logger.info(f"Skipping {caption_dir}: {reason}")
                cleaning_results[caption_dir] = {
                    'status': 'skipped',
                    'reason': reason
                }
                stats['skipped'] += 1
                
                if 'low confidence' in reason.lower():
                    stats['low_confidence'] += 1
                elif 'no primary files' in reason.lower():
                    stats['no_files'] += 1
                continue
                
            # Create cleaning prompt
            prompt = self.create_cleaning_prompt(video_id, caption_dir, match_data, year)
            
            # Run cleaning
            result = self.run_claude_cleaning(prompt, video_id, caption_dir)
            
            if result['status'] == 'completed':
                # Validate the cleaned code
                cleaned_file = self.output_dir / 'v5' / str(year) / caption_dir / 'cleaned_code.py'
                is_valid, error = self.validate_cleaned_code(cleaned_file)
                
                if is_valid:
                    self.logger.info(f"Successfully cleaned {caption_dir}")
                    result['validation'] = 'passed'
                    stats['cleaned'] += 1
                else:
                    self.logger.warning(f"Cleaned code validation failed for {caption_dir}: {error}")
                    result['validation'] = 'failed'
                    result['validation_error'] = error
                    stats['failed'] += 1
            else:
                stats['failed'] += 1
                
            cleaning_results[caption_dir] = result
            
            # Update the match file with cleaning status
            match_data['cleaning_status'] = result['status']
            match_data['cleaning_timestamp'] = datetime.now().isoformat()
            
            match_file = self.output_dir / 'v5' / str(year) / caption_dir / 'matches.json'
            with open(match_file, 'w') as f:
                json.dump(match_data, f, indent=2)
                
            # Small delay between API calls
            time.sleep(2)
            
        # Save cleaning summary
        summary = {
            'year': year,
            'timestamp': datetime.now().isoformat(),
            'stats': stats,
            'results': cleaning_results
        }
        
        summary_file = self.output_dir / f'cleaning_summary_{year}.json'
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
            
        self.logger.info(f"Cleaning complete. Summary saved to {summary_file}")
        self.logger.info(f"Stats: {stats}")
        
        return summary

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Clean matched 3Blue1Brown code files')
    parser.add_argument('--year', type=int, default=2015,
                        help='Year to process (default: 2015)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output')
    parser.add_argument('--video', type=str,
                        help='Clean a specific video by caption directory name')
    
    args = parser.parse_args()
    
    base_dir = Path(__file__).parent.parent
    cleaner = CodeCleaner(base_dir, verbose=args.verbose)
    
    if args.video:
        # Clean a specific video
        match_results = cleaner.load_match_results(args.year)
        if args.video in match_results:
            match_data = match_results[args.video]
            should_clean, reason = cleaner.should_clean_video(match_data)
            
            if should_clean:
                video_id = match_data.get('video_id', 'unknown')
                prompt = cleaner.create_cleaning_prompt(video_id, args.video, match_data, args.year)
                result = cleaner.run_claude_cleaning(prompt, video_id, args.video)
                print(f"Cleaning result: {result}")
            else:
                print(f"Video should not be cleaned: {reason}")
        else:
            print(f"No match data found for video: {args.video}")
    else:
        # Clean all matched videos
        summary = cleaner.clean_all_matched_videos(year=args.year)
        
        print("\nCleaning Summary:")
        print(f"Total matched videos: {summary['stats']['total_matched']}")
        print(f"Successfully cleaned: {summary['stats']['cleaned']}")
        print(f"Skipped: {summary['stats']['skipped']}")
        print(f"  - Low confidence: {summary['stats']['low_confidence']}")
        print(f"  - No files: {summary['stats']['no_files']}")
        print(f"Failed: {summary['stats']['failed']}")

if __name__ == '__main__':
    main()