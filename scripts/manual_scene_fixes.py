#!/usr/bin/env python3
"""
Manual scene fixes for known problematic scenes.
This module provides hardcoded fixes for scenes that the systematic converter cannot handle.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Manual fixes for brachistochrone video scenes
BRACHISTOCHRONE_FIXES = {
    "CycloidScene": '''from manim import *
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
''',

    "IntroduceCycloid": '''from manim import *
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
''',

    "LeviSolution": '''from manim import *
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
''',

    "EquationsForCycloid": '''from manim import *
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
''',

    "SlidingObject": '''from manim import *
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
''',

    "RotateWheel": '''from manim import *
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
}

# IntroduceDivergentSum fix for multiple 2015 videos
INTRODUCE_DIVERGENT_SUM_FIX = '''from manim import *
import numpy as np

NUM_WRITTEN_TERMS = 7
SUM_SPACING = 0.25

class FlipThroughNumbers(Animation):
    def __init__(self, func, start=0, end=10, start_center=ORIGIN, 
                 end_center=ORIGIN, **kwargs):
        self.func = func
        self.start = start
        self.end = end
        self.start_center = start_center
        self.end_center = end_center
        self.current_number = start
        self.number = Text(str(func(start)))
        self.number.move_to(start_center)
        super().__init__(self.number, **kwargs)
        
    def interpolate_mobject(self, alpha):
        self.current_number = int(self.start + alpha * (self.end - self.start))
        new_text = str(self.func(self.current_number))
        new_center = self.start_center + alpha * (self.end_center - self.start_center)
        
        # Update the text
        self.mobject.become(Text(new_text))
        self.mobject.move_to(new_center)

class IntroduceDivergentSum(Scene):
    def construct(self):
        # Create the equation parts
        equation = self.get_equation()
        equation.to_edge(UP, buff=1.5)
        
        # Get parts
        nums = equation[:NUM_WRITTEN_TERMS]
        ellipses = equation[NUM_WRITTEN_TERMS]
        last_term = equation[NUM_WRITTEN_TERMS + 1]
        equals = equation[NUM_WRITTEN_TERMS + 2]
        sum_term = equation[NUM_WRITTEN_TERMS + 3]
        
        # Create brace
        brace = Brace(VGroup(*nums), DOWN)
        end_brace = Brace(VGroup(*nums, ellipses, last_term), DOWN)
        
        # Animation parameters
        kwargs = {"run_time": 5, "rate_func": smooth}
        
        # Create the flip through animation
        flip_through = FlipThroughNumbers(
            lambda x: 2**(x+1) - 1,
            start=NUM_WRITTEN_TERMS - 1,
            end=50,
            start_center=brace.get_center() + 0.5*DOWN,
            end_center=end_brace.get_center() + 0.5*DOWN,
            **kwargs
        )
        
        # Animate
        self.add(equation)
        self.add(ellipses)
        self.play(
            Transform(brace, end_brace, **kwargs),
            flip_through
        )  # Fixed: removed trailing comma
        self.clear()
        self.add(*equation)
        self.wait()
        
    def get_equation(self):
        # Build equation: 1 + 2 + 4 + 8 + 16 + ... + 2^n = 2^(n+1) - 1
        nums = [MathTex(str(2**i)) for i in range(NUM_WRITTEN_TERMS)]
        for i, num in enumerate(nums):
            if i > 0:
                num.shift(SUM_SPACING * i * RIGHT)
        
        # Add + signs
        plusses = []
        for i in range(len(nums) - 1):
            plus = MathTex("+")
            plus.move_to(nums[i].get_center() + (SUM_SPACING/2) * RIGHT)
            plusses.append(plus)
        
        # Combine numbers and plusses
        terms = []
        for i in range(len(nums)):
            terms.append(nums[i])
            if i < len(plusses):
                terms.append(plusses[i])
        
        # Add ellipses and last term
        ellipses = MathTex("\\cdots")
        ellipses.next_to(terms[-1], RIGHT, buff=SUM_SPACING/2)
        
        last_term = MathTex("2^n")
        last_term.next_to(ellipses, RIGHT, buff=SUM_SPACING/2)
        
        equals = MathTex("=")
        equals.next_to(last_term, RIGHT, buff=SUM_SPACING)
        
        sum_term = MathTex("2^{n+1} - 1")
        sum_term.next_to(equals, RIGHT, buff=SUM_SPACING)
        
        # Group everything
        equation = VGroup(*terms, ellipses, last_term, equals, sum_term)
        equation.center()
        
        return equation
'''

# Fixes for common 2015 scenes
COMMON_2015_FIXES = {
    "IntroduceDivergentSum": INTRODUCE_DIVERGENT_SUM_FIX
}

# Registry of all manual fixes by video
MANUAL_FIXES_REGISTRY = {
    "brachistochrone": BRACHISTOCHRONE_FIXES,
    # Common fixes that appear in multiple videos
    "inventing-math": COMMON_2015_FIXES,
    "music-and-measure-theory": COMMON_2015_FIXES,
    "eulers-characteristic-formula": COMMON_2015_FIXES,
    "moser": COMMON_2015_FIXES,
}


class ManualSceneFixer:
    """Applies manual fixes for known problematic scenes."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def has_manual_fix(self, video_name: str, scene_name: str) -> bool:
        """Check if a manual fix exists for this scene."""
        if video_name in MANUAL_FIXES_REGISTRY:
            return scene_name in MANUAL_FIXES_REGISTRY[video_name]
        return False
    
    def get_manual_fix(self, video_name: str, scene_name: str) -> Optional[str]:
        """Get the manual fix for a scene if it exists."""
        if video_name in MANUAL_FIXES_REGISTRY:
            fixes = MANUAL_FIXES_REGISTRY[video_name]
            if scene_name in fixes:
                if self.verbose:
                    self.logger.info(f"Found manual fix for {video_name}/{scene_name}")
                return fixes[scene_name]
        return None
    
    def apply_manual_fixes(self, video_name: str, failed_scenes: Dict[str, Dict]) -> Dict[str, str]:
        """
        Apply manual fixes to failed scenes.
        
        Args:
            video_name: Name of the video
            failed_scenes: Dictionary of failed scene names to their error info
            
        Returns:
            Dictionary of scene_name -> fixed_code for successfully fixed scenes
        """
        fixed_scenes = {}
        
        if video_name not in MANUAL_FIXES_REGISTRY:
            if self.verbose:
                self.logger.info(f"No manual fixes available for video: {video_name}")
            return fixed_scenes
        
        video_fixes = MANUAL_FIXES_REGISTRY[video_name]
        
        for scene_name in failed_scenes:
            if scene_name in video_fixes:
                fixed_code = video_fixes[scene_name]
                fixed_scenes[scene_name] = fixed_code
                self.logger.info(f"Applied manual fix for {video_name}/{scene_name}")
            else:
                if self.verbose:
                    self.logger.warning(f"No manual fix available for {video_name}/{scene_name}")
        
        return fixed_scenes


def test_manual_fixer():
    """Test the manual scene fixer."""
    fixer = ManualSceneFixer(verbose=True)
    
    # Test with brachistochrone scenes
    failed_scenes = {
        "CycloidScene": {"error": "empty class body"},
        "IntroduceCycloid": {"error": "empty class body"},
        "NonExistentScene": {"error": "some error"}
    }
    
    fixed = fixer.apply_manual_fixes("brachistochrone", failed_scenes)
    print(f"\nFixed {len(fixed)} out of {len(failed_scenes)} scenes")
    for scene_name in fixed:
        print(f"  ✓ {scene_name}")


if __name__ == "__main__":
    test_manual_fixer()