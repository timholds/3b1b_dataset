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
                            match_data = json.load(f)
                            results[video_dir.name] = match_data
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"Malformed JSON in {match_file}: {e}")
                        # Try to repair simple cases like trailing shell commands
                        try:
                            with open(match_file) as f:
                                content = f.read()
                            # Remove lines that look like shell commands after valid JSON
                            lines = content.split('\n')
                            json_lines = []
                            in_json = False
                            brace_count = 0
                            for line in lines:
                                if line.strip().startswith('{'):
                                    in_json = True
                                if in_json:
                                    json_lines.append(line)
                                    brace_count += line.count('{') - line.count('}')
                                    if brace_count == 0 and line.strip().endswith('}'):
                                        break
                            json_content = '\n'.join(json_lines)
                            match_data = json.loads(json_content)
                            results[video_dir.name] = match_data
                            self.logger.info(f"Successfully repaired JSON in {match_file}")
                        except Exception as repair_error:
                            self.logger.error(f"Failed to repair JSON in {match_file}: {repair_error}")
                            continue
                        
        self.logger.info(f"Loaded {len(results)} match results for year {year}")
        return results
        
    def should_clean_video(self, match_data: Dict, force: bool = False) -> Tuple[bool, str]:
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
        # Skip this check if force is True
        if not force and match_data.get('cleaning_status') == 'completed':
            return False, "Already cleaned"
            
        return True, "Ready for cleaning"
        
    def estimate_total_file_size(self, files: List[str], year: int) -> int:
        """Estimate total size of files to be processed."""
        total_size = 0
        videos_dir = self.data_dir / 'videos' / f'_{year}'
        
        for file_name in files:
            file_path = videos_dir / file_name
            if file_path.exists():
                total_size += file_path.stat().st_size
            else:
                self.logger.warning(f"File not found: {file_path}")
                
        return total_size
        
    def create_cleaning_prompt(self, video_id: str, caption_dir: str, 
                             match_data: Dict, year: int) -> str:
        """Create a prompt for Claude to clean and inline code."""
        primary_files = match_data.get('primary_files', [])
        supporting_files = match_data.get('supporting_files', [])
        all_files = primary_files + supporting_files
        
        output_path = self.output_dir / str(year) / caption_dir / 'cleaned_code.py'
        
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

CRITICAL: Preserve exact Python syntax:
- NEVER merge separate statements onto one line
- NEVER combine 'return' with 'def' or any other statement
- Keep proper indentation for all class methods
- Ensure all function definitions start on their own line
- Validate that the output is syntactically correct Python code

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
        
    def run_claude_cleaning(self, prompt: str, video_id: str, caption_dir: str, year: int, file_size: int = 0, max_retries: int = 3) -> Dict:
        """Execute Claude to clean a single video's code with retry logic."""
        prompt_file = self.logs_dir / f"{video_id}_cleaning_prompt.txt"
        with open(prompt_file, 'w') as f:
            f.write(prompt)
            
        # Calculate timeout based on actual file sizes
        base_timeout = 600  # 10 minutes base (increased from 5)
        timeout_multiplier = getattr(self, 'timeout_multiplier', 1.0)
        
        if file_size > 50000:  # Large files (>50KB)
            timeout = 1200 * timeout_multiplier  # 20 minutes (increased from 15)
        elif file_size > 20000:  # Medium files (>20KB)
            timeout = 900 * timeout_multiplier  # 15 minutes (increased from 10)
        else:
            timeout = base_timeout * timeout_multiplier
            
        for attempt in range(max_retries):
            try:
                # Exponential backoff for retries
                if attempt > 0:
                    backoff_time = 2 ** attempt * 10  # 10s, 20s, 40s
                    self.logger.info(f"Retry {attempt}/{max_retries} for {caption_dir} after {backoff_time}s backoff")
                    time.sleep(backoff_time)
                    # Increase timeout for retries
                    current_timeout = timeout * (1.5 ** attempt)
                else:
                    current_timeout = timeout
                    
                # More specific logging - check if this is a scene-specific cleaning
                scene_name = video_id.split('_', 1)[-1] if '_' in video_id else None
                if scene_name and scene_name != video_id:
                    self.logger.info(f"Running Claude cleaning for scene '{scene_name}' in {caption_dir} (attempt {attempt + 1}/{max_retries}, timeout: {current_timeout:.0f}s, {file_size:,} chars)")
                else:
                    self.logger.info(f"Running Claude cleaning for {caption_dir} (attempt {attempt + 1}/{max_retries}, timeout: {current_timeout:.0f}s, file size: {file_size:,} bytes)")
                start_time = time.time()
                
                # Run Claude with the cleaning prompt - now using sonnet
                claude_command =  ["claude", "--dangerously-skip-permissions",  "--model", "sonnet"]
                
                try:
                    if self.verbose:
                        self.logger.info(f"Sending prompt to Claude (length: {len(prompt)} chars)")
                    
                    # Use subprocess.run with stdin
                    result = subprocess.run(
                        claude_command,
                        input=prompt,
                        capture_output=True,
                        text=True,
                        timeout=int(current_timeout)
                    )
                    
                    if self.verbose and result.stdout:
                        # Print output after completion if verbose
                        print(f"    Claude response preview: {result.stdout[:200]}...")
                        
                except subprocess.TimeoutExpired as e:
                    # Re-raise with our timeout value
                    raise subprocess.TimeoutExpired(claude_command, current_timeout)
                
                if result.returncode != 0:
                    error_msg = f"Claude returned non-zero exit code: {result.returncode}"
                    self.logger.error(f"{caption_dir}: {error_msg}")
                    
                    # Don't retry for non-timeout errors
                    return {
                        "status": "error",
                        "error": error_msg,
                        "stderr": result.stderr,
                        "attempts": attempt + 1
                    }
                    
                # Save Claude's response
                response_file = self.logs_dir / f"{video_id}_cleaning_response.txt"
                with open(response_file, 'w') as f:
                    f.write(result.stdout)
                    
                elapsed_time = time.time() - start_time
                # More specific logging - check if this is a scene-specific cleaning
                scene_name = video_id.split('_', 1)[-1] if '_' in video_id else None
                if scene_name and scene_name != video_id:
                    self.logger.info(f"Claude cleaning completed for scene '{scene_name}' in {caption_dir} in {elapsed_time:.1f} seconds")
                else:
                    self.logger.info(f"Claude cleaning completed for {caption_dir} in {elapsed_time:.1f} seconds")
                    
                return {
                    "status": "completed",
                    "prompt_file": str(prompt_file),
                    "response_file": str(response_file),
                    "elapsed_time": elapsed_time,
                    "attempts": attempt + 1
                }
                
            except subprocess.TimeoutExpired:
                error_msg = f"Claude cleaning timed out after {current_timeout:.0f} seconds (attempt {attempt + 1}/{max_retries})"
                self.logger.warning(f"{caption_dir}: {error_msg}")
                
                # Check if Claude created the file despite timeout
                expected_output = self.output_dir / str(year) / caption_dir / 'cleaned_code.py'
                
                if expected_output.exists():
                    self.logger.info(f"{caption_dir}: File created despite timeout, checking validity...")
                    
                    # Validate the file
                    is_valid, validation_error = self.validate_cleaned_code(expected_output)
                    if is_valid:
                        self.logger.info(f"{caption_dir}: Timeout but file is valid!")
                        return {
                            "status": "completed",
                            "prompt_file": str(prompt_file),
                            "response_file": str(self.logs_dir / f"{video_id}_cleaning_response.txt"),
                            "elapsed_time": current_timeout,
                            "attempts": attempt + 1,
                            "note": "Completed despite timeout"
                        }
                    else:
                        self.logger.warning(f"{caption_dir}: File created but has validation errors: {validation_error}")
                
                if attempt == max_retries - 1:
                    # Final attempt failed
                    self.logger.error(f"{caption_dir}: All retry attempts exhausted")
                    return {
                        "status": "error", 
                        "error": f"Timeout after {max_retries} attempts",
                        "attempts": max_retries
                    }
                # Continue to next retry
                
            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                self.logger.error(f"{caption_dir}: {error_msg}")
                return {
                    "status": "error", 
                    "error": error_msg,
                    "attempts": attempt + 1
                }
            
    def fix_common_syntax_issues(self, code: str) -> str:
        """Fix common syntax issues in the code before validation."""
        import re
        
        # Fix 1: String continuations with backslashes
        # Convert "string \\\n continuation" to "string " "continuation"
        def fix_string_continuation(match):
            quote = match.group(1)
            part1 = match.group(2)
            part2 = match.group(3)
            
            # Check if this would create invalid syntax like 'and" "tuple'
            # This happens when the regex incorrectly matches across code boundaries
            if part1.rstrip().endswith(' and') or part1.rstrip().endswith(' or'):
                # Don't apply the fix - return original match
                return match.group(0)
            
            # Remove trailing spaces from part1 and leading spaces from part2
            part1 = part1.rstrip()
            part2 = part2.lstrip()
            return f'{quote}{part1}{quote} {quote}{part2}{quote}'
        
        # Pattern to find strings with backslash continuation
        # More specific pattern that ensures we're actually in a string literal
        # Look for: quote, content, backslash, newline, content, same quote
        # Use positive lookbehind to ensure we're at a string boundary (after =, (, [, {, or space)
        pattern = r'(?<=[=\(\[\{\s,])(["\'])([^"\'\\]*(?:\\.[^"\'\\]*)*?)\s*\\\s*\n\s*([^"\'\\]*(?:\\.[^"\'\\]*)*?)\1'
        code = re.sub(pattern, fix_string_continuation, code, flags=re.MULTILINE)
        
        # Fix 2: Invalid escape sequences in regular strings
        # Convert "\s" to r"\s" in non-raw strings
        def fix_escape_sequences(match):
            quote = match.group(1)
            content = match.group(2)
            # Check if it contains invalid escape sequences
            if any(seq in content for seq in ['\\s', '\\p', '\\d', '\\w', '\\b']):
                # Convert to raw string
                return f'r{quote}{content}{quote}'
            return match.group(0)
        
        # Only fix non-raw strings that aren't already raw
        escape_pattern = r'(?<!r)(["\'])([^"\']*?(?:\\[spwdb][^"\']*?)*)\1'
        code = re.sub(escape_pattern, fix_escape_sequences, code)
        
        # Fix 3: Unclosed parentheses on specific patterns
        # Fix pattern like: arrow.set_points(list(reversed(arrow.get_points()))
        # Missing closing paren at the end
        unclosed_pattern = r'(\w+\.set_points\(list\(reversed\(\w+\.get_points\(\)\)\))(?=\s|$)'
        code = re.sub(unclosed_pattern, r'\1)', code)
        
        # Fix 4: Fix any invalid syntax patterns created by previous fixes
        # Pattern: keyword" "something (e.g., and" "tuple)
        invalid_pattern = r'\b(and|or|not|in|is|if|elif|else|while|for|with|as|from|import|return)\s*"\s*"\s*(\w)'
        code = re.sub(invalid_pattern, r'\1 \2', code)
        
        # Fix 5: Fix invalid assignment with quotes
        # Pattern: = " "Something (extra quotes in assignment)
        assignment_pattern = r'=\s*"\s*"\s*(\w+)'
        code = re.sub(assignment_pattern, r'= \1', code)
        
        # Fix 6: Fix malformed raw strings
        # Pattern: Text(""r" -> Text(r"
        raw_string_pattern = r'(\w+\()""r"'
        code = re.sub(raw_string_pattern, r'\1r"', code)
        
        # Fix 5: General parenthesis balancing check and fix for common patterns
        lines = code.split('\n')
        fixed_lines = []
        
        for i, line in enumerate(lines):
            # Count parentheses, but ignore those inside strings
            # Remove string literals temporarily to count parentheses correctly
            temp_line = line
            # Replace string literals with placeholders to avoid counting their contents
            string_pattern = r'(\'[^\']*\'|"[^"]*")'
            strings = re.findall(string_pattern, temp_line)
            for j, string in enumerate(strings):
                temp_line = temp_line.replace(string, f'__STRING_{j}__')
            
            # Now count parentheses in the non-string parts
            open_count = temp_line.count('(')
            close_count = temp_line.count(')')
            
            # If there are more opens than closes, check if it's a common pattern
            if open_count > close_count:
                diff = open_count - close_count
                # Check if line ends with common patterns missing parens
                # But only if the line actually ends with a closing paren (not in a string)
                if re.search(r'\)\s*$', temp_line) and diff > 0:
                    # Also check that we're not in the middle of a multi-line statement
                    # by checking if the line ends with common continuation patterns
                    if not re.search(r'[,\\]\s*$', line):
                        # Likely missing closing parens at the end
                        line = line.rstrip() + ')' * diff
                        self.logger.debug(f"Fixed unclosed parentheses on line {i+1}: added {diff} closing parens")
            
            fixed_lines.append(line)
        
        code = '\n'.join(fixed_lines)
        
        return code
    
    def validate_cleaned_code(self, file_path: Path) -> Tuple[bool, Optional[str]]:
        """Validate that the cleaned code is syntactically correct with detailed error reporting."""
        if not file_path.exists():
            return False, "File does not exist"
            
        try:
            with open(file_path) as f:
                code = f.read()
                
            # Check if it's just an error message
            if code.strip().startswith("#") and "error" in code.lower() and len(code) < 500:
                return False, "File contains error message instead of code"
            
            # Apply syntax fixes
            original_code = code
            code = self.fix_common_syntax_issues(code)
            
            if code != original_code:
                self.logger.info(f"Applied syntax fixes to {file_path.name}")
                # Write the fixed code back
                with open(file_path, 'w') as f:
                    f.write(code)
                
            # Try to compile the code
            compile(code, str(file_path), 'exec')
            
            # Additional validation checks
            lines = code.split('\n')
            
            # Check for common issues
            open_parens = code.count('(') - code.count(')')
            open_brackets = code.count('[') - code.count(']')
            open_braces = code.count('{') - code.count('}')
            
            if open_parens != 0:
                self.logger.warning(f"Unbalanced parentheses in {file_path.name}: {open_parens} unclosed")
            if open_brackets != 0:
                self.logger.warning(f"Unbalanced brackets in {file_path.name}: {open_brackets} unclosed")
            if open_braces != 0:
                self.logger.warning(f"Unbalanced braces in {file_path.name}: {open_braces} unclosed")
                
            return True, None
            
        except SyntaxError as e:
            # Provide detailed error information
            error_lines = []
            error_lines.append(f"Syntax error at line {e.lineno}: {e.msg}")
            
            if e.text:
                error_lines.append(f"Problem line: {e.text.strip()}")
                if e.offset:
                    error_lines.append(f"Error position: {' ' * (e.offset - 1)}^")
                    
            # Try to provide context
            try:
                with open(file_path) as f:
                    lines = f.readlines()
                    if e.lineno and 0 < e.lineno <= len(lines):
                        start = max(0, e.lineno - 3)
                        end = min(len(lines), e.lineno + 2)
                        error_lines.append("\nContext:")
                        for i in range(start, end):
                            prefix = ">>> " if i + 1 == e.lineno else "    "
                            error_lines.append(f"{prefix}{i+1}: {lines[i].rstrip()}")
            except:
                pass
                
            return False, "\n".join(error_lines)
            
        except Exception as e:
            return False, f"Validation error: {type(e).__name__}: {e}"
            
    def load_cleaning_checkpoint(self, year: int) -> Dict:
        """Load cleaning checkpoint to resume from previous run."""
        checkpoint_file = self.output_dir / f'cleaning_checkpoint_{year}.json'
        if checkpoint_file.exists():
            with open(checkpoint_file) as f:
                return json.load(f)
        return {"completed_videos": [], "failed_videos": {}}
    
    def save_cleaning_checkpoint(self, year: int, checkpoint_data: Dict):
        """Save cleaning checkpoint for resuming."""
        checkpoint_file = self.output_dir / f'cleaning_checkpoint_{year}.json'
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)
    
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
    
    def clean_all_matched_videos(self, year: int = 2015, video_filter: Optional[List[str]] = None, 
                               resume: bool = True, force: bool = False, mode: str = 'scene') -> Dict:
        """Clean all successfully matched videos for a given year.
        
        Args:
            year: Year to process
            video_filter: List of specific videos to process
            resume: Whether to resume from checkpoint
            force: Force re-cleaning of already cleaned files
            mode: 'monolithic' (default) or 'scene' for scene-by-scene cleaning
        """
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
            
        self.logger.info(f"Cleaning mode: {mode}")
            
        # Load checkpoint if resuming
        checkpoint = {"completed_videos": [], "failed_videos": {}}
        if resume:
            checkpoint = self.load_cleaning_checkpoint(year)
            if checkpoint["completed_videos"]:
                self.logger.info(f"Resuming from checkpoint - {len(checkpoint['completed_videos'])} videos already completed")
            
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
            
            # Skip if already completed in previous run
            if resume and caption_dir in checkpoint["completed_videos"]:
                self.logger.info(f"Skipping {caption_dir}: Already completed in previous run")
                cleaning_results[caption_dir] = {
                    'status': 'previously_completed',
                    'reason': 'Completed in checkpoint'
                }
                stats['cleaned'] += 1
                continue
            
            # Check if we should clean this video
            should_clean, reason = self.should_clean_video(match_data, force=force)
            
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
                
            # Use scene-by-scene cleaning if mode is 'scene'
            if mode == 'scene':
                try:
                    from clean_matched_code_scenes import SceneAwareCleaner
                    scene_cleaner = SceneAwareCleaner(
                        str(self.base_dir), 
                        verbose=self.verbose,
                        timeout_multiplier=self.timeout_multiplier,
                        max_retries=self.max_retries
                    )
                    
                    self.logger.info(f"Using scene-by-scene cleaning for {caption_dir}")
                    result = scene_cleaner.clean_video_by_scenes(
                        video_id, caption_dir, match_data, year
                    )
                    
                    if result.get('status') in ['completed', 'partial']:
                        if result.get('combine_success'):
                            stats['cleaned'] += 1
                            checkpoint["completed_videos"].append(caption_dir)
                        else:
                            stats['failed'] += 1
                            checkpoint["failed_videos"][caption_dir] = "Scene combination failed"
                    else:
                        stats['failed'] += 1
                        checkpoint["failed_videos"][caption_dir] = result.get('error', 'Unknown error')
                        
                    cleaning_results[caption_dir] = result
                    self.save_cleaning_checkpoint(year, checkpoint)
                    
                    # Update match file with cleaning status
                    match_data['cleaning_status'] = result.get('status', 'failed')
                    match_data['cleaning_mode'] = 'scene'
                    match_data['cleaning_timestamp'] = datetime.now().isoformat()
                    
                    match_file = self.output_dir / str(year) / caption_dir / 'matches.json'
                    with open(match_file, 'w') as f:
                        json.dump(match_data, f, indent=2)
                    
                    # Save cleaning log
                    video_dir = self.output_dir / str(year) / caption_dir
                    self.save_video_log(video_dir, 'cleaning', result)
                    
                    time.sleep(2)
                    continue
                    
                except Exception as e:
                    self.logger.error(f"Scene cleaning failed for {caption_dir}, falling back to monolithic: {e}")
                    # Fall through to monolithic cleaning
                
            # Estimate file sizes
            all_files = match_data.get('primary_files', []) + match_data.get('supporting_files', [])
            total_size = self.estimate_total_file_size(all_files, year)
            self.logger.info(f"Processing {caption_dir}: {len(all_files)} files, total size: {total_size:,} bytes")
            
            # Check if files are too large for Claude's context window
            # Claude has roughly 200k token limit, and code files compress to ~4 chars per token
            # So ~800KB is a reasonable upper limit for safety
            MAX_FILE_SIZE = 800_000  # 800KB
            if total_size > MAX_FILE_SIZE:
                self.logger.warning(f"Skipping {caption_dir}: Files too large ({total_size:,} bytes > {MAX_FILE_SIZE:,} bytes)")
                cleaning_results[caption_dir] = {
                    'status': 'skipped',
                    'reason': f'Files too large: {total_size:,} bytes exceeds {MAX_FILE_SIZE:,} byte limit'
                }
                stats['failed'] += 1
                
                # Save to checkpoint as failed
                checkpoint["failed_videos"][caption_dir] = f"Files too large: {total_size:,} bytes"
                self.save_cleaning_checkpoint(year, checkpoint)
                continue
            
            # Create cleaning prompt
            prompt = self.create_cleaning_prompt(video_id, caption_dir, match_data, year)
            
            # Run cleaning
            max_retries = getattr(self, 'max_retries', 3)
            result = self.run_claude_cleaning(prompt, video_id, caption_dir, year=year, file_size=total_size, max_retries=max_retries)
            
            if result['status'] == 'completed':
                # Validate the cleaned code
                cleaned_file = self.output_dir / str(year) / caption_dir / 'cleaned_code.py'
                is_valid, error = self.validate_cleaned_code(cleaned_file)
                
                if is_valid:
                    self.logger.info(f"Successfully cleaned {caption_dir}")
                    result['validation'] = 'passed'
                    stats['cleaned'] += 1
                    
                    # Save to checkpoint
                    checkpoint["completed_videos"].append(caption_dir)
                    self.save_cleaning_checkpoint(year, checkpoint)
                else:
                    self.logger.warning(f"Cleaned code validation failed for {caption_dir}: {error}")
                    
                    # Try to read and fix the code one more time
                    try:
                        with open(cleaned_file) as f:
                            broken_code = f.read()
                        
                        # Apply more aggressive fixes
                        fixed_code = self.fix_common_syntax_issues(broken_code)
                        
                        # Try compiling the fixed code
                        compile(fixed_code, str(cleaned_file), 'exec')
                        
                        # If we get here, the fixes worked
                        with open(cleaned_file, 'w') as f:
                            f.write(fixed_code)
                        
                        self.logger.info(f"Successfully fixed syntax errors in {caption_dir}")
                        result['validation'] = 'fixed'
                        result['validation_fixes'] = 'Applied automatic syntax fixes'
                        stats['cleaned'] += 1
                        
                        # Save to checkpoint
                        checkpoint["completed_videos"].append(caption_dir)
                        self.save_cleaning_checkpoint(year, checkpoint)
                        
                    except Exception as fix_error:
                        # Fixes didn't work, mark as failed
                        self.logger.error(f"Could not fix syntax errors in {caption_dir}: {fix_error}")
                        result['validation'] = 'failed'
                        result['validation_error'] = error
                        stats['failed'] += 1
                        
                        # Save failure to checkpoint
                        checkpoint["failed_videos"][caption_dir] = error
                        self.save_cleaning_checkpoint(year, checkpoint)
            else:
                stats['failed'] += 1
                
                # Save failure to checkpoint
                checkpoint["failed_videos"][caption_dir] = result.get('error', 'Unknown error')
                self.save_cleaning_checkpoint(year, checkpoint)
                
            cleaning_results[caption_dir] = result
            
            # Update the match file with cleaning status
            match_data['cleaning_status'] = result['status']
            match_data['cleaning_timestamp'] = datetime.now().isoformat()
            
            match_file = self.output_dir / str(year) / caption_dir / 'matches.json'
            with open(match_file, 'w') as f:
                json.dump(match_data, f, indent=2)
                
            # Save cleaning log to video's logs.json file
            video_dir = self.output_dir / str(year) / caption_dir
            log_file = video_dir / 'logs.json'
            
            # Load existing logs if file exists
            if log_file.exists():
                with open(log_file) as f:
                    logs = json.load(f)
            else:
                logs = {}
            
            # Add cleaning log
            logs['cleaning'] = {
                'timestamp': datetime.now().isoformat(),
                'data': result
            }
            
            # Save updated logs
            with open(log_file, 'w') as f:
                json.dump(logs, f, indent=2)
                
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
    parser.add_argument('--timeout-multiplier', type=float, default=1.0,
                        help='Multiply all timeouts by this factor (default: 1.0)')
    parser.add_argument('--max-retries', type=int, default=3,
                        help='Maximum number of retry attempts for timeouts (default: 3)')
    parser.add_argument('--no-resume', action='store_true',
                        help='Do not resume from checkpoint, start fresh')
    parser.add_argument('--clear-checkpoint', action='store_true',
                        help='Clear the checkpoint file before starting')
    parser.add_argument('--force', action='store_true',
                        help='Force re-cleaning of already cleaned files')
    parser.add_argument('--mode', choices=['monolithic', 'scene'], default='scene',
                        help='Cleaning mode: scene-by-scene (default) or monolithic')
    
    args = parser.parse_args()
    
    base_dir = Path(__file__).parent.parent
    cleaner = CodeCleaner(base_dir, verbose=args.verbose, timeout_multiplier=args.timeout_multiplier, max_retries=args.max_retries)
    
    if args.video:
        # Clean a specific video
        match_results = cleaner.load_match_results(args.year)
        if args.video in match_results:
            match_data = match_results[args.video]
            should_clean, reason = cleaner.should_clean_video(match_data, force=args.force)
            
            if should_clean:
                video_id = match_data.get('video_id', 'unknown')
                
                if args.mode == 'scene':
                    # Use scene-by-scene cleaning
                    from clean_matched_code_scenes import SceneAwareCleaner
                    scene_cleaner = SceneAwareCleaner(
                        str(base_dir), 
                        verbose=args.verbose,
                        timeout_multiplier=args.timeout_multiplier,
                        max_retries=args.max_retries
                    )
                    result = scene_cleaner.clean_video_by_scenes(
                        video_id, args.video, match_data, args.year
                    )
                else:
                    # Use monolithic cleaning
                    all_files = match_data.get('primary_files', []) + match_data.get('supporting_files', [])
                    total_size = cleaner.estimate_total_file_size(all_files, args.year)
                    prompt = cleaner.create_cleaning_prompt(video_id, args.video, match_data, args.year)
                    result = cleaner.run_claude_cleaning(prompt, video_id, args.video, year=args.year, 
                                                       file_size=total_size, max_retries=args.max_retries)
                print(f"Cleaning result: {result}")
            else:
                print(f"Video should not be cleaned: {reason}")
        else:
            print(f"No match data found for video: {args.video}")
    else:
        # Clear checkpoint if requested
        if args.clear_checkpoint:
            checkpoint_file = cleaner.output_dir / f'cleaning_checkpoint_{args.year}.json'
            if checkpoint_file.exists():
                checkpoint_file.unlink()
                print(f"Cleared checkpoint file: {checkpoint_file}")
        
        # Clean all matched videos
        summary = cleaner.clean_all_matched_videos(year=args.year, resume=not args.no_resume, 
                                                   force=args.force, mode=args.mode)
        
        print("\nCleaning Summary:")
        print(f"Total matched videos: {summary['stats']['total_matched']}")
        print(f"Successfully cleaned: {summary['stats']['cleaned']}")
        print(f"Skipped: {summary['stats']['skipped']}")
        print(f"  - Low confidence: {summary['stats']['low_confidence']}")
        print(f"  - No files: {summary['stats']['no_files']}")
        print(f"Failed: {summary['stats']['failed']}")

if __name__ == '__main__':
    main()