#!/usr/bin/env python3
"""
Simple character replacements for Pi Creatures in ManimCE.

This module provides simple geometric characters that can replace
the Pi Creature characters used in 3Blue1Brown videos, without
requiring any external SVG assets.
"""

from manim import *


class SimpleCharacter(VGroup):
    """Base class for simple geometric characters."""
    
    def __init__(self, color=BLUE, height=2, **kwargs):
        super().__init__(**kwargs)
        self.character_height = height
        self.character_color = color
        self.build_character()
        
    def build_character(self):
        """Override this method to build the character."""
        pass
    
    def look_at(self, point):
        """Make the character appear to look at a point."""
        # Default implementation - override in subclasses
        pass
    
    def change_emotion(self, emotion="happy"):
        """Change the character's expression."""
        # Default implementation - override in subclasses
        pass


class StickFigure(SimpleCharacter):
    """A simple stick figure character."""
    
    def build_character(self):
        # Head
        self.head = Circle(
            radius=self.character_height/4,
            color=self.character_color,
            stroke_width=3
        )
        
        # Body
        self.body = Line(
            self.head.get_bottom(),
            self.head.get_bottom() + self.character_height/2 * DOWN,
            color=self.character_color,
            stroke_width=3
        )
        
        # Arms
        arm_start = self.body.point_from_proportion(0.3)
        self.left_arm = Line(
            arm_start,
            arm_start + self.character_height/4 * (LEFT + 0.5*DOWN),
            color=self.character_color,
            stroke_width=3
        )
        self.right_arm = Line(
            arm_start,
            arm_start + self.character_height/4 * (RIGHT + 0.5*DOWN),
            color=self.character_color,
            stroke_width=3
        )
        
        # Legs
        self.left_leg = Line(
            self.body.get_bottom(),
            self.body.get_bottom() + self.character_height/4 * (LEFT + DOWN),
            color=self.character_color,
            stroke_width=3
        )
        self.right_leg = Line(
            self.body.get_bottom(),
            self.body.get_bottom() + self.character_height/4 * (RIGHT + DOWN),
            color=self.character_color,
            stroke_width=3
        )
        
        # Add all parts
        self.add(self.head, self.body, self.left_arm, self.right_arm,
                self.left_leg, self.right_leg)
    
    def wave(self):
        """Make the stick figure wave."""
        return AnimationGroup(
            Rotate(self.right_arm, angle=PI/4, about_point=self.right_arm.get_start()),
            Rotate(self.right_arm, angle=-PI/2, about_point=self.right_arm.get_start()),
            lag_ratio=0.5
        )


class SimpleFace(SimpleCharacter):
    """A simple face character with expressions."""
    
    def build_character(self):
        # Face circle
        self.face = Circle(
            radius=self.character_height/2,
            color=self.character_color,
            fill_opacity=0.3,
            stroke_width=3
        )
        
        # Eyes
        eye_y = self.character_height/6
        eye_x = self.character_height/6
        
        self.left_eye = Dot(
            point=self.face.get_center() + eye_x*LEFT + eye_y*UP,
            radius=self.character_height/20,
            color=BLACK
        )
        self.right_eye = Dot(
            point=self.face.get_center() + eye_x*RIGHT + eye_y*UP,
            radius=self.character_height/20,
            color=BLACK
        )
        
        # Mouth (default happy)
        self.mouth = self.create_mouth("happy")
        
        # Add all parts
        self.add(self.face, self.left_eye, self.right_eye, self.mouth)
    
    def create_mouth(self, emotion="happy"):
        """Create mouth based on emotion."""
        mouth_y = -self.character_height/6
        
        if emotion == "happy":
            return Arc(
                start_angle=-2*PI/3,
                angle=PI/3,
                radius=self.character_height/4,
                color=BLACK,
                stroke_width=3
            ).move_to(self.face.get_center() + mouth_y*DOWN)
        
        elif emotion == "sad":
            return Arc(
                start_angle=PI/3,
                angle=PI/3,
                radius=self.character_height/4,
                color=BLACK,
                stroke_width=3
            ).move_to(self.face.get_center() + mouth_y*DOWN)
        
        elif emotion == "surprised":
            return Circle(
                radius=self.character_height/10,
                color=BLACK,
                stroke_width=3
            ).move_to(self.face.get_center() + mouth_y*DOWN)
        
        else:  # neutral
            return Line(
                self.face.get_center() + mouth_y*DOWN + self.character_height/6*LEFT,
                self.face.get_center() + mouth_y*DOWN + self.character_height/6*RIGHT,
                color=BLACK,
                stroke_width=3
            )
    
    def change_emotion(self, emotion="happy"):
        """Change the face's expression."""
        new_mouth = self.create_mouth(emotion)
        return Transform(self.mouth, new_mouth)
    
    def look_at(self, point):
        """Make the eyes look at a specific point."""
        direction = normalize(point - self.face.get_center())
        eye_shift = direction * self.character_height/30
        
        return AnimationGroup(
            self.left_eye.animate.move_to(
                self.face.get_center() + self.character_height/6*LEFT + 
                self.character_height/6*UP + eye_shift
            ),
            self.right_eye.animate.move_to(
                self.face.get_center() + self.character_height/6*RIGHT + 
                self.character_height/6*UP + eye_shift
            )
        )


class Robot(SimpleCharacter):
    """A simple geometric robot character."""
    
    def build_character(self):
        # Head
        self.head = Square(
            side_length=self.character_height/3,
            color=self.character_color,
            fill_opacity=0.8,
            stroke_width=2
        )
        
        # Body
        self.body = Rectangle(
            height=self.character_height/2,
            width=self.character_height/2.5,
            color=self.character_color,
            fill_opacity=0.8,
            stroke_width=2
        )
        self.body.next_to(self.head, DOWN, buff=0.05)
        
        # Arms
        self.left_arm = Rectangle(
            height=self.character_height/3,
            width=self.character_height/10,
            color=GREY,
            fill_opacity=0.8,
            stroke_width=2
        )
        self.left_arm.next_to(self.body, LEFT, buff=0)
        
        self.right_arm = Rectangle(
            height=self.character_height/3,
            width=self.character_height/10,
            color=GREY,
            fill_opacity=0.8,
            stroke_width=2
        )
        self.right_arm.next_to(self.body, RIGHT, buff=0)
        
        # Legs
        self.left_leg = Rectangle(
            height=self.character_height/3,
            width=self.character_height/8,
            color=GREY,
            fill_opacity=0.8,
            stroke_width=2
        )
        self.left_leg.next_to(self.body, DOWN, buff=0).shift(0.1*LEFT)
        
        self.right_leg = Rectangle(
            height=self.character_height/3,
            width=self.character_height/8,
            color=GREY,
            fill_opacity=0.8,
            stroke_width=2
        )
        self.right_leg.next_to(self.body, DOWN, buff=0).shift(0.1*RIGHT)
        
        # Eyes (LED style)
        self.left_eye = Dot(
            radius=self.character_height/30,
            color=RED,
            fill_opacity=1
        ).move_to(self.head.get_center() + 0.1*LEFT + 0.05*UP)
        
        self.right_eye = Dot(
            radius=self.character_height/30,
            color=RED,
            fill_opacity=1
        ).move_to(self.head.get_center() + 0.1*RIGHT + 0.05*UP)
        
        # Antenna
        self.antenna_base = Line(
            self.head.get_top(),
            self.head.get_top() + 0.2*UP,
            color=GREY,
            stroke_width=2
        )
        self.antenna_tip = Dot(
            self.antenna_base.get_end(),
            radius=self.character_height/40,
            color=RED
        )
        
        # Add all parts
        self.add(
            self.body, self.head,
            self.left_arm, self.right_arm,
            self.left_leg, self.right_leg,
            self.left_eye, self.right_eye,
            self.antenna_base, self.antenna_tip
        )
    
    def blink(self):
        """Make the robot blink its LED eyes."""
        return AnimationGroup(
            Flash(self.left_eye, color=YELLOW, flash_radius=0.1),
            Flash(self.right_eye, color=YELLOW, flash_radius=0.1)
        )


class Ghost(SimpleCharacter):
    """A simple ghost character."""
    
    def build_character(self):
        # Body (rounded rectangle)
        self.body = RoundedRectangle(
            corner_radius=self.character_height/3,
            height=self.character_height,
            width=self.character_height*0.7,
            color=WHITE,
            fill_opacity=0.7,
            stroke_width=2
        )
        
        # Bottom wavy part
        wave_points = []
        bottom = self.body.get_bottom()
        width = self.body.width
        for i in range(5):
            x = -width/2 + i*width/4
            y = 0.1*np.sin(i*PI/2)
            wave_points.append(bottom + x*RIGHT + y*DOWN)
        
        self.waves = VMobject()
        self.waves.set_points_as_corners(wave_points)
        self.waves.set_color(WHITE)
        self.waves.set_stroke(width=2)
        
        # Eyes
        self.left_eye = Circle(
            radius=self.character_height/15,
            color=BLACK,
            fill_opacity=1
        ).move_to(self.body.get_center() + 0.15*LEFT + 0.2*UP)
        
        self.right_eye = Circle(
            radius=self.character_height/15,
            color=BLACK,
            fill_opacity=1
        ).move_to(self.body.get_center() + 0.15*RIGHT + 0.2*UP)
        
        # Pupils
        self.left_pupil = Dot(
            radius=self.character_height/30,
            color=WHITE
        ).move_to(self.left_eye.get_center())
        
        self.right_pupil = Dot(
            radius=self.character_height/30,
            color=WHITE
        ).move_to(self.right_eye.get_center())
        
        # Mouth
        self.mouth = Arc(
            start_angle=PI + PI/6,
            angle=-PI/3,
            radius=self.character_height/10,
            color=BLACK,
            stroke_width=2
        ).move_to(self.body.get_center() + 0.05*DOWN)
        
        # Add all parts
        self.add(
            self.body, self.waves,
            self.left_eye, self.right_eye,
            self.left_pupil, self.right_pupil,
            self.mouth
        )
    
    def float_animation(self):
        """Make the ghost float up and down."""
        return self.animate.shift(0.2*UP).shift(0.2*DOWN).set_run_time(2)


# Utility functions for common character animations

def character_thinks(character, thought_text, **kwargs):
    """Create a thought bubble for any character."""
    thought = ThoughtBubble(**kwargs)
    thought.pin_to(character)
    thought.add_content(Text(thought_text, font_size=24))
    return Create(thought)


def character_says(character, speech_text, **kwargs):
    """Create a speech bubble for any character."""
    speech = SpeechBubble(**kwargs)
    speech.pin_to(character)
    speech.add_content(Text(speech_text, font_size=24))
    return Create(speech)


# Replacement mapping for common Pi Creature names
CHAR_REPLACEMENTS = {
    "Randolph": lambda: SimpleFace(color=BLUE_E),
    "Mortimer": lambda: SimpleFace(color=GREY),
    "Teacher": lambda: Robot(color=GREEN),
    "Student": lambda: StickFigure(color=BLUE),
}


def get_character(name="default", **kwargs):
    """Get a character by name or create a default one."""
    if name in CHAR_REPLACEMENTS:
        return CHAR_REPLACEMENTS[name]()
    else:
        return SimpleFace(**kwargs)


# Example scene showing how to use these characters
class CharacterDemo(Scene):
    """Demo scene showing different character types and animations."""
    
    def construct(self):
        # Create different characters
        stick = StickFigure(color=BLUE).scale(0.5).to_edge(LEFT)
        face = SimpleFace(color=YELLOW).scale(0.5)
        robot = Robot(color=GREEN).scale(0.5).to_edge(RIGHT)
        
        # Show them
        self.play(
            FadeIn(stick),
            FadeIn(face),
            FadeIn(robot)
        )
        
        # Make them do things
        self.play(
            stick.wave(),
            face.change_emotion("surprised"),
            robot.blink()
        )
        
        # Speech bubble
        self.play(character_says(face, "Hello!"))
        
        self.wait()