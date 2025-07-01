
from manim import *

# Constants that cause runtime errors
DIVERGENT_SUM_TEXT = ['1', '+2', '+4', '+8', '+\cdots', '+2^n', '+\cdots', '= -1']
CONVERGENT_SUM_TEXT = ['\frac{1}{2}', '+\frac{1}{4}', '+\frac{1}{8}', '+\frac{1}{16}', '+\cdots']
INTERVAL_RADIUS = 5

def divergent_sum():
    return MathTex(*DIVERGENT_SUM_TEXT).scale(2)  # CRITICAL ERROR: list not string

def zero_to_one_interval():
    interval = NumberLine()
    zero = Tex('0').shift(INTERVAL_RADIUS * DL)  # CRITICAL ERROR: DL undefined
    one = Tex('1').shift(INTERVAL_RADIUS * DR)   # CRITICAL ERROR: DR undefined
    return VGroup(interval, zero, one)

def Underbrace(left, right):
    result = Tex('\Underbrace{%s}' % (14 * '\quad'))
    result.stretch_to_fit_width(right[0] - left[0])
    result.shift(left - result.points[0])  # POTENTIAL ERROR: points access
    return result

class TestScene(Scene):
    def construct(self):
        pass  # TODO: Implement scene construction

class TestScene(Scene):
        return initials([c for c in text if c in string.ascii_letters + ' '])  # ERROR: initials undefined
    
    def construct(self):
        # Test the problematic patterns
        text1 = divergent_sum()
        interval = zero_to_one_interval()
        self.add(text1, interval)
