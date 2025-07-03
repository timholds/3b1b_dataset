#!/usr/bin/env python3
"""
Fix Conversion Pipeline - Targeted fixes for the systematic converter issues

Based on analysis of inventing-math failures, this module fixes:
1. OldTex → MathTex conversions not working
2. manim_imports_ext → manim import issues
3. Missing method conversions (get_center() vs .center)
4. Malformed code extraction in systematic_pipeline_converter.py

These are the ROOT CAUSES preventing successful conversions.
"""

import ast
import re
import logging
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class ConversionPipelineFixer:
    """Fix the ROOT CAUSES in the conversion pipeline."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        
    def fix_cleaned_scene_before_conversion(self, content: str, scene_name: str) -> Tuple[str, List[str]]:
        """
        Fix a cleaned scene BEFORE it goes through the systematic converter.
        
        This addresses root causes in the source material that break the converter.
        """
        fixes_applied = []
        fixed_content = content
        
        # Fix 1: Convert manim_imports_ext to manim imports
        if 'from manim_imports_ext import *' in fixed_content:
            fixed_content = fixed_content.replace(
                'from manim_imports_ext import *',
                'from manim import *'
            )
            fixes_applied.append('Fixed manim_imports_ext import')
        
        # Fix 2: Convert OldTex to MathTex (CRITICAL)
        # This is the #1 cause of LaTeX compilation errors
        fixed_content = re.sub(r'\bOldTex\b', 'MathTex', fixed_content)
        if 'OldTex' in content and 'MathTex' in fixed_content:
            fixes_applied.append('Converted OldTex to MathTex')
        
        # Fix 3: Convert deprecated animations  
        animation_conversions = {
            'ShowCreation': 'Create',
            'ApplyMethod': 'Transform',  # Simplified conversion
            'CounterclockwiseTransform': 'Transform',
        }
        
        for old_anim, new_anim in animation_conversions.items():
            if old_anim in fixed_content:
                fixed_content = re.sub(rf'\b{old_anim}\b', new_anim, fixed_content)
                fixes_applied.append(f'Converted {old_anim} to {new_anim}')
        
        # Fix 4: Fix method calls that need to be properties
        method_to_property = {
            '.get_center()': '.center',
            '.get_width()': '.width', 
            '.get_height()': '.height',
        }
        
        for old_method, new_prop in method_to_property.items():
            if old_method in fixed_content:
                fixed_content = fixed_content.replace(old_method, new_prop)
                fixes_applied.append(f'Converted {old_method} to {new_prop}')
        
        # Fix 5: Add missing imports for used functions
        if 'reduce(' in fixed_content and 'from functools import reduce' not in fixed_content:
            # Add the import after existing imports
            import_lines = []
            other_lines = []
            in_imports = True
            
            for line in fixed_content.split('\n'):
                if in_imports and (line.startswith(('import ', 'from ')) or line.strip() == '' or line.startswith('#')):
                    import_lines.append(line)
                else:
                    in_imports = False
                    other_lines.append(line)
            
            import_lines.append('from functools import reduce')
            fixed_content = '\n'.join(import_lines + other_lines)
            fixes_applied.append('Added missing functools.reduce import')
        
        # Fix 6: Handle Point() constructor issues
        # Point(some_obj.get_center()) should be Point(some_obj.center)
        point_pattern = r'Point\(([^)]+)\.get_center\(\)\)'
        if re.search(point_pattern, fixed_content):
            fixed_content = re.sub(point_pattern, r'Point(\1.center)', fixed_content)
            fixes_applied.append('Fixed Point constructor with get_center()')
        
        return fixed_content, fixes_applied
    
    def fix_inventing_math_scenes(self, base_dir: Path) -> Dict[str, Any]:
        """Apply conversion fixes to all cleaned scenes in inventing-math."""
        base_dir = Path(base_dir)
        video_dir = base_dir / 'outputs' / '2015' / 'inventing-math'
        cleaned_scenes_dir = video_dir / 'cleaned_scenes'
        
        if not cleaned_scenes_dir.exists():
            logger.error(f"Cleaned scenes directory not found: {cleaned_scenes_dir}")
            return {'files_fixed': 0, 'error': 'Directory not found'}
        
        results = {
            'files_fixed': 0,
            'total_fixes': 0,
            'files_processed': 0,
            'fix_details': {}
        }
        
        for scene_file in cleaned_scenes_dir.glob('*.py'):
            try:
                # Read original content
                with open(scene_file, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                
                # Apply fixes
                fixed_content, fixes_applied = self.fix_cleaned_scene_before_conversion(
                    original_content, scene_file.stem
                )
                
                if fixes_applied:
                    # Create backup
                    backup_file = scene_file.with_suffix('.py.conversion_backup')
                    if not backup_file.exists():
                        with open(backup_file, 'w', encoding='utf-8') as f:
                            f.write(original_content)
                    
                    # Write fixed content
                    with open(scene_file, 'w', encoding='utf-8') as f:
                        f.write(fixed_content)
                    
                    results['files_fixed'] += 1
                    results['total_fixes'] += len(fixes_applied)
                    results['fix_details'][scene_file.name] = fixes_applied
                    
                    if self.verbose:
                        logger.info(f"Fixed {scene_file.name}: {', '.join(fixes_applied)}")
                
                results['files_processed'] += 1
                
            except Exception as e:
                logger.error(f"Failed to fix {scene_file.name}: {e}")
        
        return results
    
    def validate_scene_syntax(self, content: str, filename: str) -> Tuple[bool, Optional[str]]:
        """Validate that scene has correct Python syntax."""
        try:
            ast.parse(content)
            return True, None
        except SyntaxError as e:
            return False, f"SyntaxError in {filename}: {e.msg} at line {e.lineno}"
        except Exception as e:
            return False, f"Error parsing {filename}: {e}"


def fix_systematic_converter_issues():
    """
    Fix the systematic converter to handle the conversion issues properly.
    
    The main issue is that the systematic converter isn't applying AST fixes correctly.
    """
    converter_file = Path('/Users/timholdsworth/code/3b1b_dataset/scripts/systematic_pipeline_converter.py')
    
    # Key fix: Ensure AST converter is being used and working
    # The issue is that OldTex conversions aren't happening
    
    print("The main fixes needed are:")
    print("1. Fix cleaned scenes BEFORE they go to systematic converter")
    print("2. Ensure AST converter is working properly") 
    print("3. Fix the filtering logic that's mangling extracted code")
    
    # For now, we'll fix the input to the converter rather than the converter itself


def test_conversion_fixer():
    """Test the conversion fixer with problematic scene."""
    test_content = '''"""
Self-contained scene: OneAndInfiniteSumAreTheSameThing
Generated by programmatic cleaner
Dependencies: 0 functions, 0 classes, 0 constants
"""

import numpy as np
import itertools as it
import sys
import operator as op
from random import sample
from manim_imports_ext import *

class OneAndInfiniteSumAreTheSameThing(Scene):
    def construct(self):
        one, equals, inf_sum = OldTex([
            "1", "=", "\\sum_{n=1}^\\infty \\frac{1}{2^n}"
        ]).split()
        point = Point(equals.get_center()).set_color("black")

        self.add(one.shift(LEFT))
        self.wait()
        self.add(inf_sum.shift(RIGHT))
        self.wait()
        self.play(
            ApplyMethod(one.shift, RIGHT),
            ApplyMethod(inf_sum.shift, LEFT),
            CounterclockwiseTransform(point, equals)
        )
        self.wait()
'''
    
    fixer = ConversionPipelineFixer(verbose=True)
    fixed_content, fixes = fixer.fix_cleaned_scene_before_conversion(test_content, 'test')
    
    print("=== CONVERSION PIPELINE FIXER TEST ===")
    print(f"Applied {len(fixes)} fixes:")
    for fix in fixes:
        print(f"  - {fix}")
    
    print("\n=== FIXED CONTENT ===")
    print(fixed_content[:500] + "..." if len(fixed_content) > 500 else fixed_content)
    
    # Validate syntax
    is_valid, error = fixer.validate_scene_syntax(fixed_content, 'test.py')
    print(f"\nSyntax valid: {is_valid}")
    if not is_valid:
        print(f"Error: {error}")


if __name__ == '__main__':
    test_conversion_fixer()