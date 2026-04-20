import numpy as np
import pytest
from encord.objects.bitmask import BitmaskCoordinates

from encord_agents.core.vision import mask_to_bbox


def _mask_to_coords(mask: np.ndarray) -> BitmaskCoordinates:
    return BitmaskCoordinates(mask.astype(bool))


def test_mask_to_bbox_square_image() -> None:
    """Square image, rectangular mask at an asymmetric position."""
    mask = np.zeros((100, 100), dtype=bool)
    mask[20:40, 50:70] = True

    bbox = mask_to_bbox(_mask_to_coords(mask))

    assert bbox.top_left_x == pytest.approx(50 / 100)
    assert bbox.top_left_y == pytest.approx(20 / 100)
    assert bbox.width == pytest.approx(20 / 100)
    assert bbox.height == pytest.approx(20 / 100)


def test_mask_to_bbox_portrait_image() -> None:
    """Portrait image (taller than wide), off-centre rectangular mask."""
    mask = np.zeros((400, 200), dtype=bool)  # h=400, w=200
    mask[100:300, 50:150] = True

    bbox = mask_to_bbox(_mask_to_coords(mask))

    assert bbox.top_left_x == pytest.approx(50 / 200)
    assert bbox.top_left_y == pytest.approx(100 / 400)
    assert bbox.width == pytest.approx(100 / 200)
    assert bbox.height == pytest.approx(200 / 400)


def test_mask_to_bbox_landscape_image() -> None:
    """Landscape image (wider than tall), off-centre rectangular mask."""
    mask = np.zeros((200, 400), dtype=bool)  # h=200, w=400
    mask[50:150, 100:300] = True

    bbox = mask_to_bbox(_mask_to_coords(mask))

    assert bbox.top_left_x == pytest.approx(100 / 400)
    assert bbox.top_left_y == pytest.approx(50 / 200)
    assert bbox.width == pytest.approx(200 / 400)
    assert bbox.height == pytest.approx(100 / 200)


def test_mask_to_bbox_single_pixel() -> None:
    """A single-pixel mask yields a 1x1 bbox at that position."""
    mask = np.zeros((50, 80), dtype=bool)
    mask[10, 30] = True

    bbox = mask_to_bbox(_mask_to_coords(mask))

    assert bbox.top_left_x == pytest.approx(30 / 80)
    assert bbox.top_left_y == pytest.approx(10 / 50)
    assert bbox.width == pytest.approx(1 / 80)
    assert bbox.height == pytest.approx(1 / 50)


def test_mask_to_bbox_mask_at_origin() -> None:
    """Mask whose top-left pixel is at (0, 0)."""
    mask = np.zeros((100, 100), dtype=bool)
    mask[0:30, 0:40] = True

    bbox = mask_to_bbox(_mask_to_coords(mask))

    assert bbox.top_left_x == pytest.approx(0.0)
    assert bbox.top_left_y == pytest.approx(0.0)
    assert bbox.width == pytest.approx(40 / 100)
    assert bbox.height == pytest.approx(30 / 100)


def test_mask_to_bbox_mask_at_top_right_corner() -> None:
    """Mask whose top-right pixel is at the top-right corner of the image."""
    mask = np.zeros((100, 100), dtype=bool)
    mask[0:30, 70:100] = True

    bbox = mask_to_bbox(_mask_to_coords(mask))

    assert bbox.top_left_x == pytest.approx(70 / 100)
    assert bbox.top_left_y == pytest.approx(0.0)
    assert bbox.width == pytest.approx(30 / 100)
    assert bbox.height == pytest.approx(30 / 100)


def test_mask_to_bbox_mask_at_bottom_left_corner() -> None:
    """Mask whose bottom-left pixel is at the bottom-left corner of the image."""
    mask = np.zeros((100, 100), dtype=bool)
    mask[70:100, 0:30] = True

    bbox = mask_to_bbox(_mask_to_coords(mask))

    assert bbox.top_left_x == pytest.approx(0.0)
    assert bbox.top_left_y == pytest.approx(70 / 100)
    assert bbox.width == pytest.approx(30 / 100)
    assert bbox.height == pytest.approx(30 / 100)


def test_mask_to_bbox_mask_touching_bottom_right() -> None:
    """Mask whose bottom-right pixel is at the last pixel of the image."""
    mask = np.zeros((100, 100), dtype=bool)
    mask[70:100, 60:100] = True

    bbox = mask_to_bbox(_mask_to_coords(mask))

    assert bbox.top_left_x == pytest.approx(60 / 100)
    assert bbox.top_left_y == pytest.approx(70 / 100)
    assert bbox.width == pytest.approx(40 / 100)
    assert bbox.height == pytest.approx(30 / 100)


def test_mask_to_bbox_full_image() -> None:
    """A mask covering the full image yields a bbox covering the full image."""
    mask = np.ones((60, 90), dtype=bool)

    bbox = mask_to_bbox(_mask_to_coords(mask))

    assert bbox.top_left_x == pytest.approx(0.0)
    assert bbox.top_left_y == pytest.approx(0.0)
    assert bbox.width == pytest.approx(1.0)
    assert bbox.height == pytest.approx(1.0)


def test_mask_to_bbox_disconnected_regions() -> None:
    """Mask with two disconnected blobs — bbox should span both."""
    mask = np.zeros((100, 100), dtype=bool)
    mask[10:20, 10:20] = True
    mask[70:80, 80:90] = True

    bbox = mask_to_bbox(_mask_to_coords(mask))

    assert bbox.top_left_x == pytest.approx(10 / 100)
    assert bbox.top_left_y == pytest.approx(10 / 100)
    assert bbox.width == pytest.approx(80 / 100)
    assert bbox.height == pytest.approx(70 / 100)


def test_mask_to_bbox_diagonal_line_mask() -> None:
    """A diagonal line — bbox must span the two endpoints, not the interior pixels."""
    mask = np.zeros((100, 100), dtype=bool)
    for i in range(10, 91):
        mask[i, i] = True

    bbox = mask_to_bbox(_mask_to_coords(mask))

    assert bbox.top_left_x == pytest.approx(10 / 100)
    assert bbox.top_left_y == pytest.approx(10 / 100)
    assert bbox.width == pytest.approx(81 / 100)
    assert bbox.height == pytest.approx(81 / 100)


def test_mask_to_bbox_single_row_mask() -> None:
    """A mask filling a single row — height should be exactly 1 pixel."""
    mask = np.zeros((100, 200), dtype=bool)
    mask[40, 50:150] = True

    bbox = mask_to_bbox(_mask_to_coords(mask))

    assert bbox.top_left_x == pytest.approx(50 / 200)
    assert bbox.top_left_y == pytest.approx(40 / 100)
    assert bbox.width == pytest.approx(100 / 200)
    assert bbox.height == pytest.approx(1 / 100)


def test_mask_to_bbox_single_column_mask() -> None:
    """A mask filling a single column — width should be exactly 1 pixel."""
    mask = np.zeros((100, 200), dtype=bool)
    mask[30:80, 120] = True

    bbox = mask_to_bbox(_mask_to_coords(mask))

    assert bbox.top_left_x == pytest.approx(120 / 200)
    assert bbox.top_left_y == pytest.approx(30 / 100)
    assert bbox.width == pytest.approx(1 / 200)
    assert bbox.height == pytest.approx(50 / 100)


def test_mask_to_bbox_mask_one_pixel_from_edge() -> None:
    """Mask sits one pixel inside every edge — catches off-by-one at boundaries."""
    mask = np.zeros((100, 100), dtype=bool)
    mask[1:11, 1:11] = True

    bbox = mask_to_bbox(_mask_to_coords(mask))

    assert bbox.top_left_x == pytest.approx(1 / 100)
    assert bbox.top_left_y == pytest.approx(1 / 100)
    assert bbox.width == pytest.approx(10 / 100)
    assert bbox.height == pytest.approx(10 / 100)


def test_mask_to_bbox_l_shape_on_rectangular_image() -> None:
    """An L-shaped (irregular) mask on a rectangular image — bbox must span the union."""
    mask = np.zeros((100, 200), dtype=bool)  # h=100, w=200
    mask[20:80, 40:60] = True  # vertical arm
    mask[70:90, 40:140] = True  # horizontal arm

    bbox = mask_to_bbox(_mask_to_coords(mask))

    assert bbox.top_left_x == pytest.approx(40 / 200)
    assert bbox.top_left_y == pytest.approx(20 / 100)
    assert bbox.width == pytest.approx(100 / 200)
    assert bbox.height == pytest.approx(70 / 100)


def test_mask_to_bbox_empty_mask_raises() -> None:
    """An empty mask raises ValueError — no meaningful bbox exists."""
    mask = np.zeros((50, 50), dtype=bool)

    with pytest.raises(ValueError, match="empty bitmask"):
        mask_to_bbox(_mask_to_coords(mask))
