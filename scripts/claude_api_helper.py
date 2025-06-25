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

# Configure logging
logger = logging.getLogger(__name__)


class ClaudeErrorFixer:
    """Handles error fixing using Claude CLI for ManimCE code."""
    
    def __init__(self, verbose: bool = False, model: str = "opus", 
                 timeout: int = 120, max_attempts: int = 3,
                 use_model_strategy: bool = True):
        """
        Initialize the Claude error fixer.
        
        Args:
            verbose: Whether to show Claude's output in real-time
            model: Claude model to use (default: opus)
            timeout: Timeout for Claude command in seconds
            max_attempts: Maximum number of fix attempts
            use_model_strategy: Whether to use smart model selection
        """
        self.verbose = verbose
        self.model = model
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.use_model_strategy = use_model_strategy
        self.fix_history = []  # Track successful fixes
        self.failed_attempts = {}  # Track what didn't work
        
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
                    self.fix_history.append({
                        'error_pattern': self._extract_error_pattern(error_message),
                        'fix_summary': result['changes_made'],
                        'attempt': attempt_number
                    })
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
                self.model = get_model_for_task("fix_render_error", {
                    "attempt_number": attempt_number,
                    "error_complexity": "complex" if "TypeError" in error_message else "simple"
                })
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
            "Add comments explaining any non-obvious fixes"
        ])
        
        return "\n".join(prompt_parts)
    
    def _run_claude_fix(self, prompt: str, file_path: Path) -> Optional[str]:
        """Run Claude CLI to fix the code."""
        try:
            # Use the model selected in _generate_fix_prompt (which may have changed based on strategy)
            cmd = ["claude", "--dangerously-skip-permissions", "--model", self.model]
            
            if self.verbose:
                logger.info("Running Claude to fix render errors...")
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
            
            if returncode == 0:
                # Read the potentially modified file
                if file_path.exists():
                    with open(file_path, 'r') as f:
                        return f.read()
                else:
                    logger.error("File not found after Claude edit")
                    return None
            else:
                logger.error(f"Claude returned non-zero exit code: {returncode}")
                if stderr:
                    logger.error(f"Claude stderr: {stderr}")
                # Store error details in result
                self.last_error_details = {
                    'stdout': stdout if 'stdout' in locals() else '',
                    'stderr': stderr,
                    'exit_code': returncode
                }
                return None
                
        except subprocess.TimeoutExpired:
            logger.error(f"Claude fix timed out after {self.timeout} seconds")
            return None
        except Exception as e:
            logger.error(f"Error running Claude: {str(e)}")
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