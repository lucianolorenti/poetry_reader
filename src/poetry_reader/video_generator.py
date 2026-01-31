import os


from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.VideoClip import ImageClip, ColorClip, VideoClip
from moviepy.video.VideoClip import TextClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip


from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import textwrap
import numpy as np
from .background_generator import create_gradient_background
from .particle_generator import make_particle_clip


def _measure_text(draw_obj, s, fnt):
    """Helper to measure text with various Pillow API versions."""
    try:
        bbox = draw_obj.textbbox((0, 0), s, font=fnt)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        return (w, h)
    except Exception:
        pass
    try:
        return draw_obj.textsize(s, font=fnt)
    except Exception:
        pass
    try:
        return (fnt.getsize(s)[0], fnt.getsize(s)[1])
    except Exception:
        pass
    try:
        mask = fnt.getmask(s)
        return mask.size
    except Exception:
        pass
    try:
        bbox = fnt.getbbox(s)
        return (bbox[2] - bbox[0], bbox[3] - bbox[1])
    except Exception:
        # Fallback estimation
        return (len(s) * 10, 20)


def render_text_image(
    text: str,
    resolution: tuple,
    font_size: int = 60,
    color: tuple = (255, 255, 255),
    bg_color: Optional[str] = None,
    padding: int = 80,
    valign: str = "center",
    bottom_margin: int = 140,
    shadow: bool = True,
    elegant: bool = True,
    youtube: bool = False,
) -> np.ndarray:
    """Render text for video overlays.

    When `youtube=True` the function prefers bold, highly legible sans-serif
    fonts and draws a dark stroke around the text for good readability on
    YouTube thumbnails and videos.
    """
    width, height = resolution

    # Select font list depending on style preference
    font = None
    if youtube:
        # Try some common bold sans-serif fonts suitable for YouTube
        youtube_fonts = [
            "Montserrat-Bold.ttf",
            "Montserrat-Regular.ttf",
            "Roboto-Bold.ttf",
            "Anton-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for f in youtube_fonts:
            try:
                font = ImageFont.truetype(f, font_size)
                break
            except Exception:
                continue

    if font is None and elegant:
        for font_name in [
            "Georgia",
            "Times New Roman",
            "Palatino",
            "Garamond",
            "Liberation Serif",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        ]:
            try:
                font = ImageFont.truetype(font_name, font_size)
                break
            except Exception:
                continue

    if font is None:
        # Fallback to robust sans-serif
        for font_name in [
            "DejaVuSans.ttf",
            "DejaVuSans-Bold.ttf",
            "Arial.ttf",
            "LiberationSans-Regular.ttf",
        ]:
            try:
                font = ImageFont.truetype(font_name, font_size)
                break
            except Exception:
                continue

    if font is None:
        font = ImageFont.load_default()

    # Temporary draw to measure text
    tmp = Image.new("RGBA", (10, 10))
    tmp_draw = ImageDraw.Draw(tmp)

    # Calculate wrapping
    avg_char_width = _measure_text(tmp_draw, "A", font)[0]
    chars_per_line = max(10, (width - padding * 2) // max(1, avg_char_width))
    lines = textwrap.wrap(text, width=chars_per_line, break_long_words=False)

    if not lines:
        lines = [text]

    # Measure all lines
    line_sizes = [_measure_text(tmp_draw, line, font) for line in lines]
    line_height = max([h for (_, h) in line_sizes]) if line_sizes else font_size
    line_spacing = int(line_height * 0.35)
    text_block_height = line_height * len(lines) + line_spacing * max(0, len(lines) - 1)

    # Create image with transparency or background color
    if bg_color is None:
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    else:
        image = Image.new("RGB", (width, height), color=bg_color)

    draw = ImageDraw.Draw(image)

    # Calculate vertical position
    if valign == "center":
        y = (height - text_block_height) // 2
    elif valign == "bottom":
        y = height - bottom_margin - text_block_height
    else:  # top
        y = padding

    # Stroke/outline for YouTube readability
    stroke_width = max(1, int(font_size * 0.06)) if youtube else 0
    stroke_fill = (0, 0, 0)

    for line in lines:
        w, h = _measure_text(draw, line, font)
        x = (width - w) // 2

        # Draw shadow (subtle) if requested
        if shadow and not youtube:
            shadow_color = (0, 0, 0, 180) if bg_color is None else (0, 0, 0)
            for dx, dy in [(2, 2), (1, 1)]:
                draw.text((x + dx, y + dy), line, font=font, fill=shadow_color)

        # Draw main text with optional stroke
        try:
            # Newer Pillow supports stroke_width/stroke_fill
            draw.text(
                (x, y),
                line,
                font=font,
                fill=color,
                stroke_width=stroke_width,
                stroke_fill=stroke_fill,
            )
        except TypeError:
            # Fallback: draw outline manually
            if stroke_width > 0:
                for dx in range(-stroke_width, stroke_width + 1):
                    for dy in range(-stroke_width, stroke_width + 1):
                        if dx == 0 and dy == 0:
                            continue
                        draw.text((x + dx, y + dy), line, font=font, fill=stroke_fill)
            draw.text((x, y), line, font=font, fill=color)

        y += line_height + line_spacing

    arr = np.array(image)
    if arr.dtype != np.uint8:
        arr = arr.astype(np.uint8)
    return arr


def create_video_from_audio_and_text(
    audio_path: str,
    title: str,
    out_path: str,
    duration: Optional[float] = None,
    image_path: Optional[str] = None,
    fps: int = 24,
    resolution=(1280, 720),
):
    """Crea un video simple con una imagen de fondo (o color), el texto del título
    y el audio como pista principal. Guarda el resultado en `out_path`.
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    audio = AudioFileClip(audio_path)
    if duration is None:
        duration = audio.duration

    if image_path and os.path.exists(image_path):
        bg = ImageClip(image_path).with_duration(duration)
        bg = bg.resize(newsize=resolution)
    else:
        # Imagen en color sólido (blanco)
        bg = ColorClip(size=resolution, color=(255, 255, 255))

    # Renderizamos el título como imagen y lo usamos como ImageClip
    img_arr = render_text_image(
        title,
        resolution=resolution,
        font_size=48,
        color=(0, 0, 0),  # Black text
        bg_color=None,
        valign="bottom",
        bottom_margin=150,
    )
    txt_clip = ImageClip(img_arr).with_duration(duration).with_position((0, 0))

    video = CompositeVideoClip([bg, txt_clip]).with_duration(duration)
    video = video.with_audio(audio)
    video.write_videofile(out_path, fps=fps, codec="libx264", audio_codec="aac")


def create_video_with_subtitles(
    audio_path: str,
    subtitles: list,
    out_path: str,
    image_path: Optional[str] = None,
    fps: int = 24,
    resolution=(1280, 720),
    fontsize: int = 60,
    text_color: tuple = (255, 255, 255),
    bottom_margin: int = 140,
    gradient_palette: Optional[str] = None,
    add_particles: bool = True,
    num_particles: int = 40,
    fade_duration: float = 0.5,
):
    """Create a beautiful poetry video with gradient backgrounds, elegant text, and particles.

    Args:
        audio_path: Path to audio file
        subtitles: List of dicts [{"text": str, "start": float, "duration": float}, ...]
        out_path: Output video path
        image_path: Optional background image (if None, uses gradient)
        fps: Frames per second
        resolution: Video resolution (width, height)
        fontsize: Font size for text
        text_color: Text color as RGB tuple (default white)
        bottom_margin: Margin from bottom for text
        gradient_palette: Palette name for gradient ("sunset", "ocean", etc.) or None for random
        add_particles: Add floating particle overlay
        num_particles: Number of particles in overlay
        fade_duration: Duration of fade in/out effects in seconds
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    audio = AudioFileClip(audio_path)
    duration = audio.duration

    # Create beautiful gradient background or use provided image
    if image_path and os.path.exists(image_path):
        bg = ImageClip(image_path).with_duration(duration)
        bg = bg.resize(newsize=resolution)
    else:
        # Generate beautiful gradient background
        gradient_img = create_gradient_background(
            resolution=resolution,
            palette_name=gradient_palette,
            direction="diagonal",
            noise=True,
        )
        bg = ImageClip(gradient_img).with_duration(duration)

    # Create particle overlay
    clips_to_composite = [bg]

    if add_particles:
        particle_clip = make_particle_clip(
            duration=duration,
            resolution=resolution,
            fps=fps,
            num_particles=num_particles,
        )
        clips_to_composite.append(particle_clip)

    # Create elegant text clips with fade in/out using VideoClip
    text_clips = []
    for sub in subtitles:
        text = sub.get("text", "")
        start = float(sub.get("start", 0.0))
        dur = float(sub.get("duration", 0.0))
        if not text or dur <= 0:
            continue

        # Render elegant text with shadows (once)
        img_arr = render_text_image(
            text,
            resolution=resolution,
            font_size=fontsize,
            color=text_color,
            bg_color=None,  # Transparent background
            valign="center",
            bottom_margin=bottom_margin,
            shadow=True,
            elegant=False,
            youtube=True,
        )

        # Create a VideoClip with fade effect using opacity animation
        fade_dur_actual = min(
            fade_duration, dur / 4
        )  # Use parameter, but cap at 1/4 of duration

        def make_frame(t, img=img_arr, fade_dur=fade_dur_actual, total_dur=dur):
            """Generate frame with fade effect."""
            # Calculate opacity based on time
            if t < fade_dur:
                # Fade in
                opacity = t / fade_dur
            elif t > total_dur - fade_dur:
                # Fade out
                opacity = (total_dur - t) / fade_dur
            else:
                # Full opacity
                opacity = 1.0

            # Apply opacity to the image
            frame = img.copy()
            if frame.shape[2] == 4:  # RGBA
                frame[:, :, 3] = (frame[:, :, 3] * opacity).astype(np.uint8)
            else:  # RGB - shouldn't happen but handle it
                alpha = np.full(
                    (frame.shape[0], frame.shape[1], 1),
                    int(opacity * 255),
                    dtype=np.uint8,
                )
                frame = np.concatenate([frame, alpha], axis=2)

            return frame

        txt = (
            VideoClip(make_frame, duration=dur).with_start(start).with_position((0, 0))
        )
        text_clips.append(txt)

    # Composite all clips
    clips_to_composite.extend(text_clips)
    video = CompositeVideoClip(clips_to_composite).with_duration(duration)
    video = video.with_audio(audio)
    video.write_videofile(out_path, fps=fps, codec="libx264", audio_codec="aac")
