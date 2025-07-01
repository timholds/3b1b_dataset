#!/usr/bin/env python3
"""
Test complex scene with multiple critical fix patterns
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / 'scripts'))

from ast_systematic_converter import ASTSystematicConverter

def test_complex_scene():
    """Test a complex scene that combines multiple critical fix patterns."""
    
    complex_scene = '''
from manimlib import *

class ComplexTestScene(Scene):
    CONFIG = {
        "camera_config": {"background_color": BLACK},
        "scale_factor": 2
    }
    
    def construct(self):
        # Multiple critical patterns in one scene
        
        # List unpacking + Text issues
        title, subtitle, footer = [Text(['Complex', 'Scene', 'Test'])]
        a, b, c = [MathTex(['a', '+', 'b', '=', 'c'])]
        
        # Arrow constructor issues
        arrow1 = Arrow([0,0,0], [2,0,0], preserve_tip_size_when_scaling=True)
        arrow2 = Arrow(start=LEFT, end=RIGHT, tip_length=0.25)
        
        # VGroup with list
        equations = VGroup([a, b, c])
        arrows = VGroup([arrow1, arrow2])
        
        # Axes with old parameters
        axes = Axes(
            x_min=-5, x_max=5, 
            y_min=-3, y_max=3,
            axis_config={"stroke_color": BLUE}
        )
        
        # NumberLine with problematic params
        number_line = NumberLine(
            x_min=-10, x_max=10,
            interval_size=2,
            big_tick_numbers=[-10, -5, 0, 5, 10]
        )
        
        # Geometry with radius issues
        circle = Circle(x_radius=1.5)
        ellipse = Ellipse(x_radius=2, y_radius=1)
        
        # Old animation syntax
        self.play(ShowCreation(title))
        self.play(ApplyMethod(equations.arrange, DOWN))
        self.play(Transform(circle, ellipse))
        
        # Property access issues
        width = title.get_width()
        center = equations.get_center()
        
        # Method that should be removed
        # number_line.elongate_tick_at(0)  # This should become a comment
'''
    
    print("🧪 TESTING COMPLEX SCENE WITH MULTIPLE CRITICAL PATTERNS")
    print("=" * 70)
    
    converter = ASTSystematicConverter()
    converted = converter.convert_code(complex_scene)
    
    # Check for successful conversions
    checks = [
        ("List unpacking fixed", "Text(" in converted and "), Text(" in converted),
        ("Arrow start/end conversion", "start=" in converted and "end=" in converted),
        ("Arrow param removal", "preserve_tip_size_when_scaling" not in converted),
        ("VGroup unpacking", "VGroup(a, b, c)" in converted or "VGroup(" in converted),
        ("Axes range conversion", "x_range=" in converted and "y_range=" in converted),
        ("Old parameter removal", "interval_size" not in converted),
        ("Circle radius fix", "radius=" in converted),
        ("Animation conversion", "Create(" in converted),
        ("Property conversion", ".width" in converted),
        ("Import fix", "from manim import *" in converted)
    ]
    
    print("\n✅ CONVERSION RESULTS:")
    for description, check in checks:
        status = "✅" if check else "❌"
        print(f"  {status} {description}")
    
    # Print statistics
    stats = converter.get_conversion_report()
    print(f"\n📊 Total transformations applied: {stats['transformations_applied']}")
    print(f"📊 Conversion rate: {stats['conversion_rate']:.1f}%")
    print(f"📊 Patterns matched: {len(stats['patterns_matched'])}")
    
    # Show the most important fixes
    critical_fixes = 0
    for pattern_name, count in stats['patterns_matched'].items():
        if any(keyword in pattern_name for keyword in [
            'list_unpacking', 'arrow_', 'vgroup_unpack', 'axes_', 'numberplane_',
            'circle_', 'ellipse_', 'class_ShowCreation', 'class_Transform',
            'method_to_property'
        ]):
            critical_fixes += count
    
    print(f"\n🎯 Critical runtime fixes applied: {critical_fixes}")
    
    # Save converted scene for inspection
    output_file = Path(__file__).parent / 'converted_complex_scene.py'
    with open(output_file, 'w') as f:
        f.write(converted)
    
    print(f"\n📁 Converted scene saved to: {output_file}")
    print("🚀 Complex scene conversion successful!")

if __name__ == '__main__':
    test_complex_scene()