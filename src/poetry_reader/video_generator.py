import os


from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.VideoClip import ImageClip, ColorClip, VideoClip
from moviepy.video.VideoClip import TextClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip


from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import textwrap
import numpy as np
from .background_generator import create_gradient_background, create_zoomed_background
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


def _wrap_text(text: str, draw_obj, font, max_width: int, max_lines: Optional[int]):
    words = text.split()
    if not words:
        return [text]

    lines = []
    current = []

    for word in words:
        if not current:
            current = [word]
            continue

        candidate = " ".join(current + [word])
        if _measure_text(draw_obj, candidate, font)[0] <= max_width:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]

    if current:
        lines.append(" ".join(current))

    if max_lines and len(lines) > max_lines:
        kept = lines[: max_lines - 1]
        remaining = " ".join(lines[max_lines - 1 :])
        kept.append(remaining)
        lines = kept

        if _measure_text(draw_obj, lines[-1], font)[0] > max_width:
            avg_char_width = _measure_text(draw_obj, "A", font)[0]
            chars_per_line = max(10, max_width // max(1, avg_char_width))
            lines = textwrap.wrap(text, width=chars_per_line, break_long_words=False)

    return lines


def render_text_image(
    text: str,
    resolution: tuple,
    font_size: int = 70,
    color: tuple = (255, 255, 255),
    bg_color: Optional[str] = None,
    padding: int = 80,
    valign: str = "center",
    bottom_margin: int = 180,
    shadow: bool = True,
    elegant: bool = True,
    youtube: bool = False,
    tiktok: bool = True,
    stroke_width: Optional[int] = None,
) -> np.ndarray:
    """Render text for video overlays.

    When `youtube=True` the function prefers bold, highly legible sans-serif
    fonts and draws a dark stroke around the text for good readability on
    YouTube thumbnails and videos.

    When `tiktok=True` optimizes for mobile viewing with larger fonts,
    stronger stroke, and modern bold fonts.
    """
    width, height = resolution

    # Select font list depending on style preference
    font = None

    # TikTok optimized fonts - modern, bold, mobile-friendly
    if tiktok:
        tiktok_fonts = [
            "Montserrat-Bold.ttf",
            "Montserrat-ExtraBold.ttf",
            "Poppins-Bold.ttf",
            "Poppins-ExtraBold.ttf",
            "Roboto-Bold.ttf",
            "Roboto-Black.ttf",
            "Inter-Bold.ttf",
            "Inter-ExtraBold.ttf",
            "Nunito-Bold.ttf",
            "Nunito-ExtraBold.ttf",
            "Oswald-Bold.ttf",
            "BebasNeue-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
        for f in tiktok_fonts:
            try:
                font = ImageFont.truetype(f, font_size)
                break
            except Exception:
                continue

    if font is None and youtube:
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
    max_width = width - padding * 2
    max_lines = 2 if tiktok else None
    lines = _wrap_text(text, tmp_draw, font, max_width, max_lines)

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

    # Stroke/outline for YouTube or TikTok readability
    if stroke_width is None:
        if tiktok:
            stroke_width = max(2, int(font_size * 0.08))  # Stronger stroke for TikTok
        elif youtube:
            stroke_width = max(1, int(font_size * 0.06))
        else:
            stroke_width = 0
    stroke_fill = (0, 0, 0)

    for line in lines:
        w, h = _measure_text(draw, line, font)
        x = (width - w) // 2

        # Draw shadow/glow effect
        if shadow:
            if tiktok:
                # Multi-layer shadow for depth on TikTok
                for offset in range(4, 0, -1):
                    alpha = int(100 - offset * 20)
                    shadow_color = (0, 0, 0, alpha) if bg_color is None else (0, 0, 0)
                    draw.text(
                        (x + offset, y + offset), line, font=font, fill=shadow_color
                    )
            elif not youtube:
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
    title: Optional[str] = None,
    author: Optional[str] = None,
    image_path: Optional[str] = None,
    fps: int = 30,
    resolution=(1080, 1920),  # TikTok vertical format by default
    fontsize: int = 80,  # Larger for TikTok
    text_color: tuple = (255, 255, 255),
    bottom_margin: int = 200,  # More space for TikTok
    gradient_palette: Optional[str] = None,
    add_particles: bool = True,
    num_particles: int = 60,  # More particles for visual impact
    fade_duration: float = 0.5,
    tiktok_mode: bool = True,
    text_animation: str = "fade",  # Options: fade, typewriter, bounce, scale
    zoom_background: bool = True,  # Add subtle zoom to background
    add_sparkles: bool = True,  # Add sparkle effects
):
    """Create a beautiful poetry video optimized for TikTok.

    Args:
        audio_path: Path to audio file
        subtitles: List of dicts [{"text": str, "start": float, "duration": float}, ...]
        out_path: Output video path
        title: Optional poem title for header
        author: Optional author name for header
        image_path: Optional background image (if None, uses gradient)
        fps: Frames per second (default 30 for smooth TikTok)
        resolution: Video resolution (default 1080x1920 for TikTok vertical)
        fontsize: Font size for text (default 80 for mobile readability)
        text_color: Text color as RGB tuple (default white)
        bottom_margin: Margin from bottom for text
        gradient_palette: Palette name for gradient ("sunset", "ocean", etc.) or None for random
        add_particles: Add floating particle overlay
        num_particles: Number of particles in overlay
        fade_duration: Duration of fade in/out effects in seconds
        tiktok_mode: Enable TikTok optimizations (fonts, stroke, effects)
        text_animation: Animation style for text (fade, typewriter, bounce, scale)
        zoom_background: Add subtle zoom/pan to background
        add_sparkles: Add sparkle/light effects
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    audio = AudioFileClip(audio_path)
    duration = audio.duration

    # Create beautiful gradient background or use provided image
    if image_path and os.path.exists(image_path):
        if zoom_background:
            # Create zoom/pan effect for image background (Ken Burns style)
            img = Image.open(image_path)
            zoom_factor = 1.15
            big_width = int(resolution[0] * zoom_factor)
            big_height = int(resolution[1] * zoom_factor)
            img_resized = img.resize((big_width, big_height), Image.Resampling.LANCZOS)

            def make_frame(t):
                # Slowly pan upward over the duration
                progress = t / duration
                # Start at bottom, move to top
                y_offset = int((big_height - resolution[1]) * (1 - progress))
                x_offset = (big_width - resolution[0]) // 2  # Center horizontally
                cropped = img_resized.crop(
                    (
                        x_offset,
                        y_offset,
                        x_offset + resolution[0],
                        y_offset + resolution[1],
                    )
                )
                return np.array(cropped)

            bg = VideoClip(make_frame, duration=duration)
        else:
            bg = ImageClip(image_path).with_duration(duration)
            bg = bg.resize(newsize=resolution)
    else:
        if zoom_background:
            # Create zoomed gradient background with pan effect (Ken Burns style)
            zoom_factor = 1.15
            big_img = create_zoomed_background(
                resolution=resolution,
                palette_name=gradient_palette,
                zoom_factor=zoom_factor,
                pan_direction="up",
            )

            def make_frame(t):
                # Slowly pan upward over the duration
                progress = t / duration
                width, height = resolution
                big_width = int(width * zoom_factor)
                big_height = int(height * zoom_factor)
                # Start at bottom, move to top
                y_offset = int((big_height - height) * (1 - progress))
                x_offset = (big_width - width) // 2  # Center horizontally
                cropped = big_img.crop(
                    (x_offset, y_offset, x_offset + width, y_offset + height)
                )
                return np.array(cropped)

            bg = VideoClip(make_frame, duration=duration)
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
            add_sparkles=add_sparkles,
        )
        clips_to_composite.append(particle_clip)

    header_text = None
    if title and author:
        header_text = f"{title} — {author}"
    elif title:
        header_text = title
    elif author:
        header_text = author

    if header_text:
        header_padding = int(resolution[0] * 0.08) if tiktok_mode else 80
        header_font_size = max(36, int(fontsize * 0.55))
        header_img = render_text_image(
            header_text,
            resolution=resolution,
            font_size=header_font_size,
            color=text_color,
            bg_color=None,
            padding=header_padding,
            valign="top",
            shadow=True,
            elegant=False,
            youtube=False,
            tiktok=tiktok_mode,
        )
        header_clip = (
            ImageClip(header_img).with_duration(duration).with_position((0, 0))
        )
        clips_to_composite.append(header_clip)

    # Create elegant text clips with fade in/out using VideoClip
    text_clips = []
    for sub in subtitles:
        text = sub.get("text", "")
        start = float(sub.get("start", 0.0))
        dur = float(sub.get("duration", 0.0))
        if not text or dur <= 0:
            continue

        # Render text optimized for TikTok
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
            youtube=False,
            tiktok=tiktok_mode,
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
