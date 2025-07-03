from manim import *
import numpy as np
import itertools as it

# Color definitions to match original
X_COLOR = GREEN
Y_COLOR = RED
Z_COLOR = BLUE
OUTPUT_COLOR = YELLOW
INPUT_COLOR = MAROON_B

OUTPUT_DIRECTORY = "eola2/cramer"

# Helper class for integer matrices
class IntegerMatrix(Matrix):
    def __init__(self, matrix, **kwargs):
        # Convert to integer strings
        if isinstance(matrix, (list, np.ndarray)):
            matrix = np.array(matrix)
            # Ensure it's 2D
            if matrix.ndim == 1:
                matrix = matrix.reshape(-1, 1)
            # Create string representation of integers
            str_matrix = [[str(int(x)) for x in row] for row in matrix]
            super().__init__(str_matrix, **kwargs)
        else:
            super().__init__(matrix, **kwargs)
    
    def set_column_colors(self, *colors):
        """Set colors for each column"""
        entries = self.get_entries()
        n_rows = len(self.mob_matrix)
        n_cols = len(self.mob_matrix[0]) if n_rows > 0 else 0
        
        for j, color in enumerate(colors[:n_cols]):
            for i in range(n_rows):
                entries[i * n_cols + j].set_color(color)


def get_cramer_matrix(matrix, output_vect, index=0):
    """
    The inputs matrix and output_vect should be Matrix mobjects
    """
    # Get the matrix entries properly
    if hasattr(matrix, 'get_entries'):
        matrix_array = []
        entries = matrix.get_entries()
        n = int(np.sqrt(len(entries)))
        for i in range(n):
            row = []
            for j in range(n):
                entry = entries[i * n + j]
                # Extract the numeric value from the mobject
                if hasattr(entry, 'get_tex_string'):
                    val = float(entry.get_tex_string())
                else:
                    val = float(entry.text)
                row.append(val)
            matrix_array.append(row)
        new_matrix = np.array(matrix_array)
    else:
        new_matrix = np.array(matrix)
    
    # Get output vector entries
    if hasattr(output_vect, 'get_entries'):
        out_entries = output_vect.get_entries()
        for i in range(len(out_entries)):
            if hasattr(out_entries[i], 'get_tex_string'):
                val = float(out_entries[i].get_tex_string())
            else:
                val = float(out_entries[i].text)
            new_matrix[i, index] = val
    else:
        new_matrix[:, index] = output_vect[:, 0] if output_vect.ndim > 1 else output_vect
    
    # Create a new Matrix mobject
    result = IntegerMatrix(new_matrix)
    result.scale_to_fit_height(matrix.height)
    return result


def get_det_text(matrix, initial_scale_factor=1):
    """Create determinant notation for a matrix"""
    det_text = MathTex(r"\det")
    det_text.scale(initial_scale_factor)
    # Create a copy of the matrix for the determinant
    if hasattr(matrix, 'copy'):
        matrix_copy = matrix.copy()
    else:
        matrix_copy = matrix
    
    # Position det text to the left of matrix
    group = VGroup(det_text, matrix_copy)
    group.arrange(RIGHT, buff=SMALL_BUFF)
    
    return group


class LinearSystem(VGroup):
    def __init__(self, matrix=None, output_vect=None, 
                 dimensions=3, min_int=-9, max_int=10, 
                 height=4, **kwargs):
        super().__init__(**kwargs)
        
        if matrix is None:
            dim = dimensions
            matrix = np.random.randint(min_int, max_int, size=(dim, dim))
        else:
            dim = len(matrix)
            
        self.matrix_mobject = IntegerMatrix(matrix)
        self.equals = MathTex("=")
        self.equals.scale(1.5)

        colors = [X_COLOR, Y_COLOR, Z_COLOR][:dim]
        chars = ["x", "y", "z"][:dim]
        self.input_vect_mob = Matrix([[c] for c in chars])
        for elem, color in zip(self.input_vect_mob.get_entries(), colors):
            elem.set_color(color)

        if output_vect is None:
            output_vect = np.random.randint(min_int, max_int, size=(dim, 1))
        # Ensure output_vect is 2D (column vector)
        if isinstance(output_vect, list):
            output_vect = [[x] for x in output_vect]
        elif output_vect.ndim == 1:
            output_vect = output_vect.reshape(-1, 1)
        self.output_vect_mob = IntegerMatrix(output_vect)
        self.output_vect_mob.get_entries().set_color(OUTPUT_COLOR)

        for mob in [self.matrix_mobject, self.input_vect_mob, self.output_vect_mob]:
            mob.scale_to_fit_height(height)

        self.add(
            self.matrix_mobject,
            self.input_vect_mob,
            self.equals,
            self.output_vect_mob,
        )
        self.arrange(RIGHT, buff=SMALL_BUFF)


# Custom teacher/students scene replacement
class TeacherStudentsScene(Scene):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.teacher = None
        self.students = []
        
    def construct(self):
        # Create simple representations
        teacher_dot = Dot(color=GREY).scale(2)
        teacher_dot.to_edge(RIGHT).shift(DOWN)
        teacher_label = Text("Teacher", font_size=24).next_to(teacher_dot, DOWN)
        
        student_dots = VGroup(*[Dot(color=BLUE).scale(1.5) for _ in range(3)])
        student_dots.arrange(RIGHT, buff=1)
        student_dots.to_edge(LEFT).shift(DOWN)
        
        self.teacher = VGroup(teacher_dot, teacher_label)
        self.students = student_dots
        
        self.add(self.teacher, self.students)
        
    def teacher_says(self, text, **kwargs):
        bubble = RoundedRectangle(width=4, height=2, corner_radius=0.5)
        bubble.next_to(self.teacher, UP)
        bubble_text = Text(text, font_size=24).move_to(bubble)
        
        self.play(Create(bubble), Write(bubble_text))
    def set_input_vect_label_position(self, input_vect_mob, input_vect_label):
        # Simple positioning for the label
        input_vect_label.next_to(input_vect_mob.get_end(), RIGHT, buff=SMALL_BUFF)
        return input_vect_label
        return VGroup(bubble, bubble_text)
        
    def student_says(self, text, index=0, **kwargs):
        bubble = RoundedRectangle(width=4, height=2, corner_radius=0.5)
        bubble.next_to(self.students[index], UP)
        bubble_text = Text(text, font_size=24).move_to(bubble)
        
        self.play(Create(bubble), Write(bubble_text))
        self.wait(2)
        return VGroup(bubble, bubble_text)


# Linear transformation scene replacement
class LinearTransformationScene(Scene):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.matrix = [[1, 0], [0, 1]]
        self.background_plane = None
        self.plane = None
        self.basis_vectors = []
        self.transformable_mobjects = []
        self.foreground_mobjects = []
        
    def setup(self):
        # Create grid
        self.background_plane = NumberPlane(
            x_range=[-10, 10, 1],
            y_range=[-10, 10, 1],
            background_line_style={
                "stroke_color": GREY,
                "stroke_width": 1,
                "stroke_opacity": 0.3,
            }
        )
        self.plane = NumberPlane(
            x_range=[-10, 10, 1],
            y_range=[-10, 10, 1],
            axis_config={"stroke_color": GREY},
            background_line_style={
                "stroke_color": BLUE_D,
                "stroke_width": 1,
            }
        )
        self.add(self.background_plane, self.plane)
        
        # Create basis vectors
        self.basis_vectors = VGroup(
            Arrow(ORIGIN, RIGHT, color=X_COLOR, buff=0),
            Arrow(ORIGIN, UP, color=Y_COLOR, buff=0)
        )
        self.add(self.basis_vectors)
        
    def add_vector(self, vector, color=YELLOW, animate=True, **kwargs):
        vect = Arrow(ORIGIN, 
                    self.plane.c2p(vector[0], vector[1], 0),
                    color=color, buff=0, **kwargs)
        if animate:
            self.play(GrowArrow(vect))
        else:
            self.add(vect)
        return vect
    
    def get_vector(self, vector, color=YELLOW, **kwargs):
        """Create a vector without animating it"""
        return Arrow(ORIGIN, 
                    self.plane.c2p(vector[0], vector[1], 0),
                    color=color, buff=0, **kwargs)
        
    def apply_matrix(self, matrix, **kwargs):
        if isinstance(matrix, list):
            matrix = np.array(matrix)
        elif not isinstance(matrix, np.ndarray):
            matrix = np.array(matrix)
            
        def mat_func(p):
            x, y = self.plane.p2c(p)[:2]
            result = matrix @ np.array([x, y])
            return self.plane.c2p(result[0], result[1], 0)
            
        transformations = []
        for mob in [self.plane] + self.transformable_mobjects:
            transformations.append(ApplyPointwiseFunction(mat_func, mob))
            
        # Transform basis vectors
        new_i = matrix @ np.array([1, 0])
        new_j = matrix @ np.array([0, 1])
        transformations.extend([
            self.basis_vectors[0].animate.put_start_and_end_on(
                ORIGIN, self.plane.c2p(new_i[0], new_i[1], 0)
            ),
            self.basis_vectors[1].animate.put_start_and_end_on(
                ORIGIN, self.plane.c2p(new_j[0], new_j[1], 0)
            )
        ])
        
        self.play(*transformations, **kwargs)
        
    def apply_inverse(self, matrix, **kwargs):
        if isinstance(matrix, list):
            matrix = np.array(matrix)
        elif not isinstance(matrix, np.ndarray):
            matrix = np.array(matrix)
        self.apply_matrix(np.linalg.inv(matrix), **kwargs)
        
    def get_unit_square(self, **kwargs):
        square = Square(side_length=1, **kwargs)
        square.move_to(self.plane.c2p(0.5, 0.5, 0))
        square.set_fill(YELLOW, opacity=0.5)
        square.set_stroke(YELLOW, width=2)
        return square
        
    def add_transformable_mobject(self, mob):
        self.transformable_mobjects.append(mob)
        
    def add_foreground_mobject(self, *mobs):
        self.foreground_mobjects.extend(mobs)
        
    def add_foreground_mobjects(self, *mobs):
        self.add_foreground_mobject(*mobs)
        
    def get_vector_label(self, vector, label, **kwargs):
        label_mob = MathTex(label)
        label_mob.next_to(vector.get_end(), **kwargs)
        return label_mob


# Scene implementations
class CramerOpeningQuote(Scene):
    def construct(self):
        quote = Text("Computers are useless. They\ncan only give you answers.", 
                    font_size=36)
        author = Text("- Pablo Picasso", font_size=24)
        author.next_to(quote, DOWN, buff=0.5)
        
        self.play(Write(quote))
        self.wait()
        self.play(FadeIn(author))
        self.wait(2)


class LeaveItToComputers(TeacherStudentsScene):
    def construct(self):
        super().construct()
        
        system = LinearSystem(height=3)
        system.next_to(self.students, UP)
        
        self.play(Write(system))
        self.wait()
        
        bubble = self.teacher_says("Let the computer\nhandle it")
        self.wait(2)
        
        # Show Cramer's rule
        cramer_text = Text("Cramer's Rule", font_size=36)
        cramer_text.to_edge(UP)
        
        self.play(
            FadeOut(bubble),
            system.animate.scale(0.7).to_corner(UL),
            Write(cramer_text)
        )
        self.wait(2)


class PrerequisiteKnowledge(Scene):
    def construct(self):
        title = Text("Prerequisites", font_size=48)
        title.to_edge(UP)
        
        h_line = Line(LEFT, RIGHT).scale(5)
        h_line.next_to(title, DOWN)
        
        topics = VGroup(
            Text("• Linear transformations", font_size=32),
            Text("• Matrix multiplication", font_size=32),
            Text("• Determinants", font_size=32),
        )
        topics.arrange(DOWN, aligned_edge=LEFT, buff=0.5)
        topics.next_to(h_line, DOWN, buff=0.5)
        
        self.play(Write(title), Create(h_line))
        for topic in topics:
            self.play(Write(topic))
            self.wait(0.5)
        self.wait(2)


class SetupSimpleSystemOfEquations(LinearTransformationScene):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.matrix = [[3, 2], [-1, 2]]
        self.output_vect = [-4, -2]
        self.array_scale_factor = 0.75
        
    def construct(self):
        self.setup()
        self.introduce_system()
        self.from_system_to_matrix()
        self.show_geometry()
        
    def introduce_system(self):
        # Create system of equations
        eq1 = MathTex("3x", "+", "2y", "=", "-4")
        eq1[0].set_color(X_COLOR)
        eq1[2].set_color(Y_COLOR)
        eq1[4].set_color(OUTPUT_COLOR)
        
        eq2 = MathTex("-x", "+", "2y", "=", "-2")
        eq2[0].set_color(X_COLOR)
        eq2[2].set_color(Y_COLOR)
        eq2[4].set_color(OUTPUT_COLOR)
        
        system = VGroup(eq1, eq2)
        system.arrange(DOWN, aligned_edge=RIGHT)
        system.to_edge(UP)
        
        self.system = system
        self.play(Write(system))
        self.wait()
        
    def from_system_to_matrix(self):
        # Convert to matrix form
        matrix_system = LinearSystem(
            self.matrix, self.output_vect, height=2
        )
        matrix_system.center()
        
        self.play(
            self.system.animate.scale(0.7).to_corner(UL),
            FadeIn(matrix_system)
        )
        self.wait()
        
        # Move to corner
        corner_rect = SurroundingRectangle(matrix_system, buff=MED_SMALL_BUFF)
        corner_rect.set_fill(BLACK, opacity=0.8)
        corner_rect.set_stroke(width=0)
        
        self.play(
            FadeIn(corner_rect),
            matrix_system.animate.scale(0.8).to_corner(UL),
            corner_rect.animate.to_corner(UL, buff=0)
        )
        
        self.matrix_system = matrix_system
        self.corner_rect = corner_rect
        
    def show_geometry(self):
        # Convert matrix if needed
        if isinstance(self.matrix, list):
            matrix = np.array(self.matrix)
        else:
            matrix = self.matrix
            
        # Show output vector
        output_vect_mob = self.add_vector(self.output_vect, color=OUTPUT_COLOR, animate=False)
        output_label = IntegerMatrix([[x] for x in self.output_vect])
        output_label.scale(0.7)
        output_label.next_to(output_vect_mob.get_end(), LEFT)
        output_label.get_entries().set_color(OUTPUT_COLOR)
        
        self.play(GrowArrow(output_vect_mob), Write(output_label))
        self.wait()
        
        # Show input vector (solution)
        input_vect = np.linalg.solve(matrix, self.output_vect)
        input_vect_mob = self.add_vector(input_vect, color=INPUT_COLOR, animate=False)
        q_marks = Text("????", color=INPUT_COLOR)
        q_marks.next_to(input_vect_mob.get_end(), DOWN)
        
        # Apply transformation
        self.add_transformable_mobject(input_vect_mob)
        self.play(GrowArrow(input_vect_mob), Write(q_marks))
        self.wait()
        
        # Show column vectors
        column_mobs = VGroup()
        for i, vect in enumerate([DOWN, LEFT]):
            column_mob = IntegerMatrix([[x] for x in matrix[:, i]])
            column_mob.get_entries().set_color([X_COLOR, Y_COLOR][i])
            column_mob.scale(self.array_scale_factor)
            column_mob.next_to(
                self.get_vector(matrix[:, i]).get_end(), vect,
                buff=SMALL_BUFF
            )
            column_mobs.add(column_mob)
        
        self.apply_matrix(matrix)
        self.wait(2)


class ShowZeroDeterminantCase(LinearTransformationScene):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.matrix = [[3, -2.0], [1, -2.0/3]]
        
    def construct(self):
        self.setup()
        self.add_equation()
        self.show_det_zero()
        
    def add_equation(self):
        equation = MathTex("A", r"\vec{x}", "=", r"\vec{v}")
        equation[1].set_color(INPUT_COLOR)
        equation[3].set_color(OUTPUT_COLOR)
        equation.to_corner(UL)
        self.add(equation)
        self.equation = equation
        
    def show_det_zero(self):
        # Show that determinant is zero
        det_equation = MathTex(r"\det(", "A", ")", "=", "0")
        det_equation.next_to(self.equation, DOWN)
        
        self.play(Write(det_equation))
        self.wait()
        
        # Apply transformation
        self.apply_matrix(self.matrix)
        self.wait()
        
        # Show that some vectors can't be reached
        vect_off_span = self.add_vector([1, 2], color=OUTPUT_COLOR)
        label = Text("No input lands here", font_size=24)
        label.next_to(vect_off_span.get_end(), UP)
        
        self.play(Write(label))
        self.wait(2)


class NonZeroDeterminantCase(ShowZeroDeterminantCase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.matrix = [[3, 2], [-1, 2]]
        self.output_vect = [-4, -2]
        
    def show_det_zero(self):
        # Show that determinant is non-zero
        det_equation = MathTex(r"\det(", "A", ")", r"\neq", "0")
        det_equation.next_to(self.equation, DOWN)
        
        self.play(Write(det_equation))
        self.wait()
        
        # Apply transformation
        self.apply_matrix(self.matrix)
        self.wait()
        
        # Show unique solution
        input_vect = np.linalg.solve(self.matrix, self.output_vect)
        output_vect_mob = self.add_vector(self.output_vect, color=OUTPUT_COLOR)
        
        self.apply_inverse(self.matrix)
        input_vect_mob = self.add_vector(input_vect, color=INPUT_COLOR)
        
        self.wait(2)


class TransformingAreasYCoord(LinearTransformationScene):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.index = 1  # 0 for x-coordinate, 1 for y-coordinate
        self.matrix = [[2, -1], [0, 1]]
        self.input_vect = [3, 2]
        self.array_scale_factor = 0.75
        
    def construct(self):
        self.setup()
        self.init_matrix()
        self.show_coord_parallelogram()
        self.transform_space()
        self.solve_for_coord()
        
    def init_matrix(self):
        self.matrix = np.array(self.matrix)
        
    def show_coord_parallelogram(self):
        # Show input vector and parallelogram
        input_vect_mob = self.add_vector(self.input_vect, color=INPUT_COLOR)
        input_label = Matrix([["x"], ["y"]])
        input_label.scale(0.7)
        input_label.next_to(input_vect_mob.get_end(), RIGHT)
        
        # Create parallelogram using the helper method
        parallelogram = self.get_input_parallelogram(input_vect_mob)
        
        self.play(Write(input_label), Create(parallelogram))
        self.wait()
        
        # Show area
        area_text = MathTex(r"\text{Area} = ", ["x", "y"][self.index])
        area_text[1].set_color([X_COLOR, Y_COLOR][self.index])
        area_text.next_to(parallelogram, DR)
        
        self.play(Write(area_text))
        self.wait()
        
        self.input_parallelogram = parallelogram
        self.area_text = area_text
        self.input_vect_mob = input_vect_mob
        self.input_label = input_label
        
    def transform_space(self):
        # Apply transformation
        self.add_transformable_mobject(self.input_parallelogram)
        self.add_transformable_mobject(self.input_vect_mob)
        
        # Show matrix
        matrix_mob = IntegerMatrix(self.matrix)
        matrix_mob.set_column_colors(X_COLOR, Y_COLOR)
        matrix_mob.to_corner(UL)
        
        # Create column mobs before using them
        self.column_mobs = VGroup()
        for i, vect in enumerate([DOWN, LEFT]):
            column_mob = IntegerMatrix([[x] for x in self.matrix[:, i]])
            column_mob.get_entries().set_color([X_COLOR, Y_COLOR][i])
            column_mob.scale(self.array_scale_factor)
            self.column_mobs.add(column_mob)
        
        self.play(Write(matrix_mob))
        self.wait()
        
        # Apply transformation
        self.play(
            self.area_text.animate.shift(2*DOWN),
            self.input_label.animate.shift(2*DOWN)
        )
        
        self.apply_matrix(self.matrix)
        
        # Update area text
        new_area_text = MathTex(
            r"\text{Area} = \det(A) \cdot ", 
            ["x", "y"][self.index]
        )
        new_area_text[1].set_color([X_COLOR, Y_COLOR][self.index])
        new_area_text.move_to(self.area_text)
        
        self.play(Transform(self.area_text, new_area_text))
        self.wait()
        
        self.matrix_mob = matrix_mob
        
    def solve_for_coord(self):
        # Show Cramer's rule formula
        coord = ["x", "y"][self.index]
        formula = MathTex(
            coord, "=", 
            r"\frac{\text{Area}}{\det(A)}"
        )
        formula[0].set_color([X_COLOR, Y_COLOR][self.index])
        formula.to_edge(DOWN)
        
        # Show the output vector
        output_vect = np.dot(self.matrix, self.input_vect)
        output_vect_label = IntegerMatrix([[x] for x in output_vect])
        output_vect_label.get_entries().set_color(OUTPUT_COLOR)
        output_vect_label.scale(self.array_scale_factor)
        self.set_input_vect_label_position(self.input_vect_mob, output_vect_label)
        
        self.play(Write(formula))
        self.wait(2)
        
    def set_input_vect_label_position(self, input_vect_mob, input_vect_label):
        # Simple positioning for the label
        input_vect_label.next_to(input_vect_mob.get_end(), RIGHT, buff=SMALL_BUFF)
        return input_vect_label
    
    def get_input_parallelogram(self, input_vect_mob):
        """Create parallelogram based on input vector"""
        input_vect = np.array(self.plane.p2c(input_vect_mob.get_end())[:2])
        
        # Create transformation matrix
        square_to_para = np.identity(2)
        square_to_para[:, self.index] = input_vect
        
        # Create parallelogram points
        para_points = []
        for point in [ORIGIN, RIGHT, RIGHT+UP, UP]:
            new_point = square_to_para @ np.array([point[0], point[1]])
            para_points.append(self.plane.c2p(new_point[0], new_point[1], 0))
            
        parallelogram = Polygon(*para_points)
        parallelogram.set_fill(YELLOW, opacity=0.5)
        parallelogram.set_stroke(YELLOW, width=2)
        
        if input_vect[self.index] < 0:
            parallelogram.set_color(GOLD)
            
        return parallelogram
    
    def get_parallelogram_braces(self, parallelogram):
        """Create braces for the parallelogram"""
        braces = VGroup(
            Brace(parallelogram, DOWN, buff=SMALL_BUFF),
            Brace(parallelogram, RIGHT, buff=SMALL_BUFF)
        )
        
        for brace, tex, color in zip(braces, "xy", [X_COLOR, Y_COLOR]):
            label = MathTex(tex)
            label.set_color(color)
            label.next_to(brace, brace.direction, buff=SMALL_BUFF)
            brace.label = label
            
        return braces


class TransformingAreasXCoord(TransformingAreasYCoord):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.index = 0


class WriteCramersRule(Scene):
    def construct(self):
        title = Text("Cramer's Rule", font_size=60)
        title.set_color(YELLOW)
        
        # Show the rule
        rule = MathTex(
            r"x_i = \frac{\det(A_i)}{\det(A)}"
        )
        rule.scale(1.5)
        rule.next_to(title, DOWN, buff=1)
        
        explanation = Text(
            "Where A_i is matrix A with column i\nreplaced by the output vector",
            font_size=24
        )
        explanation.next_to(rule, DOWN, buff=1)
        
        self.play(Write(title))
        self.wait()
        self.play(Write(rule))
        self.wait()
        self.play(FadeIn(explanation))
        self.wait(3)


class ThinkItThroughYourself(TeacherStudentsScene):
    def construct(self):
        super().construct()
        self.teacher_says("Try thinking\nit through!")
        self.wait(3)


# Thumbnail scene
class Thumbnail(Scene):
    def construct(self):
        # Create grid
        plane = NumberPlane(
            x_range=[-8, 8, 1],
            y_range=[-5, 5, 1],
            background_line_style={
                "stroke_color": BLUE_D,
                "stroke_width": 2,
                "stroke_opacity": 0.5,
            }
        )
        self.add(plane)
        
        # Add title
        title = Text("Cramer's Rule", font_size=72)
        title.set_color(YELLOW)
        title.set_stroke(BLACK, width=8, background=True)
        title.to_edge(UP)
        
        # Add some visual elements
        matrix = Matrix([[2, -1], [1, 2]])
        matrix.scale(1.5)
        matrix.shift(3*LEFT)
        
        arrow = Arrow(LEFT, RIGHT, color=WHITE)
        arrow.next_to(matrix, RIGHT)
        
        formula = MathTex(r"x = \frac{\det(A_x)}{\det(A)}")
        formula.scale(1.5)
        formula.next_to(arrow, RIGHT)
        
        self.add(title, matrix, arrow, formula)
