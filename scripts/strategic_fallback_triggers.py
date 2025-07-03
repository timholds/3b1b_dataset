#!/usr/bin/env python3
"""
Strategic Claude Fallback Triggers - Maximize correctness by identifying high-risk patterns

Based on pipeline analysis showing 79.5% conversion success but only 17.1% rendering success,
this module implements strategic triggers to call Claude BEFORE validation failure occurs.

Key insights from failed scenes:
- Scenes with 30+ systematic fixes have much higher failure rates
- Syntax errors always correlate with rendering failure  
- Even high confidence (0.97+) scenes can fail to render
- Complex nested structures and list operations are high-risk

Strategy: Better to use expensive Claude for complex cases than produce broken output.
"""

import ast
import re
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class FallbackTrigger:
    """Represents a condition that should trigger Claude fallback."""
    name: str
    reason: str
    priority: str  # 'high', 'medium', 'low'
    confidence_impact: float  # How much this reduces confidence (0.0-1.0)

class StrategicFallbackAnalyzer:
    """
    Analyzes code patterns to determine if Claude fallback should be triggered
    BEFORE attempting systematic conversion.
    """
    
    def __init__(self):
        # Patterns that indicate high complexity/risk based on pipeline failures
        self.high_risk_patterns = {
            # Complex list operations that often break in conversion
            'complex_list_unpacking': r'([a-zA-Z_][a-zA-Z0-9_]*\s*,\s*){2,}[a-zA-Z_][a-zA-Z0-9_]*\s*=\s*\[',
            'nested_list_operations': r'\[\s*\[.*\]\s*\]',
            'list_comprehension_complex': r'\[.*for.*for.*\]',
            
            # Function calls with complex parameters
            'complex_function_calls': r'\w+\([^)]*\([^)]*\)[^)]*\)',
            'nested_method_chains': r'\w+\([^)]*\)\.[a-zA-Z_][a-zA-Z0-9_]*\([^)]*\)',
            
            # Math/Tex content that often needs special handling
            'complex_tex_expressions': r'(Tex|MathTex|TextMobject|OldTex)\([^)]*[\[\]{}\\][^)]*\)',
            'latex_with_variables': r'(Tex|MathTex|TextMobject|OldTex)\([^)]*%[sdf][^)]*\)',
            
            # Animation complexity indicators
            'nested_animations': r'(Transform|ReplacementTransform)\([^)]*VGroup[^)]*\)',
            'complex_animation_chains': r'(self\.play|self\.add)\([^)]*,[^)]*,[^)]*,[^)]*\)',
            
            # Control flow complexity
            'nested_conditionals': r'if.*:\s*\n\s+if.*:',
            'complex_loops': r'for.*in.*:\s*\n\s+for.*in.*:',
            
            # Error-prone patterns from pipeline analysis
            'unclosed_parentheses_risk': r'\([^)]*\([^)]*$',
            'missing_comma_risk': r'\[[^,\]]{20,}\]',  # Long lists without commas
        }
        
        # Confidence thresholds based on pipeline data analysis
        self.confidence_thresholds = {
            'syntax_error_confidence': 0.5,  # Any syntax errors should trigger fallback
            'high_complexity_confidence': 0.7,  # Complex patterns need Claude
            'moderate_complexity_confidence': 0.8,  # Moderate complexity threshold
        }
    
    def analyze_scene_for_fallback(self, 
                                  scene_code: str, 
                                  scene_name: str,
                                  systematic_fixes_count: int = 0,
                                  current_confidence: float = 1.0) -> Tuple[bool, List[FallbackTrigger], float]:
        """
        Analyze if a scene should trigger Claude fallback based on complexity patterns.
        
        Args:
            scene_code: The ManimGL scene code to analyze
            scene_name: Name of the scene for logging
            systematic_fixes_count: Number of systematic fixes that would be applied
            current_confidence: Current confidence from systematic analysis
            
        Returns:
            Tuple of (should_trigger_fallback, triggers_found, adjusted_confidence)
        """
        triggers = []
        adjusted_confidence = current_confidence
        
        # TRIGGER 1: High systematic fix count (Based on pipeline analysis)
        if systematic_fixes_count >= 35:
            triggers.append(FallbackTrigger(
                name="high_fix_count",
                reason=f"Scene requires {systematic_fixes_count} systematic fixes (>= 35 threshold)",
                priority="high",
                confidence_impact=0.4
            ))
            adjusted_confidence *= 0.6  # Reduce confidence significantly
            
        elif systematic_fixes_count >= 30:
            triggers.append(FallbackTrigger(
                name="moderate_fix_count", 
                reason=f"Scene requires {systematic_fixes_count} systematic fixes (>= 30 threshold)",
                priority="medium",
                confidence_impact=0.2
            ))
            adjusted_confidence *= 0.8
        
        # TRIGGER 2: Syntax validation (pre-conversion)
        try:
            ast.parse(scene_code)
        except SyntaxError as e:
            triggers.append(FallbackTrigger(
                name="syntax_error",
                reason=f"Syntax error in original code: {str(e)}",
                priority="high", 
                confidence_impact=0.5
            ))
            adjusted_confidence *= 0.5  # Major confidence hit for syntax errors
        
        # TRIGGER 3: Complex pattern analysis
        pattern_triggers = self._analyze_complex_patterns(scene_code)
        triggers.extend(pattern_triggers)
        
        # Adjust confidence based on pattern complexity
        for trigger in pattern_triggers:
            adjusted_confidence *= (1.0 - trigger.confidence_impact)
        
        # TRIGGER 4: Combined risk factors
        risk_factors = len([t for t in triggers if t.priority == "high"])
        if risk_factors >= 2:
            triggers.append(FallbackTrigger(
                name="multiple_risk_factors",
                reason=f"Scene has {risk_factors} high-risk factors", 
                priority="high",
                confidence_impact=0.3
            ))  
            adjusted_confidence *= 0.7
        
        # DECISION: Should we trigger Claude fallback?
        should_trigger = self._should_trigger_fallback(triggers, adjusted_confidence)
        
        if should_trigger:
            logger.info(f"🔄 CLAUDE FALLBACK TRIGGERED for {scene_name}")
            logger.info(f"   Reasons: {[t.reason for t in triggers]}")
            logger.info(f"   Confidence: {current_confidence:.2f} → {adjusted_confidence:.2f}")
        
        return should_trigger, triggers, adjusted_confidence
    
    def _analyze_complex_patterns(self, code: str) -> List[FallbackTrigger]:
        """Analyze code for complex patterns that indicate Claude should be used."""
        triggers = []
        
        for pattern_name, pattern_regex in self.high_risk_patterns.items():
            matches = re.findall(pattern_regex, code, re.MULTILINE | re.DOTALL)
            if matches:
                # Determine priority and impact based on pattern type
                if pattern_name in ['complex_list_unpacking', 'complex_tex_expressions', 'unclosed_parentheses_risk']:
                    priority = "high"
                    impact = 0.3
                elif pattern_name in ['nested_animations', 'complex_function_calls']:
                    priority = "medium" 
                    impact = 0.2
                else:
                    priority = "low"
                    impact = 0.1
                
                triggers.append(FallbackTrigger(
                    name=pattern_name,
                    reason=f"Found {len(matches)} instances of {pattern_name.replace('_', ' ')}",
                    priority=priority,
                    confidence_impact=impact
                ))
        
        return triggers
    
    def _should_trigger_fallback(self, triggers: List[FallbackTrigger], adjusted_confidence: float) -> bool:
        """Determine if Claude fallback should be triggered based on triggers and confidence."""
        
        # Always trigger for high-priority issues
        high_priority_triggers = [t for t in triggers if t.priority == "high"]
        if high_priority_triggers:
            return True
        
        # Trigger based on confidence thresholds
        if adjusted_confidence < self.confidence_thresholds['high_complexity_confidence']:
            return True
        
        # Trigger for multiple medium-priority issues
        medium_priority_triggers = [t for t in triggers if t.priority == "medium"]
        if len(medium_priority_triggers) >= 2:
            return True
        
        return False
    
    def should_skip_scene(self, adjusted_confidence: float, min_confidence: float = 0.6) -> bool:
        """Determine if a scene should be skipped entirely due to very low confidence."""
        return adjusted_confidence < min_confidence

def analyze_post_conversion_quality(converted_code: str, scene_name: str) -> Tuple[bool, List[str]]:
    """
    Analyze converted ManimCE code for common runtime issues that indicate
    successful systematic conversion but likely rendering failure.
    
    This addresses the gap between syntax validation and semantic correctness.
    """
    issues = []
    
    # Check for common runtime error patterns from pipeline analysis
    runtime_error_patterns = {
        'mathtex_list_args': r'MathTex\(\s*\[.*\]\s*\)',  # MathTex with list instead of string
        'tex_list_args': r'Tex\(\s*\[.*\]\s*\)',
        'missing_constants': r'\b(DL|DR|UL|UR)\b',  # Undefined direction constants
        'points_access_error': r'\.points\[0\]',  # Direct points access (should use get_start/get_end)
        'old_animation_methods': r'\.(get_center|get_width|get_height)\(\)',  # Method calls that should be properties
        'vgroup_construction_error': r'VGroup\([^)]*\[.*\][^)]*\)',  # VGroup with list arguments
    }
    
    for error_type, pattern in runtime_error_patterns.items():
        matches = re.findall(pattern, converted_code)
        if matches:
            issues.append(f"{error_type}: {len(matches)} instances found")
    
    # Try basic compilation check
    try:
        # Add minimal imports for compilation check
        test_code = f"""
from manim import *
import numpy as np
from typing import Optional, List, Dict, Union, Any

{converted_code}
"""
        compile(test_code, f"{scene_name}.py", "exec")
        compilation_ok = True
    except Exception as e:
        compilation_ok = False
        issues.append(f"Compilation error: {str(e)}")
    
    quality_ok = len(issues) == 0 and compilation_ok
    
    if not quality_ok:
        logger.warning(f"Post-conversion quality issues in {scene_name}: {issues}")
    
    return quality_ok, issues