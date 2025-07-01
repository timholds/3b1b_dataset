#!/usr/bin/env python3
"""Debug a specific scene that's failing in the actual pipeline."""

import sys
sys.path.append('/Users/timholdsworth/code/3b1b_dataset/scripts')

from enhanced_systematic_converter import EnhancedSystematicConverter

def test_actual_scene():
    """Test an actual scene from the inventing-math video."""
    
    # Get the actual scene code from the DivergentSum scene
    test_code = '''
from manim import *
import numpy as np
from typing import Optional, List, Dict, Union, Any
from functools import reduce
import string
import itertools as it
from random import sample
import itertools as it
import operator as op
import random
import sys

# Helper functions
def divergent_sum():
    return MathTex(DIVERGENT_SUM_TEXT).scale(2)

# Constants
DIVERGENT_SUM_TEXT = ['1', '+2', '+4', '+8', '+\\\\cdots', '+2^n', '+\\\\cdots', '= -1']

class DivergentSum(Scene):
    def construct(self):
        self.add(divergent_sum().scale(0.75))
'''
    
    print("=== Testing Actual Scene Code ===")
    
    # Create enhanced converter with more verbose output
    converter = EnhancedSystematicConverter(enable_claude_fallback=False)
    
    # Convert the scene
    try:
        result = converter.convert_scene(
            scene_code=test_code,
            scene_name="DivergentSum", 
            video_name="inventing-math",
            video_year="2015"
        )
        
        print(f"\n=== Conversion Result ===")
        print(f"Success: {result.success}")
        print(f"Method: {result.conversion_method}")
        print(f"Confidence: {result.confidence}")
        print(f"Errors: {result.errors}")
        
        # Check if the fix was applied
        if "''.join(DIVERGENT_SUM_TEXT)" in result.final_code:
            print("\n✅ AST LIST CONSTANT FIX: Applied correctly")
        else:
            print("\n❌ AST LIST CONSTANT FIX: NOT applied")
            
        # Print detailed fixes
        print(f"\n=== Systematic Fixes Applied ===")
        for fix in result.systematic_fixes_applied:
            print(f"  - {fix}")
            
        print(f"\n=== Claude Fixes Applied ===")
        for fix in result.claude_fixes_applied:
            print(f"  - {fix}")
            
        # Show a snippet of the final code to see what happened
        print(f"\n=== Final Code (first 20 lines) ===")
        lines = result.final_code.split('\n')
        for i, line in enumerate(lines[:20], 1):
            print(f"{i:2}: {line}")
            
    except Exception as e:
        print(f"\n❌ ERROR during conversion: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_actual_scene()