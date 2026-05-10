"""
Grid utilities for dividing an image into regions.
"""

from functools import lru_cache
from typing import List, Tuple


@lru_cache(maxsize=32)
def make_grid(rows: int, cols: int, image_w: int, image_h: int) -> List[Tuple[int, int, int, int]]:
    """
    Divide an image into a grid of rows x cols regions.
    
    Args:
        rows: Number of rows in the grid.
        cols: Number of columns in the grid.
        image_w: Image width in pixels.
        image_h: Image height in pixels.
    
    Returns:
        List of (x1, y1, x2, y2) tuples for each region, ordered row-major
        (i.e., region index = r * cols + c).
    """
    cell_w = image_w / cols
    cell_h = image_h / rows
    
    regions = []
    for r in range(rows):
        for c in range(cols):
            x1 = int(c * cell_w)
            y1 = int(r * cell_h)
            x2 = int((c + 1) * cell_w)
            y2 = int((r + 1) * cell_h)
            regions.append((x1, y1, x2, y2))
    
    return regions


def region_index(r: int, c: int, cols: int) -> int:
    """
    Convert (row, column) to linear region index.
    
    Args:
        r: Row index (0-based).
        c: Column index (0-based).
        cols: Number of columns in the grid.
    
    Returns:
        Linear index = r * cols + c.
    """
    return r * cols + c


def index_to_rc(i: int, cols: int) -> Tuple[int, int]:
    """
    Convert linear region index to (row, column).
    
    Args:
        i: Linear index.
        cols: Number of columns in the grid.
    
    Returns:
        (row, column) tuple.
    """
    r = i // cols
    c = i % cols
    return (r, c)


@lru_cache(maxsize=16)
def get_direction_region_indices(
    rows: int,
    cols: int,
    split: str = "vertical"
) -> Tuple[List[int], List[int]]:
    """
    Split grid region indices into Direction A and Direction B.

    For a vertical split (default):
        Direction A = left half columns, Direction B = right half columns.
    For a horizontal split:
        Direction A = top half rows, Direction B = bottom half rows.

    Args:
        rows: Number of rows in the grid.
        cols: Number of columns in the grid.
        split: Split orientation — "vertical" or "horizontal".

    Returns:
        (indices_A, indices_B) — lists of linear region indices for each direction.
    """
    N = rows * cols
    indices_A: List[int] = []
    indices_B: List[int] = []

    for i in range(N):
        r, c = index_to_rc(i, cols)
        if split == "vertical":
            if c < cols // 2:
                indices_A.append(i)
            else:
                indices_B.append(i)
        else:  # horizontal
            if r < rows // 2:
                indices_A.append(i)
            else:
                indices_B.append(i)

    return indices_A, indices_B
