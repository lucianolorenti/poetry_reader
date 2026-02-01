"""Generate beautiful gradient backgrounds for poetry videos with TikTok-style effects."""

import numpy as np
from PIL import Image, ImageFilter
import random
import math
from typing import Optional


# Elegant color palettes for poetry videos (originals)
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
    # TikTok vibrant palettes
    "tiktok_cyber": [
        (255, 0, 128),  # Hot pink
        (128, 0, 255),  # Purple
        (0, 255, 255),  # Cyan
    ],
    "tiktok_sunset": [
        (255, 50, 100),  # Vibrant pink
        (255, 150, 50),  # Orange
        (255, 220, 100),  # Yellow
    ],
    "tiktok_ocean": [
        (0, 150, 200),  # Deep cyan
        (0, 200, 255),  # Bright blue
        (100, 220, 255),  # Light blue
    ],
    "tiktok_berry": [
        (100, 0, 150),  # Deep purple
        (200, 50, 150),  # Magenta
        (255, 100, 150),  # Pink
    ],
    "tiktok_fire": [
        (150, 0, 0),  # Dark red
        (255, 100, 0),  # Orange
        (255, 200, 0),  # Gold
    ],
    "tiktok_neon": [
        (20, 0, 40),  # Dark purple
        (60, 0, 120),  # Purple
        (0, 255, 200),  # Neon cyan
    ],
}


def create_gradient_background(
    resolution: tuple,
    palette_name: Optional[str] = None,
    direction: str = "diagonal",
    noise: bool = True,
    animated: bool = False,
    time: float = 0.0,
) -> np.ndarray:
    """Create a smooth gradient background.

    Args:
        resolution: (width, height) of the image
        palette_name: Name of color palette from COLOR_PALETTES. If None, random.
        direction: "vertical", "horizontal", "diagonal", "radial", "animated"
        noise: Add subtle grain/texture overlay
        animated: Create animated gradient (shifting colors over time)
        time: Time value for animated gradients (0.0 to 1.0)

    Returns:
        numpy array (H, W, 3) uint8 RGB image
    """
    width, height = resolution

    if palette_name is None or palette_name not in COLOR_PALETTES:
        # Prefer TikTok palettes for better visual impact
        tiktok_palettes = [k for k in COLOR_PALETTES.keys() if k.startswith("tiktok_")]
        palette_name = random.choice(tiktok_palettes if tiktok_palettes else list(COLOR_PALETTES.keys()))

    colors = COLOR_PALETTES[palette_name]

    # For animated gradients, shift colors based on time
    if animated:
        colors = _shift_colors(colors, time)

    # Create gradient
    if direction == "vertical":
        gradient = _vertical_gradient(width, height, colors)
    elif direction == "horizontal":
        gradient = _horizontal_gradient(width, height, colors)
    elif direction == "radial":
        gradient = _radial_gradient(width, height, colors)
    elif direction == "spiral":
        gradient = _spiral_gradient(width, height, colors, time)
    else:  # diagonal
        gradient = _diagonal_gradient(width, height, colors)

    # Add subtle noise texture
    if noise:
        gradient = _add_noise(gradient, intensity=0.03)

    return gradient


def _shift_colors(colors: list, time: float) -> list:
    """Shift colors for animated effect."""
    shifted = []
    for i, color in enumerate(colors):
        shift = math.sin(time * 2 * math.pi + i * 0.5) * 0.1
        new_color = tuple(
            max(0, min(255, int(c * (1 + shift))))
            for c in color
        )
        shifted.append(new_color)
    return shifted


def _vertical_gradient(width: int, height: int, colors: list) -> np.ndarray:
    """Create vertical gradient."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    num_colors = len(colors)

    for y in range(height):
        t = y / (height - 1) * (num_colors - 1)
        idx = int(t)
        frac = t - idx

        if idx >= num_colors - 1:
            color = colors[-1]
        else:
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


def _spiral_gradient(width: int, height: int, colors: list, time: float = 0.0) -> np.ndarray:
    """Create spiral gradient effect for TikTok videos."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    num_colors = len(colors)
    cx, cy = width // 2, height // 2

    for y in range(height):
        for x in range(width):
            dx = x - cx
            dy = y - cy
            dist = np.sqrt(dx**2 + dy**2)
            angle = math.atan2(dy, dx) + time * 2 * math.pi

            # Combine distance and angle for spiral effect
            spiral = (dist / 100) + angle / (2 * math.pi)
            t = (spiral % 1) * (num_colors - 1)
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
    """Return a random palette name, preferring TikTok palettes."""
    tiktok_palettes = [k for k in COLOR_PALETTES.keys() if k.startswith("tiktok_")]
    return random.choice(tiktok_palettes if tiktok_palettes else list(COLOR_PALETTES.keys()))


def create_zoomed_background(
    resolution: tuple,
    palette_name: Optional[str] = None,
    zoom_factor: float = 1.1,
    pan_direction: str = "up",
) -> Image.Image:
    """Create a gradient background with zoom effect for Ken Burns style.

    Args:
        resolution: (width, height) of output
        palette_name: Color palette name
        zoom_factor: How much to zoom in (1.1 = 10% larger)
        pan_direction: "up", "down", "left", "right"

    Returns:
        PIL Image ready for zoom/pan animation
    """
    # Create larger image for zoom
    width, height = resolution
    big_width = int(width * zoom_factor)
    big_height = int(height * zoom_factor)

    # Generate gradient at larger size
    gradient = create_gradient_background(
        (big_width, big_height),
        palette_name=palette_name,
        direction="diagonal",
        noise=True,
    )

    return Image.fromarray(gradient)
