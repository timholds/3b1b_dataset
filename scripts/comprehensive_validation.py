#!/usr/bin/env python3
"""
Comprehensive Validation Module - Pre/Post Conversion Quality Assurance

This module implements comprehensive validation to catch issues before they become
rendering failures, addressing the 62% gap between conversion success and rendering success.

Key features:
1. Pre-conversion ManimGL validation (syntax, imports, basic semantics)
2. Post-conversion ManimCE validation (syntax, runtime patterns, compilation)
3. Semantic quality checks for common failure patterns
4. Risk assessment for triggering Claude fallback
"""

import ast
import re
import logging
import tempfile
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Result of comprehensive validation."""
    is_valid: bool
    confidence: float
    issues: List[str]
    warnings: List[str]
    risk_factors: List[str]
    should_use_claude: bool
    metadata: Dict[str, Any]

class ComprehensiveValidator:
    """
    Comprehensive validator for ManimGL and ManimCE code that catches
    issues before they become rendering failures.
    """
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        
        # Common import patterns for different Manim versions
        self.manim_imports = {
            'manimgl': ['from manimlib import *', 'from manimgl import *'],
            'manimce': ['from manim import *']
        }
        
        # Runtime error patterns that cause rendering failures
        self.runtime_error_patterns = {
            'tex_list_args': r'(Tex|MathTex|TextMobject|OldTex)\s*\(\s*\[',
            'vgroup_list_args': r'VGroup\s*\(\s*\[',
            'missing_constants': r'\b(DL|DR|UL|UR|FRAME_WIDTH|FRAME_HEIGHT)\b',
            'old_method_calls': r'\.(get_center|get_width|get_height|get_color)\s*\(\s*\)',
            'points_access': r'\.points\[',
            'undefined_functions': r'[a-zA-Z_][a-zA-Z0-9_]*\s*\([^)]*\)(?=.*# undefined)',
            'string_formatting_issues': r'[^r]"[^"]*\\[^nr]',
        }
        
        # Complexity indicators that suggest Claude should be used
        self.complexity_patterns = {
            'nested_conditionals': r'if.*:\s*\n\s+if.*:',
            'complex_loops': r'for.*in.*:\s*\n\s+.*for.*in.*:',
            'nested_function_calls': r'\w+\([^)]*\w+\([^)]*\)[^)]*\)',
            'complex_list_comprehensions': r'\[.*for.*for.*\]',
            'multiple_inheritance': r'class\s+\w+\([^)]*,.*\):',
            'lambda_expressions': r'lambda\s+[^:]+:',
        }
        
        # Known problematic patterns from pipeline analysis
        self.problematic_patterns = {
            'unclosed_parentheses': r'\([^)]*$',
            'unmatched_brackets': r'\[[^\]]*$',
            'missing_commas': r'\[[^,\]]{30,}\]',  # Long lists without commas
            'malformed_f_strings': r'f["\'][^"\']*\{[^}]*$',
        }
    
    def validate_manimgl_code(self, code: str, scene_name: str) -> ValidationResult:
        """
        Comprehensive validation of ManimGL code before conversion.
        
        This catches issues early to prevent problematic conversions.
        """
        issues = []
        warnings = []
        risk_factors = []
        confidence = 1.0
        metadata = {}
        
        # Check 1: Basic syntax validation
        try:
            ast.parse(code)
            metadata['syntax_valid'] = True
        except SyntaxError as e:
            issues.append(f"Syntax error: {str(e)}")
            metadata['syntax_valid'] = False
            confidence *= 0.3  # Major confidence hit for syntax errors
        except Exception as e:
            issues.append(f"Parse error: {str(e)}")
            metadata['syntax_valid'] = False
            confidence *= 0.4
        
        # Check 2: Import analysis
        import_issues = self._check_imports(code)
        if import_issues:
            warnings.extend(import_issues)
            confidence *= 0.9
        
        # Check 3: Problematic pattern detection
        problematic_count = 0
        for pattern_name, pattern in self.problematic_patterns.items():
            matches = re.findall(pattern, code, re.MULTILINE)
            if matches:
                issues.append(f"Problematic pattern '{pattern_name}': {len(matches)} instances")
                problematic_count += len(matches)
        
        if problematic_count > 0:
            confidence *= max(0.2, 1.0 - (problematic_count * 0.1))
        
        # Check 4: Complexity analysis
        complexity_score = self._calculate_complexity(code)
        metadata['complexity_score'] = complexity_score
        
        if complexity_score > 10:
            risk_factors.append(f"High complexity score: {complexity_score}")
            confidence *= 0.8
        elif complexity_score > 5:
            risk_factors.append(f"Moderate complexity score: {complexity_score}")
            confidence *= 0.9
        
        # Check 5: Scene structure validation
        scene_issues = self._validate_scene_structure(code, scene_name)
        if scene_issues:
            warnings.extend(scene_issues)
            confidence *= 0.95
        
        # Decision: Should use Claude?
        should_use_claude = self._should_use_claude_for_manimgl(
            confidence, len(issues), len(risk_factors), complexity_score
        )
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            confidence=confidence,
            issues=issues,
            warnings=warnings,
            risk_factors=risk_factors,
            should_use_claude=should_use_claude,
            metadata=metadata
        )
    
    def validate_manimce_code(self, code: str, scene_name: str) -> ValidationResult:
        """
        Comprehensive validation of converted ManimCE code before rendering.
        
        This catches semantic issues that syntax validation misses.
        """
        issues = []
        warnings = []
        risk_factors = []
        confidence = 1.0
        metadata = {}
        
        # Check 1: Basic syntax validation
        try:
            ast.parse(code)
            metadata['syntax_valid'] = True
        except SyntaxError as e:
            issues.append(f"Syntax error: {str(e)}")
            metadata['syntax_valid'] = False
            confidence = 0.0  # Converted code must be syntactically valid
            
            return ValidationResult(
                is_valid=False,
                confidence=confidence,
                issues=issues,
                warnings=warnings,
                risk_factors=risk_factors,
                should_use_claude=True,  # Always use Claude for syntax errors
                metadata=metadata
            )
        
        # Check 2: Runtime error pattern detection
        runtime_errors = 0
        for pattern_name, pattern in self.runtime_error_patterns.items():
            matches = re.findall(pattern, code, re.MULTILINE)
            if matches:
                issues.append(f"Runtime error pattern '{pattern_name}': {len(matches)} instances")
                runtime_errors += len(matches)
        
        if runtime_errors > 0:
            confidence *= max(0.1, 1.0 - (runtime_errors * 0.2))
        
        # Check 3: ManimCE compilation test
        compilation_ok, compilation_errors = self._test_manimce_compilation(code, scene_name)
        metadata['compilation_ok'] = compilation_ok
        
        if not compilation_ok:
            issues.extend(compilation_errors)
            confidence *= 0.3
        
        # Check 4: Import validation for ManimCE
        if 'from manim import *' not in code and 'import manim' not in code:
            warnings.append("Missing ManimCE imports")
            confidence *= 0.9
        
        # Check 5: Scene class validation
        scene_class_issues = self._validate_manimce_scene_class(code, scene_name)
        if scene_class_issues:
            issues.extend(scene_class_issues)
            confidence *= 0.8
        
        # Decision: Should use Claude for re-conversion?
        should_use_claude = confidence < 0.6 or runtime_errors > 3
        
        return ValidationResult(
            is_valid=len(issues) == 0 and compilation_ok,
            confidence=confidence,
            issues=issues,
            warnings=warnings,
            risk_factors=risk_factors,
            should_use_claude=should_use_claude,
            metadata=metadata
        )
    
    def _check_imports(self, code: str) -> List[str]:
        """Check for import-related issues."""
        issues = []
        
        # Check for missing imports
        if 'from manim' not in code and 'import manim' not in code:
            if 'Scene' in code or 'Mobject' in code:
                issues.append("Scene/Mobject used but no manim imports found")
        
        # Check for numpy usage without import
        if re.search(r'\bnp\.', code) and 'numpy' not in code:
            issues.append("numpy (np.) used but not imported")
        
        return issues
    
    def _calculate_complexity(self, code: str) -> int:
        """Calculate complexity score based on various factors."""
        score = 0
        
        # Count different complexity indicators
        for pattern_name, pattern in self.complexity_patterns.items():
            matches = len(re.findall(pattern, code, re.MULTILINE))
            if pattern_name in ['nested_conditionals', 'complex_loops']:
                score += matches * 3  # High weight for control flow complexity
            elif pattern_name in ['nested_function_calls', 'complex_list_comprehensions']:
                score += matches * 2  # Medium weight
            else:
                score += matches  # Standard weight
        
        # Additional complexity factors
        lines = code.split('\n')
        score += len(lines) // 50  # Roughly 1 point per 50 lines
        score += len(re.findall(r'def\s+\w+', code))  # Functions add complexity
        score += len(re.findall(r'class\s+\w+', code))  # Classes add complexity
        
        return score
    
    def _validate_scene_structure(self, code: str, scene_name: str) -> List[str]:
        """Validate basic scene structure."""
        issues = []
        
        # Check if scene class exists
        scene_pattern = rf'class\s+{re.escape(scene_name)}\s*\([^)]*Scene[^)]*\):'
        if not re.search(scene_pattern, code):
            issues.append(f"Scene class '{scene_name}' not found or doesn't inherit from Scene")
        
        # Check for construct method
        if f'def construct(self)' not in code and f'def _construct_with_args' not in code:
            issues.append("No construct() or _construct_with_args() method found")
        
        return issues
    
    def _test_manimce_compilation(self, code: str, scene_name: str) -> Tuple[bool, List[str]]:
        """Test if ManimCE code can be compiled."""
        try:
            # Create a complete test file with proper imports
            test_code = f"""
from manim import *
import numpy as np
from typing import Optional, List, Dict, Union, Any
from functools import reduce
import string
import itertools as it
from copy import deepcopy
from random import sample
import operator as op
import random
import sys

{code}
"""
            
            # Try to compile
            compile(test_code, f"{scene_name}.py", "exec")
            return True, []
            
        except SyntaxError as e:
            return False, [f"Compilation syntax error: {str(e)}"]
        except Exception as e:
            return False, [f"Compilation error: {str(e)}"]
    
    def _validate_manimce_scene_class(self, code: str, scene_name: str) -> List[str]:
        """Validate ManimCE scene class structure."""
        issues = []
        
        # Check for proper Scene inheritance
        scene_pattern = rf'class\s+{re.escape(scene_name)}\s*\(\s*Scene\s*\):'
        if not re.search(scene_pattern, code):
            # Check for other valid scene types
            valid_scene_pattern = rf'class\s+{re.escape(scene_name)}\s*\(\s*(Scene|ThreeDScene|MovingCameraScene)\s*\):'
            if not re.search(valid_scene_pattern, code):
                issues.append(f"Scene class '{scene_name}' doesn't properly inherit from Scene")
        
        return issues
    
    def _should_use_claude_for_manimgl(self, confidence: float, issue_count: int, 
                                      risk_count: int, complexity: int) -> bool:
        """Determine if Claude should be used for ManimGL conversion."""
        
        # Always use Claude for low confidence
        if confidence < 0.6:
            return True
        
        # Use Claude for high complexity with issues
        if complexity > 8 and issue_count > 0:
            return True
        
        # Use Claude for multiple risk factors
        if risk_count >= 2:
            return True
        
        # Use Claude for any syntax errors
        if issue_count > 0 and confidence < 0.8:
            return True
        
        return False

# Convenience function for integration with existing pipeline
def validate_pre_conversion(code: str, scene_name: str) -> ValidationResult:
    """Validate ManimGL code before conversion."""
    validator = ComprehensiveValidator()
    return validator.validate_manimgl_code(code, scene_name)

def validate_post_conversion(code: str, scene_name: str) -> ValidationResult:
    """Validate ManimCE code after conversion."""
    validator = ComprehensiveValidator()
    return validator.validate_manimce_code(code, scene_name)