#!/usr/bin/env python3
"""
Test cases demonstrating what the pre-compilation validator can catch.

This file contains examples of common ManimGL→ManimCE conversion errors
and shows how the validator detects them before compilation.
"""

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from manimce_precompile_validator import ManimCEPrecompileValidator


# Test Case 1: Import Issues
TEST_CASE_IMPORTS = '''
# Wrong imports
from manimlib import *  # ERROR: Should be 'manim'
from manimlib.animation.creation import ShowCreation  # ERROR: manimlib
from custom.some_module import CustomClass  # WARNING: Problematic import
from once_useful_constructs import *  # WARNING: Problematic import

# Missing manim import entirely
import numpy as np
import os
'''

# Test Case 2: Deprecated Classes and APIs
TEST_CASE_DEPRECATED = '''
from manim import *

class MyScene(Scene):
    def construct(self):
        # Deprecated text classes
        text1 = TextMobject("Hello")  # ERROR: Use Text
        text2 = TexMobject("x^2")  # ERROR: Use MathTex
        text3 = TexText("LaTeX")  # ERROR: Use Tex
        text4 = OldTex("formula")  # ERROR: Use Tex
        
        # Deprecated animations
        self.play(ShowCreation(text1))  # ERROR: Use Create
        self.play(ShowCreationThenDestruction(text2))  # ERROR: Use ShowPassingFlash
        
        # ContinualAnimation
        class MyUpdater(ContinualAnimation):  # ERROR: Use add_updater
            def update_mobject(self, dt):
                pass
'''

# Test Case 3: Method/Property Issues
TEST_CASE_METHODS = '''
from manim import *

class PropertyScene(Scene):
    def construct(self):
        circle = Circle()
        
        # Methods that should be properties
        w = circle.get_width()  # WARNING: Use .width
        h = circle.get_height()  # WARNING: Use .height
        
        # Set methods that need updating
        circle.set_width(2)  # INFO: Could use circle.width = 2
        circle.set_height(3)  # INFO: Could use circle.height = 3
        
        # These are fine
        center = circle.get_center()  # OK
        circle.to_corner(UP)  # OK
'''

# Test Case 4: Scene Structure Issues
TEST_CASE_SCENE_STRUCTURE = '''
from manim import *

# Scene without construct method
class BrokenScene(Scene):  # ERROR: Missing construct method
    def setup(self):
        self.camera.background_color = BLACK
    
    def my_animation(self):
        # This won't be called automatically
        pass

# Scene with CONFIG dict
class OldStyleScene(Scene):
    CONFIG = {  # WARNING: CONFIG dict is deprecated
        "camera_config": {"background_color": WHITE},
        "num_points": 100
    }
    
    def construct(self):
        pass

# Scene with wrong construct signature
class WrongConstructScene(Scene):
    def construct(self, extra_param):  # ERROR: construct should only have 'self'
        pass
'''

# Test Case 5: TeX String Issues
TEST_CASE_TEX_STRINGS = '''
from manim import *

class TexScene(Scene):
    def construct(self):
        # TeX strings without raw strings
        formula1 = Tex("\\frac{1}{2}")  # WARNING: Use raw string
        formula2 = MathTex("\\alpha + \\beta")  # WARNING: Use raw string
        formula3 = Tex("\\\\")  # WARNING: Use raw string
        
        # Correct usage
        formula4 = Tex(r"\\frac{1}{2}")  # OK
        formula5 = MathTex(r"\\alpha + \\beta")  # OK
'''

# Test Case 6: Pi Creature Usage
TEST_CASE_PI_CREATURES = '''
from manim import *

class PiCreatureScene(Scene):
    def construct(self):
        # Pi Creatures not available
        pi = PiCreature()  # ERROR: Not available in ManimCE
        randy = Randolph()  # ERROR: Not available
        morty = Mortimer()  # ERROR: Not available
        
        students = get_students()  # ERROR: Not available
        
        # Using pi creature methods
        pi.change_mode("happy")  # ERROR: Pi creature method
'''

# Test Case 7: Syntax Errors
TEST_CASE_SYNTAX = '''
from manim import *

class SyntaxErrorScene(Scene):
    def construct(self)  # ERROR: Missing colon
        circle = Circle()
        
        # Unclosed parenthesis
        self.play(Create(circle)  # ERROR: Missing closing parenthesis
        
        # Invalid indentation
       square = Square()  # ERROR: Inconsistent indentation
        
        # Unclosed string
        text = Text("Hello  # ERROR: Unclosed string
'''

# Test Case 8: Undefined References
TEST_CASE_UNDEFINED = '''
# No imports!

class NoImportScene(Scene):  # ERROR: Scene not imported
    def construct(self):
        # Using undefined classes
        circle = Circle()  # ERROR: Circle not imported
        self.play(Create(circle))  # ERROR: Create not imported
        
        # Using undefined constants
        circle.move_to(UP * 2)  # ERROR: UP not imported
        circle.set_color(BLUE)  # ERROR: BLUE not imported
'''


def run_validation_examples():
    """Run validation on all test cases and show results."""
    validator = ManimCEPrecompileValidator(verbose=True)
    
    test_cases = [
        ("Import Issues", TEST_CASE_IMPORTS),
        ("Deprecated Classes", TEST_CASE_DEPRECATED),
        ("Method/Property Issues", TEST_CASE_METHODS),
        ("Scene Structure", TEST_CASE_SCENE_STRUCTURE),
        ("TeX Strings", TEST_CASE_TEX_STRINGS),
        ("Pi Creatures", TEST_CASE_PI_CREATURES),
        ("Syntax Errors", TEST_CASE_SYNTAX),
        ("Undefined References", TEST_CASE_UNDEFINED)
    ]
    
    for name, code in test_cases:
        print(f"\n{'='*60}")
        print(f"Test Case: {name}")
        print(f"{'='*60}")
        
        # Validate the code
        report = validator.validate_file(f"test_{name}.py", content=code)
        
        print(f"\nValidation Results:")
        print(f"  Valid: {report.is_valid}")
        print(f"  Errors: {len(report.errors)}")
        print(f"  Warnings: {len(report.warnings)}")
        print(f"  Info: {len(report.info)}")
        
        if report.errors:
            print("\nErrors Found:")
            for error in report.errors:
                print(f"  Line {error.line_number}: [{error.error_type}] {error.message}")
                if error.suggestion:
                    print(f"    → Suggestion: {error.suggestion}")
                if error.code_snippet:
                    print(f"    Code: {error.code_snippet.strip()}")
        
        if report.warnings:
            print("\nWarnings:")
            for warning in report.warnings[:3]:  # Show first 3
                print(f"  Line {warning.line_number}: [{warning.error_type}] {warning.message}")
                if warning.suggestion:
                    print(f"    → Suggestion: {warning.suggestion}")


def demonstrate_successful_validation():
    """Show an example of code that passes validation."""
    good_code = '''
from manim import *

class WellFormedScene(Scene):
    """A properly structured ManimCE scene."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.camera.background_color = "#1e1e1e"
    
    def construct(self):
        # Create objects with correct API
        title = Text("ManimCE Example", font_size=48)
        equation = MathTex(r"E = mc^2", font_size=36)
        circle = Circle(radius=1, color=BLUE)
        square = Square(side_length=2, color=RED)
        
        # Position objects
        title.to_edge(UP)
        equation.next_to(title, DOWN, buff=0.5)
        circle.shift(LEFT * 2)
        square.shift(RIGHT * 2)
        
        # Animate with correct animations
        self.play(Write(title))
        self.play(FadeIn(equation))
        self.play(
            Create(circle),
            Create(square),
            run_time=2
        )
        
        # Use updaters instead of ContinualAnimation
        def rotate_updater(mob, dt):
            mob.rotate(PI * dt)
        
        square.add_updater(rotate_updater)
        self.wait(2)
        square.remove_updater(rotate_updater)
        
        # Transform with correct methods
        self.play(
            Transform(circle, square),
            FadeOut(equation)
        )
        
        self.wait()

class Another3DScene(ThreeDScene):
    """Example of a 3D scene."""
    
    def construct(self):
        axes = ThreeDAxes()
        self.set_camera_orientation(phi=75 * DEGREES, theta=30 * DEGREES)
        
        self.play(Create(axes))
        
        # Create a parametric surface
        surface = Surface(
            lambda u, v: axes.c2p(u, v, u**2 - v**2),
            u_range=[-2, 2],
            v_range=[-2, 2],
            resolution=(30, 30)
        )
        
        self.play(Create(surface))
        self.begin_ambient_camera_rotation(rate=0.5)
        self.wait(5)
'''
    
    print(f"\n{'='*60}")
    print("Example of Valid ManimCE Code")
    print(f"{'='*60}")
    
    validator = ManimCEPrecompileValidator(verbose=True)
    report = validator.validate_file("good_example.py", content=good_code)
    
    print(f"\nValidation Results:")
    print(f"  Valid: {report.is_valid} ✓")
    print(f"  Errors: {len(report.errors)}")
    print(f"  Warnings: {len(report.warnings)}")
    print(f"\nStatistics:")
    for key, value in report.statistics.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    print("ManimCE Pre-Compilation Validator Test Cases")
    print("=" * 60)
    
    # Run validation on problematic examples
    run_validation_examples()
    
    # Show a good example
    demonstrate_successful_validation()
    
    print("\n\nConclusion:")
    print("The pre-compilation validator can catch:")
    print("- Syntax errors before running Python")
    print("- Import issues (manimlib vs manim)")
    print("- Deprecated ManimGL APIs")
    print("- Missing construct methods")
    print("- TeX string escaping issues")
    print("- Pi Creature usage")
    print("- Undefined references")
    print("- Method/property deprecations")
    print("\nThis helps identify issues before the expensive rendering step!")