"""Generate animated particle overlays for videos."""

import numpy as np
from PIL import Image, ImageDraw
import random
import math


class Particle:
    """Represents a single floating particle."""

    def __init__(self, width, height):
        self.x = random.uniform(0, width)
        self.y = random.uniform(0, height)
        self.vx = random.uniform(-0.5, 0.5)
        self.vy = random.uniform(-1.0, -0.3)  # Upward drift
        self.size = random.uniform(1, 4)
        self.opacity = random.uniform(0.1, 0.4)
        self.width = width
        self.height = height

    def update(self):
        """Update particle position."""
        self.x += self.vx
        self.y += self.vy

        # Wrap around edges
        if self.x < 0:
            self.x = self.width
        if self.x > self.width:
            self.x = 0
        if self.y < 0:
            self.y = self.height
        if self.y > self.height:
            self.y = 0


def create_particle_frame(
    resolution: tuple, particles: list, color: tuple = (255, 255, 255)
) -> np.ndarray:
    """Create a single frame with particles.

    Args:
        resolution: (width, height) of the frame
        particles: List of Particle objects
        color: RGB color for particles

    Returns:
        RGBA numpy array with particles on transparent background
    """
    width, height = resolution
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    for p in particles:
        # Calculate opacity (0-255)
        alpha = int(p.opacity * 255)
        particle_color = color + (alpha,)

        # Draw particle as a small circle
        x0 = p.x - p.size / 2
        y0 = p.y - p.size / 2
        x1 = p.x + p.size / 2
        y1 = p.y + p.size / 2

        draw.ellipse([x0, y0, x1, y1], fill=particle_color)

        # Optional: add a soft glow effect
        if p.size > 2:
            glow_alpha = int(p.opacity * 60)
            glow_color = color + (glow_alpha,)
            glow_size = p.size * 1.5
            gx0 = p.x - glow_size / 2
            gy0 = p.y - glow_size / 2
            gx1 = p.x + glow_size / 2
            gy1 = p.y + glow_size / 2
            draw.ellipse([gx0, gy0, gx1, gy1], fill=glow_color)

    return np.array(image)


def make_particle_clip(
    duration: float, resolution: tuple, fps: int = 24, num_particles: int = 50
):
    """Create a VideoClip with animated particles.

    Args:
        duration: Duration in seconds
        resolution: (width, height) of the video
        fps: Frames per second
        num_particles: Number of particles to generate

    Returns:
        MoviePy VideoClip with particle animation
    """
    from moviepy.video.VideoClip import VideoClip

    width, height = resolution

    # Initialize particles
    particles = [Particle(width, height) for _ in range(num_particles)]

    def make_frame(t):
        """Generate a frame at time t."""
        # Update particle positions for this frame
        frame_num = int(t * fps)
        for _ in range(frame_num - getattr(make_frame, "last_frame", 0)):
            for p in particles:
                p.update()
        make_frame.last_frame = frame_num

        # Create the frame
        frame = create_particle_frame(resolution, particles, color=(255, 255, 255))
        return frame

    make_frame.last_frame = 0

    # Create VideoClip
    clip = VideoClip(make_frame, duration=duration)
    return clip
