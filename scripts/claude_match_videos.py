#!/usr/bin/env python3
"""
Use Claude to intelligently match videos to their corresponding code files.
This replaces the hardcoded mapping approach with AI-powered analysis.
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import subprocess
import sys

class ClaudeVideoMatcher:
    def __init__(self, base_dir: str, verbose: bool = False):
        self.base_dir = Path(base_dir)
        self.data_dir = self.base_dir / 'data'
        self.output_dir = self.base_dir / 'output'
        self.claude_results_dir = self.output_dir / 'claude_matches'
        self.claude_results_dir.mkdir(parents=True, exist_ok=True)
        self.verbose = verbose
        self.excluded_videos = self.load_excluded_videos()
        
    def load_video_mappings(self) -> Dict:
        """Load the video mappings from extract_video_urls.py output."""
        mappings_file = self.data_dir / 'youtube_metadata' / '2015_video_mappings.json'
        if not mappings_file.exists():
            raise FileNotFoundError(f"Run extract_video_urls.py first: {mappings_file}")
        
        with open(mappings_file) as f:
            return json.load(f)
    
    def load_excluded_videos(self) -> set:
        """Load the list of excluded videos from excluded-videos.txt."""
        excluded_file = self.base_dir / 'excluded-videos.txt'
        excluded_ids = set()
        
        if not excluded_file.exists():
            print("Warning: No excluded-videos.txt file found.")
            return excluded_ids
        
        with open(excluded_file, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and header lines
                if not line or line.startswith('We should') or line.startswith('List of'):
                    continue
                
                # Extract video ID from lines like "- title https://..."
                if line.startswith('- '):
                    # Extract URL
                    import re
                    url_match = re.search(r'https://[^\s]+', line)
                    if url_match:
                        url = url_match.group(0)
                        # Extract video ID from URL
                        video_id_match = re.search(r'[?&]v=([a-zA-Z0-9_-]+)', url)
                        if video_id_match:
                            video_id = video_id_match.group(1)
                            excluded_ids.add(video_id)
        
        print(f"Loaded {len(excluded_ids)} excluded video IDs")
        return excluded_ids
    
    def load_transcript(self, year: int, caption_dir: str) -> Tuple[str, str]:
        """Load transcript and video title for a given video."""
        transcript_path = self.data_dir / 'captions' / str(year) / caption_dir / 'english' / 'sentence_timings.json'
        title_path = self.data_dir / 'captions' / str(year) / caption_dir / 'english' / 'title.json'
        
        transcript = ""
        title = caption_dir.replace('-', ' ').title()
        
        if transcript_path.exists():
            with open(transcript_path) as f:
                data = json.load(f)
                if data:
                    sentences = [item[0] for item in data if isinstance(item, list) and len(item) >= 1]
                    transcript = ' '.join(sentences)
        
        if title_path.exists():
            with open(title_path) as f:
                title_data = json.load(f)
                if 'input' in title_data:
                    title = title_data['input']
        
        return transcript, title
    
    def create_matching_prompt(self, video_info: Dict, transcript: str, title: str, year: int) -> str:
        """Create a prompt for Claude to find matching code files."""
        
        # Make output path absolute to avoid confusion
        output_path = self.output_dir / "v5" / str(year) / video_info['caption_dir'] / "matches.json"
        output_path_str = str(output_path)
        
        return f"""You are helping match 3Blue1Brown videos to their Manim source code.

Video Information:
- Title: {title}
- YouTube ID: {video_info['video_id']}
- URL: {video_info['url']}
- Year: {year}
- Caption Directory: {video_info['caption_dir']}

Transcript:
If there is no transcript, skip the rest of the matching process and 
create a file at {output_path_str} with {{'status': 'no_transcript', 'video_id': '{video_info['video_id']}'}}. 
{transcript[:3000]}...

YOUR TASK - find the code needed to replicate this video and no more:
1. Search in the directory: data/videos/_{year}/ for Python files
2. Look for files that contain:
   - Scene classes that match the video content
   - Mathematical concepts mentioned in the transcript
   - Animation code that would produce the visuals described
   - Comments or class names that reference the video topic

3. Use these search strategies:
   - Search for key mathematical terms from the transcript
   - Look for class names containing relevant words
   - Check for animation methods that match described visuals
   - Consider file names similar to: {video_info['caption_dir'].replace('-', '_')}

4. IMPORTANT: Create and save your findings to this exact file path:
   {output_path_str}
   
   First create the directory if needed (mkdir -p the parent directory), then write the JSON file with this format:
{{
    "primary_files": ["file1.py", "file2.py"],  // Main files that generate this video
    "supporting_files": ["helper1.py"],         // Helper/utility files used
    "confidence_score": 0.95,                   // 0-1 score of match confidence
    "evidence": [                               // Key evidence for the match
        "Found class BinaryCountingScene that creates binary number animations",
        "Transcript mentions 'binary counting' which matches CountingInBinary class"
    ],
    "search_queries_used": [                    // What you searched for
        "binary", "counting", "decimal"
    ],
    "video_id": "{video_info['video_id']}",
    "status": "matched"
}}

IMPORTANT: Use the Write tool to actually create this file. Do not just output the JSON.
If confidence is below 0.5, set status to "low_confidence" in the JSON.

Please search thoroughly and provide the most accurate match possible."""

    # REMOVED: Cleaning functionality moved to clean_matched_code.py

    def run_claude_search(self, prompt: str, video_id: str) -> Dict:
        """Execute Claude search for a single video."""
        # Create a temporary prompt file
        prompt_file = self.claude_results_dir / f"{video_id}_prompt.txt"
        with open(prompt_file, 'w') as f:
            f.write(prompt)
    
        result_file = self.claude_results_dir / f"{video_id}_result.txt"
        
        # Call Claude using subprocess to process the prompt
        try:
            print(f"  🤖 Calling Claude for video: {video_id}")
            
            # Run claude-cli with the prompt
            if self.verbose:
                # Run with output streaming to console
                process = subprocess.Popen(
                    ["claude", "--continue", "--dangerously-skip-permissions", "--model", "sonnet", "-p", prompt],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Collect output while also printing it
                stdout_lines = []
                stderr_lines = []
                
                # Read stdout in real-time
                for line in iter(process.stdout.readline, ''):
                    if line:
                        print(f"    Claude: {line.rstrip()}")
                        stdout_lines.append(line)
                
                # Wait for process to complete
                process.wait()
                
                # Get any remaining stderr
                stderr = process.stderr.read()
                if stderr:
                    stderr_lines.append(stderr)
                
                result = subprocess.CompletedProcess(
                    args=process.args,
                    returncode=process.returncode,
                    stdout=''.join(stdout_lines),
                    stderr=''.join(stderr_lines)
                )
            else:
                # Original behavior - capture output silently
                result = subprocess.run(
                    ["claude", "--continue", "--dangerously-skip-permissions", "--model", "sonnet", "-p", prompt],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
            
            # Check if command succeeded
            if result.returncode != 0:
                error_file = self.claude_results_dir / f"{video_id}_error.txt"
                with open(error_file, 'w') as f:
                    f.write(f"Return code: {result.returncode}\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}")
                return {
                    "status": "error",
                    "prompt_file": str(prompt_file),
                    "error_file": str(error_file),
                    "video_id": video_id,
                    "error": f"Claude returned non-zero exit code: {result.returncode}"
                }
            
            # Save the Claude response
            with open(result_file, 'w') as f:
                f.write(result.stdout)
            
            return {
                "status": "completed",
                "prompt_file": str(prompt_file),
                "result_file": str(result_file),
                "video_id": video_id,
                "response": result.stdout
            }
        
        except FileNotFoundError:
            print(f"  ❌ Claude CLI not found. Please install it first.")
            return {
                "status": "error",
                "prompt_file": str(prompt_file),
                "video_id": video_id,
                "error": "Claude CLI not installed"
            }
        
        except subprocess.TimeoutExpired:
            print(f"  ❌ Claude call timed out after 5 minutes")
            return {
                "status": "error",
                "prompt_file": str(prompt_file),
                "video_id": video_id,
                "error": "Claude request timed out"
            }
                
        except Exception as e:
            print(f"  ❌ Unexpected error: {e}")
            # Save the error output
            error_file = self.claude_results_dir / f"{video_id}_error.txt"
            with open(error_file, 'w') as f:
                f.write(f"Error: {str(e)}\nType: {type(e).__name__}")
            
            return {
                "status": "error",
                "prompt_file": str(prompt_file),
                "error_file": str(error_file),
                "video_id": video_id,
                "error": str(e)
            }
    
    # REMOVED: Cleaning functionality moved to clean_matched_code.py
        

    def match_all_videos(self, year: int = 2015, video_filter: Optional[List[str]] = None):
        """Run Claude matching for all videos in a given year."""
        video_mappings = self.load_video_mappings()
        results = {}
        
        # Apply video filter if specified
        if video_filter:
            filtered_mappings = {k: v for k, v in video_mappings.items() if k in video_filter}
            print(f"Filtering to {len(filtered_mappings)} videos: {video_filter}")
            video_mappings = filtered_mappings
        
        print(f"Starting Claude-based matching for {len(video_mappings)} videos...")
        
        for caption_dir, video_info in video_mappings.items():
            print(f"\nProcessing: {caption_dir}")
            
            # Check if video is excluded
            if video_info['video_id'] in self.excluded_videos:
                print(f"  ⚠️  EXCLUDED: Video is in exclusion list")
                results[caption_dir] = {
                    "status": "excluded",
                    "reason": "in_exclusion_list",
                    "video_id": video_info['video_id']
                }
                continue
            
            try:
                # Load transcript and title
                transcript, title = self.load_transcript(year, caption_dir)
                
                if not transcript:
                    print(f"  ⚠️  No transcript found, skipping...")
                    results[caption_dir] = {
                        "status": "skipped",
                        "reason": "no_transcript"
                    }
                    continue
                
                # Add title to video_info for later use
                video_info['title'] = title
                
                # Create prompt
                matching_prompt = self.create_matching_prompt(video_info, transcript, title, year)
                
                # Run Claude search
                result = self.run_claude_search(matching_prompt, video_info['video_id'])
                results[caption_dir] = result
                print(f"  ✓ Search task {'completed' if result['status'] == 'completed' else 'failed'}")

                if result['status'] == 'completed':
                    # Read the JSON file Claude created
                    match_file_path = self.output_dir / f"v5/{year}/{video_info['caption_dir']}/matches.json"
                    
                    if match_file_path.exists():
                        with open(match_file_path) as f:
                            match_data = json.load(f)
                        
                        # Store match data in results
                        results[caption_dir]['match_data'] = match_data
                        
                        # Check confidence threshold
                        confidence = match_data.get('confidence_score', 0)
                        if confidence < 0.8:
                            print(f"  ⚠️  Low confidence match ({confidence})")
                            results[caption_dir]['status'] = 'low_confidence'
                        else:
                            print(f"  ✓ High confidence match ({confidence})")
                    else:
                        print(f"  ❌ Match file not created by Claude at {match_file_path}")
                        results[caption_dir]['status'] = 'no_match_file'
                else:
                    print(f"  ❌ Claude search failed for {video_info['video_id']}: {result.get('error', 'Unknown error')}")
                
                # Small delay between API calls
                time.sleep(5)
                
            except Exception as e:
                print(f"  ❌ Error: {e}")
                results[caption_dir] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return results

    def validate_match(self, match_data: Dict, transcript: str) -> Dict:
        """Basic validation of match quality."""
        validation = {
            "has_primary_files": bool(match_data.get('primary_files')),
            "reasonable_file_count": 1 <= len(match_data.get('primary_files', [])) <= 10,
            "has_evidence": bool(match_data.get('evidence')),
            "confidence_above_threshold": match_data.get('confidence_score', 0) >= 0.5
        }
        
        validation['is_valid'] = all(validation.values())
        return validation

    def save_final_results(self, results: Dict, year: int):
        """Save a summary of all matching results."""
        summary = {
            "year": year,
            "total_videos": len(results),
            "successful_matches": sum(1 for r in results.values() if r.get('status') == 'completed' and 'match_data' in r and r['match_data'].get('confidence_score', 0) >= 0.8),
            "low_confidence_matches": sum(1 for r in results.values() if r.get('status') == 'low_confidence'),
            "failed_matches": sum(1 for r in results.values() if r.get('status') == 'error'),
            "skipped_videos": sum(1 for r in results.values() if r.get('status') == 'skipped'),
            "excluded_videos": sum(1 for r in results.values() if r.get('status') == 'excluded'),
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "results": results
        }
        
        summary_file = self.output_dir / f'matching_summary_{year}.json'
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\nSummary saved to: {summary_file}")
        return summary

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Match 3Blue1Brown videos to their source code using Claude')
    parser.add_argument('--verbose', '-v', action='store_true', 
                        help='Show Claude\'s output in real-time')
    parser.add_argument('--year', type=int, default=2015,
                        help='Year to process (default: 2015)')
    
    args = parser.parse_args()
    
    base_dir = Path(__file__).parent.parent
    matcher = ClaudeVideoMatcher(base_dir, verbose=args.verbose)
    
    # Run the matching process
    results = matcher.match_all_videos(year=args.year)
    
    # Save summary
    summary = matcher.save_final_results(results, args.year)
    
    print("\nNext steps:")
    print("1. Review any errors in output/claude_matches/*_error.txt")
    print(f"2. Check low confidence matches in output/v5/{args.year}/*/matches.json")
    print(f"3. Run the cleaning script: python scripts/clean_matched_code.py --year {args.year}")
    print(f"4. Run the full pipeline: python scripts/build_dataset_pipeline.py --year {args.year}")
    print(f"\nStats:")
    print(f"- Successful matches: {summary['successful_matches']}/{summary['total_videos']}")
    print(f"- Low confidence: {summary['low_confidence_matches']}")
    print(f"- Failed: {summary['failed_matches']}")
    print(f"- Skipped (no transcript): {summary['skipped_videos']}")
    print(f"- Excluded (not Manim): {summary.get('excluded_videos', 0)}")

if __name__ == '__main__':
    main()