"""
Missing dependencies for PhaseSpaceOfPopulationModel scene from div_curl.py

This file contains all the functions, constants, and classes needed 
for the PhaseSpaceOfPopulationModel scene that are not directly in the scene class.
"""

import numpy as np
import random
from manimlib import *

# Constants from div_curl.py
FOX_COLOR = "#DF7F20"
RABBIT_COLOR = "#C6D6EF"

def preditor_prey_vector_field(point):
    """
    Predator-prey vector field function used in the population dynamics.
    This implements the Lotka-Volterra equations for predator-prey dynamics.
    
    From div_curl.py lines 144-155
    """
    alpha = 30.0
    beta = 1.0
    gamma = 30.0
    delta = 1.0
    x, y = point[:2]
    result = 0.05 * np.array([
        alpha * x - beta * x * y,
        delta * x * y - gamma * y,
        0,
    ])
    return rotate(result, 1 * DEGREES)


def move_along_vector_field(mobject, vector_field_func, **kwargs):
    """
    Creates an animation that moves a mobject along a vector field.
    Continuously updates the position based on the vector field at current position.
    
    In ManimGL, this returns a ContinualAnimation object that can be added to the scene.
    """
    def update_func(mob, dt):
        vector = vector_field_func(mob.get_center())
        mob.shift(vector * dt)
    
    class MoveAlongVectorField:
        def __init__(self, mobject, func):
            self.mobject = mobject
            self.func = func
            self.mobject.add_updater(update_func)
    
    return MoveAlongVectorField(mobject, vector_field_func)


def rotate(vector, angle):
    """
    Rotate a vector by a given angle around the z-axis.
    
    Args:
        vector: A 3D numpy array representing the vector
        angle: The angle to rotate by (in radians)
    
    Returns:
        The rotated vector as a numpy array
    """
    cos_a = np.cos(angle)
    sin_a = np.sin(angle)
    rotation_matrix = np.array([
        [cos_a, -sin_a, 0],
        [sin_a, cos_a, 0],
        [0, 0, 1]
    ])
    return np.dot(rotation_matrix, vector)


class ShowTwoPopulations(Scene):
    """
    Base class for population dynamics scenes.
    Shows foxes (predators) and rabbits (prey) evolving according to the Lotka-Volterra equations.
    
    From div_curl.py lines 2715-2893
    """
    CONFIG = {
        "total_num_animals": 80,
        "start_num_foxes": 40,
        "start_num_rabbits": 20,
        "animal_height": 0.5,
        "final_wait_time": 30,
        "count_word_scale_val": 1,
    }

    def construct(self):
        self.introduce_animals()
        self.evolve_system()

    def introduce_animals(self):
        foxes = self.foxes = VGroup(*[
            self.get_fox()
            for n in range(self.total_num_animals)
        ])
        rabbits = self.rabbits = VGroup(*[
            self.get_rabbit()
            for n in range(self.total_num_animals)
        ])
        foxes[self.start_num_foxes:].set_fill(opacity=0)
        rabbits[self.start_num_rabbits:].set_fill(opacity=0)

        fox, rabbit = examples = VGroup(foxes[0], rabbits[0])
        for mob in examples:
            mob.save_state()
            mob.set_height(3)
        examples.arrange(LEFT, buff=2)

        preditor, prey = words = VGroup(
            OldTexText("Predator"),
            OldTexText("Prey")
        )
        for mob, word in zip(examples, words):
            word.scale(1.5)
            word.next_to(mob, UP)
            self.play(
                FadeInFromDown(mob),
                Write(word, run_time=1),
            )
        self.play(
            LaggedStartMap(
                ApplyMethod, examples,
                lambda m: (m.restore,)
            ),
            LaggedStartMap(FadeOut, words),
            *[
                LaggedStartMap(
                    FadeIn,
                    group[1:],
                    run_time=4,
                    lag_ratio=0.1,
                    rate_func=lambda t: np.clip(smooth(2 * t), 0, 1)
                )
                for group in [foxes, rabbits]
            ]
        )

    def evolve_system(self):
        foxes = self.foxes
        rabbits = self.rabbits
        phase_point = VectorizedPoint(
            self.start_num_rabbits * RIGHT +
            self.start_num_foxes * UP
        )
        self.add(move_along_vector_field(
            phase_point,
            preditor_prey_vector_field,
        ))

        def get_num_rabbits():
            return phase_point.get_center()[0]

        def get_num_foxes():
            return phase_point.get_center()[1]

        def get_updater(pop_size_getter):
            def update(animals):
                target_num = pop_size_getter()
                for n, animal in enumerate(animals):
                    animal.set_fill(
                        opacity=np.clip(target_num - n, 0, 1)
                    )
                target_int = int(np.ceil(target_num))
                tail = animals.submobjects[target_int:]
                random.shuffle(tail)
                animals.submobjects[target_int:] = tail

            return update

        self.add(Mobject.add_updater(
            foxes, get_updater(get_num_foxes)
        ))
        self.add(Mobject.add_updater(
            rabbits, get_updater(get_num_rabbits)
        ))

        # Add counts for foxes and rabbits
        labels = self.get_pop_labels()
        num_foxes = Integer(10)
        num_foxes.scale(self.count_word_scale_val)
        num_foxes.next_to(labels[0], RIGHT)
        num_foxes.align_to(labels[0][0][1], DOWN)
        num_rabbits = Integer(10)
        num_rabbits.scale(self.count_word_scale_val)
        num_rabbits.next_to(labels[1], RIGHT)
        num_rabbits.align_to(labels[1][0][1], DOWN)

        num_foxes.add_updater(lambda d: d.set_value(get_num_foxes()))
        num_rabbits.add_updater(lambda d: d.set_value(get_num_rabbits()))

        self.add(num_foxes, num_rabbits)

        for count in num_foxes, num_rabbits:
            self.add(Mobject.add_updater(
                count, self.update_count_color,
            ))

        self.play(
            FadeIn(labels),
            *[
                UpdateFromAlphaFunc(count, lambda m, a: m.set_fill(opacity=a))
                for count in (num_foxes, num_rabbits)
            ]
        )

        self.wait(self.final_wait_time)

    # Helpers

    def get_animal(self, name, color):
        result = SVGMobject(
            file_name=name,
            height=self.animal_height,
            fill_color=color,
        )
        # Commented out submobject coloring code in original
        # for submob in result.family_members_with_points():
        #     if submob.is_subpath:
        #         submob.is_subpath = False
        #         submob.set_fill(
        #             interpolate_color(color, BLACK, 0.8),
        #             opacity=1
        #         )
        x_shift, y_shift = [
            (2 * random.random() - 1) * max_val
            for max_val in [
                FRAME_WIDTH / 2 - 2,
                FRAME_HEIGHT / 2 - 2
            ]
        ]
        result.shift(x_shift * RIGHT + y_shift * UP)
        return result

    def get_fox(self):
        return self.get_animal("fox", FOX_COLOR)

    def get_rabbit(self):
        # return self.get_animal("rabbit", WHITE)
        return self.get_animal("bunny", RABBIT_COLOR)

    def get_pop_labels(self):
        labels = VGroup(
            OldTexText("\\# Foxes: "),
            OldTexText("\\# Rabbits: "),
        )
        for label in labels:
            label.scale(self.count_word_scale_val)
        labels.arrange(RIGHT, buff=2)
        labels.to_edge(UP)
        return labels

    def update_count_color(self, count):
        count.set_fill(interpolate_color(
            BLUE, RED, (count.number - 20) / 30.0
        ))
        return count


# Additional ManimGL-specific imports and utilities that might be needed:
# - VectorizedPoint: A point in space that can be animated
# - SVGMobject: For loading SVG files (fox and bunny)
# - Integer: An animated integer display
# - OldTexText: Text rendering (may need to be replaced with Text in ManimCE)
# - smooth: Smoothing function for animations
# - interpolate_color: Color interpolation utility
# - LaggedStartMap: For staggered animations
# - FadeInFromDown: Specific fade-in animation
# - UpdateFromAlphaFunc: Alpha-based update animation

# Note: PhaseSpaceOfPopulationModel inherits from ShowTwoPopulations, PiCreatureScene, and MovingCameraScene
# The CONFIG for PhaseSpaceOfPopulationModel includes:
# - "origin": 5 * LEFT + 2.5 * DOWN
# - "vector_field_config": {"max_magnitude": 50}
# - "pi_creatures_start_on_screen": False
# - "default_pi_creature_kwargs": {"height": 1.8}
# - "flow_time": 10