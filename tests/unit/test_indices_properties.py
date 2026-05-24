"""Property-based tests for spectral indices using Hypothesis."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import array_shapes, arrays

from terranova.core.timeseries.indices import nbr, ndmi, ndsi, ndvi, ndwi

pytestmark = pytest.mark.unit

# Plausible surface-reflectance range for S2 / Landsat scaled to [0, 1].
_refl = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
_shape = array_shapes(min_dims=2, max_dims=2, min_side=1, max_side=16)


@st.composite
def _pair_same_shape(draw, shape_strategy=_shape):  # type: ignore[no-untyped-def]
    """Draw two float32 arrays sharing one randomly-chosen shape."""
    shape = draw(shape_strategy)
    a = draw(arrays(np.float32, shape, elements=_refl))
    b = draw(arrays(np.float32, shape, elements=_refl))
    return a, b


@given(pair=_pair_same_shape())
@settings(max_examples=50, deadline=None)
def test_ndvi_in_range(pair) -> None:  # type: ignore[no-untyped-def]
    """NDVI is bounded to [-1, 1] when both inputs are non-negative."""
    a, b = pair
    out = ndvi(a, b)
    finite = np.isfinite(out)
    assert np.all(out[finite] >= -1.0 - 1e-6)
    assert np.all(out[finite] <= 1.0 + 1e-6)


@given(pair=_pair_same_shape())
@settings(max_examples=50, deadline=None)
def test_ndvi_antisymmetry(pair) -> None:  # type: ignore[no-untyped-def]
    """Swapping the operands flips the sign."""
    a, b = pair
    forward = ndvi(a, b)
    reverse = ndvi(b, a)
    finite = np.isfinite(forward) & np.isfinite(reverse)
    np.testing.assert_allclose(forward[finite], -reverse[finite], atol=1e-6)


@pytest.mark.parametrize("fn", [ndvi, ndwi, ndmi, nbr, ndsi])
@given(arr=arrays(np.float32, (8, 8), elements=_refl))
@settings(max_examples=30, deadline=None)
def test_self_difference_is_zero(fn, arr: np.ndarray) -> None:  # type: ignore[no-untyped-def]
    """Any normalised-difference index applied to a==b is 0 (or NaN at zero)."""
    out = fn(arr, arr)
    finite = np.isfinite(out)
    assert np.all(out[finite] == 0.0)


@given(pair=_pair_same_shape())
@settings(max_examples=30, deadline=None)
def test_zero_sum_is_nan(pair) -> None:  # type: ignore[no-untyped-def]
    """Where a+b == 0 the output is NaN (no spurious zero)."""
    a, b = pair
    out = ndvi(a, b)
    zero_sum = (a + b) == 0
    assert np.all(np.isnan(out[zero_sum]))
