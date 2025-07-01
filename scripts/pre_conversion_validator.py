#!/usr/bin/env python3
"""
Pre-Conversion Validator - Static Analysis for ManimGL Code

This module performs static analysis on ManimGL code BEFORE conversion
to identify potential issues and provide actionable guidance.

Key Features:
- AST-based analysis to detect problematic patterns
- Import usage validation
- Animation sequence validation
- Confidence scoring for conversion likelihood
- Detailed issue reporting with suggested fixes
"""

import ast
import logging
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

# Import our API mappings
from scripts.api_mappings import (
    is_removed_api, get_class_mapping, get_method_info,
    get_parameter_changes, should_be_property, CLASS_MAPPINGS,
    REMOVED_APIS, BEHAVIOR_CHANGES
)

logger = logging.getLogger(__name__)


class IssueSeverity(Enum):
    """Severity levels for validation issues."""
    ERROR = "error"      # Will definitely fail
    WARNING = "warning"  # Might fail or behave differently
    INFO = "info"       # Should be aware but likely ok
    

@dataclass
class ValidationIssue:
    """Represents a single validation issue."""
    severity: IssueSeverity
    line: int
    column: int
    issue_type: str
    message: str
    suggestion: Optional[str] = None
    confidence: float = 1.0  # How confident we are this is an issue


@dataclass 
class ValidationResult:
    """Result of pre-conversion validation."""
    is_valid: bool
    issues: List[ValidationIssue]
    conversion_confidence: float  # 0-1 score of likely success
    statistics: Dict[str, Any]
    

class PreConversionValidator:
    """Validates ManimGL code before conversion to predict issues."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.issues: List[ValidationIssue] = []
        self.stats = {
            'total_lines': 0,
            'import_count': 0,
            'class_count': 0,
            'method_count': 0,
            'removed_api_calls': 0,
            'deprecated_patterns': 0,
            'complex_animations': 0
        }
        
    def validate_code(self, code: str, filename: str = "unknown") -> ValidationResult:
        """Validate ManimGL code and return detailed results."""
        self.issues = []
        self.stats = {k: 0 for k in self.stats}  # Reset stats
        
        try:
            tree = ast.parse(code)
            self.stats['total_lines'] = len(code.splitlines())
        except SyntaxError as e:
            # Syntax error means we can't analyze
            self.issues.append(ValidationIssue(
                severity=IssueSeverity.ERROR,
                line=e.lineno or 0,
                column=e.offset or 0,
                issue_type="syntax_error",
                message=f"Syntax error: {e.msg}",
                suggestion="Fix syntax errors before conversion"
            ))
            return self._create_result()
            
        # Run all validation checks
        self._check_imports(tree)
        self._check_removed_apis(tree)
        self._check_class_usage(tree)
        self._check_method_calls(tree)
        self._check_animation_patterns(tree)
        self._check_property_access(tree)
        self._check_parameter_usage(tree)
        self._check_complex_patterns(tree)
        
        return self._create_result()
    
    def _check_imports(self, tree: ast.AST):
        """Check import statements for issues."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                self.stats['import_count'] += 1
                
                # Check for manimlib imports
                if node.module and 'manimlib' in node.module:
                    # This is expected, just note it
                    pass
                    
                # Check for specific problematic imports
                if node.module == 'manimlib.imports':
                    for alias in node.names:
                        if alias.name == '*':
                            continue
                        # Check if imported item is removed
                        if is_removed_api(alias.name, 'classes'):
                            self.issues.append(ValidationIssue(
                                severity=IssueSeverity.ERROR,
                                line=node.lineno,
                                column=node.col_offset,
                                issue_type="removed_import",
                                message=f"Importing removed class: {alias.name}",
                                suggestion=f"Class {alias.name} doesn't exist in ManimCE"
                            ))
    
    def _check_removed_apis(self, tree: ast.AST):
        """Check for usage of removed APIs."""
        for node in ast.walk(tree):
            # Check class instantiation
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    class_name = node.func.id
                    if is_removed_api(class_name, 'classes'):
                        self.stats['removed_api_calls'] += 1
                        mapping = get_class_mapping(class_name)
                        if mapping != class_name:
                            suggestion = f"Replace {class_name} with {mapping}"
                        else:
                            suggestion = f"{class_name} has been removed with no direct replacement"
                            
                        self.issues.append(ValidationIssue(
                            severity=IssueSeverity.ERROR,
                            line=node.lineno,
                            column=node.col_offset,
                            issue_type="removed_class",
                            message=f"Using removed class: {class_name}",
                            suggestion=suggestion
                        ))
            
            # Check method calls
            elif isinstance(node, ast.Attribute):
                if is_removed_api(node.attr, 'methods'):
                    self.stats['removed_api_calls'] += 1
                    self.issues.append(ValidationIssue(
                        severity=IssueSeverity.ERROR,
                        line=node.lineno,
                        column=node.col_offset,
                        issue_type="removed_method",
                        message=f"Using removed method: {node.attr}",
                        suggestion="This method no longer exists in ManimCE"
                    ))
    
    def _check_class_usage(self, tree: ast.AST):
        """Check class definitions and usage."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                self.stats['class_count'] += 1
                
                # Check base classes
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        base_name = base.id
                        # Check if inheriting from removed class
                        if is_removed_api(base_name, 'classes'):
                            self.issues.append(ValidationIssue(
                                severity=IssueSeverity.ERROR,
                                line=node.lineno,
                                column=node.col_offset,
                                issue_type="removed_base_class",
                                message=f"Inheriting from removed class: {base_name}",
                                suggestion=f"Use {get_class_mapping(base_name)} instead"
                            ))
                        # Check for classes that behave differently
                        elif base_name in ['GraphScene', 'ThreeDScene', 'MovingCameraScene']:
                            self.issues.append(ValidationIssue(
                                severity=IssueSeverity.WARNING,
                                line=node.lineno,
                                column=node.col_offset,
                                issue_type="changed_base_class",
                                message=f"{base_name} has significant API changes in ManimCE",
                                suggestion="Review the ManimCE documentation for this class"
                            ))
    
    def _check_method_calls(self, tree: ast.AST):
        """Check method calls for compatibility."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    method_name = node.func.attr
                    self.stats['method_count'] += 1
                    
                    # Check for methods that should be properties
                    if should_be_property(method_name):
                        self.issues.append(ValidationIssue(
                            severity=IssueSeverity.WARNING,
                            line=node.lineno,
                            column=node.col_offset,
                            issue_type="method_to_property",
                            message=f"{method_name}() is now a property in ManimCE",
                            suggestion=f"Remove parentheses: use .{method_name[4:]} instead of .{method_name}()"
                        ))
                    
                    # Check for specific problematic method patterns
                    if method_name == 'set_submobjects':
                        self.issues.append(ValidationIssue(
                            severity=IssueSeverity.WARNING,
                            line=node.lineno,
                            column=node.col_offset,
                            issue_type="api_behavior_change",
                            message="set_submobjects behavior may differ in ManimCE",
                            suggestion="Verify the parameter handling matches expectations"
                        ))
    
    def _check_animation_patterns(self, tree: ast.AST):
        """Check animation usage patterns."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr == 'play':
                    self._analyze_play_call(node)
                    
                # Check for complex animation patterns
                if isinstance(node.func, ast.Name) and node.func.id in CLASS_MAPPINGS:
                    # Animation class being instantiated
                    if len(node.args) > 2 or len(node.keywords) > 3:
                        self.stats['complex_animations'] += 1
                        self.issues.append(ValidationIssue(
                            severity=IssueSeverity.INFO,
                            line=node.lineno,
                            column=node.col_offset,
                            issue_type="complex_animation",
                            message=f"Complex {node.func.id} with many parameters",
                            suggestion="Verify all parameters are supported in ManimCE",
                            confidence=0.7
                        ))
    
    def _check_property_access(self, tree: ast.AST):
        """Check for property access that might fail."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                # Look for patterns like obj.width where width might not exist
                attr_name = node.attr
                
                # Check for direct property access that might fail
                if attr_name in ['width', 'height', 'depth', 'center']:
                    # These are properties in ManimCE but might be accessed wrong
                    parent = self._get_parent_node(tree, node)
                    if isinstance(parent, ast.Call):
                        # They're trying to call it like a method
                        self.issues.append(ValidationIssue(
                            severity=IssueSeverity.WARNING,
                            line=node.lineno,
                            column=node.col_offset,
                            issue_type="property_as_method",
                            message=f"Accessing property {attr_name} as method",
                            suggestion=f"Use .{attr_name} without parentheses"
                        ))
    
    def _check_parameter_usage(self, tree: ast.AST):
        """Check for problematic parameter usage."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    class_name = node.func.id
                    
                    # Check Tex/MathTex size parameter
                    if class_name in ['Tex', 'TexMobject', 'MathTex']:
                        for keyword in node.keywords:
                            if keyword.arg == 'size':
                                self.issues.append(ValidationIssue(
                                    severity=IssueSeverity.ERROR,
                                    line=node.lineno,
                                    column=node.col_offset,
                                    issue_type="removed_parameter",
                                    message=f"{class_name} no longer accepts 'size' parameter",
                                    suggestion="Remove size parameter and use .scale() after creation"
                                ))
                    
                    # Check Text/TextMobject parameters
                    elif class_name in ['Text', 'TextMobject']:
                        param_changes = get_parameter_changes(f'{class_name}.__init__')
                        if param_changes:
                            for keyword in node.keywords:
                                if keyword.arg in param_changes.get('removed', []):
                                    self.issues.append(ValidationIssue(
                                        severity=IssueSeverity.ERROR,
                                        line=node.lineno,
                                        column=node.col_offset,
                                        issue_type="removed_parameter",
                                        message=f"{class_name} parameter '{keyword.arg}' removed",
                                        suggestion=param_changes.get('notes', '')
                                    ))
    
    def _check_complex_patterns(self, tree: ast.AST):
        """Check for complex patterns that might cause issues."""
        for node in ast.walk(tree):
            # Check for updater patterns
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr == 'add_updater':
                    self.stats['deprecated_patterns'] += 1
                    self.issues.append(ValidationIssue(
                        severity=IssueSeverity.WARNING,
                        line=node.lineno,
                        column=node.col_offset,
                        issue_type="updater_api_change",
                        message="Updater API has changed significantly",
                        suggestion="Ensure updater function has dt parameter",
                        confidence=0.8
                    ))
            
            # Check for coordinate system usage
            if isinstance(node, ast.Attribute):
                if node.attr in ['x_axis', 'y_axis', 'coords_to_point', 'point_to_coords']:
                    self.issues.append(ValidationIssue(
                        severity=IssueSeverity.INFO,
                        line=node.lineno,
                        column=node.col_offset,
                        issue_type="coordinate_api",
                        message="Coordinate system APIs may behave differently",
                        suggestion="Test coordinate transformations carefully",
                        confidence=0.6
                    ))
    
    def _analyze_play_call(self, node: ast.Call):
        """Analyze a play() call for potential issues."""
        # Check for chained animations or complex patterns
        if len(node.args) > 3:
            self.stats['complex_animations'] += 1
            self.issues.append(ValidationIssue(
                severity=IssueSeverity.INFO,
                line=node.lineno,
                column=node.col_offset,
                issue_type="complex_play_call",
                message="Complex play() call with many animations",
                suggestion="Verify animation timing and sequencing",
                confidence=0.5
            ))
    
    def _get_parent_node(self, tree: ast.AST, node: ast.AST) -> Optional[ast.AST]:
        """Get the parent node of a given node."""
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                if child == node:
                    return parent
        return None
    
    def _create_result(self) -> ValidationResult:
        """Create the final validation result."""
        # Calculate conversion confidence
        error_count = sum(1 for i in self.issues if i.severity == IssueSeverity.ERROR)
        warning_count = sum(1 for i in self.issues if i.severity == IssueSeverity.WARNING)
        
        # Simple confidence calculation
        if error_count > 5:
            confidence = 0.1
        elif error_count > 0:
            confidence = 0.3 - (error_count * 0.05)
        elif warning_count > 10:
            confidence = 0.6
        elif warning_count > 0:
            confidence = 0.8 - (warning_count * 0.02)
        else:
            confidence = 0.95
            
        confidence = max(0.0, min(1.0, confidence))
        
        return ValidationResult(
            is_valid=error_count == 0,
            issues=self.issues,
            conversion_confidence=confidence,
            statistics=self.stats
        )
    
    def generate_report(self, result: ValidationResult) -> str:
        """Generate a human-readable validation report."""
        lines = []
        lines.append("Pre-Conversion Validation Report")
        lines.append("=" * 50)
        lines.append(f"Conversion Confidence: {result.conversion_confidence:.1%}")
        lines.append(f"Status: {'✓ Ready' if result.is_valid else '✗ Issues Found'}")
        lines.append("")
        
        # Statistics
        lines.append("Statistics:")
        for key, value in result.statistics.items():
            lines.append(f"  {key}: {value}")
        lines.append("")
        
        # Issues by severity
        if result.issues:
            lines.append("Issues Found:")
            
            errors = [i for i in result.issues if i.severity == IssueSeverity.ERROR]
            warnings = [i for i in result.issues if i.severity == IssueSeverity.WARNING]
            infos = [i for i in result.issues if i.severity == IssueSeverity.INFO]
            
            if errors:
                lines.append(f"\nERRORS ({len(errors)}):")
                for issue in errors[:10]:  # Show first 10
                    lines.append(f"  Line {issue.line}: {issue.message}")
                    if issue.suggestion:
                        lines.append(f"    → {issue.suggestion}")
                if len(errors) > 10:
                    lines.append(f"  ... and {len(errors) - 10} more errors")
            
            if warnings:
                lines.append(f"\nWARNINGS ({len(warnings)}):")
                for issue in warnings[:5]:  # Show first 5
                    lines.append(f"  Line {issue.line}: {issue.message}")
                    if issue.suggestion:
                        lines.append(f"    → {issue.suggestion}")
                if len(warnings) > 5:
                    lines.append(f"  ... and {len(warnings) - 5} more warnings")
            
            if infos and len(errors) + len(warnings) < 10:
                lines.append(f"\nINFO ({len(infos)}):")
                for issue in infos[:3]:  # Show first 3
                    lines.append(f"  Line {issue.line}: {issue.message}")
        else:
            lines.append("No issues found! Code appears ready for conversion.")
        
        return "\n".join(lines)


def validate_file(file_path: Path, verbose: bool = False) -> ValidationResult:
    """Validate a single file."""
    validator = PreConversionValidator(verbose=verbose)
    
    with open(file_path, 'r') as f:
        code = f.read()
    
    return validator.validate_code(code, str(file_path))


if __name__ == "__main__":
    # Test validation
    test_code = '''
from manimlib.imports import *

class TestScene(Scene):
    def construct(self):
        # This will have issues
        text = TextMobject("Hello", size=2)
        circle = Circle()
        
        # Removed animation
        self.play(ShowCreation(circle))
        
        # Property access issue  
        width = circle.get_width()
        
        # Removed method
        boundary = circle.get_points_defining_boundary()
        
        # Complex updater
        circle.add_updater(lambda m: m.move_to(text))
    '''
    
    validator = PreConversionValidator(verbose=True)
    result = validator.validate_code(test_code)
    print(validator.generate_report(result))