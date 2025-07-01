#!/usr/bin/env python3
"""
Enhanced Logging System for 3Blue1Brown Pipeline

Provides comprehensive error tracking, performance monitoring, and structured logging
for all pipeline stages with consistent log structure and detailed analytics.
"""

import json
import time
import psutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import traceback
import threading
from contextlib import contextmanager

class EnhancedJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles enums and other non-serializable types."""
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)

class ErrorCategory(Enum):
    """Structured error categorization."""
    SYNTAX_ERROR = "syntax_error"
    IMPORT_ERROR = "import_error" 
    RUNTIME_ERROR = "runtime_error"
    VALIDATION_ERROR = "validation_error"
    DEPENDENCY_ERROR = "dependency_error"
    TIMEOUT_ERROR = "timeout_error"
    RESOURCE_ERROR = "resource_error"
    CLAUDE_API_ERROR = "claude_api_error"
    UNKNOWN_ERROR = "unknown_error"

class StageType(Enum):
    """Pipeline stage types."""
    MATCHING = "matching"
    CLEANING = "cleaning"
    CONVERSION = "conversion"
    RENDERING = "rendering"
    VALIDATION = "validation"

@dataclass
class RetryAttempt:
    """Single retry attempt details."""
    attempt_number: int
    method: str
    status: str  # success, failed, timeout
    duration_seconds: float
    error_category: Optional[str] = None
    error_message: Optional[str] = None
    memory_peak_mb: Optional[float] = None
    cpu_percent: Optional[float] = None
    timestamp: str = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

@dataclass
class PerformanceMetrics:
    """Detailed performance tracking."""
    start_time: float
    end_time: Optional[float] = None
    duration_seconds: Optional[float] = None
    memory_start_mb: Optional[float] = None
    memory_peak_mb: Optional[float] = None
    memory_end_mb: Optional[float] = None
    cpu_percent_avg: Optional[float] = None
    cpu_percent_peak: Optional[float] = None
    disk_io_read_mb: Optional[float] = None
    disk_io_write_mb: Optional[float] = None
    temp_files_created: int = 0
    temp_files_cleaned: int = 0
    
    def finish(self):
        """Mark performance tracking as finished."""
        self.end_time = time.time()
        self.duration_seconds = self.end_time - self.start_time
        if self.memory_start_mb and not self.memory_end_mb:
            self.memory_end_mb = self._get_memory_usage()
    
    @staticmethod
    def _get_memory_usage() -> float:
        """Get current memory usage in MB."""
        try:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except:
            return 0.0

@dataclass
class ClaudeAPIMetrics:
    """Claude API usage tracking."""
    call_id: str
    timestamp: str
    model_used: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    response_time_seconds: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None
    rate_limited: bool = False
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

@dataclass
class ErrorDetails:
    """Comprehensive error information."""
    category: ErrorCategory
    message: str
    stack_trace: Optional[str] = None
    fixable: Optional[bool] = None
    auto_recoverable: Optional[bool] = None
    suggested_fix: Optional[str] = None
    occurrence_count: int = 1
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    
    def __post_init__(self):
        timestamp = datetime.now().isoformat()
        if not self.first_seen:
            self.first_seen = timestamp
        self.last_seen = timestamp

class EnhancedVideoLogger:
    """Enhanced logging for individual videos with structured data."""
    
    def __init__(self, video_dir: Path, video_id: str):
        self.video_dir = video_dir
        self.video_id = video_id
        self.log_dir = video_dir / '.pipeline' / 'logs'
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / 'logs.json'
        
        # Performance monitoring
        self.performance_monitor = PerformanceMonitor()
        
        # Initialize log structure
        self._ensure_log_structure()
    
    def _ensure_log_structure(self):
        """Ensure consistent log file structure exists."""
        if not self.log_file.exists():
            initial_structure = {
                'video_id': self.video_id,
                'created_at': datetime.now().isoformat(),
                'stages': {},
                'errors': {},
                'performance': {},
                'claude_api_usage': [],
                'retry_attempts': {},
                'validation_history': []
            }
            with open(self.log_file, 'w') as f:
                json.dump(initial_structure, f, indent=2, cls=EnhancedJSONEncoder)
    
    def log_stage_start(self, stage: StageType, method: str = None, config: Dict = None):
        """Log the start of a pipeline stage."""
        stage_data = {
            'status': 'running',
            'method': method,
            'config': config or {},
            'start_time': datetime.now().isoformat(),
            'performance': asdict(PerformanceMetrics(start_time=time.time()))
        }
        
        self._update_log('stages', {stage.value: stage_data})
        return self.performance_monitor.start_monitoring(f"{stage.value}_{method or 'default'}")
    
    def log_stage_complete(self, stage: StageType, success: bool, 
                          result_data: Dict = None, error: ErrorDetails = None,
                          performance_id: str = None):
        """Log stage completion with results."""
        stage_data = {
            'status': 'completed' if success else 'failed',
            'end_time': datetime.now().isoformat(),
            'result_data': result_data or {},
            'success': success
        }
        
        if error:
            stage_data['error'] = asdict(error)
            self._log_error(stage.value, error)
        
        if performance_id:
            perf_metrics = self.performance_monitor.stop_monitoring(performance_id)
            if perf_metrics:
                stage_data['performance'] = asdict(perf_metrics)
        
        self._update_log('stages', {stage.value: stage_data}, merge=True)
    
    def log_retry_attempt(self, stage: StageType, attempt: RetryAttempt):
        """Log a single retry attempt."""
        stage_key = stage.value
        
        # Initialize retry list for stage if not exists
        log_data = self._load_log()
        if stage_key not in log_data.get('retry_attempts', {}):
            log_data['retry_attempts'][stage_key] = []
        
        log_data['retry_attempts'][stage_key].append(asdict(attempt))
        
        with open(self.log_file, 'w') as f:
            json.dump(log_data, f, indent=2, cls=EnhancedJSONEncoder)
    
    def log_claude_api_call(self, metrics: ClaudeAPIMetrics):
        """Log Claude API usage metrics."""
        log_data = self._load_log()
        log_data['claude_api_usage'].append(asdict(metrics))
        
        with open(self.log_file, 'w') as f:
            json.dump(log_data, f, indent=2, cls=EnhancedJSONEncoder)
    
    def log_validation_attempt(self, validation_type: str, success: bool, 
                             errors: List[str] = None, fixes_applied: List[str] = None):
        """Log validation attempts and auto-recovery."""
        validation_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': validation_type,
            'success': success,
            'errors': errors or [],
            'fixes_applied': fixes_applied or [],
            'auto_recovery_attempted': bool(fixes_applied)
        }
        
        log_data = self._load_log()
        log_data['validation_history'].append(validation_entry)
        
        with open(self.log_file, 'w') as f:
            json.dump(log_data, f, indent=2, cls=EnhancedJSONEncoder)
    
    def _log_error(self, context: str, error: ErrorDetails):
        """Log detailed error information."""
        error_key = f"{context}_{error.category.value}"
        
        log_data = self._load_log()
        if error_key in log_data['errors']:
            # Update existing error
            existing = log_data['errors'][error_key]
            existing['occurrence_count'] += 1
            existing['last_seen'] = error.last_seen
        else:
            # New error - convert enum to string value for JSON serialization
            error_dict = asdict(error)
            error_dict['category'] = error.category.value  # Convert enum to string
            log_data['errors'][error_key] = error_dict
        
        with open(self.log_file, 'w') as f:
            json.dump(log_data, f, indent=2, cls=EnhancedJSONEncoder)
    
    def _update_log(self, section: str, data: Dict, merge: bool = False):
        """Update a section of the log file."""
        log_data = self._load_log()
        
        if merge and section in log_data and isinstance(log_data[section], dict):
            log_data[section].update(data)
        else:
            log_data[section] = data
        
        with open(self.log_file, 'w') as f:
            json.dump(log_data, f, indent=2, cls=EnhancedJSONEncoder)
    
    def _load_log(self) -> Dict:
        """Load current log data."""
        if self.log_file.exists():
            try:
                with open(self.log_file, 'r') as f:
                    data = json.load(f)
                    # Ensure all required keys exist
                    required_keys = {
                        'video_id': self.video_id,
                        'stages': {},
                        'errors': {},
                        'performance': {},
                        'claude_api_usage': [],
                        'retry_attempts': {},
                        'validation_history': []
                    }
                    for key, default_value in required_keys.items():
                        if key not in data:
                            data[key] = default_value
                    return data
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                # Log file is corrupted, recreate it
                logging.warning(f"Corrupted log file {self.log_file}, recreating: {e}")
                self.log_file.unlink()  # Delete corrupted file
                self._ensure_log_structure()
                return self._load_log()
        else:
            self._ensure_log_structure()
            return self._load_log()
    
    def get_summary(self) -> Dict:
        """Get comprehensive summary of video processing."""
        log_data = self._load_log()
        
        # Calculate aggregate statistics
        total_errors = sum(error.get('occurrence_count', 1) for error in log_data.get('errors', {}).values())
        total_claude_calls = len(log_data.get('claude_api_usage', []))
        total_cost = sum(call.get('estimated_cost_usd', 0) for call in log_data.get('claude_api_usage', []))
        
        successful_stages = sum(1 for stage in log_data.get('stages', {}).values() 
                               if stage.get('success', False))
        
        return {
            'video_id': self.video_id,
            'total_stages': len(log_data.get('stages', {})),
            'successful_stages': successful_stages,
            'total_errors': total_errors,
            'total_claude_calls': total_claude_calls,
            'estimated_total_cost': total_cost,
            'processing_duration': self._calculate_total_duration(log_data),
            'error_categories': self._categorize_errors(log_data),
            'retry_summary': self._summarize_retries(log_data)
        }
    
    def _calculate_total_duration(self, log_data: Dict) -> float:
        """Calculate total processing time across all stages."""
        total_duration = 0.0
        for stage_data in log_data.get('stages', {}).values():
            if 'performance' in stage_data and stage_data['performance'].get('duration_seconds'):
                total_duration += stage_data['performance']['duration_seconds']
        return total_duration
    
    def _categorize_errors(self, log_data: Dict) -> Dict:
        """Categorize and count errors by type."""
        categories = {}
        for error in log_data.get('errors', {}).values():
            category = error.get('category', 'unknown')
            if category not in categories:
                categories[category] = 0
            categories[category] += error.get('occurrence_count', 1)
        return categories
    
    def _summarize_retries(self, log_data: Dict) -> Dict:
        """Summarize retry attempts across stages."""
        summary = {}
        for stage, attempts in log_data.get('retry_attempts', {}).items():
            summary[stage] = {
                'total_attempts': len(attempts),
                'successful_attempts': sum(1 for a in attempts if a.get('status') == 'success'),
                'avg_duration': sum(a.get('duration_seconds', 0) for a in attempts) / max(len(attempts), 1)
            }
        return summary

class PerformanceMonitor:
    """System performance monitoring for pipeline operations."""
    
    def __init__(self):
        self.active_monitors = {}
        self.lock = threading.Lock()
    
    def start_monitoring(self, operation_id: str) -> str:
        """Start monitoring performance for an operation."""
        with self.lock:
            metrics = PerformanceMetrics(
                start_time=time.time(),
                memory_start_mb=self._get_memory_usage()
            )
            self.active_monitors[operation_id] = {
                'metrics': metrics,
                'cpu_samples': [],
                'memory_samples': []
            }
        return operation_id
    
    def stop_monitoring(self, operation_id: str) -> Optional[PerformanceMetrics]:
        """Stop monitoring and return metrics."""
        with self.lock:
            if operation_id not in self.active_monitors:
                return None
            
            monitor_data = self.active_monitors.pop(operation_id)
            metrics = monitor_data['metrics']
            metrics.finish()
            
            # Calculate averages from samples
            if monitor_data['cpu_samples']:
                metrics.cpu_percent_avg = sum(monitor_data['cpu_samples']) / len(monitor_data['cpu_samples'])
                metrics.cpu_percent_peak = max(monitor_data['cpu_samples'])
            
            if monitor_data['memory_samples']:
                metrics.memory_peak_mb = max(monitor_data['memory_samples'])
            
            return metrics
    
    @staticmethod
    def _get_memory_usage() -> float:
        """Get current memory usage in MB."""
        try:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except:
            return 0.0
    
    @contextmanager
    def monitor_operation(self, operation_name: str):
        """Context manager for automatic performance monitoring."""
        monitor_id = self.start_monitoring(operation_name)
        try:
            yield monitor_id
        finally:
            self.stop_monitoring(monitor_id)

def create_error_from_exception(exc: Exception, context: str = None) -> ErrorDetails:
    """Create structured error details from an exception."""
    # Categorize exception type
    if isinstance(exc, SyntaxError):
        category = ErrorCategory.SYNTAX_ERROR
        fixable = True
        auto_recoverable = False
        suggested_fix = "Check syntax and fix parsing errors"
    elif isinstance(exc, ImportError) or isinstance(exc, ModuleNotFoundError):
        category = ErrorCategory.IMPORT_ERROR
        fixable = True
        auto_recoverable = True
        suggested_fix = "Add missing import or dependency"
    elif isinstance(exc, TimeoutError):
        category = ErrorCategory.TIMEOUT_ERROR
        fixable = True
        auto_recoverable = True
        suggested_fix = "Increase timeout or optimize operation"
    elif isinstance(exc, (MemoryError, OSError)):
        category = ErrorCategory.RESOURCE_ERROR
        fixable = False
        auto_recoverable = False
        suggested_fix = "Reduce resource usage or increase system limits"
    else:
        category = ErrorCategory.RUNTIME_ERROR
        fixable = None
        auto_recoverable = None
        suggested_fix = "Review error details and fix underlying issue"
    
    return ErrorDetails(
        category=category,
        message=str(exc),
        stack_trace=traceback.format_exc() if context else None,
        fixable=fixable,
        auto_recoverable=auto_recoverable,
        suggested_fix=suggested_fix
    )

def create_claude_metrics(call_id: str, model: str, success: bool = True, 
                         response_time: float = None, error: str = None) -> ClaudeAPIMetrics:
    """Create Claude API metrics with cost estimation."""
    # Estimate costs based on model (rough estimates)
    cost_per_1k_tokens = {
        'claude-3-haiku': 0.00025,
        'claude-3-sonnet': 0.003,
        'claude-3-opus': 0.015,
        'claude-3-5-sonnet': 0.003
    }
    
    base_cost = cost_per_1k_tokens.get(model, 0.003)  # Default to Sonnet pricing
    
    return ClaudeAPIMetrics(
        call_id=call_id,
        timestamp=datetime.now().isoformat(),
        model_used=model,
        estimated_cost_usd=base_cost * 2,  # Rough estimate for average call
        response_time_seconds=response_time,
        success=success,
        error_message=error
    )

# Example integration functions
def integrate_with_hybrid_cleaner():
    """Integration example for hybrid cleaner."""
    # This would be added to hybrid_cleaner.py
    pass

def integrate_with_systematic_converter():
    """Integration example for systematic converter.""" 
    # This would be added to systematic_pipeline_converter.py
    pass

if __name__ == '__main__':
    # Example usage
    video_dir = Path('/tmp/test_video')
    video_dir.mkdir(exist_ok=True)
    
    logger = EnhancedVideoLogger(video_dir, 'test_video')
    
    # Example stage logging
    perf_id = logger.log_stage_start(StageType.CLEANING, method='hybrid')
    
    # Simulate some work
    time.sleep(1)
    
    logger.log_stage_complete(
        StageType.CLEANING, 
        success=True, 
        result_data={'scenes_cleaned': 5},
        performance_id=perf_id
    )
    
    # Print summary
    summary = logger.get_summary()
    print(json.dumps(summary, indent=2))