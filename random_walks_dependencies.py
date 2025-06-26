"""
Complete dependencies for RandomWalks scene from hamming-codes-2.

This file contains all the custom classes and functions needed by the RandomWalks scene
that are not part of the standard ManimGL library.
"""

from manimlib import *


# From _2020/chess.py
def string_to_bools(message):
    """Convert a string message to a list of boolean values based on its binary representation."""
    # For easter eggs on the board
    as_int = int.from_bytes(message.encode(), 'big')
    bits = "{0:b}".format(as_int)
    bits = (len(message) * 8 - len(bits)) * '0' + bits
    return [bool(int(b)) for b in bits]


# Custom Lightbulb class (reconstructed based on usage)
class Lightbulb(SVGMobject):
    """
    A lightbulb SVG mobject used to represent ideas or insights.
    
    In the RandomWalks scene, it's used as:
        bulb = Lightbulb()
        bulb.next_to(idea_dot, UP)
    
    This represents the target/goal that the random walks are searching for.
    """
    
    def __init__(self, **kwargs):
        # Since we don't have the original SVG file, we create a VMobject approximation
        # that looks like a lightbulb
        
        # Create the bulb shape
        bulb = Circle(radius=0.5)
        bulb.stretch(1.3, 1)  # Make it more bulb-shaped
        
        # Create the base/screw part
        base_width = 0.35
        base_height = 0.3
        base = VGroup()
        
        # Base rectangle
        base_rect = Rectangle(width=base_width, height=base_height)
        base_rect.next_to(bulb, DOWN, buff=0)
        base.add(base_rect)
        
        # Add screw threads
        n_threads = 3
        for i in range(n_threads):
            y_offset = (i + 0.5) * base_height / n_threads
            thread = Line(
                base_rect.get_left() + [0, y_offset, 0],
                base_rect.get_right() + [0, y_offset, 0]
            )
            thread.set_stroke(width=1)
            base.add(thread)
        
        # Create filament inside bulb
        filament = VGroup()
        filament_height = bulb.get_height() * 0.5
        zigzag_points = []
        n_zigs = 4
        for i in range(n_zigs + 1):
            x = (-1)**(i) * bulb.get_width() * 0.15
            y = -filament_height/2 + i * filament_height / n_zigs
            zigzag_points.append(bulb.get_center() + [x, y, 0])
        
        filament_line = VMobject()
        filament_line.set_points_as_corners(zigzag_points)
        filament_line.set_stroke(color=YELLOW_E, width=2)
        filament.add(filament_line)
        
        # Combine all parts
        self.shape = VGroup(bulb, base, filament)
        
        # Initialize as VMobject since we don't have the SVG
        VMobject.__init__(self, **kwargs)
        
        # Add all the submobjects
        self.add(self.shape.copy())
        
        # Default styling
        self.set_height(1.5)
        self.set_stroke(color=WHITE, width=2)
        self.set_fill(color=YELLOW, opacity=0.3)
        
        # Make the base darker
        if len(self.submobjects) > 0:
            self[0][1].set_fill(GREY_B, opacity=1)


# Additional utility functions that might be used in hamming.py scenes

def get_background(color=GREY_E):
    """Create a full-screen background rectangle."""
    background = FullScreenRectangle()
    background.set_fill(color, 1)
    background.set_stroke(width=0)
    return background


def get_bit_grid(n_rows, n_cols, bits=None, buff=MED_SMALL_BUFF, height=4):
    """Create a grid of bit values (0s and 1s)."""
    bit_pair = VGroup(Integer(0), Integer(1))
    bit_mobs = VGroup(*[
        bit_pair.copy()
        for x in range(n_rows * n_cols)
    ])
    bit_mobs.arrange_in_grid(n_rows, n_cols, buff=buff)
    bit_mobs.set_height(height)
    if bits is None:
        bits = np.random.randint(0, 2, len(bit_mobs))

    for bit_mob, bit in zip(bit_mobs, bits):
        bit_mob[1 - bit].set_opacity(0)

    bit_mobs.n_rows = n_rows
    bit_mobs.n_cols = n_cols
    return bit_mobs


def get_bit_mob_value(bit_mob):
    """Get the value (0 or 1) from a bit mobject."""
    return int(bit_mob[1].get_fill_opacity() > bit_mob[0].get_fill_opacity())


def bit_grid_to_bits(bit_grid):
    """Convert a bit grid to a list of bit values."""
    return list(map(get_bit_mob_value, bit_grid))


def toggle_bit(bit):
    """Toggle a bit mobject between 0 and 1."""
    for sm in bit:
        sm.set_fill(opacity=1 - sm.get_fill_opacity())
    return bit


def hamming_syndrome(bits):
    """Calculate the Hamming syndrome for error detection."""
    return reduce(
        lambda i1, i2: i1 ^ i2,
        [i for i, b in enumerate(bits) if b],
        0,
    )


# Note: The RandomWalks scene is self-contained except for:
# 1. The Lightbulb class (defined above)
# 2. Standard ManimGL imports from manim_imports_ext
# 3. The string_to_bools function from chess.py (included above)
#
# The scene shows multiple random walks searching for an "idea" (represented by the lightbulb),
# demonstrating a visual metaphor for the search process in problem-solving.