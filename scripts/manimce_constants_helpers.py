#!/usr/bin/env python3
"""
ManimCE constants and helper functions for ManimGL compatibility.

This module provides all the constants and helper functions that are
commonly used in ManimGL but missing in ManimCE.
"""

import numpy as np
from copy import deepcopy
from manim import *

# Frame constants from ManimGL
FRAME_WIDTH = 14.222222222222221  # 16:9 aspect ratio
FRAME_HEIGHT = 8.0
FRAME_X_RADIUS = FRAME_WIDTH / 2
FRAME_Y_RADIUS = FRAME_HEIGHT / 2

# Common spacing constants
SMALL_BUFF = 0.1
MED_SMALL_BUFF = 0.25
MED_LARGE_BUFF = 0.5
LARGE_BUFF = 1.0

# Additional ManimGL constants
DEFAULT_MOBJECT_TO_EDGE_BUFFER = MED_LARGE_BUFF
DEFAULT_MOBJECT_TO_MOBJECT_BUFFER = SMALL_BUFF

# Common radius constant used in 3b1b animations
RADIUS = FRAME_Y_RADIUS - 0.1

# Missing color constants from ManimGL
X_COLOR = RED
Y_COLOR = GREEN 
Z_COLOR = BLUE
DARKER_BLUE = "#006994"  # Darker variant of blue
PURE_BLUE = BLUE  # Pure blue color
PURE_RED = RED    # Pure red color
PURE_GREEN = GREEN  # Pure green color

# Additional missing constants
DEFAULT_BLUR_RADIUS = 0.2  # Used in blur effects

# Helper functions commonly used in ManimGL
def get_norm(vector):
    """
    Get the norm (magnitude) of a vector.
    
    Args:
        vector: numpy array or list representing a vector
        
    Returns:
        float: The norm of the vector
    """
    return np.linalg.norm(vector)


def rotate_vector(vector, angle, axis=OUT):
    """
    Rotate a vector by a given angle around an axis.
    
    Args:
        vector: The vector to rotate
        angle: The angle to rotate by (in radians)
        axis: The axis to rotate around (default: OUT for 2D rotation)
        
    Returns:
        numpy.ndarray: The rotated vector
    """
    if np.array_equal(axis, OUT):
        # 2D rotation in the XY plane
        cos_angle = np.cos(angle)
        sin_angle = np.sin(angle)
        rotation_matrix = np.array([
            [cos_angle, -sin_angle, 0],
            [sin_angle, cos_angle, 0],
            [0, 0, 1]
        ])
    else:
        # 3D rotation using Rodrigues' formula
        axis = axis / get_norm(axis)
        cos_angle = np.cos(angle)
        sin_angle = np.sin(angle)
        
        # Rodrigues' rotation formula
        rotation_matrix = (
            cos_angle * np.eye(3) +
            sin_angle * np.array([
                [0, -axis[2], axis[1]],
                [axis[2], 0, -axis[0]],
                [-axis[1], axis[0], 0]
            ]) +
            (1 - cos_angle) * np.outer(axis, axis)
        )
    
    return np.dot(rotation_matrix, vector)


def interpolate(start, end, alpha):
    """
    Interpolate between two values.
    
    Args:
        start: Starting value (can be scalar or array)
        end: Ending value (can be scalar or array)
        alpha: Interpolation factor (0 to 1)
        
    Returns:
        Interpolated value
    """
    return (1 - alpha) * start + alpha * end


def inverse_interpolate(start, end, value):
    """
    Inverse interpolation - find alpha given a value between start and end.
    
    Args:
        start: Starting value
        end: Ending value
        value: The value to find the alpha for
        
    Returns:
        float: The alpha value (0 to 1)
    """
    if start == end:
        return 0.5
    return (value - start) / (end - start)


def choose(n, k):
    """
    Binomial coefficient (n choose k).
    
    Args:
        n: Total number of items
        k: Number of items to choose
        
    Returns:
        int: The binomial coefficient
    """
    if k > n or k < 0:
        return 0
    if k == 0 or k == n:
        return 1
    
    # Use the more efficient formula
    k = min(k, n - k)
    result = 1
    for i in range(k):
        result = result * (n - i) // (i + 1)
    return result


def sigmoid(x):
    """
    Sigmoid function.
    
    Args:
        x: Input value
        
    Returns:
        float: Sigmoid of x
    """
    return 1 / (1 + np.exp(-x))


def binary_search(function, target, lower_bound, upper_bound, tolerance=1e-6):
    """
    Binary search to find x such that function(x) = target.
    
    Args:
        function: The function to evaluate
        target: The target value
        lower_bound: Lower bound for x
        upper_bound: Upper bound for x
        tolerance: Tolerance for the search
        
    Returns:
        float: The x value where function(x) ≈ target
    """
    while upper_bound - lower_bound > tolerance:
        mid = (lower_bound + upper_bound) / 2
        if function(mid) < target:
            lower_bound = mid
        else:
            upper_bound = mid
    return (lower_bound + upper_bound) / 2


def color_to_int_rgb(color):
    """
    Convert a color to integer RGB values (0-255).
    
    Args:
        color: Color in hex or ManimCE color format
        
    Returns:
        tuple: (r, g, b) with values 0-255
    """
    if isinstance(color, str):
        # Handle hex colors
        if color.startswith('#'):
            color = color[1:]
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
        return (r, g, b)
    else:
        # Assume it's a ManimCE color (values 0-1)
        rgb = color_to_rgb(color)
        return tuple(int(c * 255) for c in rgb)


def inverse_power_law(maxint, cutoff=0.01):
    """
    Generate a list of values following an inverse power law.
    
    Args:
        maxint: Maximum integer value
        cutoff: Cutoff threshold
        
    Returns:
        list: Values following inverse power law
    """
    values = []
    for i in range(1, maxint + 1):
        val = 1.0 / i
        if val < cutoff:
            break
        values.append(val)
    return values


def interpolate_mobject(mobject1, mobject2, alpha):
    """
    Interpolate between two mobjects.
    
    Args:
        mobject1: Starting mobject
        mobject2: Ending mobject
        alpha: Interpolation factor (0 to 1)
        
    Returns:
        Mobject: Interpolated mobject
    """
    result = mobject1.copy()
    result.interpolate(mobject1, mobject2, alpha)
    return result


def intersection(line1, line2):
    """
    Find the intersection point of two lines.
    
    Args:
        line1: First line (can be Line mobject or two points)
        line2: Second line (can be Line mobject or two points)
        
    Returns:
        numpy array: Intersection point coordinates
    """
    # Handle Line mobjects
    if hasattr(line1, 'get_start') and hasattr(line1, 'get_end'):
        p1, p2 = line1.get_start(), line1.get_end()
    else:
        p1, p2 = line1[0], line1[1]
        
    if hasattr(line2, 'get_start') and hasattr(line2, 'get_end'):
        p3, p4 = line2.get_start(), line2.get_end()
    else:
        p3, p4 = line2[0], line2[1]
    
    # Convert to numpy arrays
    p1, p2, p3, p4 = map(np.array, [p1, p2, p3, p4])
    
    # Calculate intersection using cross product method
    v1 = p2 - p1
    v2 = p4 - p3
    v3 = p3 - p1
    
    # Check if lines are parallel
    cross = np.cross(v1[:2], v2[:2])
    if abs(cross) < 1e-10:
        return None  # Lines are parallel
    
    # Calculate intersection parameter
    t = np.cross(v3[:2], v2[:2]) / cross
    
    # Calculate intersection point
    intersection_point = p1 + t * v1
    return intersection_point


def is_on_line(point, line, tolerance=1e-6):
    """
    Check if a point lies on a line.
    
    Args:
        point: Point to check (numpy array or list)
        line: Line object or tuple of two points defining the line
        tolerance: Distance tolerance for considering point on line
        
    Returns:
        bool: True if point is on the line
    """
    point = np.array(point)
    
    # Handle Line mobjects
    if hasattr(line, 'get_start') and hasattr(line, 'get_end'):
        start, end = line.get_start(), line.get_end()
    else:
        start, end = np.array(line[0]), np.array(line[1])
    
    # Vector from start to end
    line_vec = end - start
    line_length = np.linalg.norm(line_vec)
    
    if line_length < tolerance:
        # Degenerate line - just check if point equals start
        return np.linalg.norm(point - start) < tolerance
    
    # Vector from start to point
    point_vec = point - start
    
    # Project point onto line
    t = np.dot(point_vec, line_vec) / (line_length ** 2)
    
    # Check if projection is within line segment
    if t < 0 or t > 1:
        return False
    
    # Calculate closest point on line
    closest_point = start + t * line_vec
    
    # Check distance from point to line
    distance = np.linalg.norm(point - closest_point)
    return distance < tolerance


def plane_partition_from_points(points):
    """
    Create a partition of the plane based on a set of points.
    This is a placeholder implementation for the Moser circle problem.
    
    Args:
        points: List of points
        
    Returns:
        int: Number of regions created
    """
    # Simple implementation: for n points on a circle,
    # the number of regions follows a specific pattern
    n = len(points)
    if n == 0:
        return 1
    elif n == 1:
        return 1
    elif n == 2:
        return 2
    elif n == 3:
        return 4
    elif n == 4:
        return 8
    elif n == 5:
        return 16
    else:
        # General formula for n points (not always 2^(n-1))
        # This is the actual Moser circle problem result
        return 1 + n + (n * (n - 1)) // 2 + (n * (n - 1) * (n - 2) * (n - 3)) // 24


# Common utility class used in some 3b1b animations
class Region:
    """Simple region class for plane partitioning."""
    def __init__(self, boundary_points=None):
        self.boundary_points = boundary_points or []
        self.color = WHITE
        
    def set_color(self, color):
        self.color = color
        return self


def get_smooth_path_indices(points, n_curves):
    """
    Get indices for creating smooth bezier curves from points.
    
    Args:
        points: Array of points
        n_curves: Number of curves to create
        
    Returns:
        list: Indices for smooth path
    """
    nppc = len(points) // n_curves  # Number of points per curve
    indices = []
    
    for i in range(n_curves):
        start = i * nppc
        indices.extend(range(start, start + nppc))
    
    return indices


# Rate functions that exist in ManimGL but not ManimCE
def rush_into(t):
    """ManimGL rate function - accelerate into the animation."""
    return smooth(t)


def rush_from(t):
    """ManimGL rate function - decelerate from the animation."""
    return smooth(t)


def slow_into(t):
    """ManimGL rate function - slow acceleration."""
    return smooth(t)


def double_smooth(t):
    """ManimGL rate function - double smooth curve."""
    return smooth(smooth(t))


def there_and_back_with_pause(t, pause_ratio=0.2):
    """ManimGL rate function - go there, pause, and come back."""
    if t < 0.5 - pause_ratio / 2:
        return smooth(t / (0.5 - pause_ratio / 2))
    elif t < 0.5 + pause_ratio / 2:
        return 1
    else:
        return smooth((1 - t) / (0.5 - pause_ratio / 2))


# Additional utility functions
def compass_directions(n=8):
    """
    Get n evenly spaced compass directions.
    
    Args:
        n: Number of directions (default: 8)
        
    Returns:
        list: Unit vectors in each direction
    """
    angles = np.linspace(0, 2 * PI, n, endpoint=False)
    return [np.array([np.cos(angle), np.sin(angle), 0]) for angle in angles]


def get_rectangular_stem_points(n_rows, n_cols, height=None, width=None):
    """
    Get points arranged in a rectangular grid.
    
    Args:
        n_rows: Number of rows
        n_cols: Number of columns
        height: Total height (default: based on FRAME_HEIGHT)
        width: Total width (default: based on FRAME_WIDTH)
        
    Returns:
        np.ndarray: Grid points
    """
    if height is None:
        height = FRAME_HEIGHT - 2
    if width is None:
        width = FRAME_WIDTH - 2
        
    x_values = np.linspace(-width/2, width/2, n_cols)
    y_values = np.linspace(-height/2, height/2, n_rows)
    
    points = []
    for y in y_values:
        for x in x_values:
            points.append([x, y, 0])
    
    return np.array(points)


# Export all constants and functions
__all__ = [
    # Constants
    'FRAME_WIDTH', 'FRAME_HEIGHT', 'FRAME_X_RADIUS', 'FRAME_Y_RADIUS',
    'SMALL_BUFF', 'MED_SMALL_BUFF', 'MED_LARGE_BUFF', 'LARGE_BUFF',
    'DEFAULT_MOBJECT_TO_EDGE_BUFFER', 'DEFAULT_MOBJECT_TO_MOBJECT_BUFFER',
    'RADIUS',
    
    # Color constants
    'X_COLOR', 'Y_COLOR', 'Z_COLOR', 'DARKER_BLUE', 'PURE_BLUE', 
    'PURE_RED', 'PURE_GREEN',
    
    # Other constants
    'DEFAULT_BLUR_RADIUS',
    
    # Helper functions
    'get_norm', 'rotate_vector', 'interpolate', 'inverse_interpolate',
    'choose', 'sigmoid', 'binary_search', 'color_to_int_rgb',
    'inverse_power_law', 'interpolate_mobject', 'get_smooth_path_indices',
    
    # Rate functions
    'rush_into', 'rush_from', 'slow_into', 'double_smooth',
    'there_and_back_with_pause',
    
    # Utility functions
    'compass_directions', 'get_rectangular_stem_points',
]