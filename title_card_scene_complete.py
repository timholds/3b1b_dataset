# Complete TitleCard scene with all dependencies for ManimCE

import numpy as np
from manim import *

# TitleCard Scene
class TitleCard(Scene):
    def construct(self):
        # Create the main title
        title = Text("The Beauty of", font_size=60)
        subtitle = Text("Mathematics", font_size=72, color=BLUE)
        
        # Arrange the text
        title_group = VGroup(title, subtitle)
        title_group.arrange(DOWN, buff=0.5)
        title_group.move_to(ORIGIN)
        
        # Create a number plane for background effect
        plane = NumberPlane(
            x_range=[-7, 7],
            y_range=[-4, 4],
            background_line_style={
                "stroke_color": BLUE_E,
                "stroke_width": 1,
                "stroke_opacity": 0.3,
            }
        )
        
        # Create some mathematical elements for decoration
        equation1 = MathTex(r"e^{i\pi} + 1 = 0", font_size=36)
        equation2 = MathTex(r"\int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}", font_size=36)
        equation3 = MathTex(r"\sum_{n=1}^{\infty} \frac{1}{n^2} = \frac{\pi^2}{6}", font_size=36)
        
        equations = VGroup(equation1, equation2, equation3)
        equations.arrange(DOWN, buff=0.8)
        equations.set_opacity(0.3)
        equations.shift(3*LEFT + 0.5*UP)
        
        # Create geometric shapes for visual interest
        circle = Circle(radius=1.5, color=YELLOW, stroke_width=2)
        square = Square(side_length=2, color=GREEN, stroke_width=2)
        triangle = Triangle(color=RED, stroke_width=2)
        
        shapes = VGroup(circle, square, triangle)
        shapes.arrange(RIGHT, buff=0.5)
        shapes.set_opacity(0.3)
        shapes.scale(0.7)
        shapes.shift(3*RIGHT + 0.5*DOWN)
        
        # Animation sequence
        self.add(plane)
        self.play(FadeIn(equations), FadeIn(shapes), run_time=0.5)
        
        # Write the title with style
        self.play(Write(title), run_time=1.5)
        self.play(
            Write(subtitle),
            title.animate.shift(0.2*UP),
            run_time=1.5
        )
        
        # Add a subtle animation to the title
        self.play(
            title_group.animate.scale(1.1),
            rate_func=there_and_back,
            run_time=1
        )
        
        # Create an underline effect
        underline = Line(
            start=subtitle.get_left() + 0.1*DOWN,
            end=subtitle.get_right() + 0.1*DOWN,
            color=BLUE_B,
            stroke_width=3
        )
        
        self.play(Create(underline), run_time=0.8)
        
        # Final pause
        self.wait(2)
        
        # Optional: fade everything out
        self.play(
            FadeOut(VGroup(plane, equations, shapes, title_group, underline)),
            run_time=1
        )


# Alternative minimalist TitleCard
class MinimalTitleCard(Scene):
    def construct(self):
        # Simple title with animation
        title = Text("Introduction to", font_size=48)
        subject = Text("Complex Analysis", font_size=64, color=TEAL)
        
        full_title = VGroup(title, subject).arrange(DOWN, buff=0.3)
        
        self.play(FadeIn(title, shift=DOWN), run_time=1)
        self.play(FadeIn(subject, shift=UP), run_time=1)
        self.wait(1)
        
        # Add a simple mathematical flourish
        formula = MathTex(r"f(z) = \sum_{n=0}^{\infty} a_n z^n", font_size=36)
        formula.next_to(full_title, DOWN, buff=1)
        formula.set_color(YELLOW)
        
        self.play(Write(formula), run_time=2)
        self.wait(2)


# Classic 3Blue1Brown style TitleCard
class ClassicTitleCard(Scene):
    def construct(self):
        # Title components
        main_title = Text("Linear Algebra", font_size=72, color=BLUE)
        subtitle = Text("Chapter 1: Vectors", font_size=48, color=GREY_B)
        
        # Position them
        main_title.to_edge(UP, buff=1.5)
        subtitle.next_to(main_title, DOWN, buff=0.5)
        
        # Create a grid background
        grid = NumberPlane(
            x_range=[-8, 8],
            y_range=[-5, 5],
            x_length=16,
            y_length=10,
            background_line_style={
                "stroke_color": BLUE_E,
                "stroke_width": 1,
                "stroke_opacity": 0.4,
            },
            axis_config={
                "stroke_color": BLUE_D,
                "stroke_width": 2,
            }
        )
        
        # Add grid first
        self.add(grid)
        
        # Animate the title
        self.play(
            Write(main_title, run_time=2),
            grid.animate.set_stroke(opacity=0.2),
        )
        self.play(FadeIn(subtitle, shift=UP*0.5), run_time=1)
        
        # Add some vector representations
        origin = ORIGIN
        vec1 = Arrow(origin, 2*RIGHT + UP, color=YELLOW, buff=0)
        vec2 = Arrow(origin, LEFT + 2*UP, color=GREEN, buff=0)
        vec3 = Arrow(origin, 2*RIGHT + 2*DOWN, color=RED, buff=0)
        
        vectors = VGroup(vec1, vec2, vec3)
        vectors.shift(DOWN)
        
        self.play(
            *[GrowArrow(vec) for vec in vectors],
            run_time=1.5
        )
        
        # Add vector labels
        label1 = MathTex(r"\vec{v}_1", color=YELLOW, font_size=36)
        label2 = MathTex(r"\vec{v}_2", color=GREEN, font_size=36)
        label3 = MathTex(r"\vec{v}_3", color=RED, font_size=36)
        
        label1.next_to(vec1.get_end(), RIGHT, buff=0.2)
        label2.next_to(vec2.get_end(), LEFT, buff=0.2)
        label3.next_to(vec3.get_end(), RIGHT, buff=0.2)
        
        self.play(
            Write(label1),
            Write(label2),
            Write(label3),
            run_time=1
        )
        
        self.wait(2)


# Scene with animation that builds up the title
class AnimatedTitleCard(Scene):
    def construct(self):
        # Create individual letters
        title_text = "CALCULUS"
        letters = VGroup(*[Text(letter, font_size=96) for letter in title_text])
        letters.arrange(RIGHT, buff=0.1)
        letters.set_color_by_gradient(BLUE, TEAL, GREEN)
        
        # Position at the center
        letters.move_to(ORIGIN)
        
        # Animate each letter appearing
        for i, letter in enumerate(letters):
            self.play(
                FadeIn(letter, scale=2),
                run_time=0.2
            )
        
        self.wait(0.5)
        
        # Add subtitle
        subtitle = Text("The Language of Change", font_size=36, color=GREY_A)
        subtitle.next_to(letters, DOWN, buff=0.5)
        
        self.play(Write(subtitle), run_time=1.5)
        
        # Create derivative symbol
        deriv = MathTex(r"\frac{df}{dx}", font_size=144, color=YELLOW)
        deriv.move_to(3*LEFT)
        deriv.set_opacity(0.3)
        
        # Create integral symbol
        integral = MathTex(r"\int f(x)\,dx", font_size=144, color=ORANGE)
        integral.move_to(3*RIGHT)
        integral.set_opacity(0.3)
        
        self.play(
            FadeIn(deriv, shift=RIGHT),
            FadeIn(integral, shift=LEFT),
            run_time=1.5
        )
        
        # Pulse effect on the main title
        self.play(
            letters.animate.scale(1.2).set_color(WHITE),
            rate_func=there_and_back,
            run_time=0.8
        )
        
        self.wait(2)


if __name__ == "__main__":
    # To render any of these scenes, use:
    # manim -pql title_card_scene_complete.py TitleCard
    # manim -pql title_card_scene_complete.py MinimalTitleCard
    # manim -pql title_card_scene_complete.py ClassicTitleCard
    # manim -pql title_card_scene_complete.py AnimatedTitleCard
    pass