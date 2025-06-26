# Dependencies extracted from div_curl.py for the ElectricField scene
# This file contains all the classes and functions needed to inline into ElectricField

import numpy as np
from manim import *

# ============================================
# Utility Functions from ManimGL
# ============================================

def R3_to_complex(point):
    """Convert a 3D point to a complex number (using x and y coordinates)."""
    return complex(point[0], point[1])


def complex_to_R3(z):
    """Convert a complex number to a 3D point."""
    return np.array([z.real, z.imag, 0])


def rotate_vector(vector, angle, axis=OUT):
    """Rotate a vector by a given angle around an axis."""
    # In ManimCE, we can use rotation matrices
    if np.array_equal(axis, OUT) or np.array_equal(axis, np.array([0, 0, 1])):
        # Rotation around z-axis
        cos_angle = np.cos(angle)
        sin_angle = np.sin(angle)
        rotation_matrix = np.array([
            [cos_angle, -sin_angle, 0],
            [sin_angle, cos_angle, 0],
            [0, 0, 1]
        ])
        return np.dot(rotation_matrix, vector)
    else:
        # For other axes, use Rodrigues' rotation formula
        # This is a simplified version
        raise NotImplementedError("Rotation around arbitrary axis not implemented")


# ============================================
# Mathematical Functions
# ============================================

def joukowsky_map(z):
    """Joukowsky transformation - maps a circle to an airfoil shape."""
    if z == 0:
        return 0
    return z + 1/z


def inverse_joukowsky_map(w):
    """Inverse Joukowsky transformation."""
    u = 1 if w.real >= 0 else -1
    return (w + u * np.sqrt(w**2 - 4)) / 2


def derivative(func, dt=1e-7):
    """Numerical derivative of a complex function."""
    return lambda z: (func(z + dt) - func(z)) / dt


def cylinder_flow_vector_field(point, R=1, U=1):
    """Vector field representing flow around a cylinder."""
    z = R3_to_complex(point)
    return complex_to_R3(derivative(joukowsky_map)(z).conjugate())


# ============================================
# Particle Creation Functions
# ============================================

def get_charged_particles(color, sign, radius=0.1):
    """Create a charged particle (proton or electron) visual."""
    result = Circle(
        stroke_color=WHITE,
        stroke_width=0.5,
        fill_color=color,
        fill_opacity=0.8,
        radius=radius
    )
    # In ManimCE, use Tex instead of OldTex
    sign_mob = Tex(sign)
    sign_mob.set_stroke(WHITE, 1)
    sign_mob.set_width(0.5 * result.get_width())
    sign_mob.move_to(result)
    result.add(sign_mob)
    return result


def get_proton(radius=0.1):
    """Create a proton visual (red circle with + sign)."""
    return get_charged_particles(RED, "+", radius)


def get_electron(radius=0.05):
    """Create an electron visual (blue circle with - sign)."""
    return get_charged_particles(BLUE, "-", radius)


# ============================================
# Animation Classes
# ============================================

class JigglingSubmobjects(VGroup):
    """
    A VGroup that makes its submobjects jiggle continuously.
    Each submobject moves in a random direction with sinusoidal motion.
    """
    def __init__(self, group, amplitude=0.05, jiggles_per_second=1, **kwargs):
        super().__init__(**kwargs)
        self.amplitude = amplitude
        self.jiggles_per_second = jiggles_per_second
        
        # Initialize jiggling parameters for each submobject
        for submob in group.submobjects:
            submob.jiggling_direction = rotate_vector(
                RIGHT, np.random.random() * TAU,
            )
            submob.jiggling_phase = np.random.random() * TAU
            self.add(submob)
        
        # Add the update function
        self.add_updater(lambda m, dt: m.update_jiggle(dt))
    
    def update_jiggle(self, dt):
        """Update the position of each submobject based on jiggling motion."""
        for submob in self.submobjects:
            submob.jiggling_phase += dt * self.jiggles_per_second * TAU
            submob.shift(
                self.amplitude *
                submob.jiggling_direction *
                np.sin(submob.jiggling_phase) * dt
            )


# ============================================
# Scene Classes
# ============================================

class CylinderModel(Scene):
    """
    Scene demonstrating fluid flow around a cylinder using complex analysis.
    Uses the Joukowsky transformation to visualize streamlines.
    """
    def __init__(self, production_quality_flow=True, 
                 vector_field_func=None, **kwargs):
        super().__init__(**kwargs)
        self.production_quality_flow = production_quality_flow
        self.vector_field_func = vector_field_func or cylinder_flow_vector_field

    def construct(self):
        self.add_plane()
        self.add_title()
        self.show_numbers()
        self.show_contour_lines()
        self.show_flow()
        self.apply_joukowsky_map()

    def add_plane(self):
        self.plane = ComplexPlane()
        self.plane.add_coordinates()
        # Remove the last coordinate label if needed
        if hasattr(self.plane, 'coordinate_labels'):
            self.plane.coordinate_labels.submobjects.pop(-1)
        self.add(self.plane)

    def add_title(self):
        title = Text("Complex Plane")  # Use Text instead of OldTexText
        title.to_edge(UP, buff=MED_SMALL_BUFF)
        # Add background rectangle
        title.add_background_rectangle()
        self.title = title
        self.add(title)

    def show_numbers(self):
        run_time = 5

        unit_circle = self.unit_circle = Circle(
            radius=self.plane.unit_size if hasattr(self.plane, 'unit_size') else 1,
            fill_color=BLACK,
            fill_opacity=0,
            stroke_color=YELLOW
        )
        dot = Dot()
        
        # Create update functions for ManimCE
        def update_dot(d):
            d.move_to(unit_circle.point_from_proportion(1))
            
        dot_update = dot.add_updater(update_dot)
        
        exp_tex = MathTex("e^{", "0.00", "i}")
        zero = exp_tex.get_part_by_tex("0.00")
        zero.fade(1)
        
        def update_exp_tex(et):
            et.next_to(dot, UR, SMALL_BUFF)
            
        exp_tex_update = exp_tex.add_updater(update_exp_tex)
        
        exp_decimal = DecimalNumber(
            0, num_decimal_places=2,
            color=YELLOW
        )
        # Add background rectangle to decimal
        exp_decimal.add_background_rectangle()
        exp_decimal.move_to(zero)
        
        # Create value tracker for decimal animation
        value_tracker = ValueTracker(0)
        
        def update_decimal(d):
            d.set_value(value_tracker.get_value())
            d.move_to(zero)
            
        exp_decimal.add_updater(update_decimal)

        sample_numbers = [
            complex(-5, 2),
            complex(2, 2),
            complex(3, 1),
            complex(-5, -2),
            complex(-4, 1),
        ]
        sample_labels = VGroup()
        for z in sample_numbers:
            sample_dot = Dot(self.plane.n2p(z) if hasattr(self.plane, 'n2p') 
                           else self.plane.coords_to_point(z.real, z.imag))
            sample_label = DecimalNumber(
                z,
                num_decimal_places=0,
            )
            sample_label.add_background_rectangle()
            sample_label.next_to(sample_dot, UR, SMALL_BUFF)
            sample_labels.add(VGroup(sample_dot, sample_label))

        self.play(
            ShowCreation(unit_circle, run_time=run_time),
            FadeIn(exp_tex),
            FadeIn(exp_decimal),
            value_tracker.animate.set_value(TAU),
            LaggedStartMap(
                lambda m: FadeIn(m, rate_func=there_and_back),
                sample_labels,
                run_time=run_time,
            )
        )
        
        # Clean up updaters
        dot.clear_updaters()
        exp_tex.clear_updaters()
        exp_decimal.clear_updaters()
        
        self.play(
            FadeOut(exp_tex),
            FadeOut(exp_decimal),
            FadeOut(dot),
            unit_circle.animate.set_fill(BLACK, opacity=1),
        )
        self.wait()

    def show_contour_lines(self):
        warped_grid = self.warped_grid = self.get_warpable_grid()
        h_line = Line(3 * LEFT, 3 * RIGHT, color=WHITE)
        func_label = self.get_func_label()

        self.remove(self.plane)
        self.add_foreground_mobjects(self.unit_circle, self.title)
        self.play(
            warped_grid.animate.apply_complex_function(inverse_joukowsky_map),
            FadeOut(h_line)
        )
        self.play(Write(func_label))
        self.add_foreground_mobjects(func_label)
        self.wait()

    def show_flow(self):
        stream_lines = self.get_stream_lines()
        stream_lines_copy = stream_lines.copy()
        stream_lines_copy.set_stroke(YELLOW, 1)
        stream_lines_animation = self.get_stream_lines_animation(
            stream_lines
        )

        tiny_buff = 0.0001
        v_lines = VGroup(*[
            Line(
                UP, ORIGIN,
                path_arc=0,
            ).shift(x * RIGHT)
            for x in np.linspace(0, 1, 5)
        ])
        
        # In ManimCE, we don't have match_background_image_file
        # Just set appropriate styling
        v_lines.set_stroke(BLUE, 2)
        
        fast_lines, slow_lines = [
            VGroup(*[
                v_lines.copy().next_to(point, vect, tiny_buff)
                for point, vect in [(h_point, UP), (h_point, DOWN)]
                for h_point in h_points
            ])
            for h_points in [
                [0.5 * LEFT, 0.5 * RIGHT],
                [2 * LEFT, 2 * RIGHT],
            ]
        ]
        
        for lines in [fast_lines, slow_lines]:
            lines.apply_complex_function(inverse_joukowsky_map)

        self.add(stream_lines_animation)
        self.wait(7)
        self.play(
            ShowCreationThenDestruction(
                stream_lines_copy,
                lag_ratio=0,
                run_time=3,
            )
        )
        self.wait()
        self.play(ShowCreation(fast_lines))
        self.wait(2)
        self.play(ReplacementTransform(fast_lines, slow_lines))
        self.wait(3)
        self.play(
            FadeOut(slow_lines),
            FadeOut(stream_lines_animation.mobject if hasattr(stream_lines_animation, 'mobject') 
                   else stream_lines_animation)
        )
        self.remove(stream_lines_animation)

    def apply_joukowsky_map(self):
        shift_val = 0.1 * LEFT + 0.2 * UP
        scale_factor = get_norm(RIGHT - shift_val)
        movers = VGroup(self.warped_grid, self.unit_circle)
        
        # Insert curves for smooth transformation
        if hasattr(self.unit_circle, 'insert_n_curves'):
            self.unit_circle.insert_n_curves(50)

        stream_lines = self.get_stream_lines()
        stream_lines.scale(scale_factor)
        stream_lines.shift(shift_val)
        stream_lines.apply_complex_function(joukowsky_map)

        self.play(
            movers.animate.scale(scale_factor),
            movers.animate.shift(shift_val),
        )
        self.wait()
        self.play(
            movers.animate.apply_complex_function(joukowsky_map),
            ShowCreationThenFadeAround(self.func_label),
            run_time=2
        )
        self.add(self.get_stream_lines_animation(stream_lines))
        self.wait(20)

    # Helper methods

    def get_func_label(self):
        func_label = self.func_label = MathTex("f(z) = z + 1 / z")
        func_label.add_background_rectangle()
        func_label.next_to(self.title, DOWN, MED_SMALL_BUFF)
        return func_label

    def get_warpable_grid(self):
        top_grid = NumberPlane()
        # Prepare for nonlinear transform
        if hasattr(top_grid, 'prepare_for_nonlinear_transform'):
            top_grid.prepare_for_nonlinear_transform()
        bottom_grid = top_grid.copy()
        tiny_buff = 0.0001
        top_grid.next_to(ORIGIN, UP, buff=tiny_buff)
        bottom_grid.next_to(ORIGIN, DOWN, buff=tiny_buff)
        result = VGroup(top_grid, bottom_grid)
        
        # Add boundary lines
        for vect in [LEFT, RIGHT]:
            line = Line(
                ORIGIN, config.frame_width * RIGHT / 2,
                color=WHITE,
                path_arc=0,
            ).next_to(ORIGIN, vect, buff=2)
            result.add(line)
            
        # Add horizontal line
        h_line = Line(LEFT, RIGHT, color=WHITE)
        h_line.scale(2)
        result.add(h_line)
        return result

    def get_stream_lines(self):
        func = self.vector_field_func
        if self.production_quality_flow:
            delta_x = 0.5
            delta_y = 0.1
        else:
            delta_x = 1
            delta_y = 0.1
            
        # Create starting points
        start_points = []
        for x in np.arange(-8, -7, delta_x):
            for y in np.arange(-4, 4, delta_y):
                # Add some noise
                noise = 0.1 * (np.random.random(3) - 0.5)
                start_points.append(np.array([x, y, 0]) + noise)
        
        return StreamLines(
            func,
            start_points=start_points,
            stroke_width=2,
            max_time=15,
        )

    def get_stream_lines_animation(self, stream_lines):
        if self.production_quality_flow:
            # Use thinning stroke width for production quality
            return ShowPassingFlashWithThinningStrokeWidth(
                stream_lines,
                time_width=0.3,
                run_time=10,
            )
        else:
            # Use simple passing flash
            return AnimatedStreamLines(
                stream_lines,
                lag_ratio=0.01,
                run_time=10,
            )


# ============================================
# Additional Classes for ManimCE Compatibility
# ============================================

class ComplexPlane(NumberPlane):
    """A coordinate plane for visualizing complex numbers."""
    def __init__(self, **kwargs):
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
        self.unit_size = 1  # Add unit_size attribute
        
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
    """Streamlines for visualizing vector fields."""
    def __init__(self, 
                 func,
                 start_points=None,
                 dt=0.05,
                 max_time=5,
                 min_magnitude=0.1,
                 stroke_width=2,
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
            if len(line.points) > 1:
                line.set_stroke(width=stroke_width)
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
            line.set_stroke(BLUE, opacity=0.8)
        return line


class AnimatedStreamLines(AnimationGroup):
    """Animated version of StreamLines using ShowPassingFlash."""
    def __init__(self, stream_lines, lag_ratio=0.01, run_time=3, **kwargs):
        # Store mobject for compatibility
        self.mobject = stream_lines
        
        if not isinstance(stream_lines, StreamLines):
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


class ShowPassingFlashWithThinningStrokeWidth(ShowPassingFlash):
    """A simplified version that works with ManimCE's ShowPassingFlash."""
    def __init__(self, vmobject, time_width=0.3, n_segments=10, **kwargs):
        # Create a copy with modified stroke for the effect
        vmobject_copy = vmobject.copy()
        
        # Apply some stroke width variation
        # This is a simplified version - the full effect would need custom implementation
        super().__init__(
            vmobject_copy,
            time_width=time_width,
            **kwargs
        )


# ============================================
# Constants
# ============================================

MED_SMALL_BUFF = 0.25
SMALL_BUFF = 0.1
TAU = 2 * np.pi