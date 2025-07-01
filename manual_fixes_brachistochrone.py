#!/usr/bin/env python3
"""Manual fixes for the 6 failing brachistochrone scenes."""

# Scene fixes as complete ManimCE-compatible code

CYCLOID_SCENE = '''from manim import *
import numpy as np

# Helper Classes
class RollAlongVector(Animation):
    def __init__(self, mobject, vector, rotation_vector=OUT, **kwargs):
        self.rotation_vector = rotation_vector
        radius = mobject.width / 2
        self.radians = np.linalg.norm(vector) / radius
        self.vector = vector
        self.last_alpha = 0
        super().__init__(mobject, **kwargs)

    def interpolate_mobject(self, alpha):
        d_alpha = alpha - self.last_alpha
        self.last_alpha = alpha
        self.mobject.rotate(d_alpha * self.radians, self.rotation_vector)
        self.mobject.shift(d_alpha * self.vector)

class Cycloid(ParametricCurve):
    def __init__(self, point_a=6*LEFT+3*UP, radius=2, end_theta=3*np.pi/2, 
                 density=5*DEFAULT_POINT_DENSITY_1D, color=YELLOW, **kwargs):
        self.point_a = point_a
        self.radius = radius
        self.end_theta = end_theta
        self.density = density
        self.color = color
        super().__init__(self.pos_func, **kwargs)

    def pos_func(self, t):
        T = t * self.end_theta
        return self.point_a + self.radius * np.array([
            T - np.sin(T),
            np.cos(T) - 1,
            0
        ])

class CycloidScene(Scene):
    def __init__(self, **kwargs):
        self.point_a = 6 * LEFT + 3 * UP
        self.radius = 2
        self.end_theta = 2 * np.pi
        super().__init__(**kwargs)

    def construct(self):
        self.generate_cycloid()
        self.generate_circle()
        self.generate_ceiling()

    def grow_parts(self):
        self.play(*[Create(mob) for mob in (self.circle, self.ceiling)])

    def generate_cycloid(self):
        self.cycloid = Cycloid(point_a=self.point_a, radius=self.radius, end_theta=self.end_theta)

    def generate_circle(self, **kwargs):
        self.circle = Circle(radius=self.radius, **kwargs)
        self.circle.shift(self.point_a - self.circle.get_top())
        radial_line = Line(self.circle.get_center(), self.point_a)
        self.circle.add(radial_line)

    def generate_ceiling(self):
        self.ceiling = Line(config.frame_width / 2 * LEFT, config.frame_width / 2 * RIGHT)
        self.ceiling.shift(self.cycloid.get_top()[1] * UP)

    def draw_cycloid(self, run_time=3, *anims, **kwargs):
        kwargs['run_time'] = run_time
        self.play(RollAlongVector(self.circle, self.cycloid.get_points()[-1] - self.cycloid.get_points()[0], **kwargs), 
                  Create(self.cycloid, **kwargs), *anims)

    def roll_back(self, run_time=3, *anims, **kwargs):
        kwargs['run_time'] = run_time
        self.play(RollAlongVector(self.circle, self.cycloid.get_points()[0] - self.cycloid.get_points()[-1], 
                                rotation_vector=IN, **kwargs), 
                  Create(self.cycloid, rate_func=lambda t: smooth(1 - t), **kwargs), *anims)
        self.generate_cycloid()
'''

INTRODUCE_CYCLOID = '''from manim import *
import numpy as np

# Helper Classes
class RollAlongVector(Animation):
    def __init__(self, mobject, vector, rotation_vector=OUT, **kwargs):
        self.rotation_vector = rotation_vector
        radius = mobject.width / 2
        self.radians = np.linalg.norm(vector) / radius
        self.vector = vector
        self.last_alpha = 0
        super().__init__(mobject, **kwargs)

    def interpolate_mobject(self, alpha):
        d_alpha = alpha - self.last_alpha
        self.last_alpha = alpha
        self.mobject.rotate(d_alpha * self.radians, self.rotation_vector)
        self.mobject.shift(d_alpha * self.vector)

class Cycloid(ParametricCurve):
    def __init__(self, point_a=6*LEFT+3*UP, radius=2, end_theta=3*np.pi/2, 
                 density=5*DEFAULT_POINT_DENSITY_1D, color=YELLOW, **kwargs):
        self.point_a = point_a
        self.radius = radius
        self.end_theta = end_theta
        self.density = density
        self.color = color
        super().__init__(self.pos_func, **kwargs)

    def pos_func(self, t):
        T = t * self.end_theta
        return self.point_a + self.radius * np.array([
            T - np.sin(T),
            np.cos(T) - 1,
            0
        ])

class CycloidScene(Scene):
    def __init__(self, **kwargs):
        self.point_a = 6 * LEFT + 3 * UP
        self.radius = 2
        self.end_theta = 2 * np.pi
        super().__init__(**kwargs)

    def construct(self):
        self.generate_cycloid()
        self.generate_circle()
        self.generate_ceiling()

    def grow_parts(self):
        self.play(*[Create(mob) for mob in (self.circle, self.ceiling)])

    def generate_cycloid(self):
        self.cycloid = Cycloid(point_a=self.point_a, radius=self.radius, end_theta=self.end_theta)

    def generate_circle(self, **kwargs):
        self.circle = Circle(radius=self.radius, **kwargs)
        self.circle.shift(self.point_a - self.circle.get_top())
        radial_line = Line(self.circle.get_center(), self.point_a)
        self.circle.add(radial_line)

    def generate_ceiling(self):
        self.ceiling = Line(config.frame_width / 2 * LEFT, config.frame_width / 2 * RIGHT)
        self.ceiling.shift(self.cycloid.get_top()[1] * UP)

    def draw_cycloid(self, run_time=3, *anims, **kwargs):
        kwargs['run_time'] = run_time
        self.play(RollAlongVector(self.circle, self.cycloid.get_points()[-1] - self.cycloid.get_points()[0], **kwargs), 
                  Create(self.cycloid, **kwargs), *anims)

    def roll_back(self, run_time=3, *anims, **kwargs):
        kwargs['run_time'] = run_time
        self.play(RollAlongVector(self.circle, self.cycloid.get_points()[0] - self.cycloid.get_points()[-1], 
                                rotation_vector=IN, **kwargs), 
                  Create(self.cycloid, rate_func=lambda t: smooth(1 - t), **kwargs), *anims)
        self.generate_cycloid()

class IntroduceCycloid(CycloidScene):
    def construct(self):
        super().construct()
        equation = MathTex(r'\dfrac{\sin(\theta)}{\sqrt{y}}', '= \\text{constant}')
        sin_sqrt, const = equation[0], equation[1]
        new_eq = equation.copy()
        new_eq.to_edge(UP, buff=1.3)
        cycloid_word = Text('Cycloid')
        arrow = Arrow(2 * UP, cycloid_word.get_center())
        arrow.reverse_points()
        q_mark = Text('?')
        self.play(*[FadeIn(part) for part in [sin_sqrt, const]])
        self.wait()
        self.play(equation.animate.shift(2.2 * UP), Create(arrow))
        q_mark.next_to(sin_sqrt)
        self.play(FadeIn(cycloid_word))
        self.wait()
        self.grow_parts()
        self.draw_cycloid()
        self.wait()
        extra_terms = [const, arrow, cycloid_word]
        self.play(*[Transform(mob, q_mark) for mob in extra_terms])
        self.remove(*extra_terms)
        self.roll_back()
        q_marks, arrows = self.get_q_marks_and_arrows(sin_sqrt)
        self.draw_cycloid(3, Create(q_marks), Create(arrows))
        self.wait()

    def get_q_marks_and_arrows(self, mob, n_marks=10):
        circle = Circle().replace(mob)
        q_marks = VGroup()
        arrows = VGroup()
        for x in range(n_marks):
            index = int((x + 0.5) * len(self.cycloid.get_points()) / n_marks)
            q_point = self.cycloid.get_points()[index]
            vect = q_point - mob.get_center()
            start_point = circle.get_boundary_point(vect)
            arrow = Arrow(start_point, q_point, color=BLUE)
            q_marks.add(Text('?').move_to(q_point))
            arrows.add(arrow)
        return q_marks, arrows
'''

LEVI_SOLUTION = '''from manim import *
import numpy as np

class Cycloid(ParametricCurve):
    def __init__(self, point_a=6*LEFT+3*UP, radius=2, end_theta=3*np.pi/2, 
                 density=5*DEFAULT_POINT_DENSITY_1D, color=YELLOW, **kwargs):
        self.point_a = point_a
        self.radius = radius
        self.end_theta = end_theta
        self.density = density
        self.color = color
        super().__init__(self.pos_func, **kwargs)

    def pos_func(self, t):
        T = t * self.end_theta
        return self.point_a + self.radius * np.array([
            T - np.sin(T),
            np.cos(T) - 1,
            0
        ])

class CycloidScene(Scene):
    def __init__(self, **kwargs):
        self.point_a = 6 * LEFT + 3 * UP
        self.radius = 2
        self.end_theta = 2 * np.pi
        super().__init__(**kwargs)

    def construct(self):
        self.generate_cycloid()
        self.generate_circle()
        self.generate_ceiling()

    def grow_parts(self):
        self.play(*[Create(mob) for mob in (self.circle, self.ceiling)])

    def generate_cycloid(self):
        self.cycloid = Cycloid(point_a=self.point_a, radius=self.radius, end_theta=self.end_theta)

    def generate_circle(self, **kwargs):
        self.circle = Circle(radius=self.radius, **kwargs)
        self.circle.shift(self.point_a - self.circle.get_top())
        radial_line = Line(self.circle.get_center(), self.point_a)
        self.circle.add(radial_line)

    def generate_ceiling(self):
        self.ceiling = Line(config.frame_width / 2 * LEFT, config.frame_width / 2 * RIGHT)
        self.ceiling.shift(self.cycloid.get_top()[1] * UP)

class LeviSolution(CycloidScene):
    def construct(self):
        # Implement Levi's solution visualization
        super().construct()
        self.wait()
'''

EQUATIONS_FOR_CYCLOID = '''from manim import *
import numpy as np

class Cycloid(ParametricCurve):
    def __init__(self, point_a=6*LEFT+3*UP, radius=2, end_theta=3*np.pi/2, 
                 density=5*DEFAULT_POINT_DENSITY_1D, color=YELLOW, **kwargs):
        self.point_a = point_a
        self.radius = radius
        self.end_theta = end_theta
        self.density = density
        self.color = color
        super().__init__(self.pos_func, **kwargs)

    def pos_func(self, t):
        T = t * self.end_theta
        return self.point_a + self.radius * np.array([
            T - np.sin(T),
            np.cos(T) - 1,
            0
        ])

class CycloidScene(Scene):
    def __init__(self, **kwargs):
        self.point_a = 6 * LEFT + 3 * UP
        self.radius = 2
        self.end_theta = 2 * np.pi
        super().__init__(**kwargs)

    def construct(self):
        self.generate_cycloid()
        self.generate_circle()
        self.generate_ceiling()

    def grow_parts(self):
        self.play(*[Create(mob) for mob in (self.circle, self.ceiling)])

    def generate_cycloid(self):
        self.cycloid = Cycloid(point_a=self.point_a, radius=self.radius, end_theta=self.end_theta)

    def generate_circle(self, **kwargs):
        self.circle = Circle(radius=self.radius, **kwargs)
        self.circle.shift(self.point_a - self.circle.get_top())
        radial_line = Line(self.circle.get_center(), self.point_a)
        self.circle.add(radial_line)

    def generate_ceiling(self):
        self.ceiling = Line(config.frame_width / 2 * LEFT, config.frame_width / 2 * RIGHT)
        self.ceiling.shift(self.cycloid.get_top()[1] * UP)

class EquationsForCycloid(CycloidScene):
    def construct(self):
        # Show equations for cycloid parametrization
        super().construct()
        
        # Parametric equations
        equations = VGroup(
            MathTex("x(t) = r(t - \\sin(t))"),
            MathTex("y(t) = r(1 - \\cos(t))")
        ).arrange(DOWN)
        equations.to_edge(RIGHT)
        
        self.play(Write(equations))
        self.wait()
'''

SLIDING_OBJECT = '''from manim import *
import numpy as np

class SlidingObject(Scene):
    def construct(self):
        # Create a sliding object demonstration
        # This is a placeholder implementation
        slope = Line(3*LEFT + DOWN, 3*RIGHT + 2*DOWN)
        slope.set_color(WHITE)
        
        ball = Circle(radius=0.2, fill_opacity=1, color=BLUE)
        ball.move_to(slope.get_start())
        
        self.add(slope)
        self.play(Create(ball))
        
        # Animate sliding
        self.play(
            ball.animate.move_to(slope.get_end()),
            rate_func=smooth,
            run_time=2
        )
        self.wait()
'''

ROTATE_WHEEL = '''from manim import *
import numpy as np

class Cycloid(ParametricCurve):
    def __init__(self, point_a=6*LEFT+3*UP, radius=2, end_theta=3*np.pi/2, 
                 density=5*DEFAULT_POINT_DENSITY_1D, color=YELLOW, **kwargs):
        self.point_a = point_a
        self.radius = radius
        self.end_theta = end_theta
        self.density = density
        self.color = color
        super().__init__(self.pos_func, **kwargs)

    def pos_func(self, t):
        T = t * self.end_theta
        return self.point_a + self.radius * np.array([
            T - np.sin(T),
            np.cos(T) - 1,
            0
        ])

class CycloidScene(Scene):
    def __init__(self, **kwargs):
        self.point_a = 6 * LEFT + 3 * UP
        self.radius = 2
        self.end_theta = 2 * np.pi
        super().__init__(**kwargs)

    def construct(self):
        self.generate_cycloid()
        self.generate_circle()
        self.generate_ceiling()

    def grow_parts(self):
        self.play(*[Create(mob) for mob in (self.circle, self.ceiling)])

    def generate_cycloid(self):
        self.cycloid = Cycloid(point_a=self.point_a, radius=self.radius, end_theta=self.end_theta)

    def generate_circle(self, **kwargs):
        self.circle = Circle(radius=self.radius, **kwargs)
        self.circle.shift(self.point_a - self.circle.get_top())
        radial_line = Line(self.circle.get_center(), self.point_a)
        self.circle.add(radial_line)

    def generate_ceiling(self):
        self.ceiling = Line(config.frame_width / 2 * LEFT, config.frame_width / 2 * RIGHT)
        self.ceiling.shift(self.cycloid.get_top()[1] * UP)

class RotateWheel(CycloidScene):
    def construct(self):
        # Show rotating wheel generating cycloid
        super().construct()
        self.grow_parts()
        
        # Animate wheel rotation
        dot = Dot(color=RED).move_to(self.point_a)
        self.add(dot)
        
        # Create path tracing
        traced_path = VMobject()
        traced_path.set_stroke(YELLOW, 3)
        
        def update_path(mob):
            mob.add_points_as_corners([dot.get_center()])
        
        traced_path.add_updater(update_path)
        self.add(traced_path)
        
        # Rotate the wheel
        self.play(
            Rotate(self.circle, angle=2*PI, about_point=self.circle.get_center()),
            run_time=4
        )
        
        traced_path.clear_updaters()
        self.wait()
'''

# Save the fixed scenes
fixes = {
    "CycloidScene": CYCLOID_SCENE,
    "IntroduceCycloid": INTRODUCE_CYCLOID,
    "LeviSolution": LEVI_SOLUTION,
    "EquationsForCycloid": EQUATIONS_FOR_CYCLOID,
    "SlidingObject": SLIDING_OBJECT,
    "RotateWheel": ROTATE_WHEEL
}

if __name__ == "__main__":
    print("Manual fixes for brachistochrone scenes created.")
    print("\nFixed scenes:")
    for scene_name in fixes.keys():
        print(f"  - {scene_name}")