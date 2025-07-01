#!/usr/bin/env python3
"""
Logging utilities for cleaner, more organized output in the 3Blue1Brown dataset pipeline.
Provides progress bars, aggregated statistics, and conditional verbosity.
"""

import sys
import time
from typing import Optional, Dict, List, Any
from collections import defaultdict
from datetime import datetime
import json


class ProgressBar:
    """Simple progress bar for terminal output."""
    
    def __init__(self, total: int, desc: str = "", width: int = 40, show_stats: bool = True):
        self.total = max(1, total)  # Avoid division by zero
        self.current = 0
        self.desc = desc
        self.width = width
        self.show_stats = show_stats
        self.start_time = time.time()
        self.last_update_time = 0
        self.update_interval = 0.1  # Update at most every 100ms
        
    def update(self, n: int = 1, status: str = ""):
        """Update progress by n steps."""
        self.current = min(self.current + n, self.total)
        current_time = time.time()
        
        # Only update display if enough time has passed
        if current_time - self.last_update_time >= self.update_interval or self.current == self.total:
            self._display(status)
            self.last_update_time = current_time
            
    def _display(self, status: str = ""):
        """Display the progress bar."""
        # Calculate progress
        progress = self.current / self.total
        filled = int(self.width * progress)
        bar = "█" * filled + "░" * (self.width - filled)
        
        # Calculate stats
        elapsed = time.time() - self.start_time
        rate = self.current / elapsed if elapsed > 0 else 0
        eta = (self.total - self.current) / rate if rate > 0 else 0
        
        # Build display string
        display = f"\r{self.desc}: [{bar}] {self.current}/{self.total}"
        
        if self.show_stats and elapsed > 1:
            display += f" ({progress*100:.1f}%, {rate:.1f} items/s, ETA: {eta:.0f}s)"
            
        if status:
            display += f" - {status}"
            
        # Clear line and print
        sys.stdout.write("\033[K")  # Clear to end of line
        sys.stdout.write(display)
        sys.stdout.flush()
        
        # Add newline when complete
        if self.current == self.total:
            print()


class StatsAggregator:
    """Aggregates statistics across multiple operations."""
    
    def __init__(self):
        self.stats = defaultdict(lambda: defaultdict(int))
        self.timings = defaultdict(list)
        self.errors = defaultdict(list)
        
    def add_stat(self, category: str, key: str, value: int = 1):
        """Add to a statistical counter."""
        self.stats[category][key] += value
        
    def add_timing(self, operation: str, duration: float):
        """Record a timing measurement."""
        self.timings[operation].append(duration)
        
    def add_error(self, category: str, error: str, context: Optional[str] = None):
        """Record an error occurrence."""
        self.errors[category].append({
            'error': error,
            'context': context,
            'timestamp': datetime.now().isoformat()
        })
        
    def get_summary(self) -> Dict[str, Any]:
        """Get aggregated summary statistics."""
        summary = {
            'stats': dict(self.stats),
            'timings': {},
            'errors': {}
        }
        
        # Calculate timing statistics
        for op, times in self.timings.items():
            if times:
                summary['timings'][op] = {
                    'count': len(times),
                    'total': sum(times),
                    'average': sum(times) / len(times),
                    'min': min(times),
                    'max': max(times)
                }
                
        # Summarize errors
        for category, errors in self.errors.items():
            summary['errors'][category] = {
                'count': len(errors),
                'unique': len(set(e['error'] for e in errors)),
                'samples': errors[:5]  # First 5 as samples
            }
            
        return summary


class ConditionalLogger:
    """Logger that respects verbosity settings."""
    
    def __init__(self, verbose: bool = False, prefix: str = ""):
        self.verbose = verbose
        self.prefix = prefix
        self.suppressed_count = 0
        
    def info(self, message: str, always: bool = False):
        """Log info message (only if verbose or always=True)."""
        if self.verbose or always:
            print(f"{self.prefix}{message}")
        else:
            self.suppressed_count += 1
            
    def warning(self, message: str):
        """Log warning (always shown)."""
        print(f"{self.prefix}⚠️  {message}")
        
    def error(self, message: str):
        """Log error (always shown)."""
        print(f"{self.prefix}❌ {message}")
        
    def success(self, message: str):
        """Log success (always shown)."""
        print(f"{self.prefix}✅ {message}")
        
    def debug(self, message: str):
        """Log debug message (only if verbose)."""
        if self.verbose:
            print(f"{self.prefix}🔍 {message}")
            
    def get_suppressed_count(self) -> int:
        """Get count of suppressed messages."""
        return self.suppressed_count


class SummaryTable:
    """Format data as a clean summary table."""
    
    @staticmethod
    def format_stats(stats: Dict[str, Any], title: str = "Summary") -> str:
        """Format statistics as a clean table."""
        lines = [f"\n{title}", "=" * len(title)]
        
        for category, values in stats.items():
            if isinstance(values, dict):
                lines.append(f"\n{category}:")
                for key, value in values.items():
                    if isinstance(value, float):
                        lines.append(f"  • {key}: {value:.2f}")
                    else:
                        lines.append(f"  • {key}: {value}")
            else:
                lines.append(f"{category}: {values}")
                
        return "\n".join(lines)
    
    @staticmethod
    def format_results(results: List[Dict[str, Any]], columns: List[str], max_rows: int = 10) -> str:
        """Format results as a table with specified columns."""
        if not results:
            return "No results to display"
            
        # Calculate column widths
        widths = {}
        for col in columns:
            widths[col] = max(len(col), max(len(str(r.get(col, ""))) for r in results))
            
        # Build header
        header = " | ".join(col.ljust(widths[col]) for col in columns)
        separator = "-+-".join("-" * widths[col] for col in columns)
        
        lines = [header, separator]
        
        # Add rows
        for i, result in enumerate(results[:max_rows]):
            row = " | ".join(str(result.get(col, "")).ljust(widths[col]) for col in columns)
            lines.append(row)
            
        if len(results) > max_rows:
            lines.append(f"... and {len(results) - max_rows} more")
            
        return "\n".join(lines)


class BatchProgressTracker:
    """Track progress across multiple operations with minimal output."""
    
    def __init__(self, total_operations: int, operation_name: str = "operations"):
        self.total = total_operations
        self.completed = 0
        self.failed = 0
        self.operation_name = operation_name
        self.start_time = time.time()
        self.current_operation = ""
        
    def start_operation(self, name: str):
        """Mark the start of a new operation."""
        self.current_operation = name
        self._update_display()
        
    def complete_operation(self, success: bool = True):
        """Mark the completion of the current operation."""
        if success:
            self.completed += 1
        else:
            self.failed += 1
        self._update_display()
        
    def _update_display(self):
        """Update the progress display."""
        total_processed = self.completed + self.failed
        progress = total_processed / self.total if self.total > 0 else 0
        
        # Build status line
        status_parts = [f"{total_processed}/{self.total} {self.operation_name}"]
        
        if self.completed > 0:
            status_parts.append(f"✅ {self.completed}")
        if self.failed > 0:
            status_parts.append(f"❌ {self.failed}")
            
        if total_processed > 0:
            success_rate = (self.completed / total_processed) * 100
            status_parts.append(f"({success_rate:.1f}% success)")
            
        # Add current operation
        if self.current_operation and total_processed < self.total:
            status_parts.append(f"Current: {self.current_operation[:30]}...")
            
        status = " | ".join(status_parts)
        
        # Clear line and print
        sys.stdout.write("\r\033[K" + status)
        sys.stdout.flush()
        
    def finish(self):
        """Finish tracking and print final summary."""
        print()  # New line after progress
        
        elapsed = time.time() - self.start_time
        if self.completed + self.failed > 0:
            avg_time = elapsed / (self.completed + self.failed)
            print(f"Completed in {elapsed:.1f}s (avg {avg_time:.1f}s per {self.operation_name[:-1]})")


def format_error_summary(errors: List[Dict[str, Any]], max_display: int = 5) -> str:
    """Format error summary in a concise way."""
    if not errors:
        return "No errors"
        
    # Group errors by type
    error_types = defaultdict(list)
    for error in errors:
        error_type = error.get('type', 'Unknown')
        error_types[error_type].append(error)
        
    lines = [f"Total errors: {len(errors)}"]
    
    for error_type, instances in sorted(error_types.items(), key=lambda x: -len(x[1])):
        lines.append(f"\n{error_type} ({len(instances)} occurrences):")
        for i, instance in enumerate(instances[:max_display]):
            msg = instance.get('message', '')[:80]
            if len(instance.get('message', '')) > 80:
                msg += "..."
            lines.append(f"  • {msg}")
        if len(instances) > max_display:
            lines.append(f"  ... and {len(instances) - max_display} more")
            
    return "\n".join(lines)


def print_stage_header(stage_name: str, stage_number: int, total_stages: int):
    """Print a clean stage header."""
    print(f"\n{'=' * 60}")
    print(f"🎯 STAGE {stage_number}/{total_stages}: {stage_name.upper()}")
    print(f"{'=' * 60}")


def print_stage_summary(stats: Dict[str, Any], duration: float):
    """Print a clean stage summary."""
    print(f"\n{'─' * 40}")
    print(f"✅ Stage completed in {duration:.1f}s")
    
    # Print key stats
    for key, value in stats.items():
        if isinstance(value, (int, float)):
            print(f"  • {key}: {value}")
    print(f"{'─' * 40}")