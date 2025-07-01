"""
Adaptive prompt optimization for the 3Blue1Brown pipeline.
Automatically adjusts prompts based on performance without external dependencies.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict
from datetime import datetime, timedelta


class AdaptivePromptOptimizer:
    """
    Automatically optimize prompts based on success/failure patterns.
    No external ML libraries required - uses simple heuristics.
    """
    
    def __init__(self, cache_dir: str = "prompt_optimization"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Load learned patterns
        self.patterns_file = self.cache_dir / "learned_patterns.json"
        self.patterns = self._load_patterns()
        
        # Track current session
        self.session_data = {
            'successes': [],
            'failures': []
        }
        
    def _load_patterns(self) -> Dict[str, Any]:
        """Load learned patterns from disk."""
        if self.patterns_file.exists():
            with open(self.patterns_file) as f:
                return json.load(f)
        
        return {
            'matching': {
                'successful_terms': defaultdict(int),
                'failed_terms': defaultdict(int),
                'confidence_thresholds': {'high': 0.8, 'low': 0.3}
            },
            'cleaning': {
                'successful_structures': [],
                'problematic_patterns': [],
                'timeout_factors': defaultdict(float)
            },
            'fixing': {
                'error_solutions': defaultdict(list),
                'fix_priorities': defaultdict(int)
            }
        }
        
    def _save_patterns(self):
        """Save learned patterns to disk."""
        # Convert defaultdicts to regular dicts for JSON serialization
        def convert_defaultdict(d):
            if isinstance(d, defaultdict):
                return dict(d)
            elif isinstance(d, dict):
                return {k: convert_defaultdict(v) for k, v in d.items()}
            elif isinstance(d, list):
                return [convert_defaultdict(item) for item in d]
            return d
            
        with open(self.patterns_file, 'w') as f:
            json.dump(convert_defaultdict(self.patterns), f, indent=2)
            
    def optimize_matching_prompt(
        self, 
        base_prompt: str, 
        transcript: str,
        year: int
    ) -> Tuple[str, List[str]]:
        """
        Optimize video matching prompt based on learned patterns.
        Returns: (optimized_prompt, suggested_search_terms)
        """
        patterns = self.patterns['matching']
        
        # Extract technical terms from transcript
        technical_terms = self._extract_technical_terms(transcript)
        
        # Score terms based on historical success
        scored_terms = []
        for term in technical_terms:
            success_score = patterns['successful_terms'].get(term, 0)
            failure_score = patterns['failed_terms'].get(term, 0)
            
            if success_score + failure_score > 0:
                effectiveness = success_score / (success_score + failure_score)
            else:
                effectiveness = 0.5  # Unknown term
                
            scored_terms.append((term, effectiveness))
            
        # Sort by effectiveness and select top terms
        scored_terms.sort(key=lambda x: x[1], reverse=True)
        suggested_terms = [term for term, _ in scored_terms[:5]]
        
        # Add year-specific patterns if we've learned any
        year_key = f"year_{year}_patterns"
        if year_key in patterns:
            suggested_terms.extend(patterns[year_key][:3])
            
        # Enhance prompt with learned insights
        enhancements = []
        
        if patterns['confidence_thresholds']['high'] != 0.8:
            enhancements.append(
                f"Note: Based on past results, consider confidence > "
                f"{patterns['confidence_thresholds']['high']:.1f} as high confidence"
            )
            
        if suggested_terms:
            enhancements.append(
                f"Prioritize searching for these terms that have worked well: "
                f"{', '.join(suggested_terms[:3])}"
            )
            
        if enhancements:
            enhanced_prompt = base_prompt + "\n\nLEARNED INSIGHTS:\n" + "\n".join(enhancements)
        else:
            enhanced_prompt = base_prompt
            
        return enhanced_prompt, suggested_terms
        
    def optimize_cleaning_prompt(
        self, 
        base_prompt: str,
        file_sizes: Dict[str, int]
    ) -> Tuple[str, float]:
        """
        Optimize code cleaning prompt based on file complexity.
        Returns: (optimized_prompt, suggested_timeout_multiplier)
        """
        patterns = self.patterns['cleaning']
        
        # Calculate complexity score
        total_size = sum(file_sizes.values())
        num_files = len(file_sizes)
        
        # Determine timeout multiplier based on past performance
        size_category = 'small' if total_size < 5000 else 'medium' if total_size < 20000 else 'large'
        timeout_multiplier = patterns['timeout_factors'].get(size_category, 1.0)
        
        # Add warnings for known problematic patterns
        warnings = []
        if num_files > 10:
            warnings.append(
                "Multiple files detected. Pay special attention to import resolution."
            )
            
        if any(size > 10000 for size in file_sizes.values()):
            warnings.append(
                "Large file detected. Consider breaking into logical chunks."
            )
            
        # Check for problematic patterns we've learned
        for pattern in patterns['problematic_patterns']:
            if any(pattern in str(file_sizes) for pattern in patterns['problematic_patterns']):
                warnings.append(
                    f"Warning: This matches a problematic pattern we've seen before: {pattern}"
                )
                
        if warnings:
            enhanced_prompt = base_prompt + "\n\nIMPORTANT WARNINGS:\n" + "\n".join(warnings)
        else:
            enhanced_prompt = base_prompt
            
        return enhanced_prompt, timeout_multiplier
        
    def optimize_error_fixing_prompt(
        self,
        base_prompt: str,
        error_message: str,
        attempt_number: int
    ) -> str:
        """
        Optimize error fixing prompt based on learned solutions.
        """
        patterns = self.patterns['fixing']
        
        # Look for known error patterns
        error_key = self._categorize_error(error_message)
        known_solutions = patterns['error_solutions'].get(error_key, [])
        
        # Sort solutions by success count
        if known_solutions:
            known_solutions.sort(key=lambda x: x.get('success_count', 0), reverse=True)
            
        # Build enhanced prompt
        enhancements = []
        
        if known_solutions and attempt_number == 1:
            top_solution = known_solutions[0]
            enhancements.append(
                f"KNOWN SOLUTION (worked {top_solution.get('success_count', 0)} times):\n"
                f"{top_solution['fix_description']}\n"
                f"Example: {top_solution.get('example', 'N/A')}"
            )
            
        # Add attempt-specific strategies based on what's worked
        if attempt_number > 1:
            if error_key in patterns['fix_priorities']:
                priority_fixes = patterns['fix_priorities'][error_key]
                enhancements.append(
                    f"For this error type, prioritize checking: {priority_fixes}"
                )
                
        if enhancements:
            enhanced_prompt = base_prompt + "\n\nLEARNED SOLUTIONS:\n" + "\n".join(enhancements)
        else:
            enhanced_prompt = base_prompt
            
        return enhanced_prompt
        
    def record_success(
        self,
        prompt_type: str,
        context: Dict[str, Any],
        solution: Optional[str] = None
    ):
        """Record a successful prompt execution."""
        self.session_data['successes'].append({
            'type': prompt_type,
            'context': context,
            'solution': solution,
            'timestamp': datetime.now().isoformat()
        })
        
        # Update patterns based on success
        if prompt_type == 'matching':
            for term in context.get('search_terms', []):
                self.patterns['matching']['successful_terms'][term] += 1
                
        elif prompt_type == 'cleaning':
            size_category = context.get('size_category', 'medium')
            current_timeout = self.patterns['cleaning']['timeout_factors'].get(size_category, 1.0)
            # Slightly decrease timeout if successful
            self.patterns['cleaning']['timeout_factors'][size_category] = max(0.8, current_timeout * 0.95)
            
        elif prompt_type == 'fixing' and solution:
            error_key = self._categorize_error(context.get('error', ''))
            solutions = self.patterns['fixing']['error_solutions'][error_key]
            
            # Check if this solution already exists
            existing = next((s for s in solutions if s['fix_description'] == solution), None)
            if existing:
                existing['success_count'] += 1
            else:
                solutions.append({
                    'fix_description': solution,
                    'success_count': 1,
                    'example': context.get('code_snippet', '')[:200]
                })
                
        # Periodically save patterns
        if len(self.session_data['successes']) % 10 == 0:
            self._save_patterns()
            
    def record_failure(
        self,
        prompt_type: str,
        context: Dict[str, Any],
        error: Optional[str] = None
    ):
        """Record a failed prompt execution."""
        self.session_data['failures'].append({
            'type': prompt_type,
            'context': context,
            'error': error,
            'timestamp': datetime.now().isoformat()
        })
        
        # Update patterns based on failure
        if prompt_type == 'matching':
            for term in context.get('search_terms', []):
                self.patterns['matching']['failed_terms'][term] += 1
                
        elif prompt_type == 'cleaning':
            size_category = context.get('size_category', 'medium')
            # Increase timeout if failed
            current_timeout = self.patterns['cleaning']['timeout_factors'].get(size_category, 1.0)
            self.patterns['cleaning']['timeout_factors'][size_category] = min(3.0, current_timeout * 1.1)
            
            # Record problematic pattern if identified
            if 'pattern' in context:
                if context['pattern'] not in self.patterns['cleaning']['problematic_patterns']:
                    self.patterns['cleaning']['problematic_patterns'].append(context['pattern'])
                    
    def _extract_technical_terms(self, text: str) -> List[str]:
        """Extract likely technical terms from text."""
        # Simple heuristic: CamelCase, mathematical terms, and technical keywords
        terms = []
        
        # CamelCase terms
        camel_case = re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b', text)
        terms.extend(camel_case)
        
        # Mathematical terms
        math_terms = re.findall(r'\b(?:integral|derivative|matrix|vector|function|equation|'
                               r'polynomial|exponential|logarithm|trigonometric|'
                               r'binary|decimal|hexadecimal|algorithm)\b', text, re.I)
        terms.extend(math_terms)
        
        # Technical keywords
        tech_terms = re.findall(r'\b(?:animation|transform|rotate|scale|shift|morph|'
                               r'interpolate|fade|draw|create|update)\b', text, re.I)
        terms.extend(tech_terms)
        
        # Deduplicate and return
        return list(set(term.lower() for term in terms))
        
    def _categorize_error(self, error_message: str) -> str:
        """Categorize an error message into a general type."""
        error_lower = error_message.lower()
        
        if 'import' in error_lower:
            return 'import_error'
        elif 'attribute' in error_lower:
            return 'attribute_error'
        elif 'name' in error_lower and 'not defined' in error_lower:
            return 'undefined_name'
        elif 'syntax' in error_lower:
            return 'syntax_error'
        elif 'type' in error_lower:
            return 'type_error'
        elif 'color' in error_lower:
            return 'color_error'
        elif 'animation' in error_lower:
            return 'animation_error'
        else:
            # Create a simplified key from the error
            key_words = re.findall(r'\b\w+\b', error_message)[:3]
            return '_'.join(key_words).lower() if key_words else 'unknown_error'
            
    def generate_optimization_report(self) -> str:
        """Generate a report of learned optimizations."""
        report = ["# Adaptive Prompt Optimization Report", ""]
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Matching insights
        report.append("## Video Matching Insights")
        matching = self.patterns['matching']
        
        if matching['successful_terms']:
            report.append("\n### Most Effective Search Terms:")
            sorted_terms = sorted(
                matching['successful_terms'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            for term, count in sorted_terms:
                report.append(f"  - {term}: {count} successful uses")
                
        # Cleaning insights  
        report.append("\n## Code Cleaning Insights")
        cleaning = self.patterns['cleaning']
        
        if cleaning['timeout_factors']:
            report.append("\n### Optimal Timeout Multipliers:")
            for category, multiplier in cleaning['timeout_factors'].items():
                report.append(f"  - {category} files: {multiplier:.2f}x")
                
        if cleaning['problematic_patterns']:
            report.append("\n### Problematic Patterns:")
            for pattern in cleaning['problematic_patterns'][:5]:
                report.append(f"  - {pattern}")
                
        # Fixing insights
        report.append("\n## Error Fixing Insights")
        fixing = self.patterns['fixing']
        
        if fixing['error_solutions']:
            report.append("\n### Most Successful Fixes:")
            for error_type, solutions in list(fixing['error_solutions'].items())[:5]:
                if solutions:
                    top_solution = max(solutions, key=lambda x: x.get('success_count', 0))
                    report.append(f"  - {error_type}: {top_solution['fix_description']} "
                                f"({top_solution.get('success_count', 0)} successes)")
                                
        return '\n'.join(report)


# Integration helper
def integrate_with_pipeline(optimizer: AdaptivePromptOptimizer):
    """Create wrapper functions to integrate with existing pipeline."""
    
    def enhanced_match_videos(original_match_func):
        """Wrapper for video matching with optimization."""
        def wrapper(self, *args, **kwargs):
            # Extract context
            transcript = kwargs.get('transcript', '')
            year = kwargs.get('year', 2015)
            
            # Optimize prompt
            if hasattr(self, 'prompt_template'):
                optimized_prompt, search_terms = optimizer.optimize_matching_prompt(
                    self.prompt_template, transcript, year
                )
                self.prompt_template = optimized_prompt
                kwargs['suggested_search_terms'] = search_terms
                
            # Execute original function
            try:
                result = original_match_func(self, *args, **kwargs)
                
                # Record success if confidence is high
                if result.get('confidence_score', 0) > 0.8:
                    optimizer.record_success('matching', {
                        'search_terms': search_terms,
                        'year': year
                    })
                    
                return result
                
            except Exception as e:
                optimizer.record_failure('matching', {
                    'search_terms': search_terms,
                    'year': year
                }, str(e))
                raise
                
        return wrapper
        
    return enhanced_match_videos


if __name__ == "__main__":
    # Example usage
    optimizer = AdaptivePromptOptimizer()
    
    # Simulate learning from successes
    optimizer.record_success('matching', {
        'search_terms': ['binary', 'counting', 'decimal'],
        'year': 2015
    })
    
    optimizer.record_success('fixing', {
        'error': "name 'BLUE_E' is not defined",
        'code_snippet': 'circle = Circle(color=BLUE_E)'
    }, "Import BLUE_E from manimce_constants_helpers")
    
    # Test optimization
    base_prompt = "Match this video to source code."
    transcript = "Let's explore binary counting and decimal conversion..."
    
    optimized_prompt, terms = optimizer.optimize_matching_prompt(base_prompt, transcript, 2015)
    print("Optimized prompt:")
    print(optimized_prompt)
    print(f"\nSuggested search terms: {terms}")
    
    # Generate report
    print("\n" + optimizer.generate_optimization_report())