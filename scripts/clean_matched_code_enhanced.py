#!/usr/bin/env python3
"""
Enhanced version of clean_matched_code.py with integrated prompt optimization.
Uses improved prompts with few-shot examples and adaptive learning.
"""

import json
import time
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import logging
from datetime import datetime

# Import model strategy
from model_strategy import get_model_for_task

# Import our new optimization modules
from improved_prompts import CODE_CLEANING_PROMPT, format_prompt
from adaptive_prompt_optimizer import AdaptivePromptOptimizer
from prompt_feedback_system import PromptFeedbackSystem, PromptResult

class EnhancedCodeCleaner:
    def __init__(self, base_dir: str, verbose: bool = False, timeout_multiplier: float = 1.0, max_retries: int = 3):
        self.base_dir = Path(base_dir)
        self.output_dir = self.base_dir / 'outputs'
        self.data_dir = self.base_dir / 'data'
        self.verbose = verbose
        self.timeout_multiplier = timeout_multiplier
        self.max_retries = max_retries
        
        # Setup logging with new structure
        self.logs_dir = self.output_dir / 'logs' / 'cleaning'
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure logger with lazy file creation
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file = self.logs_dir / f"cleaning_{self.timestamp}.log"
        self.log_file_created = False
        
        # Setup basic logging without file handler initially
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler() if verbose else logging.NullHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize optimization systems
        self.optimizer = AdaptivePromptOptimizer(
            cache_dir=str(self.output_dir / 'prompt_optimization')
        )
        self.feedback_system = PromptFeedbackSystem(
            feedback_dir=str(self.output_dir / 'prompt_feedback')
        )
        
        # Override logger methods to ensure file creation when needed
        self._original_info = self.logger.info
        self._original_warning = self.logger.warning
        self._original_error = self.logger.error
        
        self.logger.info = lambda msg, *args, **kwargs: self._log_with_file_creation(self._original_info, msg, *args, **kwargs)
        self.logger.warning = lambda msg, *args, **kwargs: self._log_with_file_creation(self._original_warning, msg, *args, **kwargs)
        self.logger.error = lambda msg, *args, **kwargs: self._log_with_file_creation(self._original_error, msg, *args, **kwargs)
        
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
    
    def _make_progress_bar(self, current: int, total: int, width: int = 30) -> str:
        """Create a simple ASCII progress bar."""
        if total == 0:
            return "[" + " " * width + "]"
        filled = int(width * current / total)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}]"
    
    def load_match_results(self, year: int) -> Dict[str, Dict]:
        """Load all match results for a given year."""
        results = {}
        year_dir = self.output_dir / str(year)
        
        if not year_dir.exists():
            self.logger.warning(f"No match results found for year {year}")
            return results
            
        # Iterate through all video directories
        for video_dir in year_dir.iterdir():
            if video_dir.is_dir():
                match_file = video_dir / 'matches.json'
                if match_file.exists():
                    try:
                        with open(match_file) as f:
                            data = json.load(f)
                        results[video_dir.name] = data
                    except Exception as e:
                        self.logger.error(f"Error loading {match_file}: {e}")
                        
        return results
    
    def calculate_file_sizes(self, files: List[Union[str, Dict]], year: int) -> Dict[str, int]:
        """Calculate sizes of files to be cleaned."""
        sizes = {}
        
        for file_info in files:
            if isinstance(file_info, dict):
                file_path = Path(file_info['file_path']) if file_info.get('file_path') else None
            else:
                # Convert relative path to absolute
                file_path = self.data_dir / 'videos' / f'_{year}' / file_info
            
            if file_path and file_path.exists():
                try:
                    sizes[str(file_path)] = file_path.stat().st_size
                except Exception:
                    sizes[str(file_path)] = 0
            else:
                sizes[str(file_info)] = 0
                
        return sizes
    
    def create_enhanced_cleaning_prompt(self, video_id: str, caption_dir: str, year: int,
                                      match_data: Dict, output_path: Path) -> Tuple[str, float]:
        """Create an enhanced cleaning prompt with optimization."""
        # Extract file information
        primary_files = match_data.get('primary_files', [])
        supporting_files = match_data.get('supporting_files', [])
        all_files = primary_files + supporting_files
        
        # Calculate file sizes for complexity assessment
        file_sizes = self.calculate_file_sizes(all_files, year)
        
        # Get optimized prompt and timeout multiplier
        base_prompt = CODE_CLEANING_PROMPT
        optimized_prompt, timeout_multiplier = self.optimizer.optimize_cleaning_prompt(
            base_prompt, file_sizes
        )
        
        # Apply overall timeout multiplier
        timeout_multiplier *= self.timeout_multiplier
        
        # Format the prompt with all parameters
        formatted_prompt = format_prompt(
            optimized_prompt,
            video_id=video_id,
            caption_dir=caption_dir,
            year=year,
            primary_files=json.dumps(primary_files, indent=2),
            supporting_files=json.dumps(supporting_files, indent=2),
            output_path=str(output_path)
        )
        
        return formatted_prompt, timeout_multiplier
    
    def run_claude_cleaning(self, prompt: str, video_id: str, attempt: int = 1,
                          timeout_multiplier: float = 1.0) -> Dict:
        """Execute Claude cleaning with enhanced error handling and feedback."""
        start_time = time.time()
        
        # Initialize prompt result for tracking
        prompt_result = PromptResult(
            prompt_type="cleaning",
            success=False,
            confidence=0.0,
            attempt_number=attempt
        )
        
        # Create temp directory for this cleaning operation
        temp_dir = self.logs_dir / 'temp' / video_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        prompt_file = temp_dir / f"prompt_attempt_{attempt}.txt"
        with open(prompt_file, 'w') as f:
            f.write(prompt)
        
        result_file = temp_dir / f"result_attempt_{attempt}.txt"
        
        # Adjust timeout based on attempt and multiplier
        base_timeout = 300  # 5 minutes base
        timeout = int(base_timeout * timeout_multiplier * (1 + (attempt - 1) * 0.5))
        
        self.logger.info(f"Running Claude cleaning for {video_id} (attempt {attempt}, timeout {timeout}s)")
        
        try:
            # Get appropriate model for cleaning task
            model = get_model_for_task("clean_code", {"attempt": attempt})
            
            claude_command = ["claude", "--dangerously-skip-permissions", "--model", model]
            
            # Run claude-cli with the prompt
            if self.verbose:
                print(f"    🤖 Calling Claude ({model}) for cleaning (attempt {attempt})...")
                result = subprocess.run(
                    claude_command,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                
                if result.stdout:
                    print(f"    Claude response preview: {result.stdout[:200]}...")
            else:
                result = subprocess.run(
                    claude_command,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
            
            # Check if command succeeded
            if result.returncode != 0:
                error_msg = f"Claude returned non-zero exit code: {result.returncode}"
                self.logger.error(f"{error_msg}\nSTDERR: {result.stderr}")
                
                prompt_result.error_type = "claude_error"
                prompt_result.execution_time = time.time() - start_time
                self.feedback_system.record_result(prompt_result)
                
                return {
                    "status": "error",
                    "error": error_msg,
                    "stderr": result.stderr
                }
            
            # Save the Claude response
            with open(result_file, 'w') as f:
                f.write(result.stdout)
            
            # Track success
            prompt_result.success = True
            prompt_result.confidence = 0.9  # High confidence for successful cleaning
            prompt_result.execution_time = time.time() - start_time
            self.feedback_system.record_result(prompt_result)
            
            return {
                "status": "success",
                "result_file": str(result_file),
                "response": result.stdout
            }
            
        except subprocess.TimeoutExpired:
            error_msg = f"Claude request timed out after {timeout}s"
            self.logger.warning(error_msg)
            
            prompt_result.error_type = "timeout"
            prompt_result.execution_time = time.time() - start_time
            self.feedback_system.record_result(prompt_result)
            
            # Record timeout for learning
            size_category = 'large' if timeout_multiplier > 1.5 else 'medium'
            self.optimizer.record_failure('cleaning', {
                'size_category': size_category,
                'timeout': timeout
            }, "timeout")
            
            return {
                "status": "timeout",
                "error": error_msg
            }
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.error(error_msg)
            
            prompt_result.error_type = "unexpected_error"
            prompt_result.execution_time = time.time() - start_time
            self.feedback_system.record_result(prompt_result)
            
            return {
                "status": "error",
                "error": error_msg
            }
    
    def validate_cleaned_code(self, code: str) -> Tuple[bool, Optional[str]]:
        """Validate that cleaned code is syntactically correct."""
        try:
            compile(code, '<cleaned_code>', 'exec')
            return True, None
        except SyntaxError as e:
            return False, f"Syntax error at line {e.lineno}: {e.msg}"
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def clean_single_video(self, video_id: str, caption_dir: str, match_data: Dict, 
                         year: int, force: bool = False) -> Dict:
        """Clean code for a single video with retry logic."""
        # Setup paths
        video_dir = self.output_dir / str(year) / caption_dir
        cleaned_file = video_dir / 'code_cleaned.py'
        
        # Check if already cleaned
        if cleaned_file.exists() and not force:
            self.logger.info(f"Skipping {caption_dir} - already cleaned")
            return {
                "status": "skipped",
                "reason": "already_cleaned",
                "file": str(cleaned_file)
            }
        
        # Check match quality
        confidence = match_data.get('confidence_score', 0)
        if confidence < 0.5:
            self.logger.warning(f"Skipping {caption_dir} - low confidence match ({confidence})")
            return {
                "status": "skipped",
                "reason": "low_confidence",
                "confidence": confidence
            }
        
        # Create enhanced prompt
        prompt, timeout_multiplier = self.create_enhanced_cleaning_prompt(
            video_id, caption_dir, year, match_data, cleaned_file
        )
        
        # Try cleaning with retries
        for attempt in range(1, self.max_retries + 1):
            if self.verbose:
                print(f"\n  🧹 Cleaning attempt {attempt}/{self.max_retries}")
            
            result = self.run_claude_cleaning(prompt, video_id, attempt, timeout_multiplier)
            
            if result['status'] == 'success':
                # Check if cleaned file was created
                if cleaned_file.exists():
                    # Validate the cleaned code
                    with open(cleaned_file, 'r') as f:
                        cleaned_code = f.read()
                    
                    is_valid, error = self.validate_cleaned_code(cleaned_code)
                    
                    if is_valid:
                        # Record success for learning
                        file_sizes = self.calculate_file_sizes(
                            match_data.get('primary_files', []) + match_data.get('supporting_files', []),
                            year
                        )
                        size_category = 'small' if sum(file_sizes.values()) < 5000 else 'medium' if sum(file_sizes.values()) < 20000 else 'large'
                        
                        self.optimizer.record_success('cleaning', {
                            'size_category': size_category,
                            'file_count': len(file_sizes),
                            'attempt': attempt
                        })
                        
                        return {
                            "status": "success",
                            "file": str(cleaned_file),
                            "attempts": attempt,
                            "validation": "passed"
                        }
                    else:
                        self.logger.warning(f"Cleaned code validation failed: {error}")
                        if attempt < self.max_retries:
                            # Add validation error to prompt for next attempt
                            prompt += f"\n\nPREVIOUS ATTEMPT FAILED VALIDATION:\n{error}\n"
                            prompt += "Please fix the syntax error and ensure the code is valid Python."
                        else:
                            return {
                                "status": "error",
                                "reason": "validation_failed",
                                "error": error,
                                "attempts": attempt
                            }
                else:
                    self.logger.error(f"Claude did not create the cleaned file")
                    if attempt < self.max_retries:
                        prompt += "\n\nIMPORTANT: You must use the Write tool to save the file!"
            
            elif result['status'] == 'timeout' and attempt < self.max_retries:
                # Increase timeout for next attempt
                timeout_multiplier *= 1.5
                self.logger.info(f"Increasing timeout multiplier to {timeout_multiplier}")
        
        # All attempts failed
        return {
            "status": "failed",
            "reason": "max_retries_exceeded",
            "attempts": self.max_retries
        }
    
    def clean_all_matched_videos(self, year: int = 2015, force: bool = False,
                               video_filter: Optional[List[str]] = None) -> Dict:
        """Clean all matched videos for a given year."""
        print(f"\n🧹 Cleaning matched code for year {year}")
        
        # Load match results
        match_results = self.load_match_results(year)
        
        # Filter if specified
        if video_filter:
            match_results = {k: v for k, v in match_results.items() if k in video_filter}
            print(f"   Filtering to {len(match_results)} specified videos")
        
        print(f"   Found {len(match_results)} matched videos to clean")
        
        results = {}
        successful = 0
        failed = 0
        skipped = 0
        
        total = len(match_results)
        
        for idx, (caption_dir, match_data) in enumerate(match_results.items(), 1):
            video_id = match_data.get('video_id', caption_dir)
            
            # Progress indicator
            if not self.verbose:
                progress = self._make_progress_bar(idx - 1, total)
                print(f"\r   Progress: {progress} {idx}/{total}", end='', flush=True)
            else:
                print(f"\n{'='*60}")
                print(f"Processing {idx}/{total}: {caption_dir}")
            
            # Clean single video
            clean_result = self.clean_single_video(video_id, caption_dir, match_data, year, force)
            results[caption_dir] = clean_result
            
            # Update counters
            if clean_result['status'] == 'success':
                successful += 1
            elif clean_result['status'] == 'skipped':
                skipped += 1
            else:
                failed += 1
            
            # Small delay between videos
            if idx < total:
                time.sleep(0.5)
        
        if not self.verbose:
            progress = self._make_progress_bar(total, total)
            print(f"\r   Progress: {progress} {total}/{total} ✅")
        
        # Generate summary
        summary = {
            "year": year,
            "total_matched": total,
            "cleaned": successful,
            "failed": failed,
            "skipped": skipped,
            "timestamp": datetime.now().isoformat()
        }
        
        # Save results
        summary_file = self.output_dir / f'cleaning_summary_{year}.json'
        with open(summary_file, 'w') as f:
            json.dump({
                "summary": summary,
                "results": results
            }, f, indent=2)
        
        print(f"\n📊 Cleaning Summary:")
        print(f"   Total matched: {total}")
        print(f"   ✅ Successfully cleaned: {successful}")
        print(f"   ❌ Failed: {failed}")
        print(f"   ⏭️  Skipped: {skipped}")
        print(f"\n   Results saved to: {summary_file}")
        
        # Generate optimization reports
        print("\n📊 Generating optimization insights...")
        
        opt_report = self.optimizer.generate_optimization_report()
        opt_file = self.output_dir / 'logs' / f'cleaning_optimization_{year}.txt'
        opt_file.parent.mkdir(exist_ok=True)
        with open(opt_file, 'w') as f:
            f.write(opt_report)
        
        feedback_report = self.feedback_system.generate_report()
        feedback_file = self.output_dir / 'logs' / f'cleaning_feedback_{year}.txt'
        with open(feedback_file, 'w') as f:
            f.write(feedback_report)
        
        print(f"   Optimization reports saved to logs/")
        
        return summary


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Clean matched 3Blue1Brown code files')
    parser.add_argument('--year', type=int, default=2015,
                        help='Year to process (default: 2015)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output')
    parser.add_argument('--force', '-f', action='store_true',
                        help='Force re-cleaning of already cleaned files')
    parser.add_argument('--video', action='append',
                        help='Process only specific video(s) by caption directory name')
    parser.add_argument('--timeout-multiplier', type=float, default=1.0,
                        help='Multiply all timeouts by this factor (default: 1.0)')
    parser.add_argument('--max-retries', type=int, default=3,
                        help='Maximum retry attempts (default: 3)')
    
    args = parser.parse_args()
    
    # Use enhanced cleaner
    cleaner = EnhancedCodeCleaner(
        Path(__file__).parent.parent,
        verbose=args.verbose,
        timeout_multiplier=args.timeout_multiplier,
        max_retries=args.max_retries
    )
    
    cleaner.clean_all_matched_videos(
        year=args.year,
        force=args.force,
        video_filter=args.video
    )


if __name__ == '__main__':
    main()