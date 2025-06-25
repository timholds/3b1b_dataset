#!/usr/bin/env python3
"""
Unified Claude Subprocess Manager - Centralized Claude CLI interaction

This module provides a consistent interface for all Claude subprocess calls,
replacing the scattered implementations across the codebase.
"""

import subprocess
import logging
import json
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import threading
import queue

logger = logging.getLogger(__name__)


@dataclass
class ClaudeCall:
    """Represents a single Claude subprocess call with all metadata."""
    purpose: str
    prompt: str
    file_to_edit: Optional[Path] = None
    timeout: int = 300
    attempt: int = 1
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    success: bool = False
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None
    result: Any = None
    

class ClaudeSubprocessManager:
    """
    Unified manager for all Claude CLI subprocess interactions.
    
    Features:
    - Consistent error handling and timeout management
    - Automatic retry with exponential backoff
    - Comprehensive logging and telemetry
    - Real-time output streaming (verbose mode)
    - Circuit breaker pattern to prevent cascade failures
    """
    
    def __init__(self, model: str = "opus", default_timeout: int = 300, 
                 verbose: bool = False, max_retries: int = 3,
                 enable_telemetry: bool = True):
        self.model = model
        self.default_timeout = default_timeout
        self.verbose = verbose
        self.max_retries = max_retries
        self.enable_telemetry = enable_telemetry
        
        # Call history for telemetry and pattern analysis
        self.call_history: List[ClaudeCall] = []
        
        # Circuit breaker state
        self.consecutive_failures = 0
        self.circuit_open = False
        self.circuit_open_until = None
        
        # Success patterns for learning
        self.success_patterns: Dict[str, List[str]] = {}
        
    def run_claude(self, prompt: str, purpose: str, 
                   timeout: Optional[int] = None,
                   file_to_edit: Optional[Path] = None,
                   retry_on_timeout: bool = True) -> Dict[str, Any]:
        """
        Run Claude with unified error handling and retry logic.
        
        Args:
            prompt: The prompt to send to Claude
            purpose: Description of what this call is for (e.g., "clean_code", "fix_render_error")
            timeout: Override default timeout in seconds
            file_to_edit: Optional file path that Claude should edit
            retry_on_timeout: Whether to retry on timeout with exponential backoff
            
        Returns:
            Dict with keys: success, result, error, stdout, stderr, duration, attempts
        """
        # Check circuit breaker
        if self._is_circuit_open():
            return {
                'success': False,
                'error': 'Circuit breaker open - too many consecutive failures',
                'result': None,
                'attempts': 0
            }
        
        timeout = timeout or self.default_timeout
        attempts = 0
        last_error = None
        
        while attempts < self.max_retries:
            attempts += 1
            
            # Exponential backoff for timeout
            attempt_timeout = timeout * (2 ** (attempts - 1)) if retry_on_timeout else timeout
            
            call = ClaudeCall(
                purpose=purpose,
                prompt=prompt,
                file_to_edit=file_to_edit,
                timeout=attempt_timeout,
                attempt=attempts
            )
            
            # Save prompt to temp file for debugging
            prompt_file = self._save_prompt(prompt, purpose, attempts)
            
            try:
                # Run Claude
                call.start_time = datetime.now()
                result = self._execute_claude(prompt, attempt_timeout, call)
                call.end_time = datetime.now()
                call.duration = (call.end_time - call.start_time).total_seconds()
                
                # Process result
                if result['success']:
                    call.success = True
                    call.result = result.get('output')
                    
                    # Handle file editing if needed
                    if file_to_edit and file_to_edit.exists():
                        with open(file_to_edit, 'r') as f:
                            call.result = f.read()
                    
                    # Record success
                    self._record_success(call)
                    
                    return {
                        'success': True,
                        'result': call.result,
                        'stdout': call.stdout,
                        'stderr': call.stderr,
                        'duration': call.duration,
                        'attempts': attempts,
                        'prompt_file': str(prompt_file)
                    }
                else:
                    call.error = result.get('error', 'Unknown error')
                    last_error = call.error
                    
                    # Log the error
                    logger.warning(f"Claude call failed (attempt {attempts}/{self.max_retries}): {call.error}")
                    
                    # Don't retry if not a timeout
                    if not retry_on_timeout or "timeout" not in call.error.lower():
                        break
                        
            except Exception as e:
                call.error = str(e)
                last_error = str(e)
                logger.error(f"Exception in Claude call: {e}")
                
            finally:
                # Record call for telemetry
                if self.enable_telemetry:
                    self.call_history.append(call)
                
            # Exponential backoff delay before retry
            if attempts < self.max_retries:
                delay = 2 ** attempts
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
        
        # All attempts failed
        self._record_failure()
        
        return {
            'success': False,
            'error': last_error or 'All retry attempts failed',
            'result': None,
            'attempts': attempts,
            'stdout': call.stdout if 'call' in locals() else '',
            'stderr': call.stderr if 'call' in locals() else '',
            'prompt_file': str(prompt_file) if 'prompt_file' in locals() else None
        }
    
    def _execute_claude(self, prompt: str, timeout: int, call: ClaudeCall) -> Dict[str, Any]:
        """Execute the actual Claude subprocess."""
        cmd = ["claude", "--dangerously-skip-permissions", "--model", self.model]
        
        if self.verbose:
            # Use Popen for real-time output
            return self._execute_verbose(cmd, prompt, timeout, call)
        else:
            # Use run for batch execution
            return self._execute_silent(cmd, prompt, timeout, call)
    
    def _execute_verbose(self, cmd: List[str], prompt: str, timeout: int, 
                        call: ClaudeCall) -> Dict[str, Any]:
        """Execute Claude with real-time output streaming."""
        try:
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
            
            # Set up timeout
            timeout_timer = threading.Timer(timeout, process.kill)
            timeout_timer.start()
            
            # Collect output while streaming
            stdout_lines = []
            
            try:
                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    if line:
                        print(f"    Claude: {line.rstrip()}")
                        stdout_lines.append(line)
                        call.stdout += line
                
                # Get any remaining stderr
                call.stderr = process.stderr.read()
                call.exit_code = process.returncode
                
            finally:
                timeout_timer.cancel()
            
            # Check for timeout
            if process.returncode == -9:  # SIGKILL
                return {
                    'success': False,
                    'error': f'Claude process timed out after {timeout} seconds'
                }
            
            # Check exit code
            if process.returncode == 0:
                return {
                    'success': True,
                    'output': ''.join(stdout_lines)
                }
            else:
                return {
                    'success': False,
                    'error': f'Claude exited with code {process.returncode}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Exception during execution: {str(e)}'
            }
    
    def _execute_silent(self, cmd: List[str], prompt: str, timeout: int,
                       call: ClaudeCall) -> Dict[str, Any]:
        """Execute Claude in silent mode with batch output capture."""
        try:
            result = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            call.stdout = result.stdout
            call.stderr = result.stderr
            call.exit_code = result.returncode
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'output': result.stdout
                }
            else:
                return {
                    'success': False,
                    'error': f'Claude exited with code {result.returncode}: {result.stderr}'
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': f'Claude process timed out after {timeout} seconds'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Exception during execution: {str(e)}'
            }
    
    def _save_prompt(self, prompt: str, purpose: str, attempt: int) -> Path:
        """Save prompt to file for debugging."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"claude_prompt_{purpose}_{timestamp}_attempt{attempt}.txt"
        prompt_file = Path(tempfile.gettempdir()) / filename
        
        with open(prompt_file, 'w') as f:
            f.write(prompt)
        
        return prompt_file
    
    def _is_circuit_open(self) -> bool:
        """Check if circuit breaker is open."""
        if not self.circuit_open:
            return False
            
        if datetime.now() > self.circuit_open_until:
            # Reset circuit
            self.circuit_open = False
            self.consecutive_failures = 0
            logger.info("Circuit breaker reset")
            return False
            
        return True
    
    def _record_success(self, call: ClaudeCall):
        """Record successful call for pattern analysis."""
        self.consecutive_failures = 0
        
        # Learn from success
        if call.purpose not in self.success_patterns:
            self.success_patterns[call.purpose] = []
        
        # Extract key patterns from successful prompt
        patterns = self._extract_patterns(call.prompt)
        self.success_patterns[call.purpose].extend(patterns)
    
    def _record_failure(self):
        """Record failure and potentially open circuit breaker."""
        self.consecutive_failures += 1
        
        if self.consecutive_failures >= 5:
            # Open circuit breaker for 5 minutes
            self.circuit_open = True
            self.circuit_open_until = datetime.now().timestamp() + 300
            logger.error("Circuit breaker opened due to consecutive failures")
    
    def _extract_patterns(self, prompt: str) -> List[str]:
        """Extract reusable patterns from successful prompts."""
        patterns = []
        
        # Look for instruction patterns
        lines = prompt.split('\n')
        for line in lines:
            if any(keyword in line.lower() for keyword in ['fix', 'ensure', 'check', 'verify']):
                patterns.append(line.strip())
        
        return patterns[:5]  # Keep top 5 patterns
    
    def get_telemetry_report(self) -> Dict[str, Any]:
        """Generate telemetry report for analysis."""
        if not self.call_history:
            return {'message': 'No calls recorded'}
        
        total_calls = len(self.call_history)
        successful_calls = sum(1 for call in self.call_history if call.success)
        
        # Group by purpose
        by_purpose = {}
        for call in self.call_history:
            if call.purpose not in by_purpose:
                by_purpose[call.purpose] = {
                    'total': 0,
                    'successful': 0,
                    'avg_duration': 0,
                    'timeouts': 0
                }
            
            by_purpose[call.purpose]['total'] += 1
            if call.success:
                by_purpose[call.purpose]['successful'] += 1
            if call.error and 'timeout' in call.error.lower():
                by_purpose[call.purpose]['timeouts'] += 1
            if call.duration:
                # Running average
                current_avg = by_purpose[call.purpose]['avg_duration']
                current_total = by_purpose[call.purpose]['total'] - 1
                by_purpose[call.purpose]['avg_duration'] = (
                    (current_avg * current_total + call.duration) / 
                    by_purpose[call.purpose]['total']
                )
        
        return {
            'total_calls': total_calls,
            'successful_calls': successful_calls,
            'success_rate': successful_calls / total_calls if total_calls > 0 else 0,
            'by_purpose': by_purpose,
            'consecutive_failures': self.consecutive_failures,
            'circuit_breaker_open': self.circuit_open
        }


# Convenience functions for migration
def clean_code_with_claude(code: str, file_path: str, manager: ClaudeSubprocessManager) -> Dict[str, Any]:
    """Clean code using Claude - compatible with existing clean_matched_code.py interface."""
    prompt = f"""Clean and inline this code from {file_path}.
    
Important requirements:
1. Inline all imports from local files
2. Remove Pi creature references
3. Fix syntax errors
4. Ensure ManimGL compatibility

Code:
```python
{code}
```
"""
    
    return manager.run_claude(
        prompt=prompt,
        purpose='clean_code',
        timeout=600  # 10 minutes for cleaning
    )


def fix_render_error_with_claude(scene_name: str, snippet: str, error: str, 
                                attempt: int, manager: ClaudeSubprocessManager) -> Dict[str, Any]:
    """Fix render error - compatible with existing interfaces."""
    prompt = f"""Fix this ManimCE scene that is failing to render.

Scene: {scene_name}
Attempt: {attempt}
Error: {error}

Code:
```python
{snippet}
```

Instructions:
- Fix ONLY the error causing the render failure
- Do not refactor or change code style
- Preserve all functionality
- Return the complete fixed code
"""
    
    return manager.run_claude(
        prompt=prompt,
        purpose='fix_render_error',
        timeout=120,  # 2 minutes for fixes
        retry_on_timeout=False  # Don't retry fixes
    )