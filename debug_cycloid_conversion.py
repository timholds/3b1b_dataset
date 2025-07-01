#!/usr/bin/env python3
"""Debug script to test CycloidScene conversion issue."""

import ast
import sys
import os

# Add parent directory for imports  
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scripts.ast_systematic_converter import ASTSystematicConverter

# Test code with CycloidScene that's failing
test_code = '''
from manim import *

class CycloidScene(Scene):
    CONFIG = {
        "radius": 0.5,
        "end_theta": 2 * np.pi,
    }

    def construct(self):
        self.add_cycloid_and_circle()
        self.wait()

    def add_cycloid_and_circle(self):
        circle = Circle(radius=self.radius)
        cycloid = self.get_cycloid(self.radius)
        self.add(circle, cycloid)
    
    def get_cycloid(self, radius):
        return ParametricFunction(
            lambda t: np.array([
                radius * (t - np.sin(t)),
                radius * (1 - np.cos(t)),
                0
            ]),
            t_range=[0, self.end_theta],
            color=YELLOW
        )
'''

# Create converter
converter = ASTSystematicConverter()

# Convert the code
print("Original code:")
print(test_code)
print("\n" + "="*80 + "\n")

converted_code = converter.convert_code(test_code)

print("Converted code:")
print(converted_code)
print("\n" + "="*80 + "\n")

# Parse the converted code to check for empty class bodies
try:
    tree = ast.parse(converted_code)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            print(f"Class: {node.name}")
            print(f"  Number of body elements: {len(node.body)}")
            for i, stmt in enumerate(node.body):
                if isinstance(stmt, ast.Pass):
                    print(f"  Element {i}: Pass")
                elif isinstance(stmt, ast.FunctionDef):
                    print(f"  Element {i}: Function {stmt.name}")
                elif isinstance(stmt, ast.Assign):
                    print(f"  Element {i}: Assignment")
                else:
                    print(f"  Element {i}: {type(stmt).__name__}")
except Exception as e:
    print(f"Error parsing converted code: {e}")

print("\nConversion stats:")
for key, value in converter.stats.__dict__.items():
    if value:
        print(f"  {key}: {value}")