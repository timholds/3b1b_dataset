"""
Lightbulb class definition for RandomWalks scene from hamming-codes-2.

Based on investigation, Lightbulb appears to be an SVGMobject that was likely
part of the original manimlib but not included in the public repositories.

This implementation provides a simple Lightbulb class that should work for
the RandomWalks scene where it's used with:
    bulb = Lightbulb()
    bulb.next_to(idea_dot, UP)
"""

from manimlib import *


class Lightbulb(SVGMobject):
    """
    A lightbulb SVG mobject, likely used to represent ideas or insights.
    
    Since the original SVG file is not available, this implementation creates
    a simple geometric approximation of a lightbulb shape.
    """
    
    def __init__(self, **kwargs):
        # Set default properties
        self.height = 1.5
        self.color = YELLOW
        self.stroke_color = WHITE
        self.stroke_width = 2
        self.fill_opacity = 0.8
        
        # If we had the original SVG file, we would use:
        # super().__init__(file_name="lightbulb", **kwargs)
        
        # Since we don't have the SVG, create a geometric approximation
        self.shape = self.create_lightbulb_shape()
        
        # Initialize as VMobject instead of SVGMobject
        VMobject.__init__(self, **kwargs)
        self.set_points(self.shape.get_points())
        
        # Apply styling
        self.set_height(self.height)
        self.set_stroke(self.stroke_color, self.stroke_width)
        self.set_fill(self.color, self.fill_opacity)
    
    def create_lightbulb_shape(self):
        """Create a simple geometric approximation of a lightbulb."""
        # Create bulb part (circle/ellipse)
        bulb = Circle(radius=0.5)
        bulb.stretch(1.2, 1)  # Make it slightly taller
        
        # Create base/screw part
        base_width = 0.3
        base_height = 0.25
        base = Rectangle(width=base_width, height=base_height)
        base.next_to(bulb, DOWN, buff=0)
        
        # Create screw threads
        thread_lines = VGroup()
        n_threads = 3
        for i in range(n_threads):
            y = base.get_bottom()[1] + (i + 0.5) * base_height / n_threads
            thread = Line(
                base.get_left() + [0, y - base.get_bottom()[1], 0],
                base.get_right() + [0, y - base.get_bottom()[1], 0]
            )
            thread_lines.add(thread)
        
        # Combine all parts
        lightbulb = VGroup(bulb, base, thread_lines)
        
        return lightbulb


# Alternative implementation using Unicode character
class SimpleLightbulb(Text):
    """
    A very simple lightbulb implementation using the Unicode lightbulb character.
    This can be used as a fallback if the geometric version has issues.
    """
    
    def __init__(self, **kwargs):
        super().__init__("💡", **kwargs)
        self.set_height(1.5)
        self.set_color(YELLOW)


# Function to create appropriate Lightbulb based on context
def get_lightbulb_for_scene():
    """
    Returns a Lightbulb instance appropriate for the RandomWalks scene.
    
    In the RandomWalks scene from hamming.py, the Lightbulb is used like:
        bulb = Lightbulb()
        bulb.next_to(idea_dot, UP)
    
    This suggests it's a visual representation of an "idea" or "eureka moment".
    """
    try:
        # Try to use the geometric version
        return Lightbulb()
    except:
        # Fallback to simple version
        return SimpleLightbulb()


# Notes on usage in RandomWalks scene:
# - The Lightbulb is positioned next to an "idea_dot" at coordinates (10, 3)
# - It represents the target/goal of the random walk search
# - The scene shows multiple paths searching for this "idea"
# - When a path reaches the idea spot, it likely triggers some visual effect