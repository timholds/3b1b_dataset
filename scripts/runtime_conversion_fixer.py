#!/usr/bin/env python3
"""
Runtime Conversion Fixer - Fixes the ACTUAL issues preventing scenes from rendering

Based on analysis of inventing-math failures:
1. LaTeX compilation errors (60%): Tex() vs MathTex() and malformed LaTeX
2. Runtime variable errors (25%): UnboundLocalError, wrong data types  
3. Missing constants/references (15%): Undefined globals

This addresses the REAL blocking issues, not theoretical patterns.
"""

import ast
import re
import logging
from typing import Dict, List, Tuple, Optional, Set, Any
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class RuntimeConversionFixer:
    """Fixes runtime errors that prevent scenes from actually rendering."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.fixes_applied = []
        
    def fix_video_snippets(self, year: int, base_dir: Path, video_filter: Optional[List[str]] = None) -> Dict[str, Any]:
        """Fix runtime issues in validated snippets for a specific year."""
        base_dir = Path(base_dir)
        year_dir = base_dir / 'outputs' / str(year)
        
        results = {
            'year': year,
            'total_videos': 0,
            'videos_processed': 0,
            'total_files_fixed': 0,
            'video_results': {}
        }
        
        if not year_dir.exists():
            logger.warning(f"No output directory found for year {year}")
            return results
            
        for video_dir in year_dir.iterdir():
            if not video_dir.is_dir():
                continue
                
            # Apply video filter if specified
            if video_filter and video_dir.name not in video_filter:
                continue
                
            results['total_videos'] += 1
            
            # Process validated snippets
            snippets_dir = video_dir / 'validated_snippets'
            if not snippets_dir.exists():
                continue
                
            video_result = self._fix_video_snippets(snippets_dir)
            if video_result['files_fixed'] > 0:
                results['videos_processed'] += 1
                results['total_files_fixed'] += video_result['files_fixed']
                results['video_results'][video_dir.name] = video_result
                
        return results
    
    def _fix_video_snippets(self, snippets_dir: Path) -> Dict[str, Any]:
        """Fix all snippets in a video directory."""
        result = {
            'files_fixed': 0,
            'fixes_by_type': {},
            'failed_fixes': []
        }
        
        for snippet_file in snippets_dir.glob('*.py'):
            if snippet_file.name.endswith('.runtime_backup'):
                continue
                
            try:
                # Read original content
                with open(snippet_file, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                
                # Apply fixes
                fixed_content, fixes_applied = self._fix_snippet_content(original_content, snippet_file.name)
                
                if fixes_applied:
                    # Create backup
                    backup_file = snippet_file.with_suffix('.py.runtime_backup')
                    if not backup_file.exists():
                        with open(backup_file, 'w', encoding='utf-8') as f:
                            f.write(original_content)
                    
                    # Write fixed content
                    with open(snippet_file, 'w', encoding='utf-8') as f:
                        f.write(fixed_content)
                    
                    result['files_fixed'] += 1
                    
                    # Track fix types
                    for fix in fixes_applied:
                        fix_type = fix.split(':')[0]
                        result['fixes_by_type'][fix_type] = result['fixes_by_type'].get(fix_type, 0) + 1
                        
                    if self.verbose:
                        logger.info(f"Fixed {snippet_file.name}: {len(fixes_applied)} fixes applied")
                        
            except Exception as e:
                result['failed_fixes'].append({
                    'file': snippet_file.name,
                    'error': str(e)
                })
                logger.error(f"Failed to fix {snippet_file.name}: {e}")
                
        return result
    
    def _fix_snippet_content(self, content: str, filename: str) -> Tuple[str, List[str]]:
        """Apply all runtime fixes to snippet content."""
        fixes_applied = []
        fixed_content = content
        
        # Fix 1: LaTeX compilation errors (60% of failures)
        fixed_content, latex_fixes = self._fix_latex_errors(fixed_content)
        fixes_applied.extend(latex_fixes)
        
        # Fix 2: Variable scope errors (25% of failures)
        fixed_content, scope_fixes = self._fix_variable_scope_errors(fixed_content)
        fixes_applied.extend(scope_fixes)
        
        # Fix 3: Missing constants and references (15% of failures)
        fixed_content, const_fixes = self._fix_missing_constants(fixed_content)
        fixes_applied.extend(const_fixes)
        
        # Fix 6: Replace problematic helper functions
        fixed_content, helper_fixes = self._fix_helper_functions(fixed_content)
        fixes_applied.extend(helper_fixes)
        
        # Fix 4: Type errors (Text vs MathTex issues)
        fixed_content, type_fixes = self._fix_type_errors(fixed_content)
        fixes_applied.extend(type_fixes)
        
        # Fix 5: Method signature errors
        fixed_content, method_fixes = self._fix_method_signatures(fixed_content)
        fixes_applied.extend(method_fixes)
        
        return fixed_content, fixes_applied
    
    def _fix_latex_errors(self, content: str) -> Tuple[str, List[str]]:
        """Fix LaTeX compilation errors."""
        fixes = []
        fixed_content = content
        
        # Fix 1: Convert Tex() calls with math content to MathTex()
        # Pattern: Tex('\\frac{1}{2}') -> MathTex('\\frac{1}{2}')
        math_patterns = [
            r'\\frac', r'\\cdots', r'\\sum', r'\\int', r'\\lim',
            r'\^{', r'_{', r'\\alpha', r'\\beta', r'\\gamma',
            r'\\infty', r'\\pi', r'\\times', r'\\div'
        ]
        
        # Find Tex() calls that should be MathTex()
        tex_pattern = r'Tex\(([^)]+)\)'
        matches = list(re.finditer(tex_pattern, fixed_content))
        
        for match in reversed(matches):  # Reverse to maintain positions
            tex_content = match.group(1)
            # Check if this looks like math content
            if any(pattern in tex_content for pattern in math_patterns):
                replacement = match.group(0).replace('Tex(', 'MathTex(')
                start, end = match.span()
                fixed_content = fixed_content[:start] + replacement + fixed_content[end:]
                fixes.append('latex: Converted Tex() to MathTex() for math content')
        
        # Fix 2: Fix double superscript errors
        # Pattern: '+2^n' -> '+2^{n}'
        double_superscript_pattern = r'(\+\d+)\^([a-zA-Z]+)'
        def fix_superscript(match):
            return f"{match.group(1)}^{{{match.group(2)}}}"
        
        if re.search(double_superscript_pattern, fixed_content):
            fixed_content = re.sub(double_superscript_pattern, fix_superscript, fixed_content)
            fixes.append('latex: Fixed double superscript notation')
        
        # Fix 3: Fix missing math mode in center environments
        # Pattern: \\begin{center} \\frac{1}{2} \\end{center} needs math mode
        center_math_pattern = r'(\\begin\{center\}\s*)(\\[a-zA-Z]+.*?)(\\end\{center\})'
        def add_math_mode(match):
            return f"{match.group(1)}${match.group(2)}${match.group(3)}"
        
        if re.search(center_math_pattern, fixed_content):
            fixed_content = re.sub(center_math_pattern, add_math_mode, fixed_content)
            fixes.append('latex: Added math mode to center environment')
        
        # Fix 4: Fix accidental double "MathMathTex"
        if 'MathMathTex' in fixed_content:
            fixed_content = fixed_content.replace('MathMathTex', 'MathTex')
            fixes.append('latex: Fixed double MathMathTex to MathTex')
        
        return fixed_content, fixes
    
    def _fix_variable_scope_errors(self, content: str) -> Tuple[str, List[str]]:
        """Fix variable scope errors like UnboundLocalError."""
        fixes = []
        fixed_content = content
        
        # Fix 1: ChopIntervalInProportions if/elif pattern
        # Convert multiple 'if' statements to 'if/elif' to ensure variables are always defined
        
        # Pattern: if mode == '9': ... if mode == 'p': -> if mode == '9': ... elif mode == 'p':
        mode_if_pattern = r"(if mode == '9':.*?)\n(\s+)if mode == 'p':"
        if re.search(mode_if_pattern, fixed_content, re.DOTALL):
            fixed_content = re.sub(mode_if_pattern, r"\1\n\2elif mode == 'p':", fixed_content, flags=re.DOTALL)
            fixes.append('scope: Converted sequential if statements to if/elif pattern')
        
        # Fix 2: Add default initialization for commonly undefined variables
        common_undefined_vars = ['left_terms', 'right_terms', 'prop', 'num_terms']
        
        for var in common_undefined_vars:
            # Check if variable is used but not initialized at function start
            if f'{var}' in fixed_content and f'{var} =' not in fixed_content:
                # Find function definitions and add initialization
                func_pattern = r'(def _construct_with_args\(self, [^)]*\):\s*\n)'
                def add_var_init(match):
                    init_line = f"        {var} = None  # Default initialization\n"
                    return match.group(1) + init_line
                
                if re.search(func_pattern, fixed_content):
                    fixed_content = re.sub(func_pattern, add_var_init, fixed_content)
                    fixes.append(f'scope: Added default initialization for {var}')
        
        return fixed_content, fixes
    
    def _fix_missing_constants(self, content: str) -> Tuple[str, List[str]]:
        """Fix missing constants and references."""
        fixes = []
        fixed_content = content
        
        # Common missing constants in inventing-math
        missing_constants = {
            'DIVERGENT_SUM_TEXT': "['1', '+2', '+4', '+8', '+\\\\cdots', '+2^{n}', '+\\\\cdots', '= -1']",
            'INTERVAL_RADIUS': '2',
            'OUT': 'np.array([0, 0, 1])',  # Common 3D vector
        }
        
        for const_name, const_value in missing_constants.items():
            if const_name in fixed_content and f'{const_name} =' not in fixed_content:
                # Add constant definition after imports
                import_end_pattern = r'((?:from|import).*\n)+'
                def add_constant(match):
                    return match.group(0) + f'\n# Missing constant definition\n{const_name} = {const_value}\n'
                
                if re.search(import_end_pattern, fixed_content):
                    fixed_content = re.sub(import_end_pattern, add_constant, fixed_content, count=1)
                    fixes.append(f'constants: Added missing constant {const_name}')
        
        return fixed_content, fixes
    
    def _fix_helper_functions(self, content: str) -> Tuple[str, List[str]]:
        """Replace problematic helper functions with working versions."""
        fixes = []
        fixed_content = content
        
        # Fix problematic Underbrace function
        old_underbrace = """def Underbrace(left, right):
    result = MathTex(r"\\Underbrace{%s}" % (14 * '\\quad'))
    result.stretch_to_fit_width(right[0] - left[0])
    result.shift(left - result.get_start())
    return result"""
    
        new_underbrace = """def Underbrace(left, right):
    # Simple brace implementation for ManimCE
    from manim import MathTex, DOWN
    import numpy as np
    
    width = abs(right[0] - left[0]) if hasattr(right, '__getitem__') and hasattr(left, '__getitem__') else 2
    result = MathTex(r"\\underbrace{\\quad\\quad\\quad\\quad\\quad\\quad}")
    
    # Scale to fit width
    if result.width > 0 and width > 0:
        result.scale(width / result.width)
    
    # Position between left and right
    center_x = (left[0] + right[0]) / 2 if hasattr(right, '__getitem__') and hasattr(left, '__getitem__') else 0
    result.move_to([center_x, left[1] - 0.3, 0] if hasattr(left, '__getitem__') else [0, -0.3, 0])
    
    return result"""
        
        if old_underbrace.replace(' ', '').replace('\n', '') in fixed_content.replace(' ', '').replace('\n', ''):
            # Replace the old function
            # Find the function definition more flexibly
            underbrace_pattern = r'def Underbrace\(left, right\):.*?return result'
            if re.search(underbrace_pattern, fixed_content, re.DOTALL):
                fixed_content = re.sub(underbrace_pattern, new_underbrace, fixed_content, flags=re.DOTALL)
                fixes.append('helpers: Replaced problematic Underbrace function with working version')
        
        return fixed_content, fixes
    
    def _fix_type_errors(self, content: str) -> Tuple[str, List[str]]:
        """Fix type-related errors."""
        fixes = []
        fixed_content = content
        
        # Fix 1: Text() receiving list instead of string
        # Pattern: Text([...]) -> Text(' '.join([...]))
        text_list_pattern = r'Text\((\[[^\]]+\])\)'
        def fix_text_list(match):
            return f"Text(' '.join({match.group(1)}))"
        
        if re.search(text_list_pattern, fixed_content):
            fixed_content = re.sub(text_list_pattern, fix_text_list, fixed_content)
            fixes.append('types: Fixed Text() receiving list instead of string')
        
        # Fix 2: Common type conversion issues
        # astype('float') -> astype(float)
        astype_pattern = r"\.astype\('float'\)"
        if re.search(astype_pattern, fixed_content):
            fixed_content = re.sub(astype_pattern, '.astype(float)', fixed_content)
            fixes.append('types: Fixed astype string to type')
        
        return fixed_content, fixes
    
    def _fix_method_signatures(self, content: str) -> Tuple[str, List[str]]:
        """Fix method signature errors."""
        fixes = []
        fixed_content = content
        
        # Fix 1: rotate() method signature changes
        # .rotate(angle, axis) -> .rotate(angle, axis=axis)
        rotate_pattern = r'\.rotate\(([^,]+),\s*([^)]+)\)'
        def fix_rotate(match):
            angle = match.group(1).strip()
            axis = match.group(2).strip()
            # Don't change if already has axis= or if it would create duplicate
            if 'axis=' in axis or 'axis=' in match.group(0):
                return match.group(0)  # Leave unchanged
            # Check if it's a simple axis reference
            if axis in ['RIGHT', 'UP', 'OUT', 'np.pi', 'LEFT', 'DOWN']:
                return f'.rotate({angle}, axis={axis})'
            return match.group(0)  # Leave unchanged if unsure
        
        if re.search(rotate_pattern, fixed_content):
            original_rotates = len(re.findall(rotate_pattern, fixed_content))
            fixed_content = re.sub(rotate_pattern, fix_rotate, fixed_content)
            new_rotates = len(re.findall(r'\.rotate\([^,]+,\s*axis=', fixed_content))
            if new_rotates > 0:
                fixes.append('methods: Fixed rotate() method signature')
        
        # Fix 2: Underbrace positioning
        # Common issue with custom Underbrace function
        underbrace_pattern = r'Underbrace\(([^,]+),\s*([^)]+)\)\.rotate\(np\.pi,\s*RIGHT\)'
        def fix_underbrace(match):
            return f'Underbrace({match.group(1)}, {match.group(2)}).rotate(np.pi, axis=RIGHT)'
        
        if re.search(underbrace_pattern, fixed_content):
            fixed_content = re.sub(underbrace_pattern, fix_underbrace, fixed_content)
            fixes.append('methods: Fixed Underbrace rotate method signature')
        
        return fixed_content, fixes


def test_runtime_fixer():
    """Test the runtime fixer with example problematic code."""
    test_code = '''
from manim import *
import numpy as np

class TestScene(Scene):
    def _construct_with_args(self, mode):
        if mode == '9':
            left_terms = [Tex('\\\\frac{1}{2}')]
            right_terms = [Tex('p^n')]
        if mode == 'p':
            # left_terms and right_terms not defined here!
            pass
        
        # This will fail with UnboundLocalError
        for lt, rt in zip(left_terms, right_terms):
            pass
            
        # LaTeX errors
        divergent = Tex(DIVERGENT_SUM_TEXT)  # Missing constant
        fraction = Tex('\\\\frac{1}{2}')  # Should be MathTex
        
        # Type errors
        text_obj = Text(['hello', 'world'])  # Should be string
        
        # Method signature errors
        circle = Circle().rotate(np.pi, RIGHT)  # Missing axis=
'''
    
    fixer = RuntimeConversionFixer(verbose=True)
    fixed_content, fixes = fixer._fix_snippet_content(test_code, 'test.py')
    
    print("=== RUNTIME CONVERSION FIXER TEST ===")
    print(f"Applied {len(fixes)} fixes:")
    for fix in fixes:
        print(f"  - {fix}")
    
    print("\n=== FIXED CODE ===")
    print(fixed_content)


if __name__ == '__main__':
    test_runtime_fixer()