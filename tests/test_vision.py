import numpy as np
import pytest
from encord.objects.bitmask import BitmaskCoordinates
from numpy.typing import NDArray

from encord_agents.core.vision import mask_to_bbox


def _mask_to_coords(mask: NDArray[np.bool_]) -> BitmaskCoordinates:
    return BitmaskCoordinates(mask.astype(bool))


def test_mask_to_bbox_square_image() -> None:
    """Square image, rectangular mask at an asymmetric position."""
    mask = np.zeros((100, 100), dtype=bool)
    mask[20:40, 50:70] = True

    bbox = mask_to_bbox(_mask_to_coords(mask))

    assert bbox.top_left_y == pytest.approx(20 / 100)
    assert bbox.top_left_x == pytest.approx(50 / 100)
    assert bbox.height == pytest.approx(20 / 100)
    assert bbox.width == pytest.approx(20 / 100)


def test_mask_to_bbox_portrait_image() -> None:
    """Portrait image (taller than wide), off-centre rectangular mask."""
    mask = np.zeros((400, 200), dtype=bool)  # h=400, w=200
    mask[100:300, 50:150] = True

    bbox = mask_to_bbox(_mask_to_coords(mask))

    assert bbox.top_left_y == pytest.approx(100 / 400)
    assert bbox.top_left_x == pytest.approx(50 / 200)
    assert bbox.height == pytest.approx(200 / 400)
    assert bbox.width == pytest.approx(100 / 200)


def test_mask_to_bbox_landscape_image() -> None:
    """Landscape image (wider than tall), off-centre rectangular mask."""
    mask = np.zeros((200, 400), dtype=bool)  # h=200, w=400
    mask[50:150, 100:300] = True

    bbox = mask_to_bbox(_mask_to_coords(mask))

    assert bbox.top_left_y == pytest.approx(50 / 200)
    assert bbox.top_left_x == pytest.approx(100 / 400)
    assert bbox.height == pytest.approx(100 / 200)
    assert bbox.width == pytest.approx(200 / 400)


def test_mask_to_bbox_single_pixel() -> None:
    """A single-pixel mask yields a 1x1 bbox at that position."""
    mask = np.zeros((50, 80), dtype=bool)
    mask[10, 30] = True

    bbox = mask_to_bbox(_mask_to_coords(mask))

    assert bbox.top_left_y == pytest.approx(10 / 50)
    assert bbox.top_left_x == pytest.approx(30 / 80)
    assert bbox.height == pytest.approx(1 / 50)
    assert bbox.width == pytest.approx(1 / 80)
