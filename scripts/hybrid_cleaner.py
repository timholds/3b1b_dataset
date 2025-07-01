#!/usr/bin/env python3
"""
Hybrid cleaner that combines programmatic cleaning with Claude fallback.
Uses fast AST-based cleaning for 80-90% of cases, only calls Claude for complex cases.
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple
from datetime import datetime

# Import cleaners
from programmatic_cleaner import ProgrammaticCleaner, CleaningResult
from clean_matched_code_scenes import SceneAwareCleaner
from clean_matched_code import CodeCleaner
from simple_file_includer import SimpleFileIncluder, SimpleIncludeResult

# Import enhanced logging
from enhanced_logging_system import (
    EnhancedVideoLogger, StageType, RetryAttempt, ErrorCategory, 
    create_error_from_exception
)

logger = logging.getLogger(__name__)


class HybridCleaner:
    """
    Intelligent cleaner that attempts programmatic cleaning first,
    falls back to Claude only when needed.
    """
    
    def __init__(self, base_dir: str, verbose: bool = False, 
                 timeout_multiplier: float = 1.0, max_retries: int = 3):
        self.base_dir = Path(base_dir)
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)
        
        # Initialize cleaners
        self.programmatic_cleaner = ProgrammaticCleaner(base_dir, verbose)
        self.scene_cleaner = SceneAwareCleaner(base_dir, verbose, timeout_multiplier, max_retries)
        self.monolithic_cleaner = CodeCleaner(base_dir, verbose, timeout_multiplier, max_retries)
        self.simple_includer = SimpleFileIncluder(base_dir, verbose)
        
        # Track statistics
        self.stats = {
            'total_videos': 0,
            'programmatic_success': 0,
            'claude_fallback': 0,
            'scene_mode_fallback': 0,
            'monolithic_fallback': 0,
            'total_failures': 0
        }
    
    def clean_all_matched_videos(self, year: int, video_filter: Optional[List[str]] = None,
                                force: bool = False, mode: str = 'hybrid', 
                                resume: bool = True) -> Dict:
        """
        Clean all matched videos using hybrid approach.
        
        Args:
            year: Year to process
            video_filter: Optional list of specific videos to process
            force: Force re-cleaning of existing files
            mode: Cleaning mode - 'hybrid' (default), 'programmatic', 'claude'
            resume: Resume from previous run
            
        Returns:
            Summary dictionary with results and statistics
        """
        if self.verbose:
            self.logger.info(f"Starting hybrid cleaning for year {year}")
            self.logger.info(f"Mode: {mode}")
        
        # Load matching results - check both old and new locations
        matching_file = self.base_dir / 'outputs' / f'matching_summary_{year}.json'
        matching_file_new = self.base_dir / 'outputs' / 'logs' / f'matching_summary_{year}.json'
        
        if matching_file_new.exists():
            matching_file = matching_file_new
        elif not matching_file.exists():
            raise FileNotFoundError(f"No matching results found for {year} in either location")
        
        with open(matching_file) as f:
            matching_data = json.load(f)
        
        results = matching_data.get('results', {})
        
        # Filter videos if specified
        if video_filter:
            results = {k: v for k, v in results.items() if k in video_filter}
        
        # Initialize summary
        summary = {
            'year': year,
            'timestamp': datetime.now().isoformat(),
            'mode': mode,
            'stats': {
                'total_matched': len(results),
                'processed': 0,
                'cleaned': 0,
                'failed': 0,
                'skipped': 0,
                'programmatic_success': 0,
                'claude_fallback': 0
            },
            'results': {}
        }
        
        # Process each video
        for caption_dir, match_data in results.items():
            self.stats['total_videos'] += 1
            
            # Skip if not a successful match
            # Check the process status (whether the matching process completed)
            process_status = match_data.get('process_status', match_data.get('status', ''))  # Fallback for backward compatibility
            if not isinstance(match_data, dict) or process_status not in ['completed', 'matched', 'low_confidence']:
                summary['stats']['skipped'] += 1
                summary['results'][caption_dir] = 'skipped'
                continue
            
            # Also check if we have actual match data with files
            # Handle both old format (2015) and new format (2016+)
            if 'match_data' in match_data:
                # New format: primary_files inside match_data
                actual_match = match_data.get('match_data', {})
                has_files = bool(actual_match.get('primary_files', []))
            else:
                # Old format: primary_files at top level
                actual_match = match_data
                has_files = bool(match_data.get('primary_files', []))
            
            if not has_files:
                self.logger.warning(f"Skipping {caption_dir} - no primary files found in match data")
                summary['stats']['skipped'] += 1
                summary['results'][caption_dir] = 'skipped'
                continue
            
            # Check if already processed (unless forcing)
            cleaning_status = match_data.get('cleaning_status', 'not_cleaned')
            # Check for monolith file in the standard location (not .pipeline/intermediate)
            output_file = self.base_dir / 'outputs' / str(year) / caption_dir / 'monolith_manimgl.py'
            
            # Skip only if cleaning was completed AND file exists (unless forcing)
            if cleaning_status == 'completed' and output_file.exists() and not force:
                # Skip silently unless verbose
                if self.verbose:
                    self.logger.debug(f"Skipping {caption_dir} - already completed")
                summary['stats']['skipped'] += 1
                summary['results'][caption_dir] = 'skipped'
                continue
            
            # For videos with error or no_scenes_found status, retry them
            if cleaning_status in ['error', 'no_scenes_found'] and not force:
                if self.verbose:
                    self.logger.info(f"Retrying {caption_dir} - previous status: {cleaning_status}")
            
            # For videos marked completed but missing output file, reprocess
            if cleaning_status == 'completed' and not output_file.exists():
                self.logger.warning(f"Reprocessing {caption_dir} - marked completed but missing output file")
            
            # Process video
            video_id = match_data.get('video_id', '')
            result = self._clean_single_video(video_id, caption_dir, match_data, year, mode)
            
            # Update cleaning status in matches.json
            self._update_cleaning_status(year, caption_dir, result)
            
            # Update summary
            summary['stats']['processed'] += 1
            summary['results'][caption_dir] = result
            
            if result.get('status') == 'completed':
                summary['stats']['cleaned'] += 1
                if result.get('method') == 'programmatic':
                    summary['stats']['programmatic_success'] += 1
                else:
                    summary['stats']['claude_fallback'] += 1
            else:
                summary['stats']['failed'] += 1
        
        # Update final statistics
        summary['stats'].update({
            'programmatic_success_rate': self.stats['programmatic_success'] / self.stats['total_videos'] if self.stats['total_videos'] > 0 else 0,
            'claude_fallback_rate': self.stats['claude_fallback'] / self.stats['total_videos'] if self.stats['total_videos'] > 0 else 0
        })
        
        if self.verbose:
            self.logger.info(f"Hybrid cleaning completed:")
            self.logger.info(f"  Total: {self.stats['total_videos']}")
            self.logger.info(f"  Programmatic success: {self.stats['programmatic_success']}")
            self.logger.info(f"  Claude fallback: {self.stats['claude_fallback']}")
            self.logger.info(f"  Failures: {self.stats['total_failures']}")
        
        return summary
    
    def _clean_single_video(self, video_id: str, caption_dir: str, 
                           match_data: Dict, year: int, mode: str) -> Dict:
        """Clean a single video using hybrid approach."""
        
        # Initialize enhanced logging for this video
        video_dir = self.base_dir / 'outputs' / str(year) / caption_dir
        video_logger = EnhancedVideoLogger(video_dir, video_id)
        
        # Start stage logging
        perf_id = video_logger.log_stage_start(
            StageType.CLEANING, 
            method=mode,
            config={'mode': mode, 'year': year}
        )
        
        retry_attempts = []
        start_time = time.time()
        
        # Extract the actual match data from the nested structure
        # Handle both old format (2015) and new format (2016+)
        if 'match_data' in match_data:
            # New format: match data is nested
            actual_match_data = match_data['match_data']
        else:
            # Old format: match data is at top level
            actual_match_data = match_data
            
        # Handle legacy modes
        original_mode = mode
        if mode == 'scene':
            # Legacy scene mode = Claude scene-by-scene only
            return self._fallback_to_claude(video_id, caption_dir, actual_match_data, year, 'scene')
        elif mode == 'monolithic':
            # Legacy monolithic mode = Claude monolithic only
            return self._fallback_to_claude(video_id, caption_dir, actual_match_data, year, 'monolithic')
        elif mode == 'claude':
            # Force Claude mode - skip programmatic, start with scene-by-scene
            return self._fallback_to_claude(video_id, caption_dir, actual_match_data, year, 'scene')
        
        elif mode == 'simple':
            # Simple file inclusion mode - just concatenate all files
            result = self.simple_includer.include_all_files(video_id, caption_dir, actual_match_data, year)
            if result.success:
                self.stats['programmatic_success'] += 1
                return {
                    'status': 'completed',
                    'method': 'simple_include',
                    'files_included': result.files_included,
                    'total_lines': result.total_lines,
                    'duplicates_removed': result.duplicates_removed,
                    'syntax_valid': result.syntax_valid,
                    'validation_errors': result.validation_errors
                }
            else:
                self.stats['total_failures'] += 1
                return {
                    'status': 'failed',
                    'method': 'simple_include',
                    'error': result.error
                }
        
        elif mode == 'programmatic':
            # Force programmatic mode - no fallback
            result = self.programmatic_cleaner.clean_video_files(video_id, caption_dir, actual_match_data, year)
            if result.success:
                self.stats['programmatic_success'] += 1
                return {
                    'status': 'completed',
                    'method': 'programmatic',
                    'scenes_processed': result.scenes_processed,
                    'dependencies_found': result.dependencies_found,
                    'files_inlined': result.files_inlined
                }
            else:
                self.stats['total_failures'] += 1
                return {
                    'status': 'failed',
                    'method': 'programmatic',
                    'error': result.error
                }
        
        else:  # mode == 'hybrid'
            final_result = None
            
            try:
                # Try programmatic first
                if self.verbose:
                    self.logger.debug(f"Attempting programmatic cleaning for {caption_dir}")
                
                attempt_start = time.time()
                result = self.programmatic_cleaner.clean_video_files(video_id, caption_dir, actual_match_data, year)
                attempt_duration = time.time() - attempt_start
                
                # Log retry attempt
                attempt = RetryAttempt(
                    attempt_number=1,
                    method='programmatic',
                    status='success' if result.success else 'failed',
                    duration_seconds=attempt_duration,
                    error_message=result.error if not result.success else None
                )
                video_logger.log_retry_attempt(StageType.CLEANING, attempt)
                retry_attempts.append(attempt)
                
                if result.success:
                    # Validate syntax of programmatic output
                    output_file = self.base_dir / 'outputs' / str(year) / caption_dir / 'monolith_manimgl.py'
                    is_valid, validation_error = self._validate_output_syntax(output_file)
                    
                    # Log validation attempt
                    video_logger.log_validation_attempt(
                        'syntax_validation',
                        success=is_valid,
                        errors=[validation_error] if validation_error else []
                    )
                    
                    if is_valid:
                        # Programmatic success with valid syntax!
                        self.stats['programmatic_success'] += 1
                        if self.verbose:
                            self.logger.info(f"✅ Programmatic cleaning succeeded for {caption_dir}")
                        
                        final_result = {
                            'status': 'completed',
                            'method': 'programmatic',
                            'scenes_processed': result.scenes_processed,
                            'dependencies_found': result.dependencies_found,
                            'files_inlined': result.files_inlined,
                            'elapsed_time': attempt_duration,
                            'syntax_validated': True,
                            'validation_errors': [],
                            'retry_attempts': len(retry_attempts),
                            'scenes': self._create_scene_summary_for_programmatic(result, caption_dir)
                        }
                        
                        # Log successful completion
                        video_logger.log_stage_complete(
                            StageType.CLEANING,
                            success=True,
                            result_data=final_result,
                            performance_id=perf_id
                        )
                        return final_result
                    else:
                        # Syntax errors in programmatic output - fallback to Claude
                        self.logger.warning(f"⚠️ Programmatic output has syntax errors for {caption_dir}: {validation_error}")
                        if self.verbose:
                            self.logger.info(f"Falling back to Claude for syntax repair...")
                        
                        # Log attempt for Claude fallback
                        claude_attempt_start = time.time()
                        claude_result = self._fallback_to_claude(video_id, caption_dir, actual_match_data, year, 'scene')
                        claude_attempt_duration = time.time() - claude_attempt_start
                        
                        # Log Claude retry attempt
                        claude_attempt = RetryAttempt(
                            attempt_number=2,
                            method='claude_fallback',
                            status='success' if claude_result.get('status') == 'completed' else 'failed',
                            duration_seconds=claude_attempt_duration,
                            error_message=claude_result.get('error') if claude_result.get('status') != 'completed' else None
                        )
                        video_logger.log_retry_attempt(StageType.CLEANING, claude_attempt)
                        
                        # Log stage completion
                        video_logger.log_stage_complete(
                            StageType.CLEANING,
                            success=claude_result.get('status') == 'completed',
                            result_data=claude_result,
                            error=create_error_from_exception(Exception(validation_error), 'syntax_validation') if validation_error else None,
                            performance_id=perf_id
                        )
                        return claude_result
                
                elif result.fallback_needed:
                    # Complex case - fallback to Claude
                    if self.verbose:
                        self.logger.info(f"⚠️ Falling back to Claude for {caption_dir}: {result.error}")
                    
                    claude_attempt_start = time.time()
                    claude_result = self._fallback_to_claude(video_id, caption_dir, actual_match_data, year, 'scene')
                    claude_attempt_duration = time.time() - claude_attempt_start
                    
                    # Log Claude retry attempt
                    claude_attempt = RetryAttempt(
                        attempt_number=2,
                        method='claude_fallback',
                        status='success' if claude_result.get('status') == 'completed' else 'failed',
                        duration_seconds=claude_attempt_duration,
                        error_message=claude_result.get('error') if claude_result.get('status') != 'completed' else None
                    )
                    video_logger.log_retry_attempt(StageType.CLEANING, claude_attempt)
                    
                    # Log stage completion
                    video_logger.log_stage_complete(
                        StageType.CLEANING,
                        success=claude_result.get('status') == 'completed',
                        result_data=claude_result,
                        performance_id=perf_id
                    )
                    return claude_result
                
                else:
                    # True failure
                    self.stats['total_failures'] += 1
                    self.logger.error(f"❌ Cleaning failed for {caption_dir}: {result.error}")
                    
                    final_result = {
                        'status': 'failed',
                        'method': 'programmatic',
                        'error': result.error,
                        'elapsed_time': attempt_duration,
                        'retry_attempts': len(retry_attempts)
                    }
                    
                    # Log failure
                    error = create_error_from_exception(Exception(result.error), 'cleaning')
                    video_logger.log_stage_complete(
                        StageType.CLEANING,
                        success=False,
                        result_data=final_result,
                        error=error,
                        performance_id=perf_id
                    )
                    return final_result
                    
            except Exception as e:
                # Unexpected error during cleaning
                self.stats['total_failures'] += 1
                error_msg = f"Unexpected error during cleaning: {str(e)}"
                self.logger.error(f"❌ {error_msg} for {caption_dir}")
                
                final_result = {
                    'status': 'failed',
                    'method': mode,
                    'error': error_msg,
                    'elapsed_time': time.time() - start_time,
                    'retry_attempts': len(retry_attempts)
                }
                
                # Log exception
                error = create_error_from_exception(e, 'cleaning')
                video_logger.log_stage_complete(
                    StageType.CLEANING,
                    success=False,
                    result_data=final_result,
                    error=error,
                    performance_id=perf_id
                )
                return final_result
    
    def _fallback_to_claude(self, video_id: str, caption_dir: str, 
                          match_data: Dict, year: int, claude_mode: str) -> Dict:
        """Fallback to Claude-based cleaning."""
        self.stats['claude_fallback'] += 1
        
        try:
            if claude_mode == 'scene':
                # Try scene-by-scene Claude
                if self.verbose:
                    self.logger.debug(f"Trying Claude scene-by-scene for {caption_dir}")
                result = self.scene_cleaner.clean_video_by_scenes(video_id, caption_dir, match_data, year)
                
                if result.get('status') == 'completed':
                    # Validate syntax of Claude scene output
                    output_file = self.base_dir / 'outputs' / str(year) / caption_dir / 'monolith_manimgl.py'
                    is_valid, validation_error = self._validate_output_syntax(output_file)
                    
                    if is_valid:
                        result['method'] = 'claude_scene'
                        result['syntax_validated'] = True
                        return result
                    else:
                        # Scene output has syntax errors - log but continue to monolithic fallback
                        self.logger.warning(f"⚠️ Claude scene output has syntax errors for {caption_dir}: {validation_error}")
                        self.logger.info(f"Attempting monolithic Claude fallback...")
                else:
                    # Scene mode failed, try monolithic (unless we're in legacy scene mode)
                    self.stats['monolithic_fallback'] += 1
                    if self.verbose:
                        self.logger.debug(f"Scene mode failed, trying monolithic Claude for {caption_dir}")
                    
            elif claude_mode == 'monolithic':
                # Skip scene mode, go directly to monolithic
                if self.verbose:
                    self.logger.debug(f"Using Claude monolithic mode for {caption_dir}")
                    
            # Monolithic Claude fallback
            result = self.monolithic_cleaner.clean_single_video(video_id, caption_dir, match_data, year)
            
            if result.get('status') == 'completed':
                # Validate syntax of Claude monolithic output
                output_file = self.base_dir / 'outputs' / str(year) / caption_dir / 'monolith_manimgl.py'
                is_valid, validation_error = self._validate_output_syntax(output_file)
                
                if is_valid:
                    result['method'] = 'claude_monolithic'
                    result['syntax_validated'] = True
                    return result
                else:
                    # Even monolithic failed syntax - mark as failed
                    self.stats['total_failures'] += 1
                    self.logger.error(f"❌ Claude monolithic output has syntax errors for {caption_dir}: {validation_error}")
                    return {
                        'status': 'failed',
                        'method': 'claude_monolithic',
                        'error': f'Syntax validation failed: {validation_error}',
                        'syntax_validated': False
                    }
            else:
                self.stats['total_failures'] += 1
                return {
                    'status': 'failed',
                    'method': 'claude_fallback',
                    'error': result.get('reason', 'Unknown Claude error')
                }
                
        except Exception as e:
            self.stats['total_failures'] += 1
            self.logger.error(f"Claude fallback failed for {caption_dir}: {e}")
            return {
                'status': 'failed',
                'method': 'claude_fallback',
                'error': str(e)
            }
    
    def _validate_output_syntax(self, file_path: Path) -> Tuple[bool, Optional[str]]:
        """
        Validate syntax of cleaned output and apply automatic fixes.
        Uses the comprehensive syntax fixing from CodeCleaner.
        """
        if not file_path.exists():
            return False, "File does not exist"
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            # Check if file contains error message instead of code
            if code.strip().startswith("#") and "error" in code.lower() and len(code) < 500:
                return False, "File contains error message instead of code"
            
            # Apply syntax fixes using the same method as CodeCleaner
            # Skip syntax fixes for programmatic output since it should already be correct
            if 'Generated by programmatic cleaner' in code:
                # Programmatic cleaner output should already be syntactically correct
                pass
            else:
                original_code = code
                fixed_code = self._fix_common_syntax_issues(code)
                
                # Write back fixed code if changes were made
                if fixed_code != original_code:
                    self.logger.info(f"Applied syntax fixes to {file_path.name}")
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(fixed_code)
                    code = fixed_code
            
            # Try to compile the code
            compile(code, str(file_path), 'exec')
            
            # Additional validation - check for balanced delimiters
            open_parens = code.count('(') - code.count(')')
            open_brackets = code.count('[') - code.count(']')
            open_braces = code.count('{') - code.count('}')
            
            warnings = []
            if open_parens != 0:
                warnings.append(f"Unbalanced parentheses: {open_parens} unclosed")
            if open_brackets != 0:
                warnings.append(f"Unbalanced brackets: {open_brackets} unclosed")
            if open_braces != 0:
                warnings.append(f"Unbalanced braces: {open_braces} unclosed")
            
            if warnings:
                self.logger.warning(f"Syntax warnings for {file_path.name}: {'; '.join(warnings)}")
            
            return True, None
            
        except SyntaxError as e:
            error_msg = f"Syntax error at line {e.lineno}: {e.msg}"
            if e.text:
                error_msg += f" ('{e.text.strip()}')"
            return False, error_msg
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def _fix_common_syntax_issues(self, code: str) -> str:
        """
        Apply comprehensive syntax fixes.
        This is a simplified version of the fixes from clean_matched_code.py
        """
        import re
        
        # Fix 1: String continuations with backslashes
        def fix_string_continuation(match):
            quote = match.group(1)
            part1 = match.group(2)
            part2 = match.group(3)
            
            # Avoid creating invalid syntax like 'and" "tuple'
            if part1.rstrip().endswith(' and') or part1.rstrip().endswith(' or'):
                return match.group(0)
            
            part1 = part1.rstrip()
            part2 = part2.lstrip()
            return f'{quote}{part1}{quote} {quote}{part2}{quote}'
        
        pattern = r'(?<=[=\(\[\{\s,])(["\'])([^"\'\\]*(?:\\.[^"\'\\]*)*?)\s*\\\s*\n\s*([^"\'\\]*(?:\\.[^"\'\\]*)*?)\1'
        code = re.sub(pattern, fix_string_continuation, code, flags=re.MULTILINE)
        
        # Fix 2: Invalid escape sequences in regular strings
        def fix_escape_sequences(match):
            quote = match.group(1)
            content = match.group(2)
            if any(seq in content for seq in ['\\s', '\\p', '\\d', '\\w', '\\b']):
                return f'r{quote}{content}{quote}'
            return match.group(0)
        
        escape_pattern = r'(?<!r)(["\'])([^"\']*?(?:\\[spwdb][^"\']*?)*)\1'
        code = re.sub(escape_pattern, fix_escape_sequences, code)
        
        # Fix 3: Fix invalid assignment patterns
        # Pattern: = " "Something -> = Something
        assignment_pattern = r'=\s*"\s*"(?!\s*\n)\s*(\w+)'
        code = re.sub(assignment_pattern, r'= \1', code)
        
        # Fix 4: Fix quote mismatch in raw strings
        def fix_raw_string_quote_mismatch(code):
            # Pattern: r" content """ -> r""" content """
            multiline_pattern = r'r"([^"]*\n[^"]*?)"""'
            def fix_multiline_raw(match):
                content = match.group(1)
                return f'r"""{content}"""'
            code = re.sub(multiline_pattern, fix_multiline_raw, code, flags=re.MULTILINE | re.DOTALL)
            
            # Pattern: r" content """ -> r" content " (single line)
            singleline_pattern = r'r"([^"\n]*?)"""'
            def fix_singleline_raw(match):
                content = match.group(1)
                return f'r"{content}"'
            code = re.sub(singleline_pattern, fix_singleline_raw, code)
            
            return code
        
        code = fix_raw_string_quote_mismatch(code)
        
        # Fix 5: Fix function calls with parenthesis on wrong line (astunparse issue)
        # Strategy: Look for pattern where we have func() followed by indented args on next line(s)
        # and a closing ) that matches the opening one
        
        lines = code.split('\n')
        fixed_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Check if this line ends with empty parentheses
            match = re.match(r'^(\s*)(.*?)\(\)\s*$', line)
            if match and i + 1 < len(lines):
                indent = match.group(1)
                prefix = match.group(2)
                next_line = lines[i + 1]
                
                # Check if next line is indented (contains arguments)
                next_match = re.match(r'^(\s+)(.+)$', next_line)
                if next_match and len(next_match.group(1)) > len(indent):
                    # Collect all argument lines
                    arg_lines = []
                    j = i + 1
                    
                    while j < len(lines):
                        arg_line = lines[j]
                        # Check if this line is still part of the arguments
                        if re.match(r'^\s+', arg_line) or arg_line.strip() == ')':
                            arg_lines.append(arg_line)
                            if arg_line.strip() == ')':
                                # Found the closing parenthesis
                                # Reconstruct the function call
                                args = '\n'.join(arg_lines[:-1])  # Exclude the closing )
                                # Remove common indentation from args
                                if arg_lines:
                                    min_indent = min(len(line) - len(line.lstrip()) for line in arg_lines[:-1] if line.strip())
                                    args = '\n'.join(line[min_indent:] if len(line) > min_indent else line for line in arg_lines[:-1])
                                
                                # Create the fixed line
                                fixed_line = f"{indent}{prefix}({args})"
                                fixed_lines.append(fixed_line)
                                i = j + 1
                                break
                            j += 1
                        else:
                            # Not part of arguments, just add the original line
                            fixed_lines.append(line)
                            i += 1
                            break
                    else:
                        # Didn't find closing ), add original line
                        fixed_lines.append(line)
                        i += 1
                else:
                    # Next line is not indented, add original line
                    fixed_lines.append(line)
                    i += 1
            else:
                # No match, add original line
                fixed_lines.append(line)
                i += 1
        
        code = '\n'.join(fixed_lines)
        
        # Fix 6: Simple parenthesis balancing for common patterns
        lines = code.split('\n')
        fixed_lines = []
        
        for line in lines:
            # Remove string literals temporarily to count parentheses
            temp_line = line
            string_pattern = r'(\'[^\']*\'|"[^"]*")'
            strings = re.findall(string_pattern, temp_line)
            for j, string in enumerate(strings):
                temp_line = temp_line.replace(string, f'__STRING_{j}__')
            
            # Count parentheses in non-string parts
            open_count = temp_line.count('(')
            close_count = temp_line.count(')')
            
            # If more opens than closes, try to fix by adding closing parens
            if open_count > close_count:
                diff = open_count - close_count
                # Add closing parens if line doesn't end with continuation characters
                if not re.search(r'[,\\]\s*$', line.strip()):
                    # Check if this looks like a function call, assignment, etc.
                    if re.search(r'\w+\s*\(|=\s*\w+\s*\(', temp_line):
                        line = line.rstrip() + ')' * diff
            
            fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    def _create_scene_summary_for_programmatic(self, result: CleaningResult, caption_dir: str) -> Dict:
        """
        Create scene summary for programmatic cleaning results to match pipeline expectations.
        This ensures proper statistics aggregation even when using programmatic cleaning.
        """
        scenes_summary = {}
        
        # Create mock scene entries based on the scenes processed
        for i in range(result.scenes_processed):
            scene_name = f"scene_{i+1}"  # Generic names since programmatic doesn't track individual scene names
            scenes_summary[scene_name] = {
                'status': 'completed',
                'time': 0.0,  # Programmatic is instant
                'attempts': 1,
                'validation': 'passed',
                'method': 'programmatic'
            }
        
        # If no scenes were processed but we succeeded, create at least one entry
        if result.scenes_processed == 0 and result.success:
            scenes_summary['main_content'] = {
                'status': 'completed', 
                'time': 0.0,
                'attempts': 1,
                'validation': 'passed',
                'method': 'programmatic'
            }
        
        return scenes_summary
    
    def _update_cleaning_status(self, year: int, caption_dir: str, result: Dict):
        """Update the cleaning_status field in matches.json after cleaning attempt."""
        matches_file = self.base_dir / 'outputs' / str(year) / caption_dir / '.pipeline' / 'source' / 'matches.json'
        
        if not matches_file.exists():
            self.logger.warning(f"matches.json not found for {caption_dir}")
            return
        
        try:
            # Read existing matches data
            with open(matches_file, 'r') as f:
                matches_data = json.load(f)
            
            # Determine cleaning status based on result
            if result.get('status') == 'completed':
                cleaning_status = 'completed'
            elif result.get('status') == 'no_scenes_found':
                cleaning_status = 'no_scenes_found'
            else:
                cleaning_status = 'error'
            
            # Update the cleaning status and metadata
            matches_data['cleaning_status'] = cleaning_status
            matches_data['cleaning_mode'] = result.get('method', 'unknown')
            matches_data['cleaning_timestamp'] = datetime.now().isoformat()
            
            # Add error details if failed
            if cleaning_status == 'error' and result.get('error'):
                matches_data['cleaning_error'] = result['error']
            
            # Write back to file
            with open(matches_file, 'w') as f:
                json.dump(matches_data, f, indent=2)
                
            self.logger.debug(f"Updated matches.json for {caption_dir} with status: {cleaning_status}")
            
        except Exception as e:
            self.logger.error(f"Failed to update matches.json for {caption_dir}: {e}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Clean matched videos')
    parser.add_argument('--year', type=int, default=2015, help='Year to process')
    parser.add_argument('--video', action='append', help='Specific video to process')
    parser.add_argument('--force', action='store_true', help='Force re-cleaning')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    args = parser.parse_args()
    
    from pathlib import Path
    base_dir = Path(__file__).parent.parent
    cleaner = HybridCleaner(str(base_dir), verbose=args.verbose)
    summary = cleaner.clean_all_matched_videos(args.year, video_filter=args.video, force=args.force)
    print(json.dumps(summary, indent=2))