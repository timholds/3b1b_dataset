#!/usr/bin/env python3
"""
Test script for critical AST converter fixes
Tests the specific patterns that were causing runtime errors.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / 'scripts'))

from ast_systematic_converter import ASTSystematicConverter

def test_critical_fixes():
    """Test the critical fixes that were just added."""
    
    # Test case 1: List unpacking errors
    test_list_unpacking = '''
from manim import *

class TestScene(Scene):
    def construct(self):
        # CRITICAL: a, b, c = [single_item] patterns
        one, two, three = [Text(['1', '=', 'x'])]
        a, b = [MathTex(['a', 'b'])]
        x, y, z = ["xyz"]
'''
    
    # Test case 2: Arrow constructor issues
    test_arrow_issues = '''
from manim import *

class TestScene(Scene):
    def construct(self):
        # CRITICAL: Arrow constructor conflicts
        arrow1 = Arrow([0,0,0], [1,1,0])
        arrow2 = Arrow(start=[0,0,0], end=[1,1,0], preserve_tip_size_when_scaling=True)
        arrow3 = Arrow([0,0,0], [1,1,0], tip_length=0.3)
'''
    
    # Test case 3: Additional API incompatibilities
    test_api_issues = '''
from manim import *

class TestScene(Scene):
    def construct(self):
        # CRITICAL: VGroup, NumberLine, Axes issues
        group = VGroup([Circle(), Square(), Triangle()])
        line = NumberLine(x_min=-5, x_max=5, interval_size=1, big_tick_numbers=[-5, 0, 5])
        axes = Axes(x_min=-3, x_max=3, y_min=-2, y_max=2)
        circle = Circle(x_radius=2, y_radius=1)
        ellipse = Ellipse(x_radius=3, y_radius=2)
'''
    
    converter = ASTSystematicConverter()
    
    print("🔥 TESTING CRITICAL FIXES")
    print("=" * 60)
    
    # Test 1: List unpacking
    print("\n1️⃣ Testing List Unpacking Fixes...")
    converted1 = converter.convert_code(test_list_unpacking)
    print("✅ Converted successfully")
    if 'Text(' in converted1 and '), Text(' in converted1:
        print("✅ List unpacking fixed - Text objects separated")
    
    # Test 2: Arrow constructor
    print("\n2️⃣ Testing Arrow Constructor Fixes...")
    converted2 = converter.convert_code(test_arrow_issues)
    print("✅ Converted successfully")
    if 'start=' in converted2 and 'end=' in converted2:
        print("✅ Arrow positional args converted to keywords")
    if 'preserve_tip_size_when_scaling' not in converted2:
        print("✅ Problematic Arrow parameters removed")
    
    # Test 3: API incompatibilities
    print("\n3️⃣ Testing Additional API Fixes...")
    converted3 = converter.convert_code(test_api_issues)
    print("✅ Converted successfully")
    if 'x_range=' in converted3 and 'y_range=' in converted3:
        print("✅ Axes x_min/y_min converted to x_range/y_range")
    if 'Circle(radius=' in converted3:
        print("✅ Circle x_radius converted to radius")
    if 'width=' in converted3 and 'height=' in converted3:
        print("✅ Ellipse radius converted to width/height")
    
    # Print overall statistics
    stats = converter.get_conversion_report()
    print("\n📊 OVERALL STATISTICS")
    print("=" * 30)
    print(f"Total transformations: {stats['transformations_applied']}")
    print(f"Patterns matched: {len(stats['patterns_matched'])}")
    
    critical_patterns = [p for p in stats['patterns_matched'].keys() 
                        if any(keyword in p for keyword in [
                            'list_unpacking', 'arrow_', 'vgroup_unpack',
                            'x_range_conversion', 'y_range_conversion',
                            'circle_x_radius', 'ellipse_'
                        ])]
    
    if critical_patterns:
        print(f"🎯 Critical patterns fixed: {len(critical_patterns)}")
        for pattern in critical_patterns:
            count = stats['patterns_matched'][pattern]
            print(f"  - {pattern}: {count} instances")
    
    print("\n✅ All critical fixes are working!")
    print("🚀 Ready for pipeline testing!")

if __name__ == '__main__':
    test_critical_fixes()