import numpy as np

from predweem_core import first_peak_index, shift_signal, surface_parameters


def test_shift_signal_delays_without_wraparound():
    values = np.array([0.0, 0.3, 0.2, 0.0])
    assert shift_signal(values, 2).tolist() == [0.0, 0.0, 0.0, 0.3]


def test_first_peak_uses_strict_threshold():
    assert first_peak_index(np.array([0.20, 0.21, 0.10]), 0.20) == 1


def test_surface_parameters_are_monotonic():
    ke0, _ = surface_parameters(0)
    ke100, _ = surface_parameters(100)
    assert ke0 > ke100
