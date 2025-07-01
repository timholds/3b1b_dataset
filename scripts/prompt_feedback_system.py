"""
Prompt feedback and optimization system for the 3Blue1Brown pipeline.
Tracks prompt performance and suggests improvements.
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class PromptResult:
    """Track the result of a Claude prompt execution."""
    prompt_type: str  # 'matching', 'cleaning', 'fixing', etc.
    success: bool
    confidence: float
    attempt_number: int
    error_type: Optional[str] = None
    fix_applied: Optional[str] = None
    execution_time: float = 0.0
    token_count: Optional[int] = None
    cost_estimate: float = 0.0
    
    
@dataclass
class PromptMetrics:
    """Aggregate metrics for a prompt type."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_attempts: int = 0
    avg_confidence: float = 0.0
    avg_execution_time: float = 0.0
    common_errors: Dict[str, int] = None
    successful_patterns: Dict[str, int] = None
    
    def __post_init__(self):
        if self.common_errors is None:
            self.common_errors = {}
        if self.successful_patterns is None:
            self.successful_patterns = {}
            

class PromptFeedbackSystem:
    """Track and optimize Claude prompts based on performance."""
    
    def __init__(self, feedback_dir: str = "prompt_feedback"):
        self.feedback_dir = Path(feedback_dir)
        self.feedback_dir.mkdir(exist_ok=True)
        
        self.current_session = {
            'start_time': datetime.now().isoformat(),
            'results': []
        }
        
        # Load historical data
        self.history_file = self.feedback_dir / "prompt_history.jsonl"
        self.metrics_file = self.feedback_dir / "prompt_metrics.json"
        self.metrics = self._load_metrics()
        
    def _load_metrics(self) -> Dict[str, PromptMetrics]:
        """Load aggregated metrics from file."""
        if self.metrics_file.exists():
            with open(self.metrics_file) as f:
                data = json.load(f)
                return {
                    k: PromptMetrics(**v) for k, v in data.items()
                }
        return defaultdict(PromptMetrics)
        
    def _save_metrics(self):
        """Save aggregated metrics to file."""
        data = {
            k: asdict(v) for k, v in self.metrics.items()
        }
        with open(self.metrics_file, 'w') as f:
            json.dump(data, f, indent=2)
            
    def record_result(self, result: PromptResult):
        """Record a prompt execution result."""
        # Add to current session
        self.current_session['results'].append(asdict(result))
        
        # Update metrics
        metrics = self.metrics[result.prompt_type]
        metrics.total_calls += 1
        
        if result.success:
            metrics.successful_calls += 1
            if result.fix_applied:
                metrics.successful_patterns[result.fix_applied] = \
                    metrics.successful_patterns.get(result.fix_applied, 0) + 1
        else:
            metrics.failed_calls += 1
            if result.error_type:
                metrics.common_errors[result.error_type] = \
                    metrics.common_errors.get(result.error_type, 0) + 1
                    
        metrics.total_attempts += result.attempt_number
        
        # Update averages
        n = metrics.total_calls
        metrics.avg_confidence = (
            (metrics.avg_confidence * (n - 1) + result.confidence) / n
        )
        metrics.avg_execution_time = (
            (metrics.avg_execution_time * (n - 1) + result.execution_time) / n
        )
        
        # Append to history
        with open(self.history_file, 'a') as f:
            f.write(json.dumps(asdict(result)) + '\n')
            
        # Save metrics periodically
        if metrics.total_calls % 10 == 0:
            self._save_metrics()
            
    def get_optimization_suggestions(self, prompt_type: str) -> List[str]:
        """Get suggestions for improving a prompt based on historical data."""
        metrics = self.metrics.get(prompt_type)
        if not metrics or metrics.total_calls < 10:
            return ["Not enough data for optimization suggestions"]
            
        suggestions = []
        
        # Success rate analysis
        success_rate = metrics.successful_calls / metrics.total_calls
        if success_rate < 0.7:
            suggestions.append(
                f"Low success rate ({success_rate:.1%}). Consider adding more "
                f"examples or clarifying instructions."
            )
            
        # Common errors analysis
        if metrics.common_errors:
            top_errors = sorted(
                metrics.common_errors.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:3]
            suggestions.append(
                f"Top errors: {', '.join(f'{e[0]} ({e[1]}x)' for e in top_errors)}. "
                f"Add specific handling for these cases."
            )
            
        # Attempt analysis
        avg_attempts = metrics.total_attempts / metrics.total_calls
        if avg_attempts > 1.5:
            suggestions.append(
                f"High retry rate (avg {avg_attempts:.1f} attempts). "
                f"Improve first-attempt success with clearer instructions."
            )
            
        # Successful patterns
        if metrics.successful_patterns:
            top_patterns = sorted(
                metrics.successful_patterns.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]
            suggestions.append(
                f"Successful patterns: {', '.join(f'{p[0]} ({p[1]}x)' for p in top_patterns)}. "
                f"Emphasize these in the prompt."
            )
            
        # Performance analysis
        if metrics.avg_execution_time > 30:
            suggestions.append(
                f"Slow execution (avg {metrics.avg_execution_time:.1f}s). "
                f"Consider simplifying the task or breaking it into steps."
            )
            
        return suggestions
        
    def generate_report(self) -> str:
        """Generate a comprehensive report of prompt performance."""
        report = ["# Prompt Performance Report", ""]
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        for prompt_type, metrics in sorted(self.metrics.items()):
            if metrics.total_calls == 0:
                continue
                
            report.append(f"## {prompt_type.title()} Prompts")
            report.append(f"- Total calls: {metrics.total_calls}")
            report.append(f"- Success rate: {metrics.successful_calls / metrics.total_calls:.1%}")
            report.append(f"- Average attempts: {metrics.total_attempts / metrics.total_calls:.1f}")
            report.append(f"- Average confidence: {metrics.avg_confidence:.2f}")
            report.append(f"- Average time: {metrics.avg_execution_time:.1f}s")
            
            if metrics.common_errors:
                report.append("\n### Common Errors:")
                for error, count in sorted(
                    metrics.common_errors.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )[:5]:
                    report.append(f"  - {error}: {count} occurrences")
                    
            if metrics.successful_patterns:
                report.append("\n### Successful Patterns:")
                for pattern, count in sorted(
                    metrics.successful_patterns.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5]:
                    report.append(f"  - {pattern}: {count} uses")
                    
            suggestions = self.get_optimization_suggestions(prompt_type)
            if suggestions:
                report.append("\n### Optimization Suggestions:")
                for suggestion in suggestions:
                    report.append(f"  - {suggestion}")
                    
            report.append("")
            
        return '\n'.join(report)
        
    def compare_prompt_versions(
        self, 
        prompt_type: str,
        version_a_results: List[PromptResult],
        version_b_results: List[PromptResult]
    ) -> Dict[str, any]:
        """Compare two versions of a prompt to see which performs better."""
        def calculate_stats(results: List[PromptResult]) -> Dict:
            if not results:
                return {'success_rate': 0, 'avg_attempts': 0, 'avg_time': 0}
                
            success_count = sum(1 for r in results if r.success)
            total_attempts = sum(r.attempt_number for r in results)
            total_time = sum(r.execution_time for r in results)
            
            return {
                'success_rate': success_count / len(results),
                'avg_attempts': total_attempts / len(results),
                'avg_time': total_time / len(results),
                'sample_size': len(results)
            }
            
        stats_a = calculate_stats(version_a_results)
        stats_b = calculate_stats(version_b_results)
        
        comparison = {
            'version_a': stats_a,
            'version_b': stats_b,
            'recommendation': None,
            'confidence': 0.0
        }
        
        # Determine recommendation
        if stats_a['sample_size'] < 5 or stats_b['sample_size'] < 5:
            comparison['recommendation'] = 'insufficient_data'
        else:
            score_a = (
                stats_a['success_rate'] * 0.5 +
                (1 - stats_a['avg_attempts'] / 3) * 0.3 +
                (1 - min(stats_a['avg_time'] / 60, 1)) * 0.2
            )
            score_b = (
                stats_b['success_rate'] * 0.5 +
                (1 - stats_b['avg_attempts'] / 3) * 0.3 +
                (1 - min(stats_b['avg_time'] / 60, 1)) * 0.2
            )
            
            if abs(score_a - score_b) < 0.05:
                comparison['recommendation'] = 'no_significant_difference'
            elif score_a > score_b:
                comparison['recommendation'] = 'use_version_a'
                comparison['confidence'] = abs(score_a - score_b)
            else:
                comparison['recommendation'] = 'use_version_b'
                comparison['confidence'] = abs(score_a - score_b)
                
        return comparison


# Integration with existing pipeline
def create_feedback_wrapper(feedback_system: PromptFeedbackSystem):
    """Create a wrapper to track Claude API calls."""
    
    def track_claude_call(
        prompt_type: str,
        prompt: str,
        success_callback=None,
        error_callback=None
    ):
        """Wrapper function that tracks prompt execution."""
        start_time = time.time()
        result = PromptResult(
            prompt_type=prompt_type,
            success=False,
            confidence=0.0,
            attempt_number=1
        )
        
        try:
            # Execute the actual Claude call
            response = yield prompt
            
            # Determine success and extract metrics
            if success_callback:
                success, confidence = success_callback(response)
            else:
                success, confidence = True, 1.0
                
            result.success = success
            result.confidence = confidence
            
        except Exception as e:
            result.error_type = type(e).__name__
            if error_callback:
                error_callback(e)
                
        finally:
            result.execution_time = time.time() - start_time
            feedback_system.record_result(result)
            
        return response
        
    return track_claude_call


if __name__ == "__main__":
    # Example usage
    feedback = PromptFeedbackSystem()
    
    # Simulate some results
    feedback.record_result(PromptResult(
        prompt_type="matching",
        success=True,
        confidence=0.95,
        attempt_number=1,
        execution_time=5.2
    ))
    
    feedback.record_result(PromptResult(
        prompt_type="cleaning",
        success=False,
        confidence=0.3,
        attempt_number=2,
        error_type="syntax_error",
        execution_time=8.7
    ))
    
    # Generate report
    print(feedback.generate_report())
    
    # Get suggestions
    print("\nOptimization suggestions for 'cleaning' prompts:")
    for suggestion in feedback.get_optimization_suggestions("cleaning"):
        print(f"  - {suggestion}")