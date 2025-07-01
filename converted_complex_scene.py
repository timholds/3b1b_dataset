
from manim import *
from manim import *

class ComplexTestScene(Scene):

    def __init__(self, **kwargs):
        self.camera_config = {'background_color': BLACK}
        self.scale_factor = 2
        super().__init__(**kwargs)

    def construct(self):
        (title, subtitle, footer) = [Text('Complex Scene Test'), None, None]
        (a, b, c) = [MathTex('a+b=c'), None, None]
        arrow1 = Arrow(start=[0, 0, 0], end=[2, 0, 0])
        arrow2 = Arrow(start=LEFT, end=RIGHT)
        equations = VGroup(a, b, c)
        arrows = VGroup(arrow1, arrow2)
        axes = Axes(axis_config={'stroke_color': BLUE})
        number_line = NumberLine(x_min=(- 10), x_max=10)
        circle = Circle()
        ellipse = Ellipse()
        self.play(Create(title))
        self.play(equations.animate.arrange(DOWN))
        self.play(ReplacementTransform(circle, ellipse))
        width = title.width()
        center = equations.center()
