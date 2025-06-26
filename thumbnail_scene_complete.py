# Complete Thumbnail scene with all dependencies inlined

import scipy
import scipy.integrate
import numpy as np
from manimlib.imports import *

# Constants
FREQUENCY_COLOR = RED
USE_ALMOST_FOURIER_BY_DEFAULT = True
NUM_SAMPLES_FOR_FFT = 1000
DEFAULT_COMPLEX_TO_REAL_FUNC = lambda z : z.real

# From fourier.py
def get_fourier_graph(
    axes, time_func, t_min, t_max,
    n_samples = NUM_SAMPLES_FOR_FFT,
    complex_to_real_func = lambda z : z.real,
    color = RED,
    ):
    # N = n_samples
    # T = time_range/n_samples
    time_range = float(t_max - t_min)
    time_step_size = time_range/n_samples
    time_samples = np.vectorize(time_func)(np.linspace(t_min, t_max, n_samples))
    fft_output = np.fft.fft(time_samples)
    frequencies = np.linspace(0.0, n_samples/(2.0*time_range), n_samples//2)
    #  #Cycles per second of fouier_samples[1]
    # (1/time_range)*n_samples
    # freq_step_size = 1./time_range
    graph = VMobject()
    graph.set_points_smoothly([
        axes.coords_to_point(
            x, complex_to_real_func(y)/n_samples,
        )
        for x, y in zip(frequencies, fft_output[:n_samples//2])
    ])
    graph.set_color(color)
    f_min, f_max = [
        axes.x_axis.point_to_number(graph.get_points()[i])
        for i in (0, -1)
    ]
    graph.underlying_function = lambda f : axes.y_axis.point_to_number(
        graph.point_from_proportion((f - f_min)/(f_max - f_min))
    )
    return graph

# From uncertainty.py
class GaussianDistributionWrapper(Line):
    """
    This is meant to encode a 2d normal distribution as
    a mobject (so as to be able to have it be interpolated
    during animations).  It is a line whose center is the mean
    mu of a distribution, and whose radial vector (center to end)
    is the distribution's standard deviation
    """
    CONFIG = {
        "stroke_width" : 0,
        "mu" : ORIGIN,
        "sigma" : RIGHT,
    }
    def __init__(self, **kwargs):
        Line.__init__(self, ORIGIN, RIGHT, **kwargs)
        self.change_parameters(self.mu, self.sigma)

    def change_parameters(self, mu = None, sigma = None):
        curr_mu, curr_sigma = self.get_parameters()
        mu = mu if mu is not None else curr_mu
        sigma = sigma if sigma is not None else curr_sigma
        self.put_start_and_end_on(mu - sigma, mu + sigma)
        return self

    def get_parameters(self):
        """ Return mu_x, mu_y, sigma_x, sigma_y"""
        center, end = self.get_center(), self.get_end()
        return center, end-center

    def get_random_points(self, size = 1):
        mu, sigma = self.get_parameters()
        return np.array([
            np.array([
                np.random.normal(mu_coord, sigma_coord)
                for mu_coord, sigma_coord in zip(mu, sigma)
            ])
            for x in range(size)
        ])

class ProbabalisticMobjectCloud(ContinualAnimation):
    CONFIG = {
        "fill_opacity" : 0.25,
        "n_copies" : 100,
        "gaussian_distribution_wrapper_config" : {},
        "time_per_change" : 1./60,
        "start_up_time" : 0,
    }
    def __init__(self, prototype, **kwargs):
        digest_config(self, kwargs)
        fill_opacity = self.fill_opacity or prototype.get_fill_opacity()
        if "mu" not in self.gaussian_distribution_wrapper_config:
            self.gaussian_distribution_wrapper_config["mu"] = prototype.get_center()
        self.gaussian_distribution_wrapper = GaussianDistributionWrapper(
            **self.gaussian_distribution_wrapper_config
        )
        self.time_since_last_change = np.inf
        group = VGroup(*[
            prototype.copy().set_fill(opacity = fill_opacity)
            for x in range(self.n_copies)
        ])
        ContinualAnimation.__init__(self, group, **kwargs)
        self.update_mobject(0)

    def update_mobject(self, dt):
        self.time_since_last_change += dt
        if self.time_since_last_change < self.time_per_change:
            return
        self.time_since_last_change = 0

        group = self.mobject
        points = self.gaussian_distribution_wrapper.get_random_points(len(group))
        for mob, point in zip(group, points):
            self.update_mobject_by_point(mob, point)
        return self

    def update_mobject_by_point(self, mobject, point):
        mobject.move_to(point)
        return self

class ProbabalisticDotCloud(ProbabalisticMobjectCloud):
    CONFIG = {
        "color" : BLUE,
    }
    def __init__(self, **kwargs):
        digest_config(self, kwargs)
        dot = Dot(color = self.color)
        ProbabalisticMobjectCloud.__init__(self, dot)

# The actual Thumbnail scene
class Thumbnail(Scene):
    def construct(self):
        uncertainty_principle = OldTexText("Uncertainty \\\\", "principle")
        uncertainty_principle[1].shift(SMALL_BUFF*UP)
        quantum = OldTexText("Quantum")
        VGroup(uncertainty_principle, quantum).scale(2.5)
        uncertainty_principle.to_edge(UP, MED_LARGE_BUFF)
        quantum.to_edge(DOWN, MED_LARGE_BUFF)

        arrow = OldTex("\\Downarrow")
        arrow.scale(4)
        arrow.move_to(Line(
            uncertainty_principle.get_bottom(),
            quantum.get_top(),
        ))

        cross = Cross(arrow)
        cross.set_stroke(RED, 20)

        is_word, not_word = is_not = OldTexText("is", "\\emph{NOT}")
        is_not.scale(3)
        is_word.move_to(arrow)
        # is_word.shift(0.6*UP)
        not_word.set_color(RED)
        not_word.set_stroke(RED, 3)
        not_word.rotate(10*DEGREES, about_edge = DOWN+LEFT)
        not_word.next_to(is_word, DOWN, 0.1*SMALL_BUFF)

        dot_cloud = ProbabalisticDotCloud(
            n_copies = 1000,
        )
        dot_gdw = dot_cloud.gaussian_distribution_wrapper
        # dot_gdw.rotate(3*DEGREES)
        dot_gdw.rotate(25*DEGREES)
        # dot_gdw.scale(2)
        dot_gdw.scale(2)
        # dot_gdw.move_to(quantum.get_bottom()+SMALL_BUFF*DOWN)
        dot_gdw.move_to(quantum)

        def get_func(a):
            return lambda t : 0.5*np.exp(-a*t**2)*np.cos(TAU*t)
        axes = Axes(
            x_min = -6, x_max = 6,
            x_axis_config = {"unit_size" : 0.25}
        )
        graphs = VGroup(*[
            axes.get_graph(get_func(a))
            for a in (10, 3, 1, 0.3, 0.1,)
        ])
        graphs.arrange(DOWN, buff = 0.6)
        graphs.to_corner(UP+LEFT)
        graphs.set_color_by_gradient(BLUE_B, BLUE_D)

        frequency_axes = Axes(
            x_min = 0, x_max = 2,
            x_axis_config = {"unit_size" : 1}
        )
        fourier_graphs = VGroup(*[
            get_fourier_graph(
                frequency_axes, graph.underlying_function,
                t_min = -10, t_max = 10,
            )
            for graph in graphs
        ])
        for graph, fourier_graph in zip(graphs, fourier_graphs):
            fourier_graph.pointwise_become_partial(fourier_graph, 0.02, 0.06)
            fourier_graph.scale(3)
            fourier_graph.stretch(3, 1)
            fourier_graph.move_to(graph)
            fourier_graph.to_edge(RIGHT)

        self.add(graphs, fourier_graphs)
        self.add(dot_cloud)
        self.add(
            uncertainty_principle, quantum,
        )
        self.add(arrow, cross)