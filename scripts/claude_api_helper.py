#!/usr/bin/env python3
"""
Claude API Helper - Intelligent Error Fixing with Claude CLI

This module provides automatic error recovery using Claude's CLI tool (not API).
It follows the pattern established in convert_manimgl_to_manimce.py but is
designed for modular reuse across different pipeline stages.

Key Features:
- Uses subprocess to run claude command (not API)
- Intelligent prompt generation based on error context
- Supports multiple retry attempts with different strategies
- Collects and learns from successful fixes
"""

import subprocess
import logging
import json
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import time
from datetime import datetime
import hashlib
import uuid

# Import model strategy
from model_strategy import get_model_for_task

# Import enhanced logging
from enhanced_logging_system import ClaudeAPIMetrics, create_claude_metrics

# Configure logging
logger = logging.getLogger(__name__)

# Fix logging directory
FIX_LOG_DIR = Path(__file__).parent.parent / "data" / "claude_fixes"


class ClaudeErrorFixer:
    """Handles error fixing using Claude CLI for ManimCE code."""
    
    def __init__(self, verbose: bool = False, model: str = "opus", 
                 timeout: int = 120, max_attempts: int = 3,
                 use_model_strategy: bool = True, log_fixes: bool = True):
        """
        Initialize the Claude error fixer.
        
        Args:
            verbose: Whether to show Claude's output in real-time
            model: Claude model to use (default: opus)
            timeout: Timeout for Claude command in seconds
            max_attempts: Maximum number of fix attempts
            use_model_strategy: Whether to use smart model selection
            log_fixes: Whether to log all fixes to disk for pattern extraction
        """
        self.verbose = verbose
        self.model = model
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.use_model_strategy = use_model_strategy
        self.log_fixes = log_fixes
        self.fix_history = []  # Track successful fixes
        self.failed_attempts = {}  # Track what didn't work
        
        # Ensure fix log directory exists
        if self.log_fixes:
            FIX_LOG_DIR.mkdir(parents=True, exist_ok=True)
        
    def fix_render_error(self, scene_name: str, snippet_content: str, 
                        error_message: str, attempt_number: int = 1,
                        additional_context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Attempt to fix a render error using Claude.
        
        Args:
            scene_name: Name of the scene that failed
            snippet_content: Full self-contained snippet content
            error_message: Error message from render attempt
            attempt_number: Which attempt this is (affects prompt strategy)
            additional_context: Optional additional context (e.g., validation errors)
            
        Returns:
            Dict with 'success', 'fixed_content', 'changes_made', and 'error' keys
        """
        result = {
            'success': False,
            'fixed_content': snippet_content,
            'changes_made': [],
            'error': None,
            'attempt': attempt_number,
            'claude_stdout': None,
            'claude_stderr': None
        }
        
        try:
            # Create temporary file with current content first
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp_file:
                tmp_file.write(snippet_content)
                tmp_file_path = Path(tmp_file.name)
            
            try:
                # Generate fix prompt based on attempt number
                prompt = self._generate_fix_prompt(
                    scene_name, snippet_content, error_message, 
                    attempt_number, additional_context, tmp_file_path
                )
                
                # Save prompt for debugging
                prompt_file = Path(tempfile.gettempdir()) / f"claude_fix_prompt_{scene_name}_{attempt_number}.txt"
                with open(prompt_file, 'w') as f:
                    f.write(prompt)
                
                # Run Claude to fix the error
                fixed_content = self._run_claude_fix(prompt, tmp_file_path)
                
                if fixed_content and fixed_content != snippet_content:
                    result['success'] = True
                    result['fixed_content'] = fixed_content
                    result['changes_made'] = self._analyze_changes(snippet_content, fixed_content)
                    
                    # Record successful fix for learning
                    fix_data = {
                        'error_pattern': self._extract_error_pattern(error_message),
                        'fix_summary': result['changes_made'],
                        'attempt': attempt_number
                    }
                    self.fix_history.append(fix_data)
                    
                    # Log fix to disk for pattern extraction
                    if self.log_fixes:
                        self._log_fix_to_disk(scene_name, snippet_content, fixed_content, 
                                            error_message, fix_data, additional_context)
                else:
                    result['error'] = "Claude did not make any changes"
                    # Include error details if available
                    if hasattr(self, 'last_error_details'):
                        result['claude_stdout'] = self.last_error_details.get('stdout', '')
                        result['claude_stderr'] = self.last_error_details.get('stderr', '')
                    
                    # Track failed attempt
                    if scene_name not in self.failed_attempts:
                        self.failed_attempts[scene_name] = []
                    self.failed_attempts[scene_name].append({
                        'attempt': attempt_number,
                        'error': error_message,
                        'summary': f"No changes made for: {self._extract_error_pattern(error_message)}"
                    })
                    
            finally:
                # Clean up temporary file
                if tmp_file_path.exists():
                    tmp_file_path.unlink()
                    
        except Exception as e:
            logger.error(f"Error fixing with Claude: {str(e)}")
            result['error'] = str(e)
            
        return result
    
    def _generate_fix_prompt(self, scene_name: str, snippet_content: str,
                           error_message: str, attempt_number: int,
                           additional_context: Optional[Dict] = None,
                           tmp_file_path: Optional[Path] = None) -> str:
        """Generate an intelligent prompt based on error type and attempt number."""
        
        # Select model based on task and attempt
        if self.use_model_strategy:
            try:
                from model_strategy import get_model_for_task
                original_model = self.model
                self.model = get_model_for_task("fix_render_error", {
                    "attempt_number": attempt_number,
                    "error_complexity": "complex" if "TypeError" in error_message else "simple"
                })
                if self.model != original_model:
                    logger.info(f"Switched model from {original_model} to {self.model} for attempt {attempt_number}")
            except ImportError:
                pass  # Keep default model
        
        # Extract key error indicators
        error_patterns = self._extract_error_pattern(error_message)
        
        # Build context-aware prompt
        prompt_parts = [
            f"Fix this ManimCE scene that is failing to render.",
            f"Scene name: {scene_name}",
            f"Error: {error_message[:500]}",  # Limit error message length
            ""
        ]
        
        # Add previous failed attempts context
        if scene_name in self.failed_attempts and attempt_number > 1:
            prompt_parts.extend([
                "## Previous Failed Attempts:",
                f"You already tried {len(self.failed_attempts[scene_name])} fix(es) that didn't work:"
            ])
            for i, prev_attempt in enumerate(self.failed_attempts[scene_name][-2:], 1):
                prompt_parts.append(f"{i}. {prev_attempt['summary']}")
            prompt_parts.append("")
        
        # Add attempt-specific strategies
        if attempt_number == 1:
            prompt_parts.extend([
                "## First Attempt - Common Fixes",
                "1. Check for missing imports or incorrect class names",
                "2. Fix any API differences between ManimGL and ManimCE",
                "3. Ensure all color constants use ManimCE names",
                "4. Check method signatures match ManimCE API",
                ""
            ])
        elif attempt_number == 2:
            prompt_parts.extend([
                "## Second Attempt - Deeper Analysis",
                "The first fix didn't work. Try:",
                "1. Look for subtle API differences in method arguments",
                "2. Check if animations or transforms need different syntax",
                "3. Verify all properties exist (e.g., .width vs get_width())",
                "4. Look for deprecated features that need replacement",
                ""
            ])
        else:
            prompt_parts.extend([
                "## Final Attempt - Comprehensive Review",
                "Previous fixes failed. This needs thorough analysis:",
                "1. Carefully trace the exact line causing the error",
                "2. Consider if the scene logic needs restructuring",
                "3. Check for any circular dependencies or initialization issues",
                "4. Ensure all mathematical operations are valid",
                ""
            ])
        
        # Add additional context if provided
        if additional_context:
            # Pre-conversion validation insights
            if 'pre_conversion_validation' in additional_context:
                pre_val = additional_context['pre_conversion_validation']
                prompt_parts.extend([
                    "## Pre-Conversion Analysis:",
                    f"Conversion confidence: {pre_val.get('confidence', 0):.1%}",
                    f"Known issues: {pre_val.get('error_count', 0)} errors, {pre_val.get('warning_count', 0)} warnings",
                    ""
                ])
                
                if pre_val.get('top_issues'):
                    prompt_parts.append("Top identified issues:")
                    for issue in pre_val['top_issues'][:3]:
                        prompt_parts.append(f"- Line {issue['line']}: {issue['message']}")
                        if issue.get('suggestion'):
                            prompt_parts.append(f"  Suggestion: {issue['suggestion']}")
                    prompt_parts.append("")
            
            if 'original_scene_content' in additional_context:
                prompt_parts.extend([
                    "## Original Scene Code (before conversion):",
                    "This might help you understand the intended functionality:",
                    "```python",
                    additional_context['original_scene_content'][:1000] + "...",
                    "```",
                    ""
                ])
            
            if 'dependencies' in additional_context and additional_context['dependencies']:
                deps = additional_context['dependencies']
                prompt_parts.extend([
                    "## Scene Dependencies:",
                    f"- Functions: {deps.get('function_count', 0)}",
                    f"- Classes: {deps.get('class_count', 0)}",
                    f"- Constants: {deps.get('constant_count', 0)}",
                    ""
                ])
        
        # Add specific patterns based on error type
        if "attribute" in error_message.lower():
            prompt_parts.extend([
                "## Attribute Error Detected",
                "- Check if the attribute exists in ManimCE",
                "- It might be a property now (no parentheses)",
                "- Or it might have been renamed",
                ""
            ])
        elif "argument" in error_message.lower():
            prompt_parts.extend([
                "## Argument Error Detected",
                "- Check the method signature in ManimCE docs",
                "- Parameter names or order might have changed",
                "- Some parameters might be deprecated",
                ""
            ])
        elif "import" in error_message.lower():
            prompt_parts.extend([
                "## Import Error Detected",
                "- Ensure all imports use 'from manim import *'",
                "- Check if the class/function exists in ManimCE",
                "- It might have been renamed or moved",
                ""
            ])
        
        # Add previous fix patterns if available
        if self.fix_history:
            similar_fixes = self._find_similar_fixes(error_patterns)
            if similar_fixes:
                prompt_parts.extend([
                    "## Previous Successful Fixes for Similar Errors:",
                    *[f"- {fix['fix_summary']}" for fix in similar_fixes[:3]],
                    ""
                ])
        
        # Add the code to a temporary file path
        prompt_parts.extend([
            f"## Code to Fix:",
            "```python",
            snippet_content,
            "```",
            "",
            "## Instructions:",
            f"Edit the file at: {tmp_file_path}",
            "Make ONLY the changes needed to fix the render error",
            "Do not refactor or improve code style",
            "Preserve all functionality while fixing the error",
            "Add comments explaining any non-obvious fixes",
            "",
            "IMPORTANT: Do NOT create any additional files. Only edit the file specified above.",
            "If dependencies are missing, add them directly to the file being edited.",
            "Do not create separate dependency files or any other auxiliary files."
        ])
        
        return "\n".join(prompt_parts)
    
    def _run_claude_fix(self, prompt: str, file_path: Path) -> Optional[str]:
        """Run Claude CLI to fix the code."""
        # Generate unique call ID for tracking
        call_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        try:
            # Get appropriate model based on strategy or use configured model
            if self.use_model_strategy:
                # Extract attempt number from prompt (hacky but works)
                attempt_number = 1
                if "Attempt 2" in prompt:
                    attempt_number = 2
                elif "Attempt 3" in prompt:
                    attempt_number = 3
                model = get_model_for_task("fix_render_error", context={"attempt_number": attempt_number})
            else:
                model = self.model
                
            # Estimate prompt tokens (rough approximation)
            prompt_tokens = len(prompt.split()) * 1.3  # Rough token estimate
            
            # Use the model selected
            cmd = ["claude", "--dangerously-skip-permissions", "--model", model]
            
            if self.verbose:
                logger.info(f"Running Claude ({model}) to fix render errors...")
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )
                
                # Send prompt and close stdin
                process.stdin.write(prompt)
                process.stdin.close()
                
                # Collect output while printing if verbose
                stdout_lines = []
                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    if line:
                        print(f"    Claude: {line.rstrip()}")
                        stdout_lines.append(line)
                
                stderr = process.stderr.read()
                stdout = ''.join(stdout_lines)
                returncode = process.returncode
                
            else:
                # Run silently
                result = subprocess.run(
                    cmd,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout
                )
                returncode = result.returncode
                stderr = result.stderr
                stdout = result.stdout
            
            response_time = time.time() - start_time
            
            if returncode == 0:
                # Read the potentially modified file
                if file_path.exists():
                    with open(file_path, 'r') as f:
                        fixed_content = f.read()
                    
                    # Estimate completion tokens
                    completion_tokens = len(fixed_content.split()) * 1.3
                    total_tokens = prompt_tokens + completion_tokens
                    
                    # Create and log API metrics
                    metrics = create_claude_metrics(
                        call_id=call_id,
                        model=model,
                        success=True,
                        response_time=response_time
                    )
                    metrics.prompt_tokens = int(prompt_tokens)
                    metrics.completion_tokens = int(completion_tokens)
                    metrics.total_tokens = int(total_tokens)
                    
                    # Store metrics for potential logging by caller
                    if hasattr(self, 'last_api_metrics'):
                        self.last_api_metrics = metrics
                    
                    logger.info(f"Claude fix completed (call_id: {call_id}, tokens: {int(total_tokens)}, time: {response_time:.1f}s)")
                    return fixed_content
                else:
                    logger.error("File not found after Claude edit")
                    
                    # Log failure metrics
                    metrics = create_claude_metrics(
                        call_id=call_id,
                        model=model,
                        success=False,
                        response_time=response_time,
                        error="File not found after edit"
                    )
                    if hasattr(self, 'last_api_metrics'):
                        self.last_api_metrics = metrics
                        
                    return None
            else:
                logger.error(f"Claude returned non-zero exit code: {returncode}")
                if stderr:
                    logger.error(f"Claude stderr: {stderr}")
                
                # Log failure metrics
                metrics = create_claude_metrics(
                    call_id=call_id,
                    model=model,
                    success=False,
                    response_time=response_time,
                    error=f"Exit code {returncode}: {stderr}"
                )
                if hasattr(self, 'last_api_metrics'):
                    self.last_api_metrics = metrics
                
                # Store error details in result
                self.last_error_details = {
                    'stdout': stdout if 'stdout' in locals() else '',
                    'stderr': stderr,
                    'exit_code': returncode
                }
                return None
                
        except subprocess.TimeoutExpired:
            response_time = time.time() - start_time
            logger.error(f"Claude fix timed out after {self.timeout} seconds")
            
            # Log timeout metrics
            metrics = create_claude_metrics(
                call_id=call_id,
                model=model,
                success=False,
                response_time=response_time,
                error=f"Timeout after {self.timeout}s"
            )
            if hasattr(self, 'last_api_metrics'):
                self.last_api_metrics = metrics
                
            return None
        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"Error running Claude: {str(e)}")
            
            # Log exception metrics
            metrics = create_claude_metrics(
                call_id=call_id,
                model=model,
                success=False,
                response_time=response_time,
                error=str(e)
            )
            if hasattr(self, 'last_api_metrics'):
                self.last_api_metrics = metrics
                
            return None
    
    def _extract_error_pattern(self, error_message: str) -> str:
        """Extract key pattern from error message for matching."""
        # Remove file paths and line numbers to get generic pattern
        import re
        pattern = error_message
        
        # Remove file paths
        pattern = re.sub(r'File "[^"]+", line \d+', 'File "...", line N', pattern)
        
        # Remove specific variable names but keep structure
        pattern = re.sub(r"'[^']+' object", "'X' object", pattern)
        pattern = re.sub(r'"[^"]+"', '"X"', pattern)
        
        # Get just the error type and key info
        lines = pattern.split('\n')
        if lines:
            # Usually the last line has the key error
            key_line = lines[-1].strip()
            if ':' in key_line:
                return key_line.split(':', 1)[0]
        
        return pattern[:100]  # Fallback to first 100 chars
    
    def _find_similar_fixes(self, error_pattern: str) -> List[Dict]:
        """Find previous fixes for similar errors."""
        similar = []
        for fix in self.fix_history:
            if error_pattern in fix['error_pattern'] or fix['error_pattern'] in error_pattern:
                similar.append(fix)
        return similar
    
    def _analyze_changes(self, original: str, fixed: str) -> List[str]:
        """Analyze what changes were made."""
        changes = []
        
        # Simple line-by-line diff analysis
        original_lines = original.splitlines()
        fixed_lines = fixed.splitlines()
        
        # Look for common patterns
        if "from manim import" in fixed and "from manim import" not in original:
            changes.append("Added missing imports")
        
        if len(fixed_lines) != len(original_lines):
            changes.append(f"Changed line count: {len(original_lines)} → {len(fixed_lines)}")
        
        # Check for specific replacements
        replacements = [
            ("ShowCreation", "Create"),
            ("TextMobject", "Text"),
            ("TexMobject", "MathTex"),
            ("get_width()", ".width"),
            ("get_height()", ".height"),
        ]
        
        for old, new in replacements:
            if old in original and new in fixed and old not in fixed:
                changes.append(f"Replaced {old} with {new}")
        
        if not changes:
            changes.append("Made subtle modifications")
        
        return changes
    
    def get_fix_statistics(self) -> Dict[str, Any]:
        """Get statistics about fix attempts and success patterns."""
        stats = {
            'total_attempts': len(self.fix_history) + sum(len(attempts) for attempts in self.failed_attempts.values()),
            'successful_fixes': len(self.fix_history),
            'success_rate': 0,
            'common_errors': {},
            'successful_patterns': {}
        }
        
        # Calculate success rate
        if stats['total_attempts'] > 0:
            stats['success_rate'] = stats['successful_fixes'] / stats['total_attempts']
        
        # Analyze common error patterns
        error_counts = {}
        for history in self.fix_history:
            pattern = history['error_pattern']
            error_counts[pattern] = error_counts.get(pattern, 0) + 1
        
        stats['common_errors'] = dict(sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5])
        
        # Analyze successful fix patterns
        fix_counts = {}
        for history in self.fix_history:
            for change in history['fix_summary']:
                fix_counts[change] = fix_counts.get(change, 0) + 1
        
        stats['successful_patterns'] = dict(sorted(fix_counts.items(), key=lambda x: x[1], reverse=True)[:5])
        
        return stats
    
    def _log_fix_to_disk(self, scene_name: str, original_content: str, 
                        fixed_content: str, error_message: str, 
                        fix_data: Dict, additional_context: Optional[Dict] = None):
        """Log a fix to disk for later pattern analysis."""
        # Create unique ID for this fix
        timestamp = datetime.now().isoformat()
        content_hash = hashlib.md5(original_content.encode()).hexdigest()[:8]
        fix_id = f"{scene_name}_{timestamp.replace(':', '-')}_{content_hash}"
        
        # Create log entry
        log_entry = {
            'fix_id': fix_id,
            'timestamp': timestamp,
            'scene_name': scene_name,
            'error_message': error_message,
            'error_pattern': fix_data['error_pattern'],
            'fix_summary': fix_data['fix_summary'],
            'attempt_number': fix_data['attempt'],
            'model_used': self.model,
            'original_line_count': len(original_content.splitlines()),
            'fixed_line_count': len(fixed_content.splitlines()),
            'diff_stats': self._compute_diff_stats(original_content, fixed_content)
        }
        
        # Add additional context if provided
        if additional_context:
            log_entry['context'] = {
                'dependencies': additional_context.get('dependencies', {}),
                'video_year': additional_context.get('video_year'),
                'video_name': additional_context.get('video_name')
            }
        
        # Save files
        fix_dir = FIX_LOG_DIR / fix_id
        fix_dir.mkdir(exist_ok=True)
        
        # Save original content
        with open(fix_dir / "original.py", 'w') as f:
            f.write(original_content)
        
        # Save fixed content
        with open(fix_dir / "fixed.py", 'w') as f:
            f.write(fixed_content)
        
        # Save metadata
        with open(fix_dir / "metadata.json", 'w') as f:
            json.dump(log_entry, f, indent=2)
        
        # Also append to daily log file
        daily_log = FIX_LOG_DIR / f"fixes_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        with open(daily_log, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    
    def _compute_diff_stats(self, original: str, fixed: str) -> Dict[str, int]:
        """Compute statistics about the differences."""
        stats = {
            'lines_added': 0,
            'lines_removed': 0,
            'lines_modified': 0,
            'imports_changed': False,
            'methods_changed': 0,
            'classes_changed': 0
        }
        
        # Basic line diff
        orig_lines = set(original.splitlines())
        fixed_lines = set(fixed.splitlines())
        
        stats['lines_added'] = len(fixed_lines - orig_lines)
        stats['lines_removed'] = len(orig_lines - fixed_lines)
        
        # Check specific changes
        if ('from manim import' in fixed) != ('from manim import' in original):
            stats['imports_changed'] = True
        
        # Count method/class changes (simple heuristic)
        import re
        orig_methods = len(re.findall(r'def \w+', original))
        fixed_methods = len(re.findall(r'def \w+', fixed))
        stats['methods_changed'] = abs(fixed_methods - orig_methods)
        
        orig_classes = len(re.findall(r'class \w+', original))
        fixed_classes = len(re.findall(r'class \w+', fixed))
        stats['classes_changed'] = abs(fixed_classes - orig_classes)
        
        return stats


# Backward compatibility alias
ClaudeAPIHelper = ClaudeErrorFixer


def test_claude_error_fixer():
    """Test the Claude error fixer with a sample error."""
    
    # Sample failing scene
    failing_scene = '''from manim import *

class TestScene(Scene):
    def construct(self):
        # This will fail because ShowCreation doesn't exist in ManimCE
        circle = Circle()
        self.play(ShowCreation(circle))
'''
    
    # Sample error message
    error_msg = '''Traceback (most recent call last):
  File "test.py", line 7, in construct
    self.play(ShowCreation(circle))
NameError: name 'ShowCreation' is not defined'''
    
    fixer = ClaudeErrorFixer(verbose=True)
    result = fixer.fix_render_error(
        scene_name="TestScene",
        snippet_content=failing_scene,
        error_message=error_msg,
        attempt_number=1
    )
    
    print("\nFix Result:")
    print(f"Success: {result['success']}")
    print(f"Changes: {result['changes_made']}")
    if result['success']:
        print("\nFixed content:")
        print(result['fixed_content'])
    
    return result


if __name__ == "__main__":
    # Run test if called directly
    test_claude_error_fixer()