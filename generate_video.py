#!/usr/bin/env python3
"""
Markdown to Video Generator
Converts markdown files to videos with narration, images, and subtitles.
Supports Chinese and other languages with synchronized audio-subtitle timing.
Supports both images and videos in the media directory.
Supports both pyttsx3 (offline) and edge-tts (online) for text-to-speech.
"""

import os
import sys
import pyttsx3
import markdown
from bs4 import BeautifulSoup
from moviepy.editor import (
    VideoClip, AudioFileClip, ImageClip, VideoFileClip, concatenate_videoclips,
    concatenate_audioclips, CompositeVideoClip
)
import numpy as np
import argparse
import tempfile
import re
from PIL import Image, ImageDraw, ImageFont
import unicodedata
import sys
import asyncio
import subprocess
import shutil

os.environ["PATH"] += ";" + os.path.split(__file__)[0] + "\\ffmpeg\\bin"

# Try to import edge-tts
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    print("⚠️ edge-tts not available. Install with: pip install edge-tts")

_DISABLE_CHAR_TABLE = str.maketrans(
    '',
    '',
    ''.join(
        chr(i) for i in range(sys.maxunicode + 1)
        if not (
            unicodedata.category(chr(i)).startswith(('L', 'N', 'P', 'Z'))
            or unicodedata.category(chr(i)) in ('Sc', 'Sk')
        )
    )
)

def ensure_ffmpeg():
    """Make sure ffmpeg is installed and available in PATH."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH. Please install ffmpeg first.")


def srt_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp format: HH:MM:SS,mmm"""
    total_ms = int(round(seconds * 1000))
    hours = total_ms // 3600000
    total_ms %= 3600000
    minutes = total_ms // 60000
    total_ms %= 60000
    secs = total_ms // 1000
    millis = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_srt_file(subtitle_entries, srt_path):
    """
    subtitle_entries: list of dicts:
      {"start": float, "end": float, "text": str}
    """
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, sub in enumerate(subtitle_entries, 1):
            text = sub["text"].replace("\r\n", "\n").strip()
            f.write(f"{i}\n")
            f.write(f"{srt_timestamp(sub['start'])} --> {srt_timestamp(sub['end'])}\n")
            f.write(f"{text}\n\n")


def get_default_ffmpeg_font_name():
    """Pick a reasonable default subtitle font name by OS."""
    if sys.platform.startswith("win"):
        return "Microsoft YaHei"
    elif sys.platform == "darwin":
        return "PingFang SC"
    else:
        return "Noto Sans CJK SC"


def escape_ffmpeg_filter_path(path: str) -> str:
    """
    Escape a path for use inside ffmpeg filter expressions.
    Especially important on Windows.
    """
    path = os.path.abspath(path).replace("\\", "/")
    path = path.replace(":", r"\:")
    path = path.replace("'", r"\'")
    path = path.replace(",", r"\,")
    path = path.replace("[", r"\[")
    path = path.replace("]", r"\]")
    path = path.replace(";", r"\;")
    return path


def burn_subtitles_with_ffmpeg(
    video_input,
    audio_input,
    subtitle_input,
    output_file,
    fps=24,
    preset="veryfast",
    crf=23,
    font_name=None,
    font_size=36
):
    """Burn subtitles and mux audio using ffmpeg."""
    ensure_ffmpeg()

    if font_name is None:
        font_name = get_default_ffmpeg_font_name()

    escaped_sub = escape_ffmpeg_filter_path(subtitle_input)

    # libass style
    force_style = ",".join([
        f"FontName={font_name}",
        f"FontSize={font_size}",
        "PrimaryColour=&H00FFFFFF",   # white
        "OutlineColour=&H00000000",   # black outline
        "BackColour=&H80000000",      # semi-transparent black box
        "BorderStyle=3",
        "Outline=2",
        "Shadow=0",
        "Alignment=2",                # bottom-center
        "MarginV=40"
    ])

    vf = (
        f"subtitles='{escaped_sub}':charenc=UTF-8:"
        f"force_style='{force_style}'"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_input,
        "-i", audio_input,
        "-vf", vf,
        "-r", str(fps),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        output_file
    ]

    print("\n🚀 執行 FFmpeg:")
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)
    
def filter_text(text: str) -> str:
    return text.translate(_DISABLE_CHAR_TABLE)

def markdown_to_text(markdown_content):
    """Convert markdown to plain text (display mode, not raw)."""
    # Convert markdown to HTML
    html = markdown.markdown(markdown_content, extensions=['extra', 'nl2br'])
    # Parse HTML and extract text
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text()
    # Clean up extra whitespace
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()


def generate_audio_segment_pyttsx3(text, output_path, voice_id=None, rate=150):
    """Generate audio from text using pyttsx3 (offline)."""
    engine = pyttsx3.init()
    
    # Set voice if specified
    if voice_id is not None:
        try:
            engine.setProperty('voice', voice_id)
        except:
            pass
    
    # Set speech rate
    engine.setProperty('rate', rate)
    engine.setProperty('volume', 0.9)
    
    engine.save_to_file(text, output_path)
    engine.runAndWait()
    return output_path


async def generate_audio_segment_edge_tts_async(text, output_path, voice="zh-CN-XiaoxiaoNeural", rate="+0%"):
    """Generate audio from text using edge-tts (online, async)."""
    if not EDGE_TTS_AVAILABLE:
        raise RuntimeError("edge-tts is not installed. Install with: pip install edge-tts")
    
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_path)
    return output_path


def generate_audio_segment_edge_tts(text, output_path, voice="zh-CN-XiaoxiaoNeural", rate="+0%"):
    """Generate audio from text using edge-tts (online, synchronous wrapper)."""
    return asyncio.run(generate_audio_segment_edge_tts_async(text, output_path, voice, rate))


def generate_audio_segment(text, output_path, engine="pyttsx3", voice_id=None, rate=150):
    """
    Generate audio from text using specified TTS engine.
    
    Args:
        text: Text to convert to speech
        output_path: Path to save audio file
        engine: TTS engine to use ("pyttsx3" or "edge-tts")
        voice_id: Voice identifier (format depends on engine)
        rate: Speech rate (for pyttsx3: words per minute, for edge-tts: percentage like "+0%")
    """
    if engine == "edge-tts":
        if not EDGE_TTS_AVAILABLE:
            print("⚠️ edge-tts not available, falling back to pyttsx3")
            return generate_audio_segment_pyttsx3(text, output_path, voice_id, rate)
        
        # Convert rate from pyttsx3 format to edge-tts format if needed
        if isinstance(rate, int):
            # Convert rate (e.g., 150 -> 200 means faster)
            # Default is usually 150-200 for pyttsx3
            # For edge-tts: +0% is normal, +50% is faster, -50% is slower
            rate_percent = int((rate - 150) / 150 * 100)
            rate = f"+{rate_percent}%" if rate_percent >= 0 else f"{rate_percent}%"
        
        voice = voice_id if voice_id else "zh-CN-XiaoxiaoNeural"
        return generate_audio_segment_edge_tts(text, output_path, voice, rate)
    else:
        return generate_audio_segment_pyttsx3(text, output_path, voice_id, rate)


def get_available_voices_pyttsx3():
    """Get list of available pyttsx3 TTS voices."""
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        return voices
    except:
        return []


async def get_available_voices_edge_tts_async():
    """Get list of available edge-tts voices (async)."""
    if not EDGE_TTS_AVAILABLE:
        return []
    
    voices = await edge_tts.list_voices()
    return voices


def get_available_voices_edge_tts():
    """Get list of available edge-tts voices (synchronous wrapper)."""
    return asyncio.run(get_available_voices_edge_tts_async())


def list_voices(engine="pyttsx3"):
    """List all available voices for the specified engine."""
    print(f"\n{'='*60}")
    print(f"Available voices for {engine.upper()}")
    print(f"{'='*60}\n")
    
    if engine == "edge-tts":
        if not EDGE_TTS_AVAILABLE:
            print("❌ edge-tts is not installed. Install with: pip install edge-tts")
            return
        
        voices = get_available_voices_edge_tts()
        
        # Group by language
        voices_by_lang = {}
        for voice in voices:
            lang = voice["Locale"]
            if lang not in voices_by_lang:
                voices_by_lang[lang] = []
            voices_by_lang[lang].append(voice)
        
        # Display grouped voices
        for lang in sorted(voices_by_lang.keys()):
            print(f"\n{lang}:")
            for voice in voices_by_lang[lang]:
                gender = voice.get("Gender", "Unknown")
                name = voice["ShortName"]
                friendly_name = voice.get("FriendlyName", name)
                print(f"  • {name}")
                print(f"    Name: {friendly_name}")
                print(f"    Gender: {gender}")
        
        print(f"\n{'='*60}")
        print(f"Total: {len(voices)} voices")
        print(f"{'='*60}\n")
        
        # Show some popular Chinese voices
        print("\n🔥 Popular Chinese voices:")
        chinese_voices = [
            "zh-CN-XiaoxiaoNeural",  # Female
            "zh-CN-YunxiNeural",      # Male
            "zh-CN-YunyangNeural",    # Male
            "zh-CN-XiaoyiNeural",     # Female
            "zh-TW-HsiaoChenNeural",  # Female (Traditional Chinese)
            "zh-TW-YunJheNeural",     # Male (Traditional Chinese)
            "zh-HK-HiuGaaiNeural",    # Female (Cantonese)
            "zh-HK-WanLungNeural",    # Male (Cantonese)
        ]
        for voice_name in chinese_voices:
            matching = [v for v in voices if v["ShortName"] == voice_name]
            if matching:
                v = matching[0]
                print(f"  • {voice_name} ({v.get('Gender', 'Unknown')})")
    
    else:  # pyttsx3
        voices = get_available_voices_pyttsx3()
        
        if not voices:
            print("❌ No voices found for pyttsx3")
            return
        
        for i, voice in enumerate(voices, 1):
            print(f"{i}. {voice.name}")
            print(f"   ID: {voice.id}")
            print(f"   Languages: {voice.languages}")
            print()
        
        print(f"{'='*60}")
        print(f"Total: {len(voices)} voices")
        print(f"{'='*60}\n")


def load_media_files(media_dir):
    """Load all images and videos from directory."""
    if not media_dir or not os.path.exists(media_dir):
        return []
    
    image_formats = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')
    video_formats = ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv')
    
    media_files = []
    
    for filename in sorted(os.listdir(media_dir)):
        filepath = os.path.join(media_dir, filename)
        lower_filename = filename.lower()
        
        if lower_filename.endswith(image_formats):
            media_files.append(('image', filepath))
        elif lower_filename.endswith(video_formats):
            media_files.append(('video', filepath))
    
    return media_files


def create_black_frame(width=1920, height=1080):
    """Create a black frame as numpy array."""
    return np.zeros((height, width, 3), dtype=np.uint8)


def create_video_clip(media_files, media_duration, total_duration, resolution=(1920, 1080)):
    """Create video clip with switching images/videos or black screen (optimized)."""
    if not media_files:
        # Create black screen video using ImageClip (much faster than VideoClip with lambda)
        print("  建立黑色畫面影片...")
        black_frame = create_black_frame(resolution[0], resolution[1])
        return ImageClip(black_frame, duration=total_duration)
    
    print(f"  建立影片，包含 {len(media_files)} 個媒體檔案...")
    
    # Step 1: Pre-load and process all unique media files once (caching)
    print("  預處理媒體檔案...")
    processed_cache = {}
    
    for media_type, media_path in media_files:
        if media_path in processed_cache:
            continue
        
        try:
            if media_type == 'image':
                # Load image once as numpy array
                with Image.open(media_path) as img:
                    img_array = np.array(img.convert('RGB'))
                
                # Process image: resize and fit to resolution
                temp_clip = ImageClip(img_array)
                temp_clip = temp_clip.resize(height=resolution[1])
                
                # Adjust width
                if temp_clip.w > resolution[0]:
                    temp_clip = temp_clip.crop(
                        x_center=temp_clip.w/2,
                        width=resolution[0],
                        height=resolution[1]
                    )
                elif temp_clip.w < resolution[0]:
                    temp_clip = temp_clip.on_color(
                        size=resolution,
                        color=(0, 0, 0),
                        pos='center'
                    )
                
                # Store processed frame as numpy array for fast reuse
                processed_frame = temp_clip.get_frame(0)
                processed_cache[media_path] = ('image', processed_frame)
                
            else:  # video
                # Load and process video once
                video_clip = VideoFileClip(media_path)
                video_clip = video_clip.resize(height=resolution[1])
                
                # Adjust width
                if video_clip.w > resolution[0]:
                    video_clip = video_clip.crop(
                        x_center=video_clip.w/2,
                        width=resolution[0],
                        height=resolution[1]
                    )
                elif video_clip.w < resolution[0]:
                    video_clip = video_clip.on_color(
                        size=resolution,
                        color=(0, 0, 0),
                        pos='center'
                    )
                
                # Store processed video clip
                processed_cache[media_path] = ('video', video_clip)
                
        except Exception as e:
            print(f"  ⚠️ 無法載入媒體 {os.path.basename(media_path)}: {e}")
            black_frame = create_black_frame(resolution[0], resolution[1])
            processed_cache[media_path] = ('image', black_frame)
    
    # Step 2: Pre-calculate all clips needed
    num_clips = int(np.ceil(total_duration / media_duration))
    clips = []
    
    print(f"  組合 {num_clips} 個片段...")
    
    for i in range(num_clips):
        current_time = i * media_duration
        clip_duration = min(media_duration, total_duration - current_time)
        
        media_type, media_path = media_files[i % len(media_files)]
        
        if media_path not in processed_cache:
            # Fallback to black frame
            black_frame = create_black_frame(resolution[0], resolution[1])
            clip = ImageClip(black_frame, duration=clip_duration)
        else:
            cached_type, cached_data = processed_cache[media_path]
            
            if cached_type == 'image':
                # Create clip from cached numpy array
                clip = ImageClip(cached_data, duration=clip_duration)
            else:  # video
                video_clip = cached_data
                
                if video_clip.duration < clip_duration:
                    # Loop video if needed
                    num_loops = int(np.ceil(clip_duration / video_clip.duration))
                    clip = concatenate_videoclips([video_clip] * num_loops)
                    clip = clip.subclip(0, clip_duration)
                else:
                    clip = video_clip.subclip(0, min(clip_duration, video_clip.duration))
                
                clip = clip.set_duration(clip_duration)
        
        clips.append(clip)
    
    return concatenate_videoclips(clips)


def get_chinese_font(fontsize=36):
    """Get a font that supports Chinese characters."""
    # Font options with Chinese support
    font_options = [
        # Windows fonts
        'C:\\Windows\\Fonts\\msyh.ttc',      # Microsoft YaHei
        'C:\\Windows\\Fonts\\msyhbd.ttc',    # Microsoft YaHei Bold
        'C:\\Windows\\Fonts\\simhei.ttf',    # SimHei
        'C:\\Windows\\Fonts\\simsun.ttc',    # SimSun
        'C:\\Windows\\Fonts\\simkai.ttf',    # KaiTi
        'C:\\Windows\\Fonts\\kaiu.ttf',      # DFKai-SB
        'C:\\Windows\\Fonts\\msjh.ttc',      # Microsoft JhengHei (Traditional Chinese)
        'C:\\Windows\\Fonts\\msjhbd.ttc',    # Microsoft JhengHei Bold
        # macOS fonts
        '/System/Library/Fonts/PingFang.ttc',
        '/System/Library/Fonts/STHeiti Medium.ttc',
        '/System/Library/Fonts/Hiragino Sans GB.ttc',
        # Linux fonts
        '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/arphic/uming.ttc',
        # Also try regular fonts for fallback
        'arial.ttf',
        'C:\\Windows\\Fonts\\arial.ttf',
    ]
    
    for font_path in font_options:
        try:
            font = ImageFont.truetype(font_path, fontsize)
            # Test if font supports Chinese
            test_img = Image.new('RGB', (100, 100))
            test_draw = ImageDraw.Draw(test_img)
            try:
                test_draw.text((0, 0), "測試Test", font=font)
                print(f"  ✓ 使用字體: {os.path.basename(font_path)}")
                return font
            except:
                continue
        except Exception as e:
            continue
    
    # Fallback to default
    print("  ⚠️ 未找到中文字體，使用預設字體（中文可能無法顯示）")
    return ImageFont.load_default()


def get_text_width(text, font, draw):
    """Get the width of text."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def wrap_text_multilingual(text, max_width, font, draw):
    """Wrap text to fit within max_width, supporting both English and Chinese."""
    lines = []
    
    # Split by explicit line breaks first
    paragraphs = text.split('\n')
    
    for paragraph in paragraphs:
        if not paragraph.strip():
            continue
            
        current_line = ""
        
        # For mixed Chinese/English text, process character by character
        i = 0
        while i < len(paragraph):
            char = paragraph[i]
            
            # Try adding this character
            test_line = current_line + char
            width = get_text_width(test_line, font, draw)
            
            if width <= max_width:
                current_line += char
            else:
                # Line is full
                if current_line:
                    lines.append(current_line.strip())
                    current_line = char
                else:
                    # Single character is too wide (shouldn't happen normally)
                    lines.append(char)
                    current_line = ""
            
            i += 1
        
        # Add remaining text
        if current_line.strip():
            lines.append(current_line.strip())
    
    return lines


def split_text_for_subtitles(text, max_chars=80):
    """
    Split text into subtitle segments.
    Considers sentence endings, commas, and length limits.
    Supports both English and Chinese punctuation.
    """
    # Define split characters (both English and Chinese)
    # Priority 1: End of sentence
    major_splits = r'[.!?。！？]'
    # Priority 2: Commas and other pauses
    minor_splits = r'[,;，；、]'
    
    segments = []
    current_segment = ""
    
    # First, split by major punctuation
    parts = re.split(f'({major_splits})', text)
    
    i = 0
    while i < len(parts):
        part = parts[i]
        
        # If this is punctuation, add it to the previous part
        if re.match(major_splits, part) and current_segment:
            current_segment += part
            
            # If segment is complete, add it
            if len(current_segment.strip()) > 0:
                if len(current_segment) <= max_chars:
                    segments.append(current_segment.strip())
                    current_segment = ""
                else:
                    # Segment too long, try to split by commas
                    sub_parts = re.split(f'({minor_splits})', current_segment)
                    temp_segment = ""
                    
                    for j, sub_part in enumerate(sub_parts):
                        if len(temp_segment + sub_part) <= max_chars:
                            temp_segment += sub_part
                        else:
                            if temp_segment.strip():
                                segments.append(temp_segment.strip())
                            temp_segment = sub_part
                    
                    if temp_segment.strip():
                        segments.append(temp_segment.strip())
                    current_segment = ""
        else:
            # Regular text part
            if len(current_segment + part) <= max_chars:
                current_segment += part
            else:
                # Too long, split it
                if current_segment.strip():
                    segments.append(current_segment.strip())
                
                # Handle the long part
                remaining = part
                while len(remaining) > max_chars:
                    # Try to split by comma first
                    comma_split = re.split(f'({minor_splits})', remaining[:max_chars])
                    if len(comma_split) > 1:
                        # Found comma, split there
                        split_point = len(''.join(comma_split[:-1]))
                        segments.append(remaining[:split_point].strip())
                        remaining = remaining[split_point:]
                    else:
                        # No comma, just split at max_chars
                        segments.append(remaining[:max_chars].strip())
                        remaining = remaining[max_chars:]
                
                current_segment = remaining
        
        i += 1
    
    # Add any remaining text
    if current_segment.strip():
        segments.append(current_segment.strip())
    
    # Filter out empty segments
    segments = [s for s in segments if s.strip()]
    
    return segments


def create_subtitle_image(text, resolution=(1920, 1080), fontsize=36):
    """Create a subtitle image using PIL with Chinese support."""
    width, height = resolution
    
    # Create transparent image
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Get font with Chinese support
    font = get_chinese_font(fontsize)
    
    # Wrap text
    max_text_width = width - 100
    lines = wrap_text_multilingual(text, max_text_width, font, draw)
    
    # Calculate text height
    line_height = fontsize + 10
    total_text_height = len(lines) * line_height
    
    # Draw background rectangle
    padding = 20
    bg_y = height - total_text_height - padding * 2 - 50
    draw.rectangle(
        [(0, bg_y), (width, height)],
        fill=(0, 0, 0, 180)
    )
    
    # Draw text lines
    y = bg_y + padding
    for line in lines:
        text_width = get_text_width(line, font, draw)
        x = (width - text_width) // 2
        
        # Draw text with outline for better visibility
        outline_color = (0, 0, 0, 255)
        for offset_x, offset_y in [(-2,-2), (-2,2), (2,-2), (2,2)]:
            draw.text((x+offset_x, y+offset_y), line, font=font, fill=outline_color)
        
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_height
    
    # Convert to numpy array
    return np.array(img)

def generate_audio_and_subtitles(
    text_segments, 
    resolution=(1920, 1080), 
    engine="pyttsx3",
    voice_id=None, 
    rate=150, 
    progress_callback=None
):
    """
    Generate audio for each text segment and collect subtitle timing.
    Returns:
      audio_clips, subtitle_entries, temp_files
    """
    audio_clips = []
    subtitle_entries = []
    current_time = 0
    temp_files = []
    
    print(f"  正在為 {len(text_segments)} 個片段生成音訊和字幕...")
    print(f"  使用 TTS 引擎: {engine}")
    if voice_id:
        print(f"  使用語音: {voice_id}")
    
    for i, segment in enumerate(text_segments):
        preview = segment[:50] + "..." if len(segment) > 50 else segment
        print(f"    [{i+1}/{len(text_segments)}] {preview}")
        
        if progress_callback:
            progress_callback(i + 1, len(text_segments), f"生成片段 {i+1}/{len(text_segments)}")
        
        try:
            suffix = '.mp3' if engine == "edge-tts" else '.wav'
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_audio:
                audio_path = temp_audio.name
                temp_files.append(audio_path)
            
            generate_audio_segment(segment, audio_path, engine, voice_id, rate)
            
            audio_clip = AudioFileClip(audio_path)
            segment_duration = audio_clip.duration

            subtitle_entries.append({
                "start": current_time,
                "end": current_time + segment_duration,
                "text": segment
            })
            
            audio_clips.append(audio_clip)
            
            print(f"        時長: {segment_duration:.2f}秒, 開始: {current_time:.2f}秒")
            current_time += segment_duration
            
        except Exception as e:
            print(f"  ⚠️ 警告: 無法建立片段 {i+1}: {e}")
            import traceback
            traceback.print_exc()
    
    return audio_clips, subtitle_entries, temp_files


def generate_video_from_markdown(
    markdown_file,
    output_file,
    media_dir=None,
    media_duration=5,
    resolution=(1920, 1080),
    max_subtitle_chars=80,
    tts_engine="pyttsx3",
    voice_id=None,
    speech_rate=150,
    progress_callback=None
):
    """
    Generate a video from markdown with images/videos and narration.
    
    Args:
        markdown_file: Path to markdown file or markdown text content
        output_file: Path to output MP4 file
        media_dir: Directory containing images/videos (optional)
        media_duration: Duration to show each media in seconds
        resolution: Video resolution as (width, height) tuple
        max_subtitle_chars: Maximum characters per subtitle segment
        tts_engine: TTS engine to use ("pyttsx3" or "edge-tts")
        voice_id: TTS voice ID (optional)
        speech_rate: Speech rate (default 150)
        progress_callback: Callback function(current, total, message)
    """
    print("\n" + "="*60)
    print("MARKDOWN TO VIDEO GENERATOR")
    print("="*60 + "\n")
    
    # Read markdown file or use as text
    print("📄 讀取 Markdown 檔案...")
    try:
        if os.path.isfile(markdown_file):
            with open(markdown_file, 'r', encoding='utf-8') as f:
                markdown_content = f.read()
        else:
            # Treat as markdown content
            markdown_content = markdown_file
    except Exception as e:
        print(f"❌ 錯誤: {e}")
        return False
    
    # Convert to text
    print("📝 將 Markdown 轉換為文字...")
    text = markdown_to_text(markdown_content)
    text = filter_text(text)
    print(f"\n文字預覽:\n{'-'*60}\n{text[:200]}...\n{'-'*60}\n")
    
    # Split text into subtitle segments
    print("\n✂️ 分割文字為字幕片段...")
    text_segments = split_text_for_subtitles(text, max_chars=max_subtitle_chars)
    print(f"  ✓ 建立了 {len(text_segments)} 個片段")
    
    # Generate audio and subtitles for each segment
    print("\n🔊 生成同步的音訊和字幕...")
    audio_clips, subtitle_entries, temp_files = generate_audio_and_subtitles(
        text_segments, 
        resolution,
        tts_engine,
        voice_id,
        speech_rate,
        progress_callback
    )
    
    if not audio_clips:
        print("❌ 錯誤: 未生成音訊片段！")
        return False
    
    # Concatenate all audio clips
    print("\n🎵 合併音訊片段...")
    final_audio = concatenate_audioclips(audio_clips)
    total_duration = final_audio.duration
    print(f"  ✓ 總音訊時長: {total_duration:.2f} 秒")
    
    # Load media files
    print("\n🖼️ 載入媒體檔案...")
    media_files = load_media_files(media_dir)
    if media_files:
        print(f"  ✓ 從 '{media_dir}' 載入了 {len(media_files)} 個媒體檔案")
        for idx, (media_type, path) in enumerate(media_files, 1):
            print(f"    {idx}. [{media_type}] {os.path.basename(path)}")
    else:
        print("  ℹ️ 未找到媒體檔案，使用黑色畫面")
    
    # Create video clip
    print("\n🎬 建立影片...")
    try:
        video_clip = create_video_clip(media_files, media_duration, total_duration, resolution)
        print("  ✓ 影片片段已建立")
    except Exception as e:
        print(f"❌ 建立影片片段時發生錯誤: {e}")
        final_audio.close()
        for clip in audio_clips:
            clip.close()
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        return False
    
    # Render background video + audio separately, then let ffmpeg burn subtitles
    print(f"\n💾 寫入影片到 '{output_file}'...")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_video = os.path.join(tmpdir, "background.mp4")
            temp_audio = os.path.join(tmpdir, "narration.m4a")
            temp_srt = os.path.join(tmpdir, "subtitles.srt")

            print("\n🎬 第 1 步：輸出無字幕背景影片...")
            video_clip.write_videofile(
                temp_video,
                fps=24,
                codec='libx264',
                audio=False,
                preset='ultrafast',
                threads=4
            )

            print("\n🎵 第 2 步：輸出旁白音訊...")
            final_audio.write_audiofile(
                temp_audio,
                fps=44100,
                codec='aac',
                bitrate='192k'
            )

            print("\n📝 第 3 步：建立字幕檔...")
            write_srt_file(subtitle_entries, temp_srt)

            print("\n🚀 第 4 步：使用 FFmpeg 燒錄字幕並合成音訊...")
            burn_subtitles_with_ffmpeg(
                video_input=temp_video,
                audio_input=temp_audio,
                subtitle_input=temp_srt,
                output_file=output_file,
                fps=24,
                preset='veryfast',   # or ultrafast
                crf=23,
                font_name=get_default_ffmpeg_font_name(),
                font_size=36
            )

    except Exception as e:
        print(f"❌ 寫入影片時發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print("\n🧹 清理...")
        final_audio.close()
        video_clip.close()
        for clip in audio_clips:
            clip.close()
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
    
    print(f"\n✅ 影片生成成功！")
    print(f"📁 輸出: {os.path.abspath(output_file)}")
    print(f"📊 時長: {total_duration:.2f}秒 | 解析度: {resolution[0]}x{resolution[1]}")
    print(f"📝 片段: {len(text_segments)} 個字幕/音訊片段")
    print(f"🎤 TTS 引擎: {tts_engine}")
    print("\n" + "="*60 + "\n")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description='從 Markdown 生成包含圖片/影片和旁白的影片',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  # 使用 pyttsx3 (離線):
  %(prog)s document.md
  %(prog)s document.md -o output.mp4 -i ./images -d 3
  
  # 使用 edge-tts (線上，更好的語音品質):
  %(prog)s document.md --engine edge-tts
  %(prog)s document.md --engine edge-tts --voice zh-CN-XiaoxiaoNeural
  %(prog)s document.md --engine edge-tts --voice zh-CN-YunxiNeural --rate +20%%
  
  # 列出可用的語音:
  %(prog)s --list-voices
  %(prog)s --list-voices --engine edge-tts
  
  # 其他選項:
  %(prog)s document.md --images ./media --duration 7 --resolution 1280x720
  %(prog)s document.md -m 60  # 每個字幕最多 60 個字元
        """
    )
    
    parser.add_argument(
        'markdown_file',
        nargs='?',
        help='Markdown 檔案路徑'
    )
    parser.add_argument(
        '-o', '--output',
        default='output.mp4',
        help='輸出影片檔案 (預設: output.mp4)'
    )
    parser.add_argument(
        '-i', '--images',
        help='包含圖片/影片的目錄 (選填，如未提供則使用黑色畫面)'
    )
    parser.add_argument(
        '-d', '--duration',
        type=float,
        default=5.0,
        help='每個媒體顯示的時長（秒） (預設: 5.0)'
    )
    parser.add_argument(
        '-r', '--resolution',
        default='1920x1080',
        help='影片解析度，格式為 寬x高 (預設: 1920x1080)'
    )
    parser.add_argument(
        '-m', '--max-chars',
        type=int,
        default=80,
        help='每個字幕片段的最大字元數 (預設: 80)'
    )
    parser.add_argument(
        '--engine',
        choices=['pyttsx3', 'edge-tts'],
        default='pyttsx3',
        help='TTS 引擎 (預設: pyttsx3)'
    )
    parser.add_argument(
        '--voice',
        '--voice-id',
        dest='voice_id',
        type=str,
        default=None,
        help='語音 ID (pyttsx3 使用系統語音 ID, edge-tts 使用如 "zh-CN-XiaoxiaoNeural")'
    )
    parser.add_argument(
        '--rate',
        type=str,
        default='150',
        help='語速 (pyttsx3: 數字如 150, edge-tts: 百分比如 +20%% 或 -10%%) (預設: 150)'
    )
    parser.add_argument(
        '--list-voices',
        action='store_true',
        help='列出可用的語音並退出'
    )
    
    args = parser.parse_args()
    
    # List voices mode
    if args.list_voices:
        list_voices(args.engine)
        return
    
    # Check if markdown file is provided
    if not args.markdown_file:
        parser.error("markdown_file is required when not using --list-voices")
    
    # Parse resolution
    try:
        width, height = map(int, args.resolution.split('x'))
        resolution = (width, height)
    except:
        print("⚠️ 解析度格式無效。使用預設 1920x1080")
        resolution = (1920, 1080)
    
    # Parse rate
    if args.engine == "edge-tts":
        # For edge-tts, keep as string (e.g., "+20%" or "-10%")
        if '%' not in args.rate:
            # If user provided a number, convert it
            try:
                rate_num = int(args.rate)
                rate_percent = int((rate_num - 150) / 150 * 100)
                rate = f"+{rate_percent}%" if rate_percent >= 0 else f"{rate_percent}%"
            except:
                rate = "+0%"
        else:
            rate = args.rate
    else:
        # For pyttsx3, convert to int
        try:
            rate = int(args.rate.replace('%', ''))
        except:
            rate = 150
    
    # Set default voice for edge-tts if not specified
    voice_id = args.voice_id
    if args.engine == "edge-tts" and not voice_id:
        voice_id = "zh-CN-XiaoxiaoNeural"
        print(f"ℹ️ 使用預設 edge-tts 語音: {voice_id}")
    
    # Generate video
    success = generate_video_from_markdown(
        markdown_file=args.markdown_file,
        output_file=args.output,
        media_dir=args.images,
        media_duration=args.duration,
        resolution=resolution,
        max_subtitle_chars=args.max_chars,
        tts_engine=args.engine,
        voice_id=voice_id,
        speech_rate=rate,
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()