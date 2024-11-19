import cv2
import numpy as np
from encord.objects.bitmask import BitmaskCoordinates
from encord.objects.coordinates import BoundingBoxCoordinates, PolygonCoordinates, RotatableBoundingBoxCoordinates
from numpy.typing import NDArray

CroppableCoordinates = (
    BoundingBoxCoordinates | RotatableBoundingBoxCoordinates | BitmaskCoordinates | PolygonCoordinates
)


def rbb_to_poly(
    rbb: RotatableBoundingBoxCoordinates,
    img_width: int,
    img_height: int,
) -> np.ndarray:
    x = rbb.top_left_x
    y = rbb.top_left_y
    w = rbb.width
    h = rbb.height
    bbox_not_rotated = np.array(
        [
            [x * img_width, y * img_height],
            [(x + w) * img_width, y * img_height],
            [(x + w) * img_width, (y + h) * img_height],
            [x * img_width, (y + h) * img_height],
        ]
    )
    angle = rbb.theta  # [0; 360]
    center = tuple(bbox_not_rotated.mean(0).tolist())
    rotation_matrix = cv2.getRotationMatrix2D(center, 360 - angle, scale=1.0)
    points = np.pad(
        bbox_not_rotated,
        [
            (0, 0),
            (0, 1),
        ],
        mode="constant",
        constant_values=1,
    )
    rotated_points: np.ndarray = points @ rotation_matrix.T
    return rotated_points


def poly_to_rbb(
    poly: np.ndarray,
    img_width: int,
    img_height: int,
) -> RotatableBoundingBoxCoordinates:
    v1 = poly[1] - poly[0]
    v1 = v1 / np.linalg.norm(v1, ord=2)
    angle = np.degrees(np.arccos(v1[0]))

    if not any(
        [poly[0, 0] > poly[3, 0], poly[0, 0] == poly[3, 0] and poly[0, 1] < poly[3, 1]]
    ):  # Initial points were rotated more than 180 degrees => Rotate backwards
        angle = 360 - angle

    center = poly.mean(axis=0)
    rotation_matrix = cv2.getRotationMatrix2D(center, angle, scale=1.0)
    points = np.pad(
        poly,
        [
            (0, 0),
            (0, 1),
        ],
        mode="constant",
        constant_values=1,
    )
    rotated_points = points @ rotation_matrix.T
    x, y = rotated_points.min(0)
    w, h = rotated_points.max(0) - rotated_points.min(0)
    return RotatableBoundingBoxCoordinates(
        top_left_x=float(x / img_width),
        top_left_y=float(y / img_height),
        width=float(w / img_width),
        height=float(h / img_height),
        theta=float(angle),
    )


def crop_to_bbox(image: NDArray, bbox: BoundingBoxCoordinates) -> NDArray:
    img_height, img_width = image.shape[:2]
    from_x = int(img_width * bbox.top_left_x + 0.5)
    from_y = int(img_height * bbox.top_left_y + 0.5)
    to_x = from_x + int(img_width * bbox.width + 0.5)
    to_y = from_y + int(img_height * bbox.height + 0.5)
    return image[from_y:to_y, from_x:to_x]


def poly_to_bbox(poly: PolygonCoordinates | NDArray) -> BoundingBoxCoordinates:
    if isinstance(poly, PolygonCoordinates):
        rel_coords = np.array([[v.x, v.y] for v in poly.values])
    else:
        rel_coords = poly
    x_min, y_min = rel_coords.min(0)
    x_max, y_max = rel_coords.max(0)
    w = x_max - x_min
    h = y_max - y_min
    return BoundingBoxCoordinates(top_left_x=x_min, top_left_y=y_min, width=w, height=h)


def rbbox_to_surrounding_bbox(rbb: RotatableBoundingBoxCoordinates, img_w: int, img_h: int) -> BoundingBoxCoordinates:
    abs_coords = rbb_to_poly(rbb, img_width=img_w, img_height=img_h)
    rel_coords = abs_coords / np.array([[img_w, img_h]], dtype=float)
    return poly_to_bbox(rel_coords)


def mask_to_bbox(coords: BitmaskCoordinates) -> BoundingBoxCoordinates:
    mask = np.array(coords)
    img_height, img_width = mask.shape
    pixel_coords = np.array(np.where(mask))
    x_min, y_min = pixel_coords.min(axis=1)
    x_max, y_max = (pixel_coords + 1).min(axis=1)
    width = (x_max - x_min) / img_width
    height = (y_max - y_min) / img_height
    x_min /= img_width
    y_min /= img_height
    return BoundingBoxCoordinates(top_left_x=x_min, top_left_y=y_min, width=width, height=height)


def crop_to_object(image: NDArray[np.uint8], coordinates: CroppableCoordinates) -> NDArray[np.uint8]:
    img_height, img_width = image.shape[:2]

    box: BoundingBoxCoordinates
    if isinstance(coordinates, BoundingBoxCoordinates):
        box = coordinates
    elif isinstance(coordinates, RotatableBoundingBoxCoordinates):
        box = rbbox_to_surrounding_bbox(coordinates, img_w=img_width, img_h=img_height)
    elif isinstance(coordinates, PolygonCoordinates):
        box = poly_to_bbox(coordinates)
    elif isinstance(coordinates, BitmaskCoordinates):
        box = mask_to_bbox(coordinates)
    return crop_to_bbox(image, box)