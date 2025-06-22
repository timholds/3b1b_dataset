#!/usr/bin/env python3
"""
Test if ManimCE is installed and can render a simple scene
"""

from manim import *

class TestScene(Scene):
    def construct(self):
        # Create a simple test animation
        circle = Circle(color=BLUE)
        square = Square(color=RED)
        
        self.play(Create(circle))
        self.wait(0.5)
        self.play(Transform(circle, square))
        self.wait(0.5)
        self.play(FadeOut(square))

if __name__ == "__main__":
    # This will be run by manim command line tool
    pass