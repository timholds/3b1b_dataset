#!/usr/bin/env python3
"""
Unfixable Pattern Detector - Identifies conversion patterns that are fundamentally incompatible with ManimCE

This module helps the pipeline avoid wasting Claude API calls on issues that cannot be resolved
through code conversion alone. It categorizes errors into:
1. Definitely unfixable - Skip Claude attempts entirely
2. Likely unfixable - Try once with Claude but don't retry
3. Potentially fixable - Normal Claude retry logic

By detecting these patterns early, we can:
- Save API costs by avoiding futile conversion attempts
- Provide clearer feedback about why certain scenes can't be converted
- Focus Claude resources on actually fixable issues
"""

import ast
import re
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class FixabilityLevel(Enum):
    """Categorizes how likely an issue is to be fixable."""
    DEFINITELY_UNFIXABLE = "definitely_unfixable"  # Don't even try Claude
    LIKELY_UNFIXABLE = "likely_unfixable"  # Try Claude once, no retries
    POTENTIALLY_FIXABLE = "potentially_fixable"  # Normal retry logic


@dataclass
class UnfixablePattern:
    """Represents a pattern that indicates unfixable code."""
    pattern: str  # Regex or exact match
    category: str  # Type of issue (e.g., "external_dependency", "pi_creature")
    level: FixabilityLevel
    explanation: str  # Human-readable explanation
    match_type: str = "regex"  # "regex" or "exact"


class UnfixablePatternDetector:
    """Detects patterns in code that are fundamentally incompatible with ManimCE."""
    
    def __init__(self):
        self.patterns = self._initialize_patterns()
        self.stats = {
            'definitely_unfixable': 0,
            'likely_unfixable': 0,
            'potentially_fixable': 0,
            'patterns_detected': {}
        }
    
    def _initialize_patterns(self) -> List[UnfixablePattern]:
        """Initialize the list of unfixable patterns."""
        return [
            # External Dependencies (Definitely Unfixable)
            UnfixablePattern(
                pattern=r'import\s+cv2|from\s+cv2\s+import',
                category="external_dependency",
                level=FixabilityLevel.DEFINITELY_UNFIXABLE,
                explanation="OpenCV (cv2) is not available in ManimCE environment"
            ),
            UnfixablePattern(
                pattern=r'import\s+displayer|from\s+displayer\s+import',
                category="external_dependency", 
                level=FixabilityLevel.DEFINITELY_UNFIXABLE,
                explanation="displayer is a custom 3b1b module not available in ManimCE"
            ),
            UnfixablePattern(
                pattern=r'import\s+pygame|from\s+pygame\s+import',
                category="external_dependency",
                level=FixabilityLevel.DEFINITELY_UNFIXABLE,
                explanation="pygame is not part of ManimCE"
            ),
            
            # Pi Creature System (Definitely Unfixable)
            UnfixablePattern(
                pattern=r'\b(ThoughtBubble|SpeechBubble|Face|PiCreature|Randolph|Mortimer|Mathematician)\s*\(',
                category="pi_creature",
                level=FixabilityLevel.DEFINITELY_UNFIXABLE,
                explanation="Pi Creature animation system is not available in ManimCE"
            ),
            UnfixablePattern(
                pattern=r'\b(randy|mortimer|randolph|pi_creature)\s*\.',
                category="pi_creature",
                level=FixabilityLevel.DEFINITELY_UNFIXABLE,
                explanation="Pi Creature character references not available in ManimCE"
            ),
            
            # Complex Inheritance (Likely Unfixable)
            UnfixablePattern(
                pattern=r'class\s+\w+\s*\((CycloidScene|PathSlidingScene|MultilayeredScene|PhotonScene|ThetaTGraph|VideoLayout)\)',
                category="custom_inheritance",
                level=FixabilityLevel.LIKELY_UNFIXABLE,
                explanation="Inherits from custom 3b1b scene class not in ManimCE"
            ),
            
            # Complex Custom Animations (Likely Unfixable)
            UnfixablePattern(
                pattern=r'class\s+\w+\s*\(.*ContinualAnimation.*\)',
                category="continual_animation",
                level=FixabilityLevel.LIKELY_UNFIXABLE,
                explanation="ContinualAnimation has no direct ManimCE equivalent"
            ),
            
            # Structural Issues (Definitely Unfixable)
            UnfixablePattern(
                pattern=r'^SyntaxError:\s+invalid\s+syntax\s+at\s+line\s+1',
                category="syntax_corruption",
                level=FixabilityLevel.DEFINITELY_UNFIXABLE,
                explanation="AST transformation produced structurally broken code",
                match_type="exact"
            ),
            
            # Complex CONFIG with Dynamic Elements (Likely Unfixable)
            UnfixablePattern(
                pattern=r'CONFIG\s*=\s*\{[^}]*lambda[^}]*\}',
                category="complex_config",
                level=FixabilityLevel.LIKELY_UNFIXABLE,
                explanation="CONFIG contains lambda functions requiring manual refactoring"
            ),
            
            # Missing Core Classes (Likely Unfixable)
            UnfixablePattern(
                pattern=r'NameError:\s+name\s+[\'"]ParametricCurve[\'"]\s+is\s+not\s+defined',
                category="missing_class",
                level=FixabilityLevel.LIKELY_UNFIXABLE,
                explanation="ParametricCurve requires specific ManimCE implementation",
                match_type="regex"
            ),
            
            # GLSL Shaders (Definitely Unfixable)
            UnfixablePattern(
                pattern=r'\.glsl|shader_wrapper|ShaderWrapper',
                category="glsl_shader",
                level=FixabilityLevel.DEFINITELY_UNFIXABLE,
                explanation="GLSL shaders are not supported in ManimCE"
            ),
            
            # Complex 3D Features (Likely Unfixable)
            UnfixablePattern(
                pattern=r'class\s+\w+\s*\(.*ThreeDScene.*\).*CONFIG.*camera_config',
                category="complex_3d",
                level=FixabilityLevel.LIKELY_UNFIXABLE,
                explanation="Complex 3D camera configurations may not translate to ManimCE"
            ),
            
            # Interactive Mouse/Keyboard Scenes (Definitely Unfixable)
            UnfixablePattern(
                pattern=r'on_mouse_motion|on_mouse_press|on_key_press|mouse_drag_point|InteractiveScene',
                category="interactive_scene",
                level=FixabilityLevel.DEFINITELY_UNFIXABLE,
                explanation="Interactive scenes require live OpenGL window and cannot be pre-rendered as videos"
            ),
            
            # Direct OpenGL Access (Definitely Unfixable)
            UnfixablePattern(
                pattern=r'moderngl\.|TRIANGLE_STRIP|direct.*opengl',
                category="direct_opengl",
                level=FixabilityLevel.DEFINITELY_UNFIXABLE,
                explanation="Direct OpenGL calls are not supported in ManimCE"
            )
        ]
    
    def analyze_code(self, code: str, error_message: Optional[str] = None) -> Tuple[FixabilityLevel, List[str]]:
        """
        Analyze code to determine if it contains unfixable patterns.
        
        Args:
            code: The Python code to analyze
            error_message: Optional error message from previous conversion attempt
            
        Returns:
            Tuple of (fixability_level, list_of_explanations)
        """
        detected_issues = []
        worst_level = FixabilityLevel.POTENTIALLY_FIXABLE
        
        # Check code patterns
        for pattern in self.patterns:
            if pattern.match_type == "regex":
                if re.search(pattern.pattern, code, re.MULTILINE):
                    detected_issues.append(f"{pattern.category}: {pattern.explanation}")
                    if pattern.level.value < worst_level.value:
                        worst_level = pattern.level
                    self._update_stats(pattern)
            elif pattern.match_type == "exact" and error_message:
                if pattern.pattern in error_message:
                    detected_issues.append(f"{pattern.category}: {pattern.explanation}")
                    if pattern.level.value < worst_level.value:
                        worst_level = pattern.level
                    self._update_stats(pattern)
        
        # Additional AST-based checks
        try:
            tree = ast.parse(code)
            ast_issues = self._analyze_ast(tree)
            detected_issues.extend(ast_issues)
        except SyntaxError:
            # Syntax errors are often fixable by Claude - only skip if clearly corrupted
            if self._is_corrupted_code(code):
                detected_issues.append("syntax_corruption: Code appears to be corrupted beyond repair")
                worst_level = FixabilityLevel.DEFINITELY_UNFIXABLE
            else:
                detected_issues.append("syntax_error: Code has syntax errors but may be fixable by Claude")
                # Don't change worst_level - let other patterns determine fixability
        
        self.stats[worst_level.value] += 1
        
        return worst_level, detected_issues
    
    def _analyze_ast(self, tree: ast.AST) -> List[str]:
        """Perform AST-based analysis for complex patterns."""
        issues = []
        
        class PatternVisitor(ast.NodeVisitor):
            def __init__(self):
                self.found_issues = []
                self.defined_classes = set()
                self.imported_names = set()
            
            def visit_ClassDef(self, node):
                self.defined_classes.add(node.name)
                
                # Check for CONFIG with complex initialization
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name) and target.id == "CONFIG":
                                # Check if CONFIG contains complex elements
                                if self._has_complex_config(item.value):
                                    self.found_issues.append(
                                        "complex_config: CONFIG contains complex initialization requiring manual conversion"
                                    )
                self.generic_visit(node)
            
            def visit_Import(self, node):
                for alias in node.names:
                    self.imported_names.add(alias.name)
                self.generic_visit(node)
            
            def visit_ImportFrom(self, node):
                if node.module:
                    self.imported_names.add(node.module)
                self.generic_visit(node)
            
            def _has_complex_config(self, node):
                """Check if CONFIG dict has complex elements."""
                if isinstance(node, ast.Dict):
                    for value in node.values:
                        if isinstance(value, (ast.Lambda, ast.ListComp, ast.DictComp)):
                            return True
                        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
                            # Check for dynamic function calls in CONFIG
                            if value.func.id in ['lambda', 'eval', 'exec']:
                                return True
                return False
        
        visitor = PatternVisitor()
        visitor.visit(tree)
        
        return visitor.found_issues
    
    def _is_corrupted_code(self, code: str) -> bool:
        """
        Detect if code is corrupted beyond repair (as opposed to just having syntax errors).
        
        Returns True only for code that appears to be structurally destroyed.
        """
        # Check for signs of corruption
        corruption_indicators = [
            # Binary data mixed in
            re.search(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\xFF]', code),
            # Completely random characters
            len(re.findall(r'[a-zA-Z_]', code)) < len(code) * 0.3,  # Less than 30% letters/underscores
            # Extremely short but still causing syntax errors
            len(code.strip()) < 10 and code.strip(),
            # No recognizable Python keywords at all
            not any(keyword in code for keyword in ['def', 'class', 'import', 'from', 'if', 'for', 'while', 'return'])
        ]
        
        # Only consider corrupted if multiple indicators are present
        return sum(bool(indicator) for indicator in corruption_indicators) >= 2
    
    def _update_stats(self, pattern: UnfixablePattern):
        """Update statistics for detected patterns."""
        if pattern.category not in self.stats['patterns_detected']:
            self.stats['patterns_detected'][pattern.category] = 0
        self.stats['patterns_detected'][pattern.category] += 1
    
    def should_skip_claude(self, code: str, error_message: Optional[str] = None, 
                          previous_attempts: int = 0) -> Tuple[bool, str]:
        """
        Determine if we should skip Claude API calls for this code.
        
        Args:
            code: The code to analyze
            error_message: Optional error message from conversion
            previous_attempts: Number of previous Claude attempts
            
        Returns:
            Tuple of (should_skip, reason)
        """
        level, issues = self.analyze_code(code, error_message)
        
        if level == FixabilityLevel.DEFINITELY_UNFIXABLE:
            return True, f"Definitely unfixable issues detected: {'; '.join(issues)}"
        
        if level == FixabilityLevel.LIKELY_UNFIXABLE and previous_attempts > 0:
            return True, f"Likely unfixable issues detected after {previous_attempts} attempts: {'; '.join(issues)}"
        
        return False, ""
    
    def get_fixability_report(self) -> str:
        """Generate a report of fixability statistics."""
        total_analyzed = sum([
            self.stats['definitely_unfixable'],
            self.stats['likely_unfixable'], 
            self.stats['potentially_fixable']
        ])
        
        if total_analyzed == 0:
            return "No patterns analyzed yet."
        
        report = f"""
Fixability Analysis Report
==========================
Total scenes analyzed: {total_analyzed}

Breakdown by fixability:
- Definitely unfixable: {self.stats['definitely_unfixable']} ({self.stats['definitely_unfixable']/total_analyzed*100:.1f}%)
- Likely unfixable: {self.stats['likely_unfixable']} ({self.stats['likely_unfixable']/total_analyzed*100:.1f}%)
- Potentially fixable: {self.stats['potentially_fixable']} ({self.stats['potentially_fixable']/total_analyzed*100:.1f}%)

Most common unfixable patterns:
"""
        
        for category, count in sorted(self.stats['patterns_detected'].items(), 
                                    key=lambda x: x[1], reverse=True)[:5]:
            report += f"- {category}: {count} occurrences\n"
        
        return report


def integrate_with_pipeline(detector: UnfixablePatternDetector, 
                          scene_code: str,
                          error_message: Optional[str] = None,
                          previous_attempts: int = 0) -> Dict[str, any]:
    """
    Integration point for the pipeline to check if a scene should skip Claude.
    
    Returns a dict with:
    - should_skip: bool
    - reason: str
    - fixability_level: str
    - detected_issues: List[str]
    """
    should_skip, reason = detector.should_skip_claude(scene_code, error_message, previous_attempts)
    level, issues = detector.analyze_code(scene_code, error_message)
    
    return {
        'should_skip': should_skip,
        'reason': reason,
        'fixability_level': level.value,
        'detected_issues': issues
    }