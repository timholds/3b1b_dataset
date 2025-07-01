#!/usr/bin/env python3
"""
Enhanced version of claude_api_helper.py with integrated prompt optimization.
Uses improved error fixing prompts with learned solutions.
"""

import subprocess
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple, List
import json
import time

# Import our optimization modules
from improved_prompts import ERROR_FIXING_PROMPT, format_prompt
from adaptive_prompt_optimizer import AdaptivePromptOptimizer
from prompt_feedback_system import PromptFeedbackSystem, PromptResult

class EnhancedClaudeAPIHelper:
    """Enhanced helper for making Claude API calls with optimized prompts."""
    
    def __init__(self, verbose: bool = False, base_dir: Optional[Path] = None):
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)
        
        # Set base directory for optimization data
        if base_dir is None:
            base_dir = Path(__file__).parent.parent
        
        self.output_dir = base_dir / 'outputs'
        
        # Initialize optimization systems
        self.optimizer = AdaptivePromptOptimizer(
            cache_dir=str(self.output_dir / 'prompt_optimization')
        )
        self.feedback_system = PromptFeedbackSystem(
            feedback_dir=str(self.output_dir / 'prompt_feedback')
        )
        
    def fix_render_error(self, snippet_path: Path, error_message: str, 
                        scene_name: str, attempt: int = 1,
                        previous_fixes: Optional[List[str]] = None) -> Tuple[bool, str]:
        """
        Fix a render error using Claude with optimized prompts.
        
        Returns:
            Tuple[bool, str]: (success, error_message or success_message)
        """
        start_time = time.time()
        
        # Read the current snippet content
        try:
            with open(snippet_path, 'r') as f:
                snippet_content = f.read()
        except Exception as e:
            return False, f"Failed to read snippet: {e}"
        
        # Create attempt-specific strategy
        attempt_strategies = {
            1: """
Focus on these common issues:
1. Missing imports (especially 'from functools import reduce')
2. Undefined color constants (import from manimce_constants_helpers)
3. Changed animation names (ShowCreation → Create, etc.)
4. Missing helper functions (add them directly to the file)
""",
            2: """
Look deeper for:
1. Subtle API differences in ManimCE
2. Animation/Transform syntax changes
3. Deprecated features that need replacement
4. Missing dependencies that should be inlined
""",
            3: """
Comprehensive review:
1. Trace the exact error line and context
2. Check for circular dependencies
3. Consider restructuring the logic if needed
4. Ensure ALL dependencies are included in the file
"""
        }
        
        attempt_strategy = attempt_strategies.get(
            attempt, 
            attempt_strategies[3]  # Use most comprehensive for attempt > 3
        )
        
        # Get optimized prompt
        base_prompt = ERROR_FIXING_PROMPT
        optimized_prompt = self.optimizer.optimize_error_fixing_prompt(
            base_prompt, error_message, attempt
        )
        
        # Add previous fixes context if available
        if previous_fixes and attempt > 1:
            fixes_context = "\n\nPREVIOUS FIX ATTEMPTS:\n"
            for i, fix in enumerate(previous_fixes, 1):
                fixes_context += f"Attempt {i}: {fix}\n"
            optimized_prompt = optimized_prompt.replace(
                "## Current Error:",
                f"{fixes_context}\n## Current Error:"
            )
        
        # Format the prompt
        formatted_prompt = format_prompt(
            optimized_prompt,
            scene_name=scene_name,
            error_message=error_message[:1000],  # Limit error message length
            attempt_number=attempt,
            attempt_specific_strategy=attempt_strategy,
            code=snippet_content,
            file_path=str(snippet_path)
        )
        
        # Initialize tracking
        prompt_result = PromptResult(
            prompt_type="fixing",
            success=False,
            confidence=0.0,
            attempt_number=attempt
        )
        
        # Call Claude
        try:
            # Determine model based on attempt
            if attempt == 1:
                model = "claude-3-haiku-20240307"
            elif attempt == 2:
                model = "claude-3-sonnet-20240229"
            else:
                model = "claude-3-5-sonnet-20241022"
            
            if self.verbose:
                self.logger.info(f"Calling Claude ({model}) to fix error (attempt {attempt})")
            
            # Run Claude command
            result = subprocess.run(
                ["claude", "--dangerously-skip-permissions", "--model", model],
                input=formatted_prompt,
                capture_output=True,
                text=True,
                timeout=180  # 3 minute timeout
            )
            
            if result.returncode != 0:
                error_msg = f"Claude returned error: {result.stderr}"
                prompt_result.error_type = "claude_error"
                prompt_result.execution_time = time.time() - start_time
                self.feedback_system.record_result(prompt_result)
                return False, error_msg
            
            # Check if the file was successfully modified
            # Claude should have edited the file directly
            
            # Validate the fix by trying to compile
            try:
                with open(snippet_path, 'r') as f:
                    fixed_content = f.read()
                compile(fixed_content, str(snippet_path), 'exec')
                
                # Success! Record for learning
                prompt_result.success = True
                prompt_result.confidence = 0.95
                prompt_result.execution_time = time.time() - start_time
                self.feedback_system.record_result(prompt_result)
                
                # Extract what fix was applied from Claude's response
                fix_description = self._extract_fix_description(result.stdout)
                if fix_description:
                    self.optimizer.record_success('fixing', {
                        'error': error_message,
                        'code_snippet': snippet_content[:200]
                    }, fix_description)
                
                return True, "Fix applied successfully"
                
            except SyntaxError as e:
                # Fix created syntax error
                error_msg = f"Fix created syntax error: {e}"
                prompt_result.error_type = "syntax_error_after_fix"
                prompt_result.execution_time = time.time() - start_time
                self.feedback_system.record_result(prompt_result)
                
                self.optimizer.record_failure('fixing', {
                    'error': error_message,
                    'attempt': attempt
                }, "syntax_error_after_fix")
                
                return False, error_msg
                
        except subprocess.TimeoutExpired:
            error_msg = "Claude request timed out"
            prompt_result.error_type = "timeout"
            prompt_result.execution_time = time.time() - start_time
            self.feedback_system.record_result(prompt_result)
            return False, error_msg
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            prompt_result.error_type = "unexpected_error"
            prompt_result.execution_time = time.time() - start_time
            self.feedback_system.record_result(prompt_result)
            return False, error_msg
    
    def _extract_fix_description(self, claude_output: str) -> Optional[str]:
        """Extract a description of what fix was applied from Claude's output."""
        # Look for common patterns in Claude's responses
        lines = claude_output.strip().split('\n')
        
        # Look for lines that describe what was done
        fix_indicators = [
            "added", "fixed", "changed", "imported", "replaced",
            "modified", "updated", "corrected", "included"
        ]
        
        for line in lines:
            line_lower = line.lower()
            if any(indicator in line_lower for indicator in fix_indicators):
                return line.strip()
        
        # If no clear description, take first non-empty line
        for line in lines:
            if line.strip() and not line.startswith(('#', '//')):
                return line.strip()[:200]
        
        return None
    
    def convert_scene_with_fixes(self, scene_path: Path, scene_name: str,
                               max_fix_attempts: int = 3) -> Dict:
        """
        Convert a scene and fix any errors that arise.
        
        Returns dict with:
            - success: bool
            - error_count: int
            - fixes_applied: List[str]
            - final_error: Optional[str]
        """
        result = {
            'success': False,
            'error_count': 0,
            'fixes_applied': [],
            'final_error': None
        }
        
        # First, try to render without any fixes
        render_success, error_msg = self._test_render(scene_path, scene_name)
        
        if render_success:
            result['success'] = True
            return result
        
        # Need to fix errors
        result['error_count'] = 1
        previous_fixes = []
        
        for attempt in range(1, max_fix_attempts + 1):
            if self.verbose:
                self.logger.info(f"Attempting fix {attempt}/{max_fix_attempts}")
            
            # Try to fix the error
            fix_success, fix_msg = self.fix_render_error(
                scene_path, error_msg, scene_name, attempt, previous_fixes
            )
            
            if fix_success:
                # Test if the fix worked
                render_success, new_error = self._test_render(scene_path, scene_name)
                
                if render_success:
                    result['success'] = True
                    result['fixes_applied'].append(fix_msg)
                    
                    # Generate a summary of what was learned
                    if self.verbose:
                        suggestions = self.optimizer.get_optimization_suggestions('fixing')
                        if suggestions:
                            self.logger.info("Optimization insights from this fix:")
                            for suggestion in suggestions:
                                self.logger.info(f"  - {suggestion}")
                    
                    return result
                else:
                    # Fix didn't completely solve the problem
                    if new_error != error_msg:
                        # Different error now, progress was made
                        result['error_count'] += 1
                        error_msg = new_error
                        previous_fixes.append(fix_msg)
                    else:
                        # Same error, fix didn't help
                        previous_fixes.append(f"Failed: {fix_msg}")
            else:
                # Fix attempt failed
                previous_fixes.append(f"Failed: {fix_msg}")
        
        # All attempts exhausted
        result['final_error'] = error_msg
        return result
    
    def _test_render(self, scene_path: Path, scene_name: str) -> Tuple[bool, Optional[str]]:
        """Test if a scene can be rendered successfully."""
        try:
            # Try a quick render test
            result = subprocess.run(
                ["manim", "-ql", "-s", str(scene_path), scene_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return True, None
            else:
                # Extract error message
                error_lines = result.stderr.strip().split('\n')
                # Look for the actual error message
                for i, line in enumerate(error_lines):
                    if 'Error' in line or 'error' in line:
                        # Get this line and a few context lines
                        error_context = '\n'.join(error_lines[max(0, i-2):i+3])
                        return False, error_context
                
                # No clear error found, return last few lines
                return False, '\n'.join(error_lines[-5:])
                
        except subprocess.TimeoutExpired:
            return False, "Render test timed out"
        except Exception as e:
            return False, str(e)
    
    def generate_fix_report(self) -> str:
        """Generate a report of error fixing patterns and success rates."""
        report_lines = [
            "# Error Fixing Optimization Report",
            "",
            self.optimizer.generate_optimization_report(),
            "",
            "## Detailed Performance Metrics",
            "",
            self.feedback_system.generate_report()
        ]
        
        return '\n'.join(report_lines)


# Provide a compatibility wrapper for existing code
class ClaudeAPIHelper(EnhancedClaudeAPIHelper):
    """Compatibility wrapper that maintains the original interface."""
    
    def fix_render_error_with_claude(self, *args, **kwargs):
        """Compatibility method name."""
        return self.fix_render_error(*args, **kwargs)


if __name__ == "__main__":
    # Test the enhanced API helper
    helper = EnhancedClaudeAPIHelper(verbose=True)
    
    print("Enhanced Claude API Helper initialized")
    print("Features:")
    print("  - Adaptive prompt optimization")
    print("  - Learning from successful fixes")
    print("  - Progressive model selection")
    print("  - Performance tracking and reporting")
    
    # Generate a sample report
    print("\nSample optimization report:")
    print(helper.generate_fix_report())