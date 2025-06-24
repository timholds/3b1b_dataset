#!/usr/bin/env python3
"""
Custom animation implementations for ManimGL to ManimCE conversion.

This module provides compatibility implementations for ManimGL animations
that don't have direct equivalents in ManimCE.
"""

from manim import *
from typing import List, Union, Optional, Callable
import numpy as np


class FlipThroughNumbers(Animation):
    """
    Animation that flips through a sequence of numbers on a display.
    
    This is a compatibility implementation for ManimGL's FlipThroughNumbers.
    """
    
    def __init__(
        self,
        text_mob: Union[Text, MathTex],
        numbers: List[Union[int, float, str]],
        run_time: float = 3.0,
        rate_func: Callable = linear,
        **kwargs
    ):
        self.text_mob = text_mob
        self.numbers = [str(n) for n in numbers]  # Convert all to strings
        self.original_text = text_mob.text if hasattr(text_mob, 'text') else ""
        
        super().__init__(text_mob, run_time=run_time, rate_func=rate_func, **kwargs)
    
    def interpolate_mobject(self, alpha: float) -> None:
        """Update the text based on animation progress."""
        # Calculate which number to show
        if alpha >= 1:
            index = len(self.numbers) - 1
        else:
            index = int(alpha * len(self.numbers))
        
        # Update the text
        new_text = self.numbers[index]
        
        # Create a new text object with the same properties
        if isinstance(self.text_mob, MathTex):
            new_mob = MathTex(new_text)
        else:
            new_mob = Text(new_text)
        
        # Copy properties from original
        new_mob.match_height(self.text_mob)
        new_mob.match_style(self.text_mob)
        new_mob.move_to(self.text_mob)
        
        # Replace the submobjects
        self.text_mob.become(new_mob)


class DelayByOrder(AnimationGroup):
    """
    Animation that delays submobject animations based on their order.
    
    This is a compatibility wrapper around LaggedStart for ManimGL's DelayByOrder.
    """
    
    def __init__(
        self,
        animation_class: type,
        mobject: Mobject,
        lag_ratio: float = 0.1,
        run_time: Optional[float] = None,
        **kwargs
    ):
        # Extract animation-specific kwargs
        anim_kwargs = {}
        group_kwargs = {}
        
        # Common animation parameters
        for key in ['rate_func', 'remover']:
            if key in kwargs:
                anim_kwargs[key] = kwargs.pop(key)
        
        # Remaining kwargs go to AnimationGroup
        group_kwargs.update(kwargs)
        
        # Create individual animations for each submobject
        animations = []
        submobs = list(mobject.submobjects) if mobject.submobjects else [mobject]
        
        for submob in submobs:
            anim = animation_class(submob, **anim_kwargs)
            animations.append(anim)
        
        # If run_time is specified, use it
        if run_time is not None:
            group_kwargs['run_time'] = run_time
        
        # Use lag_ratio to control the timing
        group_kwargs['lag_ratio'] = lag_ratio
        
        # Initialize as LaggedStart
        super().__init__(*animations, **group_kwargs)


def create_flip_through_numbers(
    position: np.ndarray = ORIGIN,
    numbers: List[Union[int, float, str]] = None,
    height: float = 0.5,
    run_time: float = 3.0,
    **kwargs
) -> FlipThroughNumbers:
    """
    Convenience function to create a number flipping animation.
    
    Args:
        position: Where to place the number display
        numbers: List of numbers to flip through
        height: Height of the text
        run_time: Total animation duration
        **kwargs: Additional arguments for the animation
    
    Returns:
        FlipThroughNumbers animation ready to play
    """
    if numbers is None:
        numbers = list(range(10))
    
    # Create initial text mobject
    text = Text(str(numbers[0]), font_size=int(height * 100))
    text.move_to(position)
    
    return FlipThroughNumbers(text, numbers, run_time=run_time, **kwargs)


def convert_continual_animation_to_updater(
    mobject: Mobject,
    update_function: Callable[[Mobject, float], None],
    **kwargs
) -> Mobject:
    """
    Helper to convert ContinualAnimation patterns to updater functions.
    
    Args:
        mobject: The mobject to add the updater to
        update_function: Function that takes (mobject, dt) and updates it
        **kwargs: Additional arguments (for compatibility)
    
    Returns:
        The mobject with updater added
    """
    mobject.add_updater(update_function)
    return mobject


# Specialized animation implementations

class CountingAnimation(Animation):
    """
    Animation that counts from one number to another.
    Similar to ManimGL's Count animation.
    """
    
    def __init__(
        self,
        decimal_mob: DecimalNumber,
        start_value: float = 0,
        end_value: float = 10,
        run_time: float = 2.0,
        rate_func: Callable = linear,
        **kwargs
    ):
        self.decimal_mob = decimal_mob
        self.start_value = start_value
        self.end_value = end_value
        
        # Set initial value
        decimal_mob.set_value(start_value)
        
        super().__init__(decimal_mob, run_time=run_time, rate_func=rate_func, **kwargs)
    
    def interpolate_mobject(self, alpha: float) -> None:
        """Update the number based on animation progress."""
        value = interpolate(self.start_value, self.end_value, alpha)
        self.decimal_mob.set_value(value)


class RotatingAnimation(Animation):
    """
    Continuous rotation animation, similar to ManimGL's Rotating.
    Can be used as a replacement for ContinualAnimation patterns.
    """
    
    def __init__(
        self,
        mobject: Mobject,
        angle: float = TAU,
        axis: np.ndarray = OUT,
        about_point: Optional[np.ndarray] = None,
        run_time: float = 5.0,
        rate_func: Callable = linear,
        **kwargs
    ):
        self.angle = angle
        self.axis = axis
        self.about_point = about_point if about_point is not None else mobject.get_center()
        
        super().__init__(mobject, run_time=run_time, rate_func=rate_func, **kwargs)
    
    def interpolate_mobject(self, alpha: float) -> None:
        """Rotate the mobject based on animation progress."""
        self.mobject.rotate(
            self.angle * self.rate_func(alpha) / self.run_time * self.dt,
            axis=self.axis,
            about_point=self.about_point
        )


# Utility functions for common conversions

def create_delayed_animation(
    animation_class: type,
    mobjects: Union[Mobject, List[Mobject]],
    lag_ratio: float = 0.1,
    **kwargs
) -> LaggedStart:
    """
    Create a delayed animation for multiple mobjects.
    
    This is a convenience wrapper for the common pattern of applying
    the same animation to multiple objects with delays.
    """
    if isinstance(mobjects, Mobject):
        mobjects = list(mobjects.submobjects) if mobjects.submobjects else [mobjects]
    
    animations = [animation_class(mob, **kwargs) for mob in mobjects]
    return LaggedStart(*animations, lag_ratio=lag_ratio)


def create_counting_animation(
    start: float = 0,
    end: float = 100,
    position: np.ndarray = ORIGIN,
    num_decimal_places: int = 0,
    **kwargs
) -> tuple[DecimalNumber, CountingAnimation]:
    """
    Create a number that counts from start to end.
    
    Returns both the DecimalNumber and the animation for flexibility.
    """
    number = DecimalNumber(
        start,
        num_decimal_places=num_decimal_places,
        include_sign=start < 0 or end < 0
    )
    number.move_to(position)
    
    count_anim = CountingAnimation(
        number,
        start_value=start,
        end_value=end,
        **kwargs
    )
    
    return number, count_anim


# Export all custom animations
__all__ = [
    'FlipThroughNumbers',
    'DelayByOrder',
    'CountingAnimation',
    'RotatingAnimation',
    'create_flip_through_numbers',
    'convert_continual_animation_to_updater',
    'create_delayed_animation',
    'create_counting_animation',
]