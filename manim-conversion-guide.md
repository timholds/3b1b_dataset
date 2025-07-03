
A Rosetta Stone for ManimGL to ManimCE Translation: A Technical Migration Guide


Introduction: The Two Manims

This document serves as an authoritative technical guide for translating Python animation scripts from the manimgl library (the version developed and used by Grant "3b1b" Sanderson) to the manim library (the Community Edition, or ManimCE). Its primary purpose is to provide a high-accuracy, detailed resource for training a Large Language Model (LLM) and for human developers performing quality assurance on the translation process.
Section 1: Foundational and Structural Divergence
This section addresses the high-level environmental and architectural differences between the two libraries. Correctly identifying and translating these foundational elements is the most critical first step in any migration effort, as errors at this stage will lead to fundamental and systemic failures in the translated code.
1.2 The CONFIG Paradigm Shift: From Magic Dictionary to Explicit init

A defining architectural difference is the handling of default object properties. ManimGL frequently employs a class-level dictionary named CONFIG to set default parameters for Mobject and Scene subclasses.13 While convenient for a single developer, this pattern obscures class inheritance and constructor signatures.
In a move toward more explicit and standard Pythonic design, ManimCE deprecated the CONFIG dictionary starting in version v0.2.0 (January 2021).12 This change is a major source of translation errors. A
CONFIG dictionary left in a translated script will be silently ignored by the ManimCE renderer. This does not raise a Traceback, but results in visual bugs where objects are created with their default attributes instead of the intended ones (e.g., a shape appearing in default white instead of a specified color).13
Correctly translating the CONFIG pattern requires understanding its two primary use cases and applying the appropriate refactoring:
For defining new, class-specific attributes: CONFIG key-value pairs that introduce new variables should be converted directly into class attributes.
ManimGL:
Python
class MyScene(Scene):
    CONFIG = {"my_variable": 5}


ManimCE Translation:
Python
class MyScene(Scene):
    my_variable = 5


For overriding parent class attributes: CONFIG keys that correspond to existing attributes of a parent class (like color or fill_opacity) must be converted into keyword arguments in the class's __init__ method and passed to the parent's constructor via super().__init__().
ManimGL:
Python
class RedCircle(Circle):
    CONFIG = {"color": RED, "fill_opacity": 0.5}


ManimCE Translation:
Python
class RedCircle(Circle):
    def __init__(self, color=RED, fill_opacity=0.5, **kwargs):
        super().__init__(color=color, fill_opacity=fill_opacity, **kwargs)


The following table provides a direct mapping for this critical refactoring task.

ManimGL CONFIG Key
ManimCE Equivalent
Target Class(es)
ManimGL Example
ManimCE Translation
Notes
"color"
__init__ kwarg color
VMobject & subclasses
class BlueSquare(Square): CONFIG={"color":BLUE}
class BlueSquare(Square): def __init__(self, color=BLUE, **kwargs): super().__init__(color=color, **kwargs)
Silently ignored in CE if not translated.
"fill_opacity"
__init__ kwarg fill_opacity
VMobject & subclasses
class HalfFill(Circle): CONFIG={"fill_opacity":0.5}
class HalfFill(Circle): def __init__(self, fill_opacity=0.5, **kwargs): super().__init__(fill_opacity=fill_opacity, **kwargs)
Affects the fill, not the stroke.
Custom Variables
Class attribute
Any class
class MyScene(Scene): CONFIG={"wait_time": 2}
class MyScene(Scene): wait_time = 2
For variables not part of the parent API.
"camera_config"
Class attribute camera_config
Scene
class MyScene(Scene): CONFIG={"camera_config":{"background_color":BLUE}}
class MyScene(Scene): def construct(self): self.camera.background_color = BLUE
In CE, camera properties are set on self.camera.


1.3 Global and File-Based Configuration

While less critical for single-script translation, understanding the configuration file differences provides important context.
ManimGL: Uses a YAML file named custom_config.yml placed in the project directory to control global settings like output directories, render quality, and asset paths.9
ManimCE: Uses a .cfg file, typically manim.cfg, which follows the configparser INI-style format. This file is searched for in the directory of the script being rendered, allowing for project-specific configurations.15

Section 2: The Mobject API: A Deep Dive into Class and Method Mapping

This section provides the core API mapping for the fundamental visual objects used in animations. The translation process requires careful attention to class name changes, method refactoring, and shifts in idiomatic usage.

2.1 Base Classes: Mobject and VMobject

The fundamental class hierarchy of Mobject (the base class for all on-screen objects) and VMobject (the subclass for vector-based graphics) is conserved between both versions.17 However, the methods for styling and manipulating these objects have diverged significantly.
A primary difference lies in how styles are applied. ManimGL code often uses a single, comprehensive set_style() method to configure multiple properties like fill color, opacity, and stroke width in one call.19 ManimCE promotes a more granular and explicit approach. The idiomatic ManimCE way is to pass styling properties as individual keyword arguments directly to the mobject's constructor (e.g.,
Square(fill_color=BLUE, fill_opacity=0.5)) or to use distinct setter methods for each property (e.g., .set_fill(color=BLUE, opacity=0.5) and .set_stroke(width=2)).20 This shift from a bundled style method to discrete arguments and setters is a common refactoring pattern required during translation.
Furthermore, ManimCE has invested heavily in creating a more extensive and consistently named set of methods for positioning (.to_edge(), .next_to(), .align_to()) and retrieving properties (.get_center(), .get_width(), .get_height()). These methods are thoroughly documented and provide predictable behavior.17 ManimGL's methods may be less numerous or have inconsistent names, often necessitating direct inspection of the source code to understand their function.22

2.2 The Great Text Rework: TextMobject vs. Text, Tex, and MathTex

The handling of text and mathematical equations is one of the most complex and error-prone areas of translation. This is not a simple renaming task; it requires a semantic analysis of the content being rendered.
ManimGL's Unified LaTeX Approach:
ManimGL primarily relies on two classes, both of which use a full LaTeX installation for rendering:
TextMobject: This class is intended for text. It uses LaTeX but operates in "text mode." It can be used to render simple mathematical expressions by enclosing them in dollar signs ($).24
TexMobject: This class is intended for mathematical equations. By default, it wraps the input string in a LaTeX align* environment, treating the entire string as math content.24
Historically, these class names have changed, which can lead to NameError: name 'TextMobject' is not defined when running older code against newer library versions.26
ManimCE's Specialized and Modernized Approach:
ManimCE replaced the dual-class system with three specialized classes, separating the rendering backend based on the content type:
Text: This class uses the Pango text layout engine and does not use LaTeX. It is the modern, preferred method for all non-equation text. Its advantages are significant: it is faster, provides superior control over fonts, and has excellent native support for Unicode, including non-English alphabets and emojis.28
Tex: This class uses LaTeX and is the direct replacement for TextMobject when LaTeX processing is required, particularly for sentences that mix plain text with mathematical formulas (e.g., Tex("The value of Euler's number is $e \\approx 2.718$")).
MathTex: This class also uses LaTeX but is specialized for standalone equations. It automatically wraps the input string in a math environment (by default, $... $), making it the most convenient and explicit choice for rendering formulas like MathTex("e^{i\\pi} + 1 = 0").27
This architectural shift means that a translation tool cannot simply map TextMobject to one class. It must analyze the string content to determine the most appropriate ManimCE target. This semantic decision-making is crucial for generating correct, efficient, and idiomatic code.
ManimGL Class
String Content Example
Heuristic Rule for Translation
Recommended ManimCE Class
ManimCE Translation Example
Rationale / Footgun
TextMobject
"Hello World"
Contains no LaTeX commands or $ delimiters.
Text
Text("Hello World")
Use Text for performance, font control, and Unicode. Using Tex would be slower and unnecessary.
TextMobject
"Value: $x^2$"
Contains a mix of plain text and $ delimiters.
Tex
Tex("Value: $x^2$")
Tex is designed for mixed text/math content.
TexMobject
"e^{i\\pi} + 1 = 0"
Contains only a mathematical expression.
MathTex
MathTex("e^{i\\pi} + 1 = 0")
MathTex is the specialized, idiomatic class for equations.
TextMobject or TexMobject
(Any string)
Code requires a custom LaTeX preamble.
Tex or MathTex
my_template = TexTemplate(...)\nTex("...", tex_template=my_template)
ManimCE's TexTemplate object allows for portable, per-project preamble customization, unlike ManimGL's global file editing.30


2.3 Color and Gradients: From Methods to Declarative Arguments

The application of color and gradients has been streamlined in ManimCE.
ManimGL: Applying a gradient typically involves calling a specific method like set_color_by_gradient(...) or set_submobject_colors_by_gradient(...) after the object has been created.31
ManimCE: The idiomatic approach is more declarative. A gradient is applied by passing a tuple of colors to the color, fill_color, or stroke_color keyword argument, either during object instantiation or in a subsequent .set_color() call.29 For example,
my_text.set_color_by_gradient(RED, BLUE) in ManimGL becomes my_text = Text("...", color=(RED, BLUE)) in ManimCE.
The color system itself is also more advanced in the community version. ManimCE features a robust ManimColor class for color representation and manipulation 21 and provides a vast library of predefined color constants from various standards (e.g., X11, XKCD). These must be explicitly imported from their respective modules, such as
from manim.utils.color import XKCD.35 In contrast, ManimGL's color constants are typically defined in a single
constants.py file.32
Furthermore, ManimCE offers more precise control over the appearance of gradients. The sheen_direction property of a VMobject can be used to explicitly set the vector along which the gradient is applied, a feature that is often fixed or less controllable in ManimGL.36

Section 3: Animating the Scene: play, Updaters, and Workflow

This section addresses the dynamic aspects of Manim—the methods and concepts used to create motion and change over time. The core logic is similar, but key differences in class names, syntax interpretation, and workflow features must be handled carefully.

3.1 The play() Method and Animation Classes

The scene.play() method is the central function for executing animations in both libraries.8 However, many of the animation classes passed to
play() have been renamed in ManimCE for greater clarity and consistency. A direct lookup table is essential for translation.
ManimGL Class Name
ManimCE Class Name
Notes
ShowCreation
Create
Functionally identical.8
ShowPartial
Create
ShowPartial is an older name for ShowCreation.
TransformMatchingTex
TransformMatchingShapes or TransformMatchingTex
ManimCE's versions have more refined behavior and handle mismatches differently.39
FadeOutAndShift
FadeOut + shift
In CE, this is typically composed: FadeOut(mobj, shift=DOWN).
ApplyMethod
.animate syntax
The .animate syntax is the modern replacement.

A critical footgun exists with the .animate syntax (e.g., self.play(mobj.animate.shift(RIGHT))), which is supported by both versions.38 ManimCE's documentation explicitly warns that
.animate works by interpolating between the mobject's starting state and its ending state.38 This can produce unexpected or incorrect visual results. For instance,
mobj.animate.rotate(PI) might result in no visible animation if the start and end orientations are identical, as there is no intermediate state to interpolate. The more robust and predictable approach in ManimCE is to use explicit animation classes, such as Rotate(mobj, angle=PI), which guarantees the intended rotational motion.38 Translating
.animate calls from ManimGL should favor this more explicit form to ensure correctness.

3.2 Updaters and ValueTracker

The concept of "updaters"—functions that are executed on every frame of an animation—is central to creating dynamic and responsive scenes in both libraries.39 The
ValueTracker object, which encapsulates a numerical value that can be animated, is also a shared concept.41
Syntax: Older ManimGL code might use helper functions like always(f, x).39 The modern ManimCE idiom is to use the
.add_updater(lambda m:...) method on a mobject or the always_redraw(lambda:...) wrapper function. always_redraw is a convenient shorthand that effectively removes and re-adds the updated mobject to the scene on every frame.41
The .become() Method: ManimCE introduces the powerful .become(other_mobject) method, which has no direct equivalent in ManimGL. This method instantly makes one mobject adopt the points, position, and style of another. When used inside an updater, it allows for complex, continuous transformations that are otherwise difficult to achieve, such as a Brace that dynamically resizes to match a changing Line.43 This pattern is a key tool for translating complex updater logic from ManimGL.
Performance Footgun: A known performance issue can arise in ManimCE when using .become() to update a DecimalNumber based on a ValueTracker. This specific combination can cause the number of points in the underlying VMobject to grow unboundedly with each frame, leading to severe rendering slowdown over the course of the animation. The recommended workaround is to use the DecimalNumber.set_value() method instead, which updates the number without recreating the entire object.44

3.3 Non-Translatable Concepts: The Interactive Workflow

A significant portion of ManimGL code, especially that found in 3Blue1Brown's video repositories, contains commands related to an interactive development workflow. These are not part of the animation's definition and have no equivalent in a standard ManimCE render. They must be identified and removed during translation.
self.embed(): This command is frequently found in ManimGL scripts.8 It is not an animation command. It pauses the OpenGL render and drops the user into an interactive IPython shell, allowing for live manipulation of the scene's mobjects. This command is not recognized by the standard ManimCE renderer and must be deleted.
Checkpointing (checkpoint_paste): Grant Sanderson's personal workflow involves custom text editor plugins that can copy a highlighted block of code and execute it against a saved state of the scene in the interactive terminal.45 Any code or comments referring to this functionality (e.g.,
checkpoint_paste()) are artifacts of this external tooling and are not part of the ManimGL library itself. They are untranslatable and must be removed.
Live Camera Interaction: The ability to pan (s key), zoom (z key), and rotate (d key) the camera with the mouse during a live preview is a feature of ManimGL's OpenGL window.8 While ManimCE has its own interactive OpenGL mode with similar features, these interactions are not scripted within the
construct method and are therefore not relevant to the translation of a scene's definition.46

A Compendium of Common Errors and Translation Footguns
This final section serves as a practical diagnostic guide for debugging and quality control. It highlights common errors, dangerous "silent failures," and provides a checklist for human review of translated code.

4.1 Error Message Rosetta Stone: Mapping Symptoms to Causes

Translating between the libraries often produces predictable errors. Understanding their root cause is key to efficient debugging.
Symptom: NameError: name 'TextMobject' is not defined 26
Root Cause: The script is using a deprecated ManimGL class name in a ManimCE environment.
Solution: Replace with the appropriate specialized class: Text, Tex, or MathTex, based on the semantic analysis of the string content as described in Section 2.2.
Symptom: AttributeError: 'Square' object has no attribute 'set_style'
Root Cause: The script is calling a method that was refactored or removed in ManimCE. The bundled set_style method from ManimGL is a common example.
Solution: Unpack the arguments from the deprecated method call. Apply them as individual keyword arguments in the mobject's constructor or through separate, specific setter methods (e.g., .set_fill(), .set_stroke()).
Symptom: Manim says that “there are no scenes inside that module” 12
Root Cause: This almost always indicates a Python environment or version mix-up. The manim executable from a manimgl installation is being used to run a script that imports from manim (ManimCE), or vice-versa.
Solution: Ensure the correct environment is activated. Use the unambiguous python -m manim <file>.py <SceneName> command to invoke the renderer, which guarantees the correct library is used.
Symptom: LaTeX Error: File 'standalone.cls' not found 27
Root Cause: This is an external dependency issue, not a library bug. The user's LaTeX distribution is incomplete and is missing the required standalone package.
Solution: The user must install the missing package using their LaTeX distribution's package manager (e.g., MiKTeX Console or tlmgr).

4.2 The Perils of Silent Failures and Visual Bugs

More dangerous than explicit errors are the "footguns" that allow the code to run without crashing but produce incorrect or visually flawed output. These can only be caught by careful visual inspection.
The CONFIG Trap: As detailed in Section 1.2, a leftover CONFIG dictionary is silently ignored by ManimCE, causing mobjects to render with default styling instead of the intended custom styling.13
The .animate Ambiguity: As discussed in Section 3.1, using .animate for certain transformations like rotation can lead to unexpected paths or no motion at all if the start and end states are visually identical.38
The Gradient Direction Shift: Default gradient orientations may differ. A gradient that appears diagonal in ManimGL might render horizontally in ManimCE unless a sheen_direction vector is explicitly set.36
The Updater Performance Decay: The specific combination of DecimalNumber and .become inside an updater can lead to a memory leak-like behavior where the mobject's point data grows unboundedly, causing severe rendering slowdown over time.44

4.3 A Post-Translation Audit Checklist 
For verifying the quality of an LLM-based translation, this checklist provides a structured framework for this review process.
1. Visual Style Verification:
[ ] Colors and Opacity: Do all mobjects have the correct fill color, stroke color, and opacity? (Verifies CONFIG and set_style translation).
[ ] Gradients: Are gradients present where expected? Is their orientation and color progression correct? (Verifies set_color_by_gradient translation and sheen_direction).
2. Text and LaTeX Rendering:
[ ] Correct Class Usage: Has the appropriate class (Text, Tex, or MathTex) been chosen based on the content?
[ ] Mathematical Accuracy: Are all equations, symbols, and formulas rendered correctly?
[ ] Font and Unicode: Are custom fonts and non-English characters displayed properly? (Verifies correct usage of Pango-based Text).
3. Animation and Motion:
[ ] Animation Smoothness: Do all animations play smoothly and follow the intended path? (Checks for .animate ambiguities).
[ ] Timing and Pacing: Is the run_time and rate_func of each animation preserved and correct?
[ ] Grouped Motion: Do objects grouped in a VGroup move together as a single unit?
4. Updaters and Dynamic Behavior:
[ ] Correctness: Do all dynamic elements (e.g., labels following points, braces resizing) update correctly throughout the animation?
[ ] Performance: Is there any noticeable slowdown or stuttering as the animation progresses? (Checks for updater performance footguns).
5. Code Sanity and Idiomatic Correctness:
[ ] Workflow Artifacts: Have all non-translatable workflow commands (self.embed(), checkpoint_paste) been removed?
[ ] Readability: Does the translated code follow modern ManimCE idioms (e.g., using __init__ kwargs, explicit animation classes, specialized text classes)?

Conclusion

The translation from ManimGL to ManimCE is a complex process whose core challenges lie in recognizing and correctly translating divergent architectural patterns, such as the CONFIG dictionary and the specialized text rendering system.
A significant portion of potential translation errors are visual and silent; they do not produce runtime exceptions but result in incorrect graphical output. 
An LLM tasked with this translation must be trained not merely as a code converter but as an intelligent refactoring tool. It must be guided by the heuristics and patterns outlined in this document to upgrade the code to modern, robust ManimCE idioms while actively identifying and removing non-translatable workflow artifacts. By leveraging this detailed mapping, the translation process can effectively bridge the gap between the two Manims, producing clean, maintainable, and visually correct animations in the community-supported ecosystem.

--------------------------------------------------------------------
ManimGL → ManimCE Conversion Guide
Overview
Focus: Unidirectional conversion only (GL → CE)
Key Principles
ManimCE is stricter in typing and structure
Default behaviors differ significantly
Animation APIs are fundamentally redesigned

1. Import Structure & Setup
ManimGL
ManimCE
Notes
from manimlib.imports import *
from manim import *
Mandatory change
config.background_color = WHITE
config.background_color = WHITE
Identical syntax
self.camera.frame.set_height(10)
self.camera.frame_height = 10
CE uses direct property assignment
ThreeDScene
ThreeDScene
Same name, but camera controls differ


2. Mobject Creation
Basic Shapes
ManimGL
ManimCE
Gotchas
Circle()
Circle()
Identical
Square()
Square()
Identical
Rectangle(height=3, width=4)
Rectangle(height=3, width=4)
Same parameters
Annulus(inner_radius=1, outer_radius=2)
Annulus(inner_radius=1, outer_radius=2)
Identical

Text & LaTeX
ManimGL
ManimCE
Critical Changes
TextMobject("text")
Text("text")
TextMobject removed
Tex("\\sum")
MathTex("\\sum")
Use MathTex for LaTeX math
text.set_color(BLUE)
text.set_color(BLUE)
Same method
text.scale(1.5)
text.scale(1.5)
Identical


3. Animations
Core Animation Mapping
ManimGL
ManimCE
Behavioral Differences
ShowCreation(mobj)
Create(mobj)
ShowCreation deprecated
Write(mobj)
Write(mobj)
Identical but slower by default
FadeIn(mobj)
FadeIn(mobj)
Default opacity curve differs
Transform(A, B)
Transform(A, B)
CE does not auto-remove A
ReplacementTransform(A, B)
Transform(A, B)
CE requires self.remove(A) after
ApplyMethod(mobj.shift, UP)
mobj.animate.shift(UP)
Biggest change: Use .animate
Rotating(mobj)
Rotate(mobj)
Rotating renamed to Rotate

Animation Control
ManimGL
ManimCE
Notes
self.play(anim, run_time=2)
self.play(anim, run_time=2)
Same syntax
self.wait(1)
self.wait(1)
Identical
anim.set_rate_func(smooth)
anim.set_rate_func(smooth)
Same functions


4. Scene Graph & Groups
ManimGL
ManimCE
Pitfalls
Group(A, B)
Group(A, B)
Identical
self.add(mobj)
self.add(mobj)
Same
self.remove(mobj)
self.remove(mobj)
Critical in CE for cleanup
self.bring_to_front(mobj)
self.bring_to_front(mobj)
Same
mobj.copy()
mobj.copy()
Identical


5. Positioning & Layout
ManimGL
ManimCE
Deviations
mobj.next_to(target, DOWN)
mobj.next_to(target, DOWN)
Identical
mobj.shift(UP*2)
mobj.shift(UP*2)
Same
mobj.move_to([x,y,z])
mobj.move_to([x,y,z])
Coordinate system flipped in 3D
mobj.align_to(target, LEFT)
mobj.align_to(target, LEFT)
Identical
mobj.rotate(PI/2)
mobj.rotate(PI/2)
Same


6. Styling & Properties
ManimGL
ManimCE
Notes
mobj.set_color(RED)
mobj.set_color(RED)
Identical
mobj.set_fill(BLUE, opacity=0.5)
mobj.set_fill(BLUE, opacity=0.5)
Same
mobj.set_stroke(width=4)
mobj.set_stroke(width=4)
Identical
mobj.set_opacity(0.3)
mobj.set_opacity(0.3)
Same
mobj.set_gloss(0.8)
Not supported
Remove in CE


7. Advanced Tools
Coordinate Systems
ManimGL
ManimCE
Changes
NumberPlane()
NumberPlane()
Same
Axes()
Axes()
Identical
self.play(mobj.to_edge, UP)
self.play(mobj.animate.to_edge(UP))
Must use .animate

3D Rendering
ManimGL
ManimCE
Key Differences
self.set_camera_orientation(phi=75°)
self.set_camera_orientation(phi=75°)
Same syntax
mobj.rotate(angle, axis=OUT)
mobj.rotate(angle, axis=OUT)
Identical
ThreeDAxes()
ThreeDAxes()
Same
self.begin_ambient_camera_rotation()
self.begin_ambient_camera_rotation()
Same

Updaters
ManimGL
ManimCE
Critical
mobj.add_updater(func)
mobj.add_updater(func)
Identical
self.add(mobj)
self.add(mobj)
Required for updaters
mobj.remove_updater(func)
mobj.remove_updater(func)
Same


8. Common Errors & Solutions
Transform Leaves Ghost Objects
Fix: Always call self.remove(old_mobj) after Transform in CE.
.animate Not Working
Cause: Forgetting to call .animate before methods.
 Correct: mobj.animate.shift(UP), NOT mobj.shift(UP).
Text Rendering Fails
Solution: Replace TextMobject → Text, Tex → MathTex.
3D Camera Jitters
Fix: Add self.renderer.camera.light_source.move_to(3*IN) in CE.
Animation Speed Mismatch
Adjust: Set run_time explicitly (CE defaults are slower).
LaTeX Compilation Errors
Workaround: Use MathTex(r"\LaTeX") with raw strings.

9. Full Scene Translation Example
ManimGL Original:
```
from manimlib.imports import *
class Example(Scene):
    def construct(self):
        circle = Circle()
        square = Square()
        self.play(ShowCreation(circle))
        self.play(ReplacementTransform(circle, square))
        self.play(ApplyMethod(square.shift, UP))
        self.wait()
ManimCE Equivalent:
python
from manim import *
class Example(Scene):
    def construct(self):
        circle = Circle()
        square = Square()
        self.play(Create(circle))                   # ShowCreation → Create
        self.play(Transform(circle, square))        # ReplacementTransform → Transform
        self.remove(circle)                         # Explicit removal required!
        self.play(square.animate.shift(UP))         # ApplyMethod → .animate
        self.wait()

10. Critical Best Practices
Explicit Cleanup: Always remove mobjects after Transform.
Use .animate: Never apply methods directly in animations.
Test Frame-by-Frame: Use -n <frame> flag to debug animations.
Avoid Deprecations:
ShowCreation → Create
TextMobject → Text
Rotating → Rotate
3D Scene Setup: Add light sources manually in CE.

ManimGL to ManimCE Technical Conversion Guide
Core API and Import Mappings
The fundamental difference between ManimGL and ManimCE begins with package naming and import structure. ManimGL uses manimlib as its module name while ManimCE uses manim. This distinction serves as the primary identifier when determining which version a codebase targets.
Import Statement Conversion
ManimGL imports:
from manimlib import *
from manimlib import Scene, Circle, Square
from manimlib.imports import *  # Legacy pattern

ManimCE equivalent:
from manim import *
from manim import Scene, Circle, Square

The import statement serves as the definitive version identifier. Any code containing manimlib targets ManimGL, while manim indicates ManimCE. Legacy code may use from big_ol_pile_of_manim_imports import *, indicating pre-2020 ManimCairo versions.
Text and LaTeX Class Mappings
Text handling represents one of the most significant API changes between versions. ManimGL's text classes underwent complete renaming in ManimCE:
Class name conversions:
TextMobject → Text (plain text rendering)
TexMobject → Tex (LaTeX text)
OldTex → MathTex (mathematical expressions)
TexText → Tex (mixed text/LaTeX)
Critical implementation difference: ManimCE migrated from Cairo text rendering to Pango, fundamentally changing text rendering behavior. The Text class in ManimCE uses Pango by default, with CairoText available as a fallback option.
Text Conversion Examples
ManimGL:
title = TextMobject("Chapter 1: Introduction")
equation = TexMobject(r"E = mc^2")
mixed = TexText("The equation ", "$E=mc^2$", " changed physics")

ManimCE:
title = Text("Chapter 1: Introduction")
equation = MathTex(r"E = mc^2")
mixed = Tex("The equation ", r"$E=mc^2$", " changed physics")

Animation Method Conversions
Animation creation methods underwent significant renaming:
Primary conversions:
ShowCreation → Create
ShowCreationThenFadeOut → Sequential Create and FadeOut
ShowCreationThenDestructionAround → No direct equivalent
The .animate syntax works in both versions but with subtle differences. ManimGL supports both direct method animation (self.play(circle.shift, LEFT)) and the newer syntax, while ManimCE primarily uses .animate.
Animation Pattern Examples
ManimGL:
self.play(ShowCreation(circle))
self.play(circle.shift, LEFT)  # Direct method animation
self.play(circle.animate.shift(RIGHT))  # Animate syntax

ManimCE:
self.play(Create(circle))
self.play(circle.animate.shift(LEFT))  # Preferred syntax
# Direct method animation deprecated

Architectural and Rendering Differences
The fundamental architectural split defines the performance and feature differences between versions:
ManimGL Architecture:
OpenGL-based rendering with GPU acceleration
Real-time preview with interactive controls
Shader pipeline for transformations
Command: manimgl file.py SceneName
Interactive development via self.embed()
ManimCE Architecture:
Cairo-based CPU rendering (default)
Experimental OpenGL renderer (slower than ManimGL)
Offline batch rendering workflow
Command: manim file.py SceneName -pql
Multiple quality presets: -ql (low), -qm (medium), -qh (high), -qk (4K)
Performance implications: ManimGL renders approximately 5x faster than ManimCE's experimental OpenGL renderer. For performance-critical applications, migration may not be advisable.
Color System Differences
ManimCE version 0.18.0 introduced a complete color system rewrite:
ManimGL: Traditional RGB/hex color handling with limited predefined colors
ManimCE: New ManimColor class with extensive color palettes:
Removed colour library dependency
Added hundreds of predefined colors from AS2700, BS381, DVIPSNAMES, SVGNAMES, XKCD, X11
Breaking change: ManimColor.from_hex(hex=...) → ManimColor.from_hex(hex_str=...)
Both versions support standard color constants (RED, BLUE, etc.), but ManimCE offers significantly more options and better color manipulation methods.
Configuration System Migration
Configuration handling differs fundamentally between versions:
ManimGL Configuration:
class MyScene(Scene):
    CONFIG = {
        "camera_config": {"background_color": BLACK},
        "some_parameter": 42
    }

Uses custom_config.yml for global settings.
ManimCE Configuration:
class MyScene(Scene):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.camera.background_color = BLACK

Uses manim.cfg files with comprehensive ManimConfig class:
[CLI]
quality = medium_quality
preview = True
format = mp4

[camera]
background_color = WHITE
frame_height = 8.0

The CONFIG dictionary pattern is deprecated in ManimCE. All configuration should use constructor parameters or configuration files.
Command Line Interface Differences
ManimGL commands:
manimgl example.py SceneName        # Basic rendering
manimgl example.py SceneName -w     # Write to file
manimgl example.py SceneName -o     # Open when done
manimgl example.py SceneName -s     # Save last frame

ManimCE commands:
manim example.py SceneName -pql     # Preview, quality low
manim example.py SceneName -pqh     # Preview, quality high
manim example.py SceneName --format=gif
manim example.py SceneName -a       # Render all scenes

Common Migration Errors and Solutions
Installation Conflicts
Problem: Both packages provide a manim executable, causing PATH conflicts.
Solutions:
Use python -m manim for explicit module calling
Check version with manim --version
Use virtual environments to isolate installations
Consider using manimce executable alias
Module Import Errors
Error: ModuleNotFoundError: No module named 'manimlib'
Solution: Replace all manimlib imports with manim
Class Name Errors
Error: NameError: name 'TextMobject' is not defined
Solution: Update to new class names (Text, MathTex, etc.)
Animation Method Errors
Error: AttributeError: module 'manim' has no attribute 'ShowCreation'
Solution: Replace ShowCreation with Create
Specific Function and Method Mappings
Graph and Axes Methods
ManimGL:
axes = Axes()
graph = axes.get_graph(lambda x: x**2)
label = axes.get_graph_label(graph, "y=x^2")

ManimCE:
axes = Axes()
graph = axes.plot(lambda x: x**2)
label = axes.get_graph_label(graph, "y=x^2")

Camera Operations
ManimGL:
class CameraScene(Scene):
    def construct(self):
        self.camera.frame.shift(UP)
        self.camera.frame.scale(0.5)

ManimCE:
class CameraScene(MovingCameraScene):  # Note inheritance change
    def construct(self):
        self.camera.frame.shift(UP)
        self.camera.frame.scale(0.5)

Text Styling and Parameters
ManimGL:
text = TextMobject("Hello").scale(2)
text.set_color_by_tex("Hello", RED)

ManimCE:
text = Text("Hello", font_size=96)  # Direct font_size parameter
text.set_color(RED)  # Simplified color setting

Version-Specific Breaking Changes
ManimCE Major Breaking Changes
v0.2.0: Removal of CONFIG dictionaries
 v0.3.0: Text rendering migration to Pango
 v0.18.0: Complete color system rewrite
 v0.19.0: Point3D type system changes, Code mobject rewrite
ManimGL Breaking Changes
ManimGL explicitly states "breaking changes between versions are not documented." Experimental features frequently change without notice, making version pinning critical for stability.
Scene Structure Differences
Both versions maintain similar scene structure, but with key differences:
Interactive Features:
ManimGL: self.embed() for interactive IPython terminal
ManimCE: Jupyter notebook integration for interactivity
3D Scenes:
ManimGL: Built-in 3D support with OpenGL
ManimCE: ThreeDScene class for 3D animations
Module Structure Mapping
ManimGL structure:
manimlib/
├── animation/
├── mobject/
├── scene/
├── utils/
└── window.py  # OpenGL window management

ManimCE structure:
manim/
├── animation/
├── camera/
├── mobject/
│   ├── geometry/
│   ├── text/
│   └── types/
├── renderer/
├── scene/
└── utils/
    └── color/

ManimCE's modular structure with separate renderer backends contrasts with ManimGL's tightly integrated OpenGL system.
Coordinate System and Camera Differences
ManimGL: OpenGL-based camera with hardware-accelerated transformations and real-time matrix computations.
ManimCE: Software-based camera system with get_pixel_coordinates() for cartesian mapping and cairo context management.
Migration Strategy Recommendations
When to Migrate
Migrate to ManimCE when:
Stability and documentation are priorities
Working in teams requiring consistent output
Need comprehensive configuration management
Require extensive community support
Migration Checklist
Identify version: Check imports for manimlib vs manim
Update imports: Replace module names systematically
Convert text classes: TextMobject→Text, TexMobject→MathTex
Update animations: ShowCreation→Create
Migrate CONFIG: Convert to constructor parameters
Update CLI commands: Adjust flags and options
Test thoroughly: Verify visual output matches expectations
Handle performance: Consider if slower rendering is acceptable
Critical Gotchas and Footguns
Font rendering differences: Text may appear different due to Pango vs Cairo rendering
Interactive features: No direct equivalent to ManimGL's embed()
Executable conflicts: Both install manim command
Color system changes: Some color manipulations require updates
CONFIG deprecation: Significant refactoring needed for configuration
Method signature changes: Subtle parameter differences in common methods
Version Detection Pattern
# Automatic version detection
try:
    from manimlib import Scene
    USING_MANIMGL = True
except ImportError:
    from manim import Scene
    USING_MANIMGL = False

This pattern enables compatibility layers for codebases supporting both versions.
Conclusion
Converting ManimGL to ManimCE requires systematic updates to imports, class names, animation methods, and configuration patterns. While core animation logic remains similar, architectural differences in rendering, text handling, and performance characteristics make this a non-trivial migration. The stability, documentation, and community support advantages of ManimCE often justify the migration effort, but performance-critical applications may need to remain on ManimGL. This guide provides the technical foundation for accurate automated or manual code conversion between these divergent animation frameworks.

