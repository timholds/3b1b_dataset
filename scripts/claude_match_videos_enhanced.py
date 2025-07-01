#!/usr/bin/env python3
"""
Enhanced version of claude_match_videos.py with integrated prompt optimization.
Uses improved prompts with few-shot examples and adaptive learning.
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import subprocess
import sys

# Import model strategy
from model_strategy import get_model_for_task

# Import our new optimization modules
from improved_prompts import VIDEO_MATCHING_PROMPT, format_prompt
from adaptive_prompt_optimizer import AdaptivePromptOptimizer
from prompt_feedback_system import PromptFeedbackSystem, PromptResult

class EnhancedClaudeVideoMatcher:
    def __init__(self, base_dir: str, verbose: bool = False):
        self.base_dir = Path(base_dir)
        self.data_dir = self.base_dir / 'data'
        self.output_dir = self.base_dir / 'outputs'
        self.claude_results_dir = self.output_dir / 'claude_matches'
        self.claude_results_dir.mkdir(parents=True, exist_ok=True)
        self.verbose = verbose
        self.excluded_videos = self.load_excluded_videos()
        
        # Initialize optimization systems
        self.optimizer = AdaptivePromptOptimizer(
            cache_dir=str(self.output_dir / 'prompt_optimization')
        )
        self.feedback_system = PromptFeedbackSystem(
            feedback_dir=str(self.output_dir / 'prompt_feedback')
        )
        
    def load_video_mappings(self, year: int) -> Dict:
        """Load the video mappings from extract_video_urls.py output."""
        mappings_file = self.data_dir / 'youtube_metadata' / f'{year}_video_mappings.json'
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
    
    def get_video_transcript(self, year: int, caption_dir: str) -> str:
        """Read transcript from caption file."""
        caption_file = self.data_dir / 'captions' / str(year) / caption_dir / 'transcript.txt'
        
        if not caption_file.exists():
            return ""
            
        with open(caption_file, 'r', encoding='utf-8') as f:
            return f.read()
    
    def create_enhanced_matching_prompt(self, video_info: Dict, year: int, transcript: str, 
                                      output_path: Path) -> str:
        """Create an enhanced matching prompt with optimization."""
        # Extract expected filename pattern
        expected_filename = video_info['caption_dir'].replace('-', '_')
        
        # Get optimized prompt and search terms
        base_prompt = VIDEO_MATCHING_PROMPT
        optimized_prompt, suggested_terms = self.optimizer.optimize_matching_prompt(
            base_prompt, transcript, year
        )
        
        # Format the prompt with all parameters
        formatted_prompt = format_prompt(
            optimized_prompt,
            title=video_info.get('title', 'Unknown'),
            video_id=video_info['video_id'],
            year=year,
            caption_dir=video_info['caption_dir'],
            transcript=transcript,
            expected_filename=expected_filename,
            output_path=str(output_path)
        )
        
        # Store suggested terms for later use
        self.current_search_terms = suggested_terms
        
        return formatted_prompt

    def run_claude_search(self, prompt: str, video_id: str) -> Dict:
        """Execute Claude search for a single video with feedback tracking."""
        start_time = time.time()
        
        # Create a temporary prompt file
        prompt_file = self.claude_results_dir / f"{video_id}_prompt.txt"
        with open(prompt_file, 'w') as f:
            f.write(prompt)
    
        result_file = self.claude_results_dir / f"{video_id}_result.txt"
        
        # Initialize prompt result for tracking
        prompt_result = PromptResult(
            prompt_type="matching",
            success=False,
            confidence=0.0,
            attempt_number=1
        )
        
        # Call Claude using subprocess to process the prompt
        try:
            # Get appropriate model for matching task
            model = get_model_for_task("match_videos")
            print(f"  🤖 Calling Claude ({model}) for video: {video_id}")
            claude_command = ["claude", "--dangerously-skip-permissions", "--model", model]
            
            # Run claude-cli with the prompt
            if self.verbose:
                # Run with output streaming to console
                process = subprocess.Popen(
                    claude_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    text=True,
                    bufsize=1  # Line buffered
                )
                
                # Send the prompt to stdin
                process.stdin.write(prompt)
                process.stdin.close()
                
                # Collect output while also printing it
                stdout_lines = []
                
                # Read stdout in real-time
                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    if line:
                        print(f"    Claude: {line.rstrip()}")
                        stdout_lines.append(line)
                
                # Get any remaining stderr
                stderr = process.stderr.read()
                
                result = subprocess.CompletedProcess(
                    args=process.args,
                    returncode=process.returncode,
                    stdout=''.join(stdout_lines),
                    stderr=stderr
                )
            else:
                # Original behavior - capture output silently
                result = subprocess.run(
                    claude_command,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
            
            # Check if command succeeded
            if result.returncode != 0:
                error_file = self.claude_results_dir / f"{video_id}_error.txt"
                with open(error_file, 'w') as f:
                    f.write(f"Return code: {result.returncode}\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}")
                
                prompt_result.error_type = "claude_error"
                prompt_result.execution_time = time.time() - start_time
                self.feedback_system.record_result(prompt_result)
                
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
            
            # Track success
            prompt_result.success = True
            prompt_result.execution_time = time.time() - start_time
            self.feedback_system.record_result(prompt_result)
            
            return {
                "process_status": "completed",
                "prompt_file": str(prompt_file),
                "result_file": str(result_file),
                "video_id": video_id,
                "response": result.stdout
            }
        
        except FileNotFoundError:
            print(f"  ❌ Claude CLI not found. Please install it first.")
            prompt_result.error_type = "cli_not_found"
            prompt_result.execution_time = time.time() - start_time
            self.feedback_system.record_result(prompt_result)
            
            return {
                "process_status": "error",
                "prompt_file": str(prompt_file),
                "video_id": video_id,
                "error": "Claude CLI not installed"
            }
        
        except subprocess.TimeoutExpired:
            print(f"  ❌ Claude request timed out after 5 minutes")
            prompt_result.error_type = "timeout"
            prompt_result.execution_time = time.time() - start_time
            self.feedback_system.record_result(prompt_result)
            
            return {
                "process_status": "error",
                "prompt_file": str(prompt_file),
                "video_id": video_id,
                "error": "Claude request timed out"
            }
        
        except Exception as e:
            print(f"  ❌ Unexpected error: {str(e)}")
            prompt_result.error_type = "unexpected_error"
            prompt_result.execution_time = time.time() - start_time
            self.feedback_system.record_result(prompt_result)
            
            return {
                "process_status": "error",
                "prompt_file": str(prompt_file),
                "video_id": video_id,
                "error": f"Unexpected error: {str(e)}"
            }
    
    def match_single_video(self, video_info: Dict, year: int) -> Dict:
        """Match a single video to its code files with enhanced prompts."""
        video_id = video_info['video_id']
        caption_dir = video_info['caption_dir']
        
        # Skip if video is excluded
        if video_id in self.excluded_videos:
            print(f"  ⏭️  Skipping excluded video: {video_id}")
            return {
                "status": "excluded",
                "video_id": video_id
            }
        
        # Get transcript
        transcript = self.get_video_transcript(year, caption_dir)
        
        # Prepare output path
        output_path = self.output_dir / str(year) / caption_dir / 'matches.json'
        
        # Check if already matched
        if output_path.exists() and not self.verbose:
            with open(output_path) as f:
                existing = json.load(f)
            
            # Record this as a cached success for learning
            if existing.get('confidence_score', 0) > 0.8:
                self.optimizer.record_success('matching', {
                    'search_terms': existing.get('search_queries_used', []),
                    'year': year
                })
            
            return existing
        
        print(f"\n🎬 Processing: {caption_dir}")
        print(f"   Video ID: {video_id}")
        
        # Create enhanced prompt
        prompt = self.create_enhanced_matching_prompt(video_info, year, transcript, output_path)
        
        # Run Claude search
        claude_result = self.run_claude_search(prompt, video_id)
        
        # Check and load the match result
        if output_path.exists():
            with open(output_path) as f:
                match_result = json.load(f)
            
            # Record success/failure for learning
            confidence = match_result.get('confidence_score', 0)
            if confidence > 0.8:
                self.optimizer.record_success('matching', {
                    'search_terms': self.current_search_terms,
                    'year': year
                })
                print(f"  ✅ Successfully matched with confidence: {confidence}")
            else:
                self.optimizer.record_failure('matching', {
                    'search_terms': self.current_search_terms,
                    'year': year
                })
                print(f"  ⚠️  Low confidence match: {confidence}")
            
            return match_result
        else:
            # No output file created
            self.optimizer.record_failure('matching', {
                'search_terms': self.current_search_terms,
                'year': year
            }, "No output file created")
            
            return {
                "status": "failed",
                "video_id": video_id,
                "error": "Claude did not create output file",
                "claude_result": claude_result
            }
    
    def match_all_videos(self, year: int = 2015, video_filter: Optional[List[str]] = None) -> Dict[str, Dict]:
        """Match all videos for a given year with progress tracking."""
        print(f"\n🔍 Matching videos to code for year {year}")
        
        # Load video mappings
        video_mappings = self.load_video_mappings(year)
        
        # Filter videos if specified
        if video_filter:
            video_mappings = {k: v for k, v in video_mappings.items() if k in video_filter}
            print(f"   Filtering to {len(video_mappings)} specified videos")
        
        print(f"   Found {len(video_mappings)} videos to process")
        
        results = {}
        total = len(video_mappings)
        
        for idx, (caption_dir, video_info) in enumerate(video_mappings.items(), 1):
            # Progress indicator
            if not self.verbose:
                progress = self._make_progress_bar(idx - 1, total)
                print(f"\r   Progress: {progress} {idx}/{total}", end='', flush=True)
            
            # Match single video
            match_result = self.match_single_video(video_info, year)
            results[caption_dir] = match_result
            
            # Small delay to avoid rate limiting
            if idx < total:
                time.sleep(0.5)
        
        if not self.verbose:
            progress = self._make_progress_bar(total, total)
            print(f"\r   Progress: {progress} {total}/{total} ✅")
        
        # Generate optimization report
        print("\n📊 Generating optimization insights...")
        report = self.optimizer.generate_optimization_report()
        report_file = self.output_dir / 'logs' / f'matching_optimization_{year}.txt'
        report_file.parent.mkdir(exist_ok=True)
        with open(report_file, 'w') as f:
            f.write(report)
        print(f"   Optimization report saved to: {report_file}")
        
        # Save feedback system report
        feedback_report = self.feedback_system.generate_report()
        feedback_file = self.output_dir / 'logs' / f'matching_feedback_{year}.txt'
        with open(feedback_file, 'w') as f:
            f.write(feedback_report)
        
        return results
    
    def _make_progress_bar(self, current: int, total: int, width: int = 30) -> str:
        """Create a simple ASCII progress bar."""
        if total == 0:
            return "[" + " " * width + "]"
        filled = int(width * current / total)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}]"
    
    def save_final_results(self, results: Dict[str, Dict], year: int) -> Dict:
        """Save final matching results and generate summary."""
        # Same as original implementation
        summary = {
            "year": year,
            "total_videos": len(results),
            "successful_matches": 0,
            "low_confidence_matches": 0,
            "failed_matches": 0,
            "skipped_videos": 0,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        for caption_dir, result in results.items():
            status = result.get("status", "unknown")
            if status == "matched":
                confidence = result.get("confidence_score", 0)
                if confidence >= 0.8:
                    summary["successful_matches"] += 1
                else:
                    summary["low_confidence_matches"] += 1
            elif status == "no_transcript":
                summary["skipped_videos"] += 1
            elif status == "excluded":
                summary["skipped_videos"] += 1
            else:
                summary["failed_matches"] += 1
        
        # Save summary
        summary_file = self.output_dir / f'matching_summary_{year}.json'
        with open(summary_file, 'w') as f:
            json.dump({
                "summary": summary,
                "results": results,
                "stats": summary
            }, f, indent=2)
        
        print(f"\n📊 Matching Summary:")
        print(f"   Total videos: {summary['total_videos']}")
        print(f"   ✅ Successful matches: {summary['successful_matches']}")
        print(f"   ⚠️  Low confidence: {summary['low_confidence_matches']}")
        print(f"   ❌ Failed: {summary['failed_matches']}")
        print(f"   ⏭️  Skipped: {summary['skipped_videos']}")
        print(f"\n   Results saved to: {summary_file}")
        
        return summary


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Match 3Blue1Brown videos to code using Claude')
    parser.add_argument('--year', type=int, default=2015,
                        help='Year to process (default: 2015)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output')
    parser.add_argument('--video', action='append',
                        help='Process only specific video(s) by caption directory name')
    
    args = parser.parse_args()
    
    # Use enhanced matcher
    matcher = EnhancedClaudeVideoMatcher(Path(__file__).parent.parent, verbose=args.verbose)
    results = matcher.match_all_videos(year=args.year, video_filter=args.video)
    matcher.save_final_results(results, args.year)


if __name__ == '__main__':
    main()