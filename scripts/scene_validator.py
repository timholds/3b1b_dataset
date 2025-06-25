#!/usr/bin/env python3
"""
Scene validation module for checking cleaned scenes before conversion.
This ensures scenes are ready for the next stage of processing.
"""

import ast
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    """Represents a validation issue found in a scene."""
    severity: str  # 'error', 'warning', 'info'
    issue_type: str
    message: str
    line_number: Optional[int] = None
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of validating a scene."""
    scene_name: str
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    dependencies_resolved: bool = True
    imports_complete: bool = True
    syntax_valid: bool = True
    
    def add_issue(self, issue: ValidationIssue):
        self.issues.append(issue)
        if issue.severity == 'error':
            self.is_valid = False


class SceneValidator:
    """Validates cleaned scenes before conversion."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        
        # Known Manim imports that should be present
        self.required_imports = {
            'manimlib': ['from manimlib import *', 'from manimlib.imports import'],
            'numpy': ['import numpy', 'from numpy import'],
            'manim_imports_ext': ['from manim_imports_ext import *']
        }
        
        # Common Manim objects that indicate proper setup
        self.manim_indicators = {
            'Scene', 'ThreeDScene', 'MovingCameraScene', 'ZoomedScene',
            'VMobject', 'Mobject', 'Group', 'VGroup',
            'Circle', 'Square', 'Rectangle', 'Line', 'Arrow',
            'Text', 'TexMobject', 'TextMobject', 'MathTex',
            'Create', 'Write', 'FadeIn', 'FadeOut', 'Transform'
        }
    
    def validate_scene_file(self, scene_path: Path) -> ValidationResult:
        """Validate a single scene file."""
        result = ValidationResult(scene_name=scene_path.stem, is_valid=True)
        
        # Read the file
        try:
            with open(scene_path, 'r') as f:
                content = f.read()
        except Exception as e:
            result.add_issue(ValidationIssue(
                severity='error',
                issue_type='file_read_error',
                message=f"Could not read file: {e}"
            ))
            return result
        
        # Check syntax
        result.syntax_valid = self._check_syntax(content, result)
        if not result.syntax_valid:
            return result  # Can't continue with invalid syntax
        
        # Parse AST for deeper analysis
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            result.add_issue(ValidationIssue(
                severity='error',
                issue_type='parse_error',
                message=f"AST parse error: {e}",
                line_number=e.lineno
            ))
            return result
        
        # Run all validation checks
        self._check_imports(tree, content, result)
        self._check_scene_class(tree, result)
        self._check_dependencies(tree, content, result)
        self._check_common_issues(tree, content, result)
        
        return result
    
    def _check_syntax(self, content: str, result: ValidationResult) -> bool:
        """Check if the code has valid Python syntax."""
        try:
            compile(content, result.scene_name, 'exec')
            return True
        except SyntaxError as e:
            result.add_issue(ValidationIssue(
                severity='error',
                issue_type='syntax_error',
                message=str(e),
                line_number=e.lineno,
                suggestion="Fix the syntax error before proceeding"
            ))
            result.syntax_valid = False
            return False
    
    def _check_imports(self, tree: ast.AST, content: str, result: ValidationResult):
        """Check if necessary imports are present."""
        found_imports = set()
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found_imports.add(f"import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for alias in node.names:
                        if alias.name == '*':
                            found_imports.add(f"from {node.module} import *")
                        else:
                            found_imports.add(f"from {node.module} import {alias.name}")
        
        # Check for required imports
        has_manim_import = any('manimlib' in imp for imp in found_imports)
        
        if not has_manim_import:
            result.add_issue(ValidationIssue(
                severity='error',
                issue_type='missing_import',
                message="No manimlib import found",
                suggestion="Add 'from manimlib import *' at the beginning of the file"
            ))
            result.imports_complete = False
        
        # Check if imports are at the top of the file
        lines = content.split('\n')
        import_lines = []
        for i, line in enumerate(lines):
            if line.strip().startswith(('import ', 'from ')):
                import_lines.append(i)
        
        if import_lines and max(import_lines) > 20:
            non_top_imports = [i for i in import_lines if i > 20]
            if non_top_imports:
                result.add_issue(ValidationIssue(
                    severity='warning',
                    issue_type='import_location',
                    message=f"Imports found after line 20 at lines: {non_top_imports}",
                    suggestion="Move all imports to the top of the file"
                ))
    
    def _check_scene_class(self, tree: ast.AST, result: ValidationResult):
        """Check if the scene class is properly defined."""
        scene_classes = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if it inherits from a Scene class
                for base in node.bases:
                    if isinstance(base, ast.Name) and 'Scene' in base.id:
                        scene_classes.append(node)
                        break
        
        if not scene_classes:
            result.add_issue(ValidationIssue(
                severity='error',
                issue_type='no_scene_class',
                message="No Scene class found in file",
                suggestion="Ensure the file contains a class that inherits from Scene"
            ))
            return
        
        # Check each scene class
        for scene in scene_classes:
            # Check for construct method
            has_construct = False
            for item in scene.body:
                if isinstance(item, ast.FunctionDef) and item.name == 'construct':
                    has_construct = True
                    break
            
            if not has_construct:
                result.add_issue(ValidationIssue(
                    severity='error',
                    issue_type='missing_construct',
                    message=f"Scene class '{scene.name}' has no construct method",
                    suggestion="Add a 'def construct(self):' method to the scene class"
                ))
    
    def _check_dependencies(self, tree: ast.AST, content: str, result: ValidationResult):
        """Check if all referenced names are defined or imported."""
        # Collect all defined names
        defined_names = set()
        imported_names = set()
        
        # Built-in names and common globals
        builtin_names = set(dir(__builtins__))
        common_globals = {'PI', 'TAU', 'DEGREES', 'UP', 'DOWN', 'LEFT', 'RIGHT', 
                         'ORIGIN', 'OUT', 'IN', 'UL', 'UR', 'DL', 'DR'}
        
        # Collect imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.names[0].name == '*':
                    # Star import - we'll assume it provides common names
                    imported_names.update(self.manim_indicators)
                else:
                    for alias in node.names:
                        imported_names.add(alias.asname or alias.name)
        
        # Collect definitions
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                defined_names.add(node.name)
            elif isinstance(node, ast.ClassDef):
                defined_names.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        defined_names.add(target.id)
        
        # Check for undefined names
        undefined_names = set()
        
        class NameChecker(ast.NodeVisitor):
            def visit_Name(self, node):
                if isinstance(node.ctx, ast.Load):
                    name = node.id
                    if (name not in defined_names and 
                        name not in imported_names and
                        name not in builtin_names and
                        name not in common_globals and
                        name != 'self'):
                        undefined_names.add(name)
                self.generic_visit(node)
        
        checker = NameChecker()
        checker.visit(tree)
        
        if undefined_names:
            # Filter out likely false positives
            real_undefined = set()
            for name in undefined_names:
                # Skip if it's likely from a star import
                if name in self.manim_indicators:
                    continue
                # Skip common color names
                if name.endswith(('_A', '_B', '_C', '_D', '_E')) and name[:-2] in ['BLUE', 'RED', 'GREEN', 'YELLOW']:
                    continue
                real_undefined.add(name)
            
            if real_undefined:
                result.add_issue(ValidationIssue(
                    severity='warning',
                    issue_type='undefined_names',
                    message=f"Potentially undefined names: {', '.join(sorted(real_undefined))}",
                    suggestion="Ensure all referenced names are defined or imported"
                ))
                result.dependencies_resolved = False
    
    def _check_common_issues(self, tree: ast.AST, content: str, result: ValidationResult):
        """Check for common issues in cleaned scenes."""
        lines = content.split('\n')
        
        # Check for leftover file reading attempts
        for i, line in enumerate(lines):
            if 'open(' in line and '.py' in line:
                result.add_issue(ValidationIssue(
                    severity='warning',
                    issue_type='file_operation',
                    message=f"File operation found at line {i+1}",
                    line_number=i+1,
                    suggestion="All dependencies should be inlined, not read from files"
                ))
        
        # Check for print statements (should use self.add or similar)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == 'print':
                    result.add_issue(ValidationIssue(
                        severity='info',
                        issue_type='print_statement',
                        message="Print statement found",
                        line_number=node.lineno,
                        suggestion="Consider using self.add(Text(...)) for on-screen text"
                    ))
        
        # Check for very long lines
        for i, line in enumerate(lines):
            if len(line) > 120:
                result.add_issue(ValidationIssue(
                    severity='info',
                    issue_type='long_line',
                    message=f"Line {i+1} is {len(line)} characters long",
                    line_number=i+1,
                    suggestion="Consider breaking long lines for readability"
                ))
    
    def validate_scene_directory(self, scenes_dir: Path) -> Dict[str, ValidationResult]:
        """Validate all scenes in a directory."""
        results = {}
        
        if not scenes_dir.exists():
            logger.error(f"Scenes directory not found: {scenes_dir}")
            return results
        
        scene_files = list(scenes_dir.glob('*.py'))
        logger.info(f"Validating {len(scene_files)} scene files...")
        
        for scene_file in scene_files:
            if self.verbose:
                logger.info(f"Validating {scene_file.name}...")
            
            result = self.validate_scene_file(scene_file)
            results[scene_file.stem] = result
            
            if not result.is_valid:
                logger.warning(f"{scene_file.name}: {len(result.issues)} issues found")
        
        return results
    
    def generate_validation_report(self, results: Dict[str, ValidationResult]) -> str:
        """Generate a human-readable validation report."""
        report_lines = ["Scene Validation Report", "=" * 50, ""]
        
        total_scenes = len(results)
        valid_scenes = sum(1 for r in results.values() if r.is_valid)
        
        report_lines.append(f"Total scenes: {total_scenes}")
        report_lines.append(f"Valid scenes: {valid_scenes}")
        report_lines.append(f"Invalid scenes: {total_scenes - valid_scenes}")
        report_lines.append("")
        
        # Group by issue type
        issue_counts = {}
        for result in results.values():
            for issue in result.issues:
                key = f"{issue.severity}:{issue.issue_type}"
                issue_counts[key] = issue_counts.get(key, 0) + 1
        
        if issue_counts:
            report_lines.append("Issue Summary:")
            for issue_type, count in sorted(issue_counts.items()):
                severity, itype = issue_type.split(':', 1)
                report_lines.append(f"  {severity.upper()} - {itype}: {count}")
            report_lines.append("")
        
        # Detailed issues for invalid scenes
        invalid_scenes = [(name, result) for name, result in results.items() if not result.is_valid]
        
        if invalid_scenes:
            report_lines.append("Invalid Scenes:")
            report_lines.append("-" * 50)
            
            for scene_name, result in invalid_scenes:
                report_lines.append(f"\n{scene_name}:")
                for issue in result.issues:
                    if issue.severity == 'error':
                        line_info = f" (line {issue.line_number})" if issue.line_number else ""
                        report_lines.append(f"  ERROR: {issue.message}{line_info}")
                        if issue.suggestion:
                            report_lines.append(f"    → {issue.suggestion}")
        
        return '\n'.join(report_lines)