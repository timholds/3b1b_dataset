# Missing dependencies for CylinderModel scene
# Sources: div_curl.py and manimGL library

import numpy as np
from manim import *

# Mathematical transformation functions from div_curl.py
def joukowsky_map(z):
    """Joukowsky transformation - maps a circle to an airfoil shape.
    
    Args:
        z: Complex number input
        
    Returns:
        Complex number result of z + 1/z
    """
    if z == 0:
        return 0
    return z + 1/z  # Note: fdiv replaced with regular division for ManimCE


def inverse_joukowsky_map(w):
    """Inverse Joukowsky transformation.
    
    Args:
        w: Complex number input
        
    Returns:
        Complex number - one of the two inverse values
    """
    u = 1 if w.real >= 0 else -1
    return (w + u * np.sqrt(w**2 - 4)) / 2


def derivative(func, dt=1e-7):
    """Numerical derivative of a complex function.
    
    Args:
        func: Function to differentiate
        dt: Small step size for numerical differentiation
        
    Returns:
        Derivative function
    """
    return lambda z: (func(z + dt) - func(z)) / dt


def R3_to_complex(point):
    """Convert a 3D point to a complex number (using x and y coordinates).
    
    Args:
        point: 3D numpy array [x, y, z]
        
    Returns:
        Complex number x + iy
    """
    return complex(point[0], point[1])


def complex_to_R3(z):
    """Convert a complex number to a 3D point.
    
    Args:
        z: Complex number
        
    Returns:
        3D numpy array [Re(z), Im(z), 0]
    """
    return np.array([z.real, z.imag, 0])


def cylinder_flow_vector_field(point, R=1, U=1):
    """Vector field representing flow around a cylinder.
    
    Uses the Joukowsky transformation to model fluid flow.
    
    Args:
        point: 3D point where to evaluate the field
        R: Cylinder radius (default: 1)
        U: Flow velocity (default: 1)
        
    Returns:
        3D vector representing the flow at that point
    """
    z = R3_to_complex(point)
    # Flow is related to the derivative of the Joukowsky map
    return complex_to_R3(derivative(joukowsky_map)(z).conjugate())


# ManimGL Classes that need to be implemented for ManimCE

class ComplexPlane(NumberPlane):
    """A coordinate plane for visualizing complex numbers.
    
    This is a ManimGL class that extends NumberPlane with complex number features.
    In ManimCE, we can use NumberPlane with some customization.
    """
    def __init__(self, **kwargs):
        # Set default configuration for complex plane
        default_config = {
            "x_range": [-5, 5, 1],
            "y_range": [-5, 5, 1],
            "background_line_style": {
                "stroke_color": BLUE_D,
                "stroke_width": 1,
                "stroke_opacity": 0.5,
            }
        }
        default_config.update(kwargs)
        super().__init__(**default_config)
        
    def n2p(self, number):
        """Number to point - handles complex numbers."""
        if isinstance(number, complex):
            return self.coords_to_point(number.real, number.imag)
        return super().n2p(number)
    
    def p2n(self, point):
        """Point to number - returns complex number."""
        x, y = self.point_to_coords(point)
        return complex(x, y)


class StreamLines(VGroup):
    """Streamlines for visualizing vector fields.
    
    This is a simplified version of the ManimGL StreamLines class.
    Creates curves that follow the flow of a vector field.
    """
    def __init__(self, 
                 func,
                 start_points=None,
                 dt=0.05,
                 max_time=5,
                 min_magnitude=0.1,
                 **kwargs):
        super().__init__(**kwargs)
        
        self.func = func
        self.dt = dt
        self.max_time = max_time
        self.min_magnitude = min_magnitude
        
        if start_points is None:
            # Create default grid of starting points
            start_points = []
            for x in np.linspace(-5, 5, 20):
                for y in np.linspace(-3, 3, 12):
                    start_points.append(np.array([x, y, 0]))
        
        # Create stream lines
        for start_point in start_points:
            line = self.create_stream_line(start_point)
            if len(line.points) > 1:  # Only add non-trivial lines
                self.add(line)
    
    def create_stream_line(self, start_point):
        """Create a single stream line starting from a point."""
        points = [start_point]
        point = start_point.copy()
        time = 0
        
        while time < self.max_time:
            vector = self.func(point)
            magnitude = get_norm(vector)
            
            if magnitude < self.min_magnitude:
                break
                
            # Normalize step size
            step = vector * self.dt / magnitude
            point = point + step
            points.append(point.copy())
            time += self.dt
            
            # Stop if we've left the frame
            if abs(point[0]) > 10 or abs(point[1]) > 10:
                break
        
        line = VMobject()
        if len(points) > 1:
            line.set_points_as_corners(points)
            line.set_stroke(BLUE, width=2, opacity=0.8)
        return line


class AnimatedStreamLines(AnimationGroup):
    """Animated version of StreamLines using ShowPassingFlash.
    
    This creates an animation where stream lines appear to flow.
    """
    def __init__(self, stream_lines, lag_ratio=0.01, run_time=3, **kwargs):
        if not isinstance(stream_lines, StreamLines):
            # If passed a vector field function, create StreamLines first
            stream_lines = StreamLines(stream_lines)
        
        # Create ShowPassingFlash animations for each line
        animations = []
        for line in stream_lines:
            if isinstance(line, VMobject) and len(line.points) > 0:
                anim = ShowPassingFlash(
                    line.copy(),
                    time_width=0.3,
                    run_time=run_time
                )
                animations.append(anim)
        
        super().__init__(
            *animations,
            lag_ratio=lag_ratio,
            **kwargs
        )


class ShowPassingFlashWithThinningStrokeWidth(AnimationGroup):
    """An animation that shows a flash passing through with thinning stroke.
    
    Creates multiple copies of the mobject with decreasing stroke widths
    that animate in sequence to create a thinning effect.
    """
    def __init__(self, 
                 vmobject, 
                 n_segments=10, 
                 time_width=0.1, 
                 remover=True,
                 **kwargs):
        self.n_segments = n_segments
        self.time_width = time_width
        self.remover = remover
        
        max_stroke_width = vmobject.get_stroke_width()
        max_time_width = kwargs.get("time_width", self.time_width)
        
        # Create multiple ShowPassingFlash animations with different stroke widths
        animations = []
        for stroke_width, time_width in zip(
            np.linspace(0, max_stroke_width, self.n_segments),
            np.linspace(max_time_width, 0, self.n_segments)
        ):
            flash = ShowPassingFlash(
                vmobject.copy().set_stroke(width=stroke_width),
                time_width=time_width,
                **kwargs
            )
            animations.append(flash)
        
        super().__init__(*animations)


# Additional constants that might be needed
MED_SMALL_BUFF = 0.25
SMALL_BUFF = 0.1
TAU = 2 * np.pi

# Note: ShowPassingFlash is already available in ManimCE
# These implementations are simplified versions suitable for ManimCE