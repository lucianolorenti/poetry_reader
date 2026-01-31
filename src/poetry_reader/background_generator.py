"""Generate beautiful gradient backgrounds for poetry videos."""

import numpy as np
from PIL import Image
import random
from typing import Optional


# Elegant color palettes for poetry videos
COLOR_PALETTES = {
    "sunset": [(255, 94, 77), (255, 184, 140), (253, 216, 193)],
    "ocean": [(26, 42, 108), (58, 96, 115), (148, 187, 233)],
    "forest": [(22, 56, 48), (46, 125, 50), (129, 199, 132)],
    "lavender": [(94, 53, 177), (155, 81, 224), (206, 147, 216)],
    "rose": [(136, 14, 79), (194, 24, 91), (233, 30, 99)],
    "golden": [(255, 160, 0), (255, 213, 79), (255, 245, 157)],
    "midnight": [(13, 27, 42), (27, 38, 59), (65, 90, 119)],
    "peach": [(255, 138, 101), (255, 209, 163), (255, 234, 213)],
    "mint": [(0, 137, 123), (0, 188, 212), (128, 222, 234)],
    "autumn": [(191, 54, 12), (230, 81, 0), (255, 138, 101)],
}


def create_gradient_background(
    resolution: tuple,
    palette_name: Optional[str] = None,
    direction: str = "diagonal",
    noise: bool = True,
) -> np.ndarray:
    """Create a smooth gradient background.

    Args:
        resolution: (width, height) of the image
        palette_name: Name of color palette from COLOR_PALETTES. If None, random.
        direction: "vertical", "horizontal", "diagonal", "radial"
        noise: Add subtle grain/texture overlay

    Returns:
        numpy array (H, W, 3) uint8 RGB image
    """
    width, height = resolution

    if palette_name is None or palette_name not in COLOR_PALETTES:
        palette_name = random.choice(list(COLOR_PALETTES.keys()))

    colors = COLOR_PALETTES[palette_name]

    # Create gradient
    if direction == "vertical":
        gradient = _vertical_gradient(width, height, colors)
    elif direction == "horizontal":
        gradient = _horizontal_gradient(width, height, colors)
    elif direction == "radial":
        gradient = _radial_gradient(width, height, colors)
    else:  # diagonal
        gradient = _diagonal_gradient(width, height, colors)

    # Add subtle noise texture
    if noise:
        gradient = _add_noise(gradient, intensity=0.03)

    return gradient


def _vertical_gradient(width: int, height: int, colors: list) -> np.ndarray:
    """Create vertical gradient."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    num_colors = len(colors)

    for y in range(height):
        # Map y to color index (float)
        t = y / (height - 1) * (num_colors - 1)
        idx = int(t)
        frac = t - idx

        if idx >= num_colors - 1:
            color = colors[-1]
        else:
            # Interpolate between colors[idx] and colors[idx+1]
            c1 = np.array(colors[idx])
            c2 = np.array(colors[idx + 1])
            color = c1 * (1 - frac) + c2 * frac

        img[y, :, :] = color

    return img


def _horizontal_gradient(width: int, height: int, colors: list) -> np.ndarray:
    """Create horizontal gradient."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    num_colors = len(colors)

    for x in range(width):
        t = x / (width - 1) * (num_colors - 1)
        idx = int(t)
        frac = t - idx

        if idx >= num_colors - 1:
            color = colors[-1]
        else:
            c1 = np.array(colors[idx])
            c2 = np.array(colors[idx + 1])
            color = c1 * (1 - frac) + c2 * frac

        img[:, x, :] = color

    return img


def _diagonal_gradient(width: int, height: int, colors: list) -> np.ndarray:
    """Create diagonal gradient (top-left to bottom-right)."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    num_colors = len(colors)
    max_dist = np.sqrt(width**2 + height**2)

    for y in range(height):
        for x in range(width):
            dist = np.sqrt(x**2 + y**2)
            t = (dist / max_dist) * (num_colors - 1)
            idx = int(t)
            frac = t - idx

            if idx >= num_colors - 1:
                color = colors[-1]
            else:
                c1 = np.array(colors[idx])
                c2 = np.array(colors[idx + 1])
                color = c1 * (1 - frac) + c2 * frac

            img[y, x, :] = color

    return img


def _radial_gradient(width: int, height: int, colors: list) -> np.ndarray:
    """Create radial gradient from center."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    num_colors = len(colors)
    cx, cy = width // 2, height // 2
    max_dist = np.sqrt(cx**2 + cy**2)

    for y in range(height):
        for x in range(width):
            dx = x - cx
            dy = y - cy
            dist = np.sqrt(dx**2 + dy**2)
            t = (dist / max_dist) * (num_colors - 1)
            idx = int(t)
            frac = t - idx

            if idx >= num_colors - 1:
                color = colors[-1]
            else:
                c1 = np.array(colors[idx])
                c2 = np.array(colors[idx + 1])
                color = c1 * (1 - frac) + c2 * frac

            img[y, x, :] = color

    return img


def _add_noise(img: np.ndarray, intensity: float = 0.03) -> np.ndarray:
    """Add subtle grain texture."""
    noise = np.random.normal(0, intensity * 255, img.shape)
    noisy = img.astype(np.float32) + noise
    noisy = np.clip(noisy, 0, 255).astype(np.uint8)
    return noisy


def get_random_palette() -> str:
    """Return a random palette name."""
    return random.choice(list(COLOR_PALETTES.keys()))
