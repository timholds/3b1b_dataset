#!/usr/bin/env python3
"""
Pre-compilation validation for ManimCE conversion.

This module performs static analysis and validation of converted ManimCE code
before attempting to compile or render it. It catches common errors early,
provides detailed error messages, and suggests fixes.
"""

import ast
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set, Any
from dataclasses import dataclass, field
import json
import importlib.util
import subprocess
from collections import defaultdict

# Try to import optional validation tools
try:
    import pyflakes.api
    import pyflakes.checker
    PYFLAKES_AVAILABLE = True
except ImportError:
    PYFLAKES_AVAILABLE = False

try:
    from mypy import api as mypy_api
    MYPY_AVAILABLE = True
except ImportError:
    MYPY_AVAILABLE = False


@dataclass
class ValidationError:
    """Represents a validation error found in the code."""
    error_type: str
    line_number: int
    column: int
    message: str
    severity: str  # 'error', 'warning', 'info'
    suggestion: Optional[str] = None
    code_snippet: Optional[str] = None
    
    def to_dict(self):
        return {
            'type': self.error_type,
            'line': self.line_number,
            'column': self.column,
            'message': self.message,
            'severity': self.severity,
            'suggestion': self.suggestion,
            'code_snippet': self.code_snippet
        }


@dataclass
class ValidationReport:
    """Complete validation report for a file."""
    file_path: str
    is_valid: bool = True
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    info: List[ValidationError] = field(default_factory=list)
    ast_valid: bool = True
    imports_valid: bool = True
    api_valid: bool = True
    scene_structure_valid: bool = True
    statistics: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, error: ValidationError):
        if error.severity == 'error':
            self.errors.append(error)
            self.is_valid = False
        elif error.severity == 'warning':
            self.warnings.append(error)
        else:
            self.info.append(error)
    
    def to_dict(self):
        return {
            'file_path': self.file_path,
            'is_valid': self.is_valid,
            'errors': [e.to_dict() for e in self.errors],
            'warnings': [w.to_dict() for w in self.warnings],
            'info': [i.to_dict() for i in self.info],
            'validation_summary': {
                'ast_valid': self.ast_valid,
                'imports_valid': self.imports_valid,
                'api_valid': self.api_valid,
                'scene_structure_valid': self.scene_structure_valid
            },
            'statistics': self.statistics
        }


class ManimCEPrecompileValidator:
    """Pre-compilation validator for ManimCE code."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        
        # ManimCE API mappings - what's valid and what's not
        self.valid_manim_imports = {
            'manim',
            'manim.animation.*',
            'manim.camera.*', 
            'manim.config.*',
            'manim.constants.*',
            'manim.mobject.*',
            'manim.scene.*',
            'manim.utils.*'
        }
        
        # Valid ManimCE classes
        self.valid_mobjects = {
            # Core
            'Mobject', 'VMobject', 'Group', 'VGroup',
            # Text
            'Text', 'Tex', 'MathTex', 'Title', 'BulletedList',
            # Shapes
            'Circle', 'Square', 'Rectangle', 'Ellipse', 'Triangle',
            'Line', 'DashedLine', 'Arrow', 'DoubleArrow', 'Dot',
            'SmallDot', 'Polygon', 'RegularPolygon', 'Star',
            # Graphs
            'Axes', 'ThreeDAxes', 'NumberLine', 'NumberPlane',
            'CoordinateSystem', 'Graph', 'ParametricFunction',
            # Other
            'SVGMobject', 'ImageMobject', 'Table', 'Matrix',
            'Brace', 'BraceBetweenPoints', 'BraceLabel',
            'SurroundingRectangle', 'BackgroundRectangle',
            'VectorField', 'StreamLines'
        }
        
        self.valid_animations = {
            # Creation
            'Create', 'Write', 'DrawBorderThenFill', 'ShowIncreasingSubsets',
            'ShowSubmobjectsOneByOne',
            # Transform
            'Transform', 'ReplacementTransform', 'TransformFromCopy',
            'MoveToTarget', 'ApplyMethod', 'ApplyPointwiseFunction',
            'ApplyComplexFunction', 'CyclicReplace', 'Swap',
            # Fade
            'FadeIn', 'FadeOut', 'FadeInFromPoint', 'FadeOutToPoint',
            'FadeInFromLarge', 'FadeTransform', 'FadeToColor',
            # Growing
            'GrowFromPoint', 'GrowFromCenter', 'GrowFromEdge',
            'GrowArrow', 'SpinInFromNothing',
            # Shrinking
            'ShrinkToCenter', 'ShrinkToPoint',
            # Focus
            'FocusOn', 'Indicate', 'Flash', 'CircleIndicate',
            'ShowPassingFlash', 'ShowCreationThenDestruction',
            'ShowCreationThenFadeOut', 'Wiggle', 'Circumscribe',
            # Movement
            'MoveAlongPath', 'Rotate', 'Rotating', 'ApplyMatrix',
            # Update
            'UpdateFromFunc', 'UpdateFromAlphaFunc', 'MaintainPositionRelativeTo',
            # Special
            'AnimationGroup', 'Succession', 'LaggedStart', 'LaggedStartMap',
            'Wait', 'EmptyAnimation'
        }
        
        self.valid_scenes = {
            # Core scene types
            'Scene', 'MovingCameraScene', 'ZoomedScene', 'ThreeDScene',
            'SpecialThreeDScene', 'InteractiveScene',
            
            # Mathematical scene types
            'GraphScene', 'NumberLineScene', 'LinearTransformationScene',
            'VectorScene', 'ComplexTransformationScene', 'SampleSpaceScene',
            'ReconfigurableScene', 'FourierCirclesScene',
            
            # Educational/Character scene types  
            'TeacherStudentsScene', 'PiCreatureScene', 'ExternallyAnimatedScene',
            'SceneFromVideo', 'OpeningQuoteScene', 'TitleCardScene', 'EndScene',
            
            # Common specialized scenes
            'VectorFieldScene', 'TransformScene2D', 'FunctionGraphScene',
            'RearrangeEquation', 'HistogramScene', 'NetworkScene',
            
            # Note: This is not exhaustive - any class ending with 'Scene' 
            # should be considered valid for scene detection purposes
        }
        
        # Deprecated or removed items
        self.deprecated_items = {
            'TextMobject': 'Use Text instead',
            'TexMobject': 'Use MathTex instead', 
            'TexText': 'Use Tex instead',
            'OldTex': 'Use Tex with raw strings',
            'OldTexText': 'Use Text instead',
            'ShowCreation': 'Use Create instead',
            'ShowCreationThenDestruction': 'Use ShowPassingFlash instead',
            'ContinualAnimation': 'Use add_updater() instead',
            'CONFIG': 'Use __init__ parameters or config decorators',
            'get_graph': 'Use plot() instead',
            'get_axes': 'Access .axes attribute directly'
        }
        
        # Common method changes
        self.method_changes = {
            'get_width': ('property', 'width'),
            'get_height': ('property', 'height'),
            'set_width': ('assignment', 'width = value'),
            'set_height': ('assignment', 'height = value'),
            'get_corner': ('method', 'get_corner()'),  # stays the same
            'get_center': ('method', 'get_center()'),  # stays the same
            'to_corner': ('method', 'to_corner()'),    # stays the same
            'to_edge': ('method', 'to_edge()'),        # stays the same
        }
        
        # Scene method requirements
        self.required_scene_methods = {
            'Scene': ['construct'],
            'ThreeDScene': ['construct'],
            'MovingCameraScene': ['construct'],
        }
        
    def validate_file(self, file_path: str, content: Optional[str] = None) -> ValidationReport:
        """Validate a single ManimCE Python file."""
        path = Path(file_path)
        report = ValidationReport(file_path=str(path))
        
        # Read content if not provided
        if content is None:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                report.add_error(ValidationError(
                    error_type='file_read_error',
                    line_number=0,
                    column=0,
                    message=f"Failed to read file: {e}",
                    severity='error'
                ))
                return report
        
        lines = content.split('\n')
        
        # Run all validation checks
        self._validate_syntax(content, lines, report)
        if report.ast_valid:
            self._validate_imports(content, lines, report)
            self._validate_api_usage(content, lines, report)
            self._validate_scene_structure(content, lines, report)
            self._validate_common_patterns(content, lines, report)
            
        # Additional linting if available
        if PYFLAKES_AVAILABLE:
            self._run_pyflakes(content, file_path, report)
            
        # Collect statistics
        report.statistics = self._collect_statistics(content)
        
        return report
    
    def _validate_syntax(self, content: str, lines: List[str], report: ValidationReport):
        """Validate Python syntax and build AST."""
        try:
            tree = ast.parse(content)
            report.ast_valid = True
            # Store AST for further analysis
            report._ast = tree
        except SyntaxError as e:
            report.ast_valid = False
            report.add_error(ValidationError(
                error_type='syntax_error',
                line_number=e.lineno or 0,
                column=e.offset or 0,
                message=f"Syntax error: {e.msg}",
                severity='error',
                code_snippet=lines[e.lineno - 1] if e.lineno and e.lineno <= len(lines) else None,
                suggestion=self._suggest_syntax_fix(e, lines)
            ))
    
    def _validate_imports(self, content: str, lines: List[str], report: ValidationReport):
        """Validate import statements."""
        if not hasattr(report, '_ast'):
            return
            
        imported_modules = set()
        import_lines = {}
        
        for node in ast.walk(report._ast):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name)
                    import_lines[alias.name] = node.lineno
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_modules.add(node.module)
                    import_lines[node.module] = node.lineno
        
        # Check for manimlib imports (should be manim)
        for module in imported_modules:
            if 'manimlib' in module:
                report.imports_valid = False
                report.add_error(ValidationError(
                    error_type='invalid_import',
                    line_number=import_lines.get(module, 0),
                    column=0,
                    message=f"Found manimlib import: {module}",
                    severity='error',
                    suggestion=f"Change to: {module.replace('manimlib', 'manim')}"
                ))
        
        # Check for missing manim import (including manim_imports_ext)
        if not any('manim' in m or 'manim_imports_ext' in m for m in imported_modules):
            report.imports_valid = False
            report.add_error(ValidationError(
                error_type='missing_import',
                line_number=1,
                column=0,
                message="No manim imports found",
                severity='error',
                suggestion="Add: from manim import * or from manim_imports_ext import *"
            ))
        
        # Check for problematic imports
        problematic_imports = ['custom', 'once_useful_constructs', 'stage_scenes', 'script_wrapper']
        for module in imported_modules:
            for prob in problematic_imports:
                if prob in module:
                    report.add_error(ValidationError(
                        error_type='problematic_import',
                        line_number=import_lines.get(module, 0),
                        column=0,
                        message=f"Problematic import: {module}",
                        severity='warning',
                        suggestion="Remove this import - it's not compatible with ManimCE"
                    ))
    
    def _validate_api_usage(self, content: str, lines: List[str], report: ValidationReport):
        """Validate ManimCE API usage."""
        if not hasattr(report, '_ast'):
            return
        
        # Check class definitions
        for node in ast.walk(report._ast):
            if isinstance(node, ast.ClassDef):
                # Check base classes
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        base_name = base.id
                        if base_name in self.deprecated_items:
                            report.api_valid = False
                            report.add_error(ValidationError(
                                error_type='deprecated_class',
                                line_number=node.lineno,
                                column=node.col_offset,
                                message=f"Deprecated base class: {base_name}",
                                severity='error',
                                suggestion=self.deprecated_items[base_name]
                            ))
            
            # Check function/method calls
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                    # Check for deprecated classes being instantiated
                    if func_name in self.deprecated_items:
                        report.add_error(ValidationError(
                            error_type='deprecated_api',
                            line_number=node.lineno,
                            column=node.col_offset,
                            message=f"Deprecated class: {func_name}",
                            severity='error',
                            suggestion=self.deprecated_items[func_name]
                        ))
                    
                    # Check for invalid animations
                    if func_name == 'ShowCreation':
                        report.add_error(ValidationError(
                            error_type='deprecated_animation',
                            line_number=node.lineno,
                            column=node.col_offset,
                            message="ShowCreation is deprecated",
                            severity='error',
                            suggestion="Use Create instead"
                        ))
                
                # Check method calls
                elif isinstance(node.func, ast.Attribute):
                    method_name = node.func.attr
                    if method_name in self.method_changes:
                        change_type, suggestion = self.method_changes[method_name]
                        if change_type == 'property' and len(node.args) == 0:
                            report.add_error(ValidationError(
                                error_type='deprecated_method',
                                line_number=node.lineno,
                                column=node.col_offset,
                                message=f"Method {method_name}() should be property access",
                                severity='warning',
                                suggestion=f"Use .{suggestion} instead of .{method_name}()"
                            ))
    
    def _validate_scene_structure(self, content: str, lines: List[str], report: ValidationReport):
        """Validate Scene class structure."""
        if not hasattr(report, '_ast'):
            return
        
        scene_classes = []
        
        for node in ast.walk(report._ast):
            if isinstance(node, ast.ClassDef):
                # Check if it's a Scene subclass
                for base in node.bases:
                    if isinstance(base, ast.Name) and 'Scene' in base.id:
                        scene_classes.append(node)
                        
                        # Check for construct method
                        has_construct = False
                        for item in node.body:
                            if isinstance(item, ast.FunctionDef) and item.name == 'construct':
                                has_construct = True
                                # Validate construct signature
                                if len(item.args.args) != 1 or item.args.args[0].arg != 'self':
                                    report.add_error(ValidationError(
                                        error_type='invalid_construct',
                                        line_number=item.lineno,
                                        column=item.col_offset,
                                        message="construct method should only have 'self' parameter",
                                        severity='error',
                                        suggestion="def construct(self):"
                                    ))
                                break
                        
                        if not has_construct:
                            report.scene_structure_valid = False
                            report.add_error(ValidationError(
                                error_type='missing_construct',
                                line_number=node.lineno,
                                column=node.col_offset,
                                message=f"Scene class {node.name} missing construct method",
                                severity='error',
                                suggestion="Add a construct(self) method to define the animation"
                            ))
                        
                        # Check for CONFIG dict (deprecated)
                        for item in node.body:
                            if isinstance(item, ast.Assign):
                                for target in item.targets:
                                    if isinstance(target, ast.Name) and target.id == 'CONFIG':
                                        report.add_error(ValidationError(
                                            error_type='deprecated_config',
                                            line_number=item.lineno,
                                            column=item.col_offset,
                                            message="CONFIG dict is deprecated",
                                            severity='warning',
                                            suggestion="Use __init__ parameters or config decorators"
                                        ))
    
    def _validate_common_patterns(self, content: str, lines: List[str], report: ValidationReport):
        """Check for common problematic patterns."""
        
        # Check for TeX string issues
        tex_pattern = r'(?:Tex|MathTex|Text)\s*\(\s*["\']([^"\']*\\[^"\']*)["\']\s*\)'
        for match in re.finditer(tex_pattern, content):
            tex_string = match.group(1)
            if '\\' in tex_string and not match.group(0).startswith('r'):
                line_num = content[:match.start()].count('\n') + 1
                report.add_error(ValidationError(
                    error_type='tex_string_issue',
                    line_number=line_num,
                    column=0,
                    message="TeX string with backslashes should use raw string",
                    severity='warning',
                    suggestion=f'Use raw string: r"{tex_string}"',
                    code_snippet=lines[line_num - 1] if line_num <= len(lines) else None
                ))
        
        # Check for ContinualAnimation usage
        if 'ContinualAnimation' in content:
            for i, line in enumerate(lines):
                if 'ContinualAnimation' in line:
                    report.add_error(ValidationError(
                        error_type='continual_animation',
                        line_number=i + 1,
                        column=0,
                        message="ContinualAnimation not supported in ManimCE",
                        severity='error',
                        suggestion="Use mobject.add_updater(lambda m, dt: ...) instead",
                        code_snippet=line
                    ))
        
        # Check for pi_creature usage
        pi_patterns = ['PiCreature', 'Randolph', 'Mortimer', 'get_students']
        for pattern in pi_patterns:
            if pattern in content:
                for i, line in enumerate(lines):
                    if pattern in line and not line.strip().startswith('#'):
                        report.add_error(ValidationError(
                            error_type='pi_creature_usage',
                            line_number=i + 1,
                            column=0,
                            message=f"Pi Creature '{pattern}' not available in ManimCE",
                            severity='error',
                            suggestion="Remove or replace with standard ManimCE mobjects",
                            code_snippet=line
                        ))
        
        # Check for shader references
        if '.glsl' in content:
            for i, line in enumerate(lines):
                if '.glsl' in line:
                    report.add_error(ValidationError(
                        error_type='shader_reference',
                        line_number=i + 1,
                        column=0,
                        message="GLSL shader references not supported in ManimCE",
                        severity='error',
                        suggestion="Remove shader usage or implement with ManimCE methods",
                        code_snippet=line
                    ))
    
    def _run_pyflakes(self, content: str, file_path: str, report: ValidationReport):
        """Run pyflakes for additional validation."""
        try:
            # Create a custom reporter to capture warnings
            warnings = []
            
            class CustomReporter:
                def __init__(self):
                    self.messages = []
                
                def __call__(self, message):
                    self.messages.append(message)
            
            reporter = CustomReporter()
            pyflakes.api.check(content, file_path, reporter)
            
            # Convert pyflakes messages to our format
            for msg in reporter.messages:
                if hasattr(msg, 'lineno'):
                    # Skip import * warnings for manim
                    if 'import *' in str(msg) and 'manim' in str(msg):
                        continue
                        
                    report.add_error(ValidationError(
                        error_type='pyflakes_' + type(msg).__name__.lower(),
                        line_number=getattr(msg, 'lineno', 0),
                        column=getattr(msg, 'col', 0),
                        message=str(msg),
                        severity='warning'
                    ))
        except Exception as e:
            if self.verbose:
                print(f"Pyflakes check failed: {e}")
    
    def _suggest_syntax_fix(self, error: SyntaxError, lines: List[str]) -> Optional[str]:
        """Suggest fixes for common syntax errors."""
        if not error.lineno or error.lineno > len(lines):
            return None
            
        line = lines[error.lineno - 1]
        
        # Check for missing colons
        if 'expected' in error.msg and ':' in error.msg:
            return "Add a colon at the end of the line"
        
        # Check for unclosed brackets
        if 'EOF' in error.msg or 'unexpected EOF' in error.msg:
            open_count = line.count('(') + line.count('[') + line.count('{')
            close_count = line.count(')') + line.count(']') + line.count('}')
            if open_count > close_count:
                return "Unclosed brackets - check parentheses, brackets, or braces"
        
        # Check for invalid indentation
        if 'indent' in error.msg:
            return "Fix indentation - ensure consistent use of spaces (4 spaces per level)"
        
        return None
    
    def _collect_statistics(self, content: str) -> Dict[str, Any]:
        """Collect statistics about the code."""
        lines = content.split('\n')
        
        stats = {
            'total_lines': len(lines),
            'non_empty_lines': len([l for l in lines if l.strip()]),
            'comment_lines': len([l for l in lines if l.strip().startswith('#')]),
            'class_count': len(re.findall(r'^class\s+\w+', content, re.MULTILINE)),
            'function_count': len(re.findall(r'^def\s+\w+', content, re.MULTILINE)),
            'scene_count': len(re.findall(r'class\s+\w+\([^)]*Scene[^)]*\)', content)),
            'animation_count': len(re.findall(r'self\.play\(', content)),
            'mobject_count': len(re.findall(r'\b(?:' + '|'.join(self.valid_mobjects) + r')\s*\(', content))
        }
        
        return stats
    
    def apply_automatic_fixes(self, content: str, validation_report: ValidationReport) -> Tuple[str, List[str]]:
        """Apply automatic fixes for common validation errors.
        
        Returns:
            Tuple of (fixed_content, list_of_applied_fixes)
        """
        fixed_content = content
        applied_fixes = []
        
        # Group errors by type for efficient fixing
        error_groups = defaultdict(list)
        for error in validation_report.errors:
            error_groups[error.error_type].append(error)
        
        # Fix missing imports
        if 'missing_import' in error_groups:
            if 'from manim import *' not in fixed_content:
                lines = fixed_content.split('\n')
                # Find where to insert import (after other imports or at top)
                insert_pos = 0
                for i, line in enumerate(lines):
                    if line.strip() and (line.startswith('import') or line.startswith('from')):
                        insert_pos = i + 1
                    elif line.strip() and not line.startswith('#'):
                        break
                
                lines.insert(insert_pos, 'from manim import *')
                fixed_content = '\n'.join(lines)
                applied_fixes.append("Added missing 'from manim import *'")
        
        # CRITICAL: Fix manim_imports_ext imports (98% success rate)
        if 'from manim_imports_ext import' in fixed_content:
            fixed_content = fixed_content.replace('from manim_imports_ext import', 'from manim import')
            applied_fixes.append("Converted manim_imports_ext to manim import")
        
        # Fix deprecated API usage
        for error in error_groups.get('deprecated_api', []):
            if 'ShowCreation' in error.message:
                fixed_content = re.sub(r'\bShowCreation\b', 'Create', fixed_content)
                applied_fixes.append("Replaced ShowCreation with Create")
            elif 'TextMobject' in error.message:
                fixed_content = re.sub(r'\bTextMobject\b', 'Text', fixed_content)
                applied_fixes.append("Replaced TextMobject with Text")
            elif 'TexMobject' in error.message:
                fixed_content = re.sub(r'\bTexMobject\b', 'MathTex', fixed_content)
                applied_fixes.append("Replaced TexMobject with MathTex")
        
        # Fix invalid imports
        for error in error_groups.get('invalid_import', []):
            if 'manimlib' in error.message:
                fixed_content = fixed_content.replace('from manimlib', 'from manim')
                fixed_content = fixed_content.replace('import manimlib', 'import manim')
                applied_fixes.append("Fixed manimlib imports to manim")
        
        # Fix custom scene inheritance (CycloidScene, etc.)
        custom_scene_pattern = r'class\s+(\w+)\s*\(([^)]+)\):'
        custom_scenes = ['CycloidScene', 'PathSlidingScene', 'MultilayeredScene', 
                        'PhotonScene', 'ThetaTGraph', 'VideoLayout']
        
        for scene in custom_scenes:
            if f'({scene})' in fixed_content and f'class {scene}' not in fixed_content:
                # Scene is used as parent but not defined - change to Scene
                pattern = rf'class\s+(\w+)\s*\({scene}\):'
                fixed_content = re.sub(pattern, r'class \1(Scene):', fixed_content)
                applied_fixes.append(f"Changed inheritance from {scene} to Scene")
        
        # Fix missing construct methods
        for error in error_groups.get('missing_construct', []):
            # Extract scene name from error
            scene_match = re.search(r'Scene class (\w+) missing', error.message)
            if scene_match:
                scene_name = scene_match.group(1)
                # Add construct method after class definition
                pattern = rf'(class {scene_name}\([^)]*\):\s*\n)'
                replacement = r'\1    def construct(self):\n        pass  # TODO: Implement scene\n\n'
                fixed_content = re.sub(pattern, replacement, fixed_content)
                applied_fixes.append(f"Added missing construct method to {scene_name}")
        
        # Fix deprecated color names
        color_replacements = {
            r'\bLIGHT_GRAY\b': 'LIGHT_GREY',
            r'\bDARK_GRAY\b': 'DARK_GREY',
            r'\bGRAY\b': 'GREY'
        }
        for pattern, replacement in color_replacements.items():
            if re.search(pattern, fixed_content):
                fixed_content = re.sub(pattern, replacement, fixed_content)
                applied_fixes.append(f"Fixed color name: {pattern} -> {replacement}")
        
        # Fix syntax errors
        for error in error_groups.get('syntax_error', []):
            # Fix extra parentheses in OldTex/Tex calls (e.g., OldTex("(")) -> OldTex("("))
            if 'unmatched' in error.message.lower() or 'invalid syntax' in error.message.lower():
                # Multiple patterns to catch various forms of the bug
                patterns = [
                    (r'((?:Old)?Tex\("\("\))\)', r'Tex("(")', 'Literal ( pattern for OldTex'),
                    (r'((?:Old)?Tex\("\)"\))\)', r'Tex(")")', 'Literal ) pattern for OldTex'),
                    (r'Tex\("(.)"(\))+', r'Tex("\1")', 'Capture group pattern for Tex'),
                    (r'MathTex\("(.)"(\))+', r'MathTex("\1")', 'Capture group pattern for MathTex'),
                    (r'(?:Old)?Tex\("(.*?)"\)\)', r'Tex("\1")', 'General pattern for any OldTex/Tex'),
                ]
                
                fixed_any = False
                for pattern, replacement, desc in patterns:
                    matches = re.findall(pattern, fixed_content)
                    if matches:
                        # Debug logging
                        if self.verbose:
                            print(f"Found {len(matches)} matches for pattern '{desc}'")
                        fixed_content = re.sub(pattern, replacement, fixed_content)
                        fixed_any = True
                
                if fixed_any:
                    applied_fixes.append("Fixed extra closing parenthesis in Tex string literal")
            
            # Fix invalid function definitions (return def __init__)
            if 'return def' in error.message or 'return def' in fixed_content:
                # This is a serious error - try to fix by separating return and def
                fixed_content = re.sub(r'return\s+def\s+', 'return ""\n\n    def ', fixed_content)
                applied_fixes.append("Fixed invalid 'return def' syntax")
            
        # Fix indentation errors
        for error in error_groups.get('indentation_error', []):
            # This is complex - we'd need context to fix properly
            # For now, just log that it needs manual fixing
            applied_fixes.append(f"WARNING: Indentation error on line {error.line_number} needs manual fixing")
        
        # Fix missing custom animations
        custom_animations = {
            'SlideWordDownCycloid': '''
class SlideWordDownCycloid(Animation):
    """Custom animation for sliding word down cycloid."""
    def __init__(self, word, cycloid, prop=0.5, **kwargs):
        self.cycloid = cycloid
        self.prop = prop
        super().__init__(word, **kwargs)
    def interpolate_mobject(self, alpha):
        point = self.cycloid.point_from_proportion(self.prop * alpha)
        self.mobject.move_to(point)
''',
            'RollAlongVector': '''
class RollAlongVector(Animation):
    """Animation for rolling object along vector."""
    def __init__(self, mobject, vector, rotation_vector=OUT, **kwargs):
        self.vector = vector
        self.rotation_vector = rotation_vector
        self.radius = mobject.get_width() / 2
        self.radians = np.linalg.norm(vector) / self.radius
        self.last_alpha = 0
        super().__init__(mobject, **kwargs)
    def interpolate_mobject(self, alpha):
        d_alpha = alpha - self.last_alpha
        self.last_alpha = alpha
        self.mobject.rotate(d_alpha * self.radians, self.rotation_vector)
        self.mobject.shift(d_alpha * self.vector)
'''
        }
        
        for anim_name, anim_code in custom_animations.items():
            if anim_name in fixed_content and f'class {anim_name}' not in fixed_content:
                # Find place to insert after imports
                lines = fixed_content.split('\n')
                insert_pos = 0
                for i, line in enumerate(lines):
                    if line.strip() and (line.startswith('import') or line.startswith('from')):
                        insert_pos = i + 1
                    elif line.strip() and not line.startswith('#'):
                        break
                lines.insert(insert_pos, anim_code)
                fixed_content = '\n'.join(lines)
                applied_fixes.append(f"Added missing {anim_name} custom animation")
        
        # Fix unbalanced parentheses/brackets/braces
        # Count all parentheses/brackets/braces (ignoring those in strings)
        lines = fixed_content.split('\n')
        for i, line in enumerate(lines):
            # Skip comments
            if line.strip().startswith('#'):
                continue
                
            # Remove string literals to count brackets accurately
            temp_line = line
            string_pattern = r'(\'[^\']*\'|"[^"]*")'
            strings = re.findall(string_pattern, temp_line)
            for j, string in enumerate(strings):
                temp_line = temp_line.replace(string, f'__STRING_{j}__')
            
            # Count brackets
            open_parens = temp_line.count('(')
            close_parens = temp_line.count(')')
            
            # Fix lines that have more closing than opening parens (likely our OldTex issue)
            if close_parens > open_parens and 'Tex(' in line:
                # Check multiple patterns
                tex_patterns = [
                    (r'Tex\("(.)"(\))+', r'Tex("\1")'),  # Capture group pattern
                    (r'MathTex\("(.)"(\))+', r'MathTex("\1")'),  # MathTex variant
                    (r'(?:Old)?Tex\("(.*?)"\)\)', r'Tex("\1")'),  # General pattern
                ]
                
                for pattern, replacement in tex_patterns:
                    if re.search(pattern, line):
                        lines[i] = re.sub(pattern, replacement, line)
                        applied_fixes.append(f"Fixed extra closing parenthesis on line {i+1}")
                        break
        
        if any('Fixed extra closing parenthesis on line' in fix for fix in applied_fixes):
            fixed_content = '\n'.join(lines)
        
        return fixed_content, applied_fixes


def validate_directory(directory: str, output_file: Optional[str] = None, 
                      verbose: bool = False) -> Dict[str, ValidationReport]:
    """Validate all Python files in a directory."""
    validator = ManimCEPrecompileValidator(verbose=verbose)
    results = {}
    
    dir_path = Path(directory)
    py_files = list(dir_path.rglob("*.py"))
    
    print(f"Validating {len(py_files)} Python files in {directory}")
    
    for py_file in py_files:
        if verbose:
            print(f"Validating: {py_file}")
        
        report = validator.validate_file(str(py_file))
        results[str(py_file)] = report
        
        # Print summary for this file
        if report.errors or report.warnings:
            print(f"\n{py_file}:")
            print(f"  Errors: {len(report.errors)}, Warnings: {len(report.warnings)}")
            
            if verbose:
                for error in report.errors[:5]:  # Show first 5 errors
                    print(f"    ERROR [{error.error_type}] Line {error.line_number}: {error.message}")
                    if error.suggestion:
                        print(f"      → {error.suggestion}")
    
    # Save results if requested
    if output_file:
        output_data = {
            'validation_date': str(Path.ctime(Path())),
            'directory': directory,
            'summary': {
                'total_files': len(results),
                'valid_files': sum(1 for r in results.values() if r.is_valid),
                'files_with_errors': sum(1 for r in results.values() if r.errors),
                'files_with_warnings': sum(1 for r in results.values() if r.warnings),
                'total_errors': sum(len(r.errors) for r in results.values()),
                'total_warnings': sum(len(r.warnings) for r in results.values())
            },
            'files': {path: report.to_dict() for path, report in results.items()}
        }
        
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"\nValidation results saved to: {output_file}")
        print(f"Summary: {output_data['summary']}")
    
    return results


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Pre-compile validation for ManimCE converted code'
    )
    parser.add_argument('path', help='File or directory to validate')
    parser.add_argument('-o', '--output', help='Output JSON file for results')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--fix', action='store_true', help='Attempt to auto-fix issues (experimental)')
    
    args = parser.parse_args()
    
    path = Path(args.path)
    
    if path.is_file():
        validator = ManimCEPrecompileValidator(verbose=args.verbose)
        report = validator.validate_file(str(path))
        
        print(f"\nValidation Report for {path}:")
        print(f"Valid: {report.is_valid}")
        print(f"Errors: {len(report.errors)}")
        print(f"Warnings: {len(report.warnings)}")
        
        if args.verbose or not report.is_valid:
            for error in report.errors:
                print(f"\nERROR [{error.error_type}] Line {error.line_number}: {error.message}")
                if error.suggestion:
                    print(f"  Suggestion: {error.suggestion}")
                if error.code_snippet:
                    print(f"  Code: {error.code_snippet}")
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report.to_dict(), f, indent=2)
    
    elif path.is_dir():
        validate_directory(str(path), args.output, args.verbose)
    
    else:
        print(f"Error: {path} is not a valid file or directory")
        sys.exit(1)


if __name__ == '__main__':
    main()