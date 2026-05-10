"""
Convert bounding boxes to a binary occupancy grid.
"""

from typing import List, Tuple, Dict

from src.vision.grid import get_direction_region_indices


def boxes_to_occupancy(
    boxes_xyxy: List[Tuple[int, int, int, int]],
    rows: int,
    cols: int,
    image_w: int,
    image_h: int,
    overlap_threshold: float = 0.3,
    box_coverage_threshold: float = 0.5,
) -> List[int]:
    """
    Convert a list of bounding boxes to a binary occupancy grid.

    A cell is marked occupied when EITHER:
    - the bounding box covers at least ``overlap_threshold`` of the cell's
      area (handles large vehicles spanning multiple cells), OR
    - the cell covers at least ``box_coverage_threshold`` of the bounding
      box's own area (handles small/distant vehicles whose box is smaller
      than a single cell).

    This prevents edge-grazing boxes from spuriously activating adjacent
    cells while ensuring distant vehicles with small bounding boxes still
    trigger the cell they occupy.

    Args:
        boxes_xyxy: List of (x1, y1, x2, y2) bounding boxes (e.g., from YOLO).
        rows: Number of rows in the grid.
        cols: Number of columns in the grid.
        image_w: Image width in pixels.
        image_h: Image height in pixels.
        overlap_threshold: Minimum fraction of a cell's area that must be
            covered by the bounding box for the cell to be marked occupied.
            Range [0, 1]; default 0.3.
        box_coverage_threshold: Minimum fraction of the bounding box's own
            area that must lie within a cell for the cell to be marked
            occupied. Handles small/distant objects whose box is smaller
            than a single cell. Range [0, 1]; default 0.5.

    Returns:
        List of length rows*cols with 1 for occupied regions, 0 otherwise.
        Ordered row-major (index = r * cols + c).
    """
    N = rows * cols
    occupancy = [0] * N

    cell_w = image_w / cols
    cell_h = image_h / rows
    cell_area = cell_w * cell_h

    for box in boxes_xyxy:
        x1, y1, x2, y2 = box
        box_area = max((x2 - x1) * (y2 - y1), 1)

        c0 = min(int(x1 / cell_w), cols - 1)
        r0 = min(int(y1 / cell_h), rows - 1)
        c1 = min(int(x2 / cell_w), cols - 1)
        r1 = min(int(y2 / cell_h), rows - 1)

        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                cell_x1 = c * cell_w
                cell_y1 = r * cell_h
                cell_x2 = cell_x1 + cell_w
                cell_y2 = cell_y1 + cell_h

                inter_w = max(0.0, min(x2, cell_x2) - max(x1, cell_x1))
                inter_h = max(0.0, min(y2, cell_y2) - max(y1, cell_y1))
                inter_area = inter_w * inter_h

                if (inter_area / cell_area >= overlap_threshold or
                        inter_area / box_area >= box_coverage_threshold):
                    occupancy[r * cols + c] = 1

    return occupancy


def classify_boxes_by_direction(
    boxes_xyxy: List[Tuple[int, int, int, int]],
    image_w: int,
    image_h: int,
    split: str = "vertical"
) -> Tuple[List[Tuple[int, int, int, int]], List[Tuple[int, int, int, int]]]:
    """
    Classify bounding boxes into Direction A and Direction B based on
    the centre point of each box.

    For a vertical split:
        centre_x < image_w / 2  →  Direction A (left half)
        otherwise               →  Direction B (right half)
    For a horizontal split:
        centre_y < image_h / 2  →  Direction A (top half)
        otherwise               →  Direction B (bottom half)

    Args:
        boxes_xyxy: List of (x1, y1, x2, y2) bounding boxes.
        image_w: Image width in pixels.
        image_h: Image height in pixels.
        split: "vertical" or "horizontal".

    Returns:
        (boxes_A, boxes_B) — two lists of bounding boxes.
    """
    boxes_A: List[Tuple[int, int, int, int]] = []
    boxes_B: List[Tuple[int, int, int, int]] = []

    for box in boxes_xyxy:
        x1, y1, x2, y2 = box
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2

        if split == "vertical":
            if cx < image_w / 2:
                boxes_A.append(box)
            else:
                boxes_B.append(box)
        else:  # horizontal
            if cy < image_h / 2:
                boxes_A.append(box)
            else:
                boxes_B.append(box)

    return boxes_A, boxes_B


def directional_occupancy(
    boxes_xyxy: List[Tuple[int, int, int, int]],
    rows: int,
    cols: int,
    image_w: int,
    image_h: int,
    split: str = "vertical",
    overlap_threshold: float = 0.3,
    box_coverage_threshold: float = 0.5,
) -> Dict[str, object]:
    """
    Compute per-direction occupancy and density.

    Splits detected vehicles into Direction A / B, builds an occupancy grid
    for each direction (using only that direction's boxes), and calculates
    density over only the grid regions that belong to that direction's half.

    Args:
        boxes_xyxy: All detected bounding boxes.
        rows: Grid rows.
        cols: Grid columns.
        image_w: Image width.
        image_h: Image height.
        split: "vertical" or "horizontal".
        overlap_threshold: Passed through to boxes_to_occupancy; minimum cell
            overlap fraction for a cell to be marked occupied.
        box_coverage_threshold: Passed through to boxes_to_occupancy; minimum
            fraction of the box's area that must intersect a cell for the
            cell to be marked occupied.

    Returns:
        Dict with keys:
            boxes_A, boxes_B          — bounding boxes per direction
            occupancy_A, occupancy_B  — full-length occupancy arrays (only their half is meaningful)
            indices_A, indices_B      — region indices belonging to each direction
            count_A, count_B          — occupied region count per direction
            density_A, density_B      — density per direction (0-1)
    """
    boxes_A, boxes_B = classify_boxes_by_direction(
        boxes_xyxy, image_w, image_h, split
    )

    # Full occupancy using only direction-specific boxes
    occupancy_A = boxes_to_occupancy(
        boxes_A, rows, cols, image_w, image_h, overlap_threshold, box_coverage_threshold
    )
    occupancy_B = boxes_to_occupancy(
        boxes_B, rows, cols, image_w, image_h, overlap_threshold, box_coverage_threshold
    )

    # Region indices for each half
    indices_A, indices_B = get_direction_region_indices(rows, cols, split)

    # Count occupied cells only in the relevant half
    count_A = sum(occupancy_A[i] for i in indices_A)
    count_B = sum(occupancy_B[i] for i in indices_B)

    n_A = len(indices_A) if indices_A else 1
    n_B = len(indices_B) if indices_B else 1

    return {
        "boxes_A": boxes_A,
        "boxes_B": boxes_B,
        "occupancy_A": occupancy_A,
        "occupancy_B": occupancy_B,
        "indices_A": indices_A,
        "indices_B": indices_B,
        "count_A": count_A,
        "count_B": count_B,
        "density_A": count_A / n_A,
        "density_B": count_B / n_B,
    }
