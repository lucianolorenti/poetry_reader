"""Generate animated particle overlays for videos with TikTok-style effects."""

from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import random
import math


class Particle:
    """Represents a single floating particle with TikTok-style effects."""

    PARTICLE_TYPES = ["circle", "star", "sparkle", "diamond", "heart"]

    def __init__(self, width, height, particle_type=None, color=None):
        self.width = width
        self.height = height
        self.x = random.uniform(0, width)
        self.y = random.uniform(height * 0.8, height)  # Start from bottom

        # Movement - organic floating
        self.vx = random.uniform(-1.0, 1.0)
        self.vy = random.uniform(-2.5, -0.8)  # Faster upward drift
        self.sway_amplitude = random.uniform(0.5, 2.0)
        self.sway_frequency = random.uniform(0.5, 2.0)
        self.sway_phase = random.uniform(0, 2 * math.pi)
        self.time = 0

        # Size and opacity with variation
        self.size = random.uniform(2, 8)
        self.base_opacity = random.uniform(0.15, 0.6)
        self.opacity = self.base_opacity
        self.twinkle_speed = random.uniform(1.0, 3.0)
        self.twinkle_phase = random.uniform(0, 2 * math.pi)

        # Particle type
        if particle_type is None:
            weights = [0.4, 0.3, 0.2, 0.05, 0.05]  # More circles and stars
            self.type = random.choices(self.PARTICLE_TYPES, weights=weights)[0]
        else:
            self.type = particle_type

        # Color - TikTok style: whites, golds, pinks, cyans
        if color is None:
            color_palettes = [
                [(255, 255, 255)],  # Pure white
                [(255, 215, 0), (255, 223, 100)],  # Gold
                [(255, 105, 180), (255, 150, 200)],  # Pink
                [(0, 255, 255), (100, 255, 255)],  # Cyan
                [(255, 255, 150), (255, 255, 200)],  # Light yellow
            ]
            palette = random.choice(color_palettes)
            self.color = random.choice(palette)
        else:
            self.color = color

        # Rotation for non-circular particles
        self.rotation = random.uniform(0, 360)
        self.rotation_speed = random.uniform(-30, 30)

    def update(self, dt=1.0):
        """Update particle position with organic movement."""
        self.time += dt * 0.1

        # Sway motion for organic feel
        sway = math.sin(self.time * self.sway_frequency + self.sway_phase) * self.sway_amplitude

        # Update position
        self.x += self.vx + sway * 0.1
        self.y += self.vy

        # Twinkle effect
        twinkle = math.sin(self.time * self.twinkle_speed + self.twinkle_phase)
        self.opacity = self.base_opacity * (0.7 + 0.3 * twinkle)

        # Update rotation
        self.rotation += self.rotation_speed * dt * 0.1

        # Wrap around edges with reset
        if self.y < -20:
            self.y = self.height + 20
            self.x = random.uniform(0, self.width)
            self.opacity = 0  # Fade in when respawning
        if self.x < -20:
            self.x = self.width + 20
        if self.x > self.width + 20:
            self.x = -20


class Sparkle:
    """Represents a sparkle/light burst effect."""

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.reset()

    def reset(self):
        """Reset sparkle to new random position."""
        self.x = random.uniform(0, self.width)
        self.y = random.uniform(0, self.height)
        self.size = random.uniform(5, 20)
        self.max_life = random.uniform(0.5, 2.0)
        self.life = self.max_life
        self.color = random.choice([
            (255, 255, 255),
            (255, 215, 0),  # Gold
            (255, 105, 180),  # Pink
            (0, 255, 255),  # Cyan
            (255, 255, 150),  # Yellow
        ])
        self.active = True

    def update(self, dt):
        """Update sparkle life."""
        self.life -= dt
        if self.life <= 0:
            self.active = False

    def get_opacity(self):
        """Get current opacity based on life."""
        if self.life > self.max_life * 0.7:
            # Fade in
            return 1 - (self.life - self.max_life * 0.7) / (self.max_life * 0.3)
        else:
            # Fade out
            return self.life / (self.max_life * 0.7)


def draw_star(draw, cx, cy, size, color, opacity):
    """Draw a star shape."""
    points = []
    for i in range(10):
        angle = math.pi / 2 + (2 * math.pi * i / 10)
        if i % 2 == 0:
            r = size
        else:
            r = size * 0.4
        x = cx + r * math.cos(angle)
        y = cy - r * math.sin(angle)
        points.append((x, y))

    alpha = int(opacity * 255)
    draw.polygon(points, fill=color + (alpha,))


def draw_sparkle(draw, cx, cy, size, color, opacity):
    """Draw a sparkle/cross shape."""
    alpha = int(opacity * 255)

    # Four-pointed sparkle
    arm_length = size
    arm_width = size * 0.2

    # Horizontal arm
    draw.ellipse(
        [cx - arm_length, cy - arm_width, cx + arm_length, cy + arm_width],
        fill=color + (alpha,)
    )

    # Vertical arm
    draw.ellipse(
        [cx - arm_width, cy - arm_length, cx + arm_width, cy + arm_length],
        fill=color + (alpha,)
    )


def draw_diamond(draw, cx, cy, size, color, opacity, rotation=0):
    """Draw a diamond/rhombus shape."""
    alpha = int(opacity * 255)
    rad = math.radians(rotation)

    points = []
    for i in range(4):
        angle = rad + (math.pi / 2) * i
        if i % 2 == 0:
            r = size
        else:
            r = size * 0.6
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        points.append((x, y))

    draw.polygon(points, fill=color + (alpha,))


def draw_heart(draw, cx, cy, size, color, opacity):
    """Draw a heart shape."""
    alpha = int(opacity * 255)

    # Use ellipse approximation for heart
    # Left lobe
    draw.ellipse(
        [cx - size * 0.6, cy - size * 0.4, cx, cy + size * 0.3],
        fill=color + (alpha,)
    )
    # Right lobe
    draw.ellipse(
        [cx, cy - size * 0.4, cx + size * 0.6, cy + size * 0.3],
        fill=color + (alpha,)
    )
    # Bottom point (triangle approximation)
    points = [
        (cx - size * 0.5, cy + size * 0.1),
        (cx + size * 0.5, cy + size * 0.1),
        (cx, cy + size * 0.8)
    ]
    draw.polygon(points, fill=color + (alpha,))


def draw_glow(draw, cx, cy, size, color, opacity):
    """Draw a soft glow effect around particle."""
    for i in range(3, 0, -1):
        glow_size = size * (1 + i * 0.5)
        glow_alpha = int(opacity * 30 / i)
        draw.ellipse(
            [cx - glow_size, cy - glow_size, cx + glow_size, cy + glow_size],
            fill=color + (glow_alpha,)
        )


def create_particle_frame(
    resolution: tuple,
    particles: list,
    sparkles: Optional[list] = None,
    color: Optional[tuple] = None
) -> np.ndarray:
    """Create a single frame with particles and sparkles.

    Args:
        resolution: (width, height) of the frame
        particles: List of Particle objects
        sparkles: List of Sparkle objects (optional)
        color: Default color (unused, particles have their own colors)

    Returns:
        RGBA numpy array with particles on transparent background
    """
    width, height = resolution
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Draw particles
    for p in particles:
        alpha = int(max(0, min(1, p.opacity)) * 255)
        if alpha < 10:
            continue

        particle_color = p.color + (alpha,)

        # Draw glow first (behind particle)
        draw_glow(draw, p.x, p.y, p.size, p.color, p.opacity)

        # Draw particle based on type
        if p.type == "circle":
            x0 = p.x - p.size
            y0 = p.y - p.size
            x1 = p.x + p.size
            y1 = p.y + p.size
            draw.ellipse([x0, y0, x1, y1], fill=particle_color)

        elif p.type == "star":
            draw_star(draw, p.x, p.y, p.size, p.color, p.opacity)

        elif p.type == "sparkle":
            draw_sparkle(draw, p.x, p.y, p.size * 1.5, p.color, p.opacity)

        elif p.type == "diamond":
            draw_diamond(draw, p.x, p.y, p.size, p.color, p.opacity, p.rotation)

        elif p.type == "heart":
            draw_heart(draw, p.x, p.y, p.size, p.color, p.opacity)

    # Draw sparkles
    if sparkles:
        for s in sparkles:
            if s.active:
                opacity = s.get_opacity()
                draw_sparkle(draw, s.x, s.y, s.size, s.color, opacity)

    return np.array(image)


def make_particle_clip(
    duration: float,
    resolution: tuple,
    fps: int = 30,
    num_particles: int = 80,
    add_sparkles: bool = True,
):
    """Create a VideoClip with animated TikTok-style particles.

    Args:
        duration: Duration in seconds
        resolution: (width, height) of the video
        fps: Frames per second
        num_particles: Number of particles to generate
        add_sparkles: Add sparkle burst effects

    Returns:
        MoviePy VideoClip with particle animation
    """
    from moviepy.video.VideoClip import VideoClip

    width, height = resolution

    # Initialize particles with varied types
    particles = []
    for _ in range(num_particles):
        # Stagger start times for organic feel
        p = Particle(width, height)
        p.y = random.uniform(0, height)  # Random start positions
        particles.append(p)

    # Initialize sparkles
    sparkles = []
    if add_sparkles:
        max_sparkles = 5
        for _ in range(max_sparkles):
            s = Sparkle(width, height)
            s.active = False  # Start inactive
            sparkles.append(s)

    last_frame = 0

    def make_frame(t):
        """Generate a frame at time t."""
        nonlocal last_frame
        frame_num = int(t * fps)
        dt = (frame_num - last_frame) / fps if last_frame > 0 else 1 / fps
        last_frame = frame_num

        # Update particles
        for p in particles:
            p.update(dt)

        # Update and respawn sparkles
        if add_sparkles:
            for s in sparkles:
                if s.active:
                    s.update(1 / fps)
                else:
                    # Random chance to spawn
                    if random.random() < 0.02:  # 2% chance per frame
                        s.reset()

        # Create the frame
        frame = create_particle_frame(resolution, particles, sparkles)
        return frame

    # Create VideoClip
    clip = VideoClip(make_frame, duration=duration)
    return clip
