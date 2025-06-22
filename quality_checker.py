#!/usr/bin/env python3
"""
Quality checker for 3b1b dataset extraction pipeline.
Validates inlined code files to ensure they are complete and runnable.
"""

import re
import ast
import json
from typing import Dict, List, Tuple, Set
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class QualityReport:
    """Holds the results of quality checks"""
    filename: str
    quality_score: str = "PENDING"  # PASS, WARN, FAIL
    checks: Dict[str, List[str]] = field(default_factory=dict)
    total_issues: int = 0
    critical_issues: int = 0
    warnings: int = 0
    recommendation: str = ""
    
    def to_dict(self):
        return {
            "filename": self.filename,
            "quality_score": self.quality_score,
            "checks": self.checks,
            "total_issues": self.total_issues,
            "critical_issues": self.critical_issues,
            "warnings": self.warnings,
            "recommendation": self.recommendation
        }


class ManimCodeQualityChecker:
    """Quality checker for manim code files"""
    
    # Common manim imports that should be present
    ESSENTIAL_IMPORTS = [
        "from manim_imports_ext import *",
        "from manimlib",
        "import numpy as np"
    ]
    
    # Common manim classes that should be defined or imported
    COMMON_MANIM_CLASSES = {
        # Core classes
        'Scene', 'GraphScene', 'ThreeDScene', 'NumberLineScene',
        # Mobjects
        'Mobject', 'VMobject', 'Mobject1D', 'Mobject2D', 'Group',
        # Text
        'Text', 'Tex', 'MathTex', 'TexText', 'OldTex', 'OldTexText',
        # Shapes
        'Circle', 'Square', 'Rectangle', 'Line', 'Arrow', 'Dot', 'Ellipse',
        # Animations
        'Animation', 'Transform', 'ReplacementTransform', 'FadeIn', 'FadeOut',
        'Write', 'ShowCreation', 'Create', 'Uncreate', 'GrowFromCenter',
        # Other common classes
        'NumberLine', 'Axes', 'ThreeDAxes', 'Camera', 'NumberPlane',
        'VGroup', 'SVGMobject', 'ImageMobject'
    }
    
    # Common constants that should be defined
    COMMON_CONSTANTS = {
        'ORIGIN', 'UP', 'DOWN', 'LEFT', 'RIGHT', 'OUT', 'IN',
        'UL', 'UR', 'DL', 'DR',  # Diagonal directions
        'FRAME_HEIGHT', 'FRAME_WIDTH', 'FRAME_X_RADIUS', 'FRAME_Y_RADIUS',
        'DEFAULT_STROKE_WIDTH', 'DEFAULT_MOBJECT_TO_EDGE_BUFFER',
        'PI', 'TAU', 'DEGREES',
        'RED', 'GREEN', 'BLUE', 'YELLOW', 'WHITE', 'BLACK', 'GREY', 'GRAY',
        'SMALL_BUFF', 'MED_SMALL_BUFF', 'MED_LARGE_BUFF', 'LARGE_BUFF'
    }
    
    def __init__(self):
        self.report = None
        
    def check_code(self, code: str, filename: str, metadata: dict = None) -> QualityReport:
        """Run all quality checks on a code file"""
        self.report = QualityReport(filename=filename)
        
        # Run all checks
        self._check_imports(code)
        self._check_code_structure(code)
        self._check_undefined_references(code)
        self._check_circular_imports(code, filename)
        self._check_completeness(code)
        self._check_commented_code(code)
        self._check_syntax(code)
        
        # Calculate final score
        self._calculate_final_score()
        
        return self.report
    
    def _check_imports(self, code: str):
        """Check for essential imports and import issues"""
        issues = []
        warnings = []
        
        # Check for essential imports
        has_essential_import = False
        for import_stmt in self.ESSENTIAL_IMPORTS:
            if import_stmt in code:
                has_essential_import = True
                break
        
        if not has_essential_import:
            issues.append("Missing essential manim imports (manim_imports_ext or manimlib)")
        
        # Check for commented out critical imports
        commented_import_pattern = r'#\s*from\s+(animation|mobject|constants|scene|camera|utils)'
        commented_imports = re.findall(commented_import_pattern, code, re.IGNORECASE)
        if commented_imports:
            issues.append(f"Critical imports are commented out: {', '.join(set(commented_imports))}")
        
        # Check for incomplete inlining markers
        if "# Inlined above" in code and code.count("# Inlined above") > 2:
            warnings.append("Multiple 'Inlined above' comments found - verify all imports are actually inlined")
        
        # Check for mixed import styles
        if "from manim_imports_ext import *" in code and "from manimlib" in code:
            warnings.append("Mixed import styles detected (both manim_imports_ext and manimlib)")
        
        self.report.checks["imports"] = issues
        self.report.checks["import_warnings"] = warnings
        self.report.critical_issues += len(issues)
        self.report.warnings += len(warnings)
    
    def _check_code_structure(self, code: str):
        """Check for structural issues in the code"""
        issues = []
        lines = code.split('\n')
        
        # Track line numbers for different elements
        first_class_line = None
        first_function_line = None
        last_import_line = None
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Skip comments and docstrings
            if stripped.startswith('#') or stripped.startswith('"""'):
                continue
                
            if stripped.startswith('class '):
                first_class_line = first_class_line or i
            elif stripped.startswith('def ') and not line.startswith(' '):
                first_function_line = first_function_line or i
            elif stripped.startswith(('import ', 'from ')) and not stripped.startswith('#'):
                last_import_line = i
        
        # Check if classes are defined before imports
        if first_class_line is not None and last_import_line is not None:
            if first_class_line < last_import_line:
                issues.append(f"Class defined before imports (line {first_class_line + 1} < {last_import_line + 1})")
        
        # Check if there are multiple source file markers
        source_file_markers = re.findall(r'# ============+\n# Source file: (.+)\n# ============+', code)
        if len(source_file_markers) > 1:
            issues.append(f"Multiple source files merged: {', '.join(source_file_markers)}")
        
        self.report.checks["structure"] = issues
        self.report.critical_issues += len(issues)
    
    def _check_undefined_references(self, code: str):
        """Check for potentially undefined classes and functions"""
        issues = []
        warnings = []
        
        # Try to parse the AST
        try:
            tree = ast.parse(code)
        except SyntaxError:
            # Syntax errors will be caught in _check_syntax
            return
        
        # Collect all defined names
        defined_names = set()
        imported_names = set()
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                defined_names.add(node.name)
            elif isinstance(node, ast.FunctionDef):
                defined_names.add(node.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and '*' in [alias.name for alias in node.names]:
                    # Star import - assume common manim classes are available
                    if 'manim' in str(node.module):
                        imported_names.update(self.COMMON_MANIM_CLASSES)
                        imported_names.update(self.COMMON_CONSTANTS)
                else:
                    for alias in node.names:
                        imported_names.add(alias.asname or alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name)
        
        # Check for undefined class references
        class_pattern = r'\b(' + '|'.join(self.COMMON_MANIM_CLASSES) + r')\b'
        used_classes = set(re.findall(class_pattern, code))
        
        for class_name in used_classes:
            if (class_name not in defined_names and 
                class_name not in imported_names and
                "from manim" not in code and
                "import *" not in code):
                warnings.append(f"Class '{class_name}' used but not clearly imported/defined")
        
        # Check for undefined constants
        constant_pattern = r'\b(' + '|'.join(self.COMMON_CONSTANTS) + r')\b'
        used_constants = set(re.findall(constant_pattern, code))
        
        for constant in used_constants:
            if (constant not in defined_names and 
                constant not in imported_names and
                "from manim" not in code and
                "import *" not in code):
                warnings.append(f"Constant '{constant}' used but not clearly imported/defined")
        
        self.report.checks["undefined_references"] = issues
        self.report.checks["undefined_warnings"] = warnings
        self.report.critical_issues += len(issues)
        self.report.warnings += len(warnings)
    
    def _check_circular_imports(self, code: str, filename: str):
        """Check for self-referential imports"""
        issues = []
        
        # Extract module name from filename
        module_name = Path(filename).stem
        
        # Check for various forms of self-import
        self_import_patterns = [
            f"from .{module_name} import",
            f"from {module_name} import",
            f"import {module_name}"
        ]
        
        for pattern in self_import_patterns:
            if pattern in code:
                issues.append(f"Self-referential import detected: '{pattern}'")
        
        self.report.checks["circular_imports"] = issues
        self.report.critical_issues += len(issues)
    
    def _check_completeness(self, code: str):
        """Check if the code file is complete and has actual content"""
        issues = []
        warnings = []
        
        # Check for minimum content
        lines = [line.strip() for line in code.split('\n') if line.strip() and not line.strip().startswith('#')]
        
        if len(lines) < 10:
            issues.append("File appears to be incomplete (less than 10 non-comment lines)")
        
        # Check for at least one Scene class
        scene_classes = re.findall(r'class\s+(\w+)\s*\([^)]*Scene[^)]*\):', code)
        if not scene_classes:
            warnings.append("No Scene-based classes found")
        
        # Check for construct methods
        construct_methods = re.findall(r'def\s+construct\s*\(', code)
        if scene_classes and len(construct_methods) < len(scene_classes):
            warnings.append(f"Found {len(scene_classes)} Scene classes but only {len(construct_methods)} construct methods")
        
        # Check for command_line_create_scene
        if "if __name__ == '__main__':" in code and "command_line_create_scene" not in code:
            warnings.append("Main block present but no command_line_create_scene call")
        
        self.report.checks["completeness"] = issues
        self.report.checks["completeness_warnings"] = warnings
        self.report.critical_issues += len(issues)
        self.report.warnings += len(warnings)
    
    def _check_commented_code(self, code: str):
        """Check for excessive commented code that might indicate problems"""
        warnings = []
        
        lines = code.split('\n')
        comment_lines = sum(1 for line in lines if line.strip().startswith('#'))
        total_lines = len([line for line in lines if line.strip()])
        
        if total_lines > 0:
            comment_ratio = comment_lines / total_lines
            if comment_ratio > 0.4:
                warnings.append(f"High ratio of commented lines ({comment_ratio:.1%}) - verify code is active")
        
        # Check for large blocks of commented code
        consecutive_comments = 0
        max_consecutive = 0
        
        for line in lines:
            if line.strip().startswith('#'):
                consecutive_comments += 1
                max_consecutive = max(max_consecutive, consecutive_comments)
            else:
                consecutive_comments = 0
        
        if max_consecutive > 20:
            warnings.append(f"Large block of commented code ({max_consecutive} consecutive lines)")
        
        self.report.checks["commented_code"] = warnings
        self.report.warnings += len(warnings)
    
    def _check_syntax(self, code: str):
        """Check if the code has valid Python syntax"""
        issues = []
        
        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(f"Syntax error at line {e.lineno}: {e.msg}")
        except Exception as e:
            issues.append(f"Failed to parse code: {str(e)}")
        
        self.report.checks["syntax"] = issues
        self.report.critical_issues += len(issues)
    
    def _calculate_final_score(self):
        """Calculate the final quality score and recommendation"""
        self.report.total_issues = self.report.critical_issues + self.report.warnings
        
        if self.report.critical_issues > 0:
            self.report.quality_score = "FAIL"
            self.report.recommendation = "Critical issues found - manual review required"
        elif self.report.warnings > 5:
            self.report.quality_score = "WARN"
            self.report.recommendation = "Multiple warnings - review recommended"
        elif self.report.warnings > 0:
            self.report.quality_score = "WARN"
            self.report.recommendation = "Minor issues detected - likely OK"
        else:
            self.report.quality_score = "PASS"
            self.report.recommendation = "No issues found - ready for use"


def check_file(filepath: str, metadata: dict = None) -> QualityReport:
    """Convenience function to check a single file"""
    checker = ManimCodeQualityChecker()
    
    with open(filepath, 'r') as f:
        code = f.read()
    
    return checker.check_code(code, filepath, metadata)


def check_directory(directory: str, output_file: str = None) -> Dict[str, QualityReport]:
    """Check all code.py files in a directory structure"""
    results = {}
    checker = ManimCodeQualityChecker()
    
    for code_file in Path(directory).rglob("code.py"):
        # Try to load metadata if it exists
        metadata_file = code_file.parent / "metadata.json"
        metadata = {}
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
        
        # Check the file
        with open(code_file, 'r') as f:
            code = f.read()
        
        report = checker.check_code(code, str(code_file), metadata)
        results[str(code_file)] = report
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"File: {code_file}")
        print(f"Score: {report.quality_score}")
        print(f"Critical Issues: {report.critical_issues}, Warnings: {report.warnings}")
        print(f"Recommendation: {report.recommendation}")
        
        if report.critical_issues > 0:
            print("\nCritical Issues:")
            for check_name, issues in report.checks.items():
                if issues and not check_name.endswith("_warnings"):
                    print(f"  {check_name}:")
                    for issue in issues:
                        print(f"    - {issue}")
    
    # Save results if output file specified
    if output_file:
        output_data = {
            "summary": {
                "total_files": len(results),
                "passed": sum(1 for r in results.values() if r.quality_score == "PASS"),
                "warnings": sum(1 for r in results.values() if r.quality_score == "WARN"),
                "failed": sum(1 for r in results.values() if r.quality_score == "FAIL"),
            },
            "files": {path: report.to_dict() for path, report in results.items()}
        }
        
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"\n\nResults saved to: {output_file}")
        print(f"Summary: {output_data['summary']}")
    
    return results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python quality_checker.py <file_or_directory> [output.json]")
        sys.exit(1)
    
    path = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else None
    
    if Path(path).is_file():
        report = check_file(path)
        print(json.dumps(report.to_dict(), indent=2))
    else:
        check_directory(path, output)