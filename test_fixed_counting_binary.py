#!/usr/bin/env python3
"""
Fixed version of counting_in_binary.py for ManimCE
This demonstrates how the conversion should work
"""

from manim import *
import numpy as np

# Define missing constants
FINGER_WORDS = [
    "Thumb",
    "Index Finger", 
    "Middle Finger",
    "Ring Finger",
    "Pinky",
]

# Tip positions for finger labels
COUNT_TO_TIP_POS = {
    0: np.array([3.0, -1.5, 0.0]),
    1: np.array([1.5, 0.5, 0.0]),
    2: np.array([0.3, 1.2, 0.0]),
    3: np.array([-0.9, 0.8, 0.0]),
    4: np.array([-2.1, -0.3, 0.0]),
}

def finger_tip_power_of_2(finger_no):
    """Create a label showing 2^finger_no at the finger tip position"""
    return Tex(str(2**finger_no)).move_to(COUNT_TO_TIP_POS[finger_no])

class SimplifiedHand(VGroup):
    """Simplified hand representation using circles for fingers"""
    def __init__(self, finger_states=[False]*5, **kwargs):
        super().__init__(**kwargs)
        self.finger_states = finger_states
        self.fingers = VGroup()
        
        # Create fingers as circles
        for i, state in enumerate(finger_states):
            finger = Circle(radius=0.3)
            finger.move_to(COUNT_TO_TIP_POS[i])
            if state:  # Finger is up
                finger.set_fill(GREEN, opacity=0.8)
            else:  # Finger is down
                finger.set_fill(RED, opacity=0.3)
            self.fingers.add(finger)
        
        self.add(self.fingers)
        
        # Add palm
        palm = Rectangle(width=4, height=2)
        palm.move_to(DOWN * 2)
        palm.set_fill(GRAY, opacity=0.5)
        self.add_to_back(palm)

class CountingInBinary(Scene):
    def construct(self):
        # Title
        title = Text("Counting in Binary", font_size=48)
        title.to_edge(UP)
        self.play(Write(title))
        
        # Create initial hand (all fingers down)
        hand = SimplifiedHand([False]*5)
        self.play(FadeIn(hand))
        
        # Add finger labels
        labels = VGroup()
        for i in range(5):
            label = finger_tip_power_of_2(i)
            label.scale(0.8)
            labels.add(label)
        
        self.play(Write(labels))
        self.wait()
        
        # Show counting from 0 to 7
        for count in range(8):
            # Convert count to binary finger states
            binary = format(count, '05b')
            finger_states = [bit == '1' for bit in reversed(binary)]
            
            # Create new hand with updated states
            new_hand = SimplifiedHand(finger_states)
            
            # Add count label
            count_label = Text(f"Count: {count}", font_size=36)
            count_label.to_edge(DOWN)
            binary_label = Text(f"Binary: {binary}", font_size=24)
            binary_label.next_to(count_label, UP)
            
            if count == 0:
                self.play(Write(count_label), Write(binary_label))
            else:
                self.play(
                    Transform(hand, new_hand),
                    count_label.animate.become(
                        Text(f"Count: {count}", font_size=36).to_edge(DOWN)
                    ),
                    binary_label.animate.become(
                        Text(f"Binary: {binary}", font_size=24).next_to(count_label, UP)
                    )
                )
            
            self.wait(0.5)
        
        # Show the algorithm
        algorithm_title = Text("The Algorithm:", font_size=36)
        algorithm_title.to_edge(LEFT).shift(UP)
        
        step1 = Text("1. Turn up the rightmost finger that is down", font_size=24)
        step2 = Text("2. Turn down all fingers to its right", font_size=24)
        
        step1.next_to(algorithm_title, DOWN, aligned_edge=LEFT)
        step2.next_to(step1, DOWN, aligned_edge=LEFT)
        
        self.play(
            FadeOut(count_label),
            FadeOut(binary_label),
            Write(algorithm_title),
            Write(step1),
            Write(step2)
        )
        
        self.wait(2)

class BinaryFingerDemo(Scene):
    """A simpler demo showing just the binary representation"""
    def construct(self):
        # Create finger representation
        fingers = VGroup()
        for i in range(5):
            finger = Square(side_length=0.8)
            finger.shift(RIGHT * (i - 2) * 1.2)
            fingers.add(finger)
        
        # Add power of 2 labels
        labels = VGroup()
        for i in range(5):
            label = Tex(f"2^{{{i}}}")
            label.next_to(fingers[i], UP)
            labels.add(label)
        
        # Add value labels
        values = VGroup()
        for i in range(5):
            value = Tex(str(2**i))
            value.next_to(fingers[i], DOWN)
            values.add(value)
        
        self.play(Create(fingers))
        self.play(Write(labels))
        self.play(Write(values))
        self.wait()
        
        # Demonstrate counting to 31
        for num in [1, 2, 3, 7, 15, 31]:
            binary = format(num, '05b')
            
            # Update finger colors
            for i, bit in enumerate(binary[::-1]):
                if bit == '1':
                    self.play(fingers[i].animate.set_fill(GREEN, opacity=0.8), run_time=0.2)
                else:
                    self.play(fingers[i].animate.set_fill(RED, opacity=0.2), run_time=0.2)
            
            # Show the number
            num_label = Tex(f"Number: {num}", font_size=48)
            num_label.to_edge(DOWN)
            
            if num == 1:
                self.play(Write(num_label))
            else:
                self.play(Transform(num_label, Tex(f"Number: {num}", font_size=48).to_edge(DOWN)))
            
            self.wait()

if __name__ == "__main__":
    # Run with: manim test_fixed_counting_binary.py CountingInBinary -pql
    pass