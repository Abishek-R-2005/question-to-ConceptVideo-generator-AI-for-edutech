import os
import io
import json
import hashlib
import tempfile
from typing import List, Dict, Any, Tuple

import streamlit as st

from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS
from pydub import AudioSegment
import numpy as np

import moviepy.editor as mpe

# --- START OF FIX: Corrected MoviePy audio speed change import ---
# Access the audio speedx function directly from the audio fx submodule
# For stability, we import the core moviepy modules and rename the function.
try:
    from moviepy.audio.fx import speedx
    audio_speedx = speedx
except ImportError:
    # Fallback to the vfx/afx container from moviepy.editor if structure is different
    try:
        audio_speedx = mpe.afx.speedx
    except AttributeError:
        # Final fallback - this should rarely be hit if moviepy is correctly installed
        def audio_speedx(clip, factor):
            return clip.fx(mpe.vfx.speedx, factor) # Revert to video speedx which handles audio too
# --- END OF FIX ---


# Optional .env support
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _safe_filename(name: str) -> str:
    keep = [c if c.isalnum() or c in ("-", "_") else "-" for c in name.strip()]
    collapsed = "".join(keep)
    return collapsed[:120] or "output"


def _hex_color_from_text(text: str) -> str:
    digest = hashlib.md5(text.encode("utf-8")).hexdigest()
    r = (int(digest[0:2], 16) + 64) // 2
    g = (int(digest[2:4], 16) + 96) // 2
    b = (int(digest[4:6], 16) + 128) // 2
    return f"#{r:02x}{g:02x}{b:02x}"


def _parse_color(value: str, fallback_seed: str) -> str:
    if isinstance(value, str) and value.startswith("#") and len(value) in (4, 7):
        return value
    return _hex_color_from_text(fallback_seed)


def _wrap_text(text: str, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont, max_width: int) -> List[str]:
    words = text.split()
    lines: List[str] = []
    current = []
    
    # Helper function to get text size using the modern method
    def get_text_size(txt, f):
        # Calculate bounding box (left, top, right, bottom)
        bbox = draw.textbbox(xy=(0, 0), text=txt, font=f)
        return bbox[2] - bbox[0], bbox[3] - bbox[1] # width, height

    for word in words:
        trial = (" ".join(current + [word])).strip()
        w, _ = get_text_size(trial, font) 
        
        if w <= max_width or not current:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines


def build_slide_image(
    title: str,
    bullet_text: str,
    color: str,
    size: Tuple[int, int] = (1280, 720),
) -> Image.Image:
    width, height = size
    img = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(img)

    try:
        title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 60)
        body_font = ImageFont.truetype("DejaVuSans.ttf", 36)
    except Exception:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()

    # Helper function to get text size using the modern method
    def get_text_size(txt, f):
        # Returns (left, top, right, bottom)
        bbox = draw.textbbox(xy=(0, 0), text=txt, font=f)
        return bbox[2] - bbox[0], bbox[3] - bbox[1] # width, height

    title = title[:160]
    
    title_w, title_h = get_text_size(title, title_font)
    
    title_x = (width - title_w) // 2
    title_y = 60

    margin_x = 120
    box_width = width - 2 * margin_x
    lines = _wrap_text(bullet_text, draw, body_font, box_width)
    
    line_h = get_text_size("Ag", body_font)[1] + 8
    
    text_y = title_y + title_h + 40

    overlay_top = text_y - 20
    overlay_bottom = min(height - 60, overlay_top + min(12, len(lines)) * line_h + 40)
    overlay = Image.new("RGBA", (width - 80, overlay_bottom - overlay_top), (0, 0, 0, 80))
    img.paste(overlay, (40, overlay_top), overlay)

    draw.text((title_x, title_y), title, font=title_font, fill=(255, 255, 255))
    y = text_y
    for ln in lines[:14]:
        draw.text((margin_x, y), ln, font=body_font, fill=(255, 255, 255))
        y += line_h

    return img


def estimate_duration_seconds_for_text(text: str, words_per_minute: int = 150) -> float:
    words = max(1, len(text.strip().split()))
    return 60.0 * words / float(words_per_minute)


def tts_generate_segments(segments: List[Dict[str, Any]], language_code: str, tmp_dir: str) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for idx, seg in enumerate(segments):
        narration = seg.get("narration", "").strip() or seg.get("text", "").strip()
        title = seg.get("title", f"Segment {idx+1}")
        filename = _safe_filename(f"seg_{idx+1}_{title}") + ".mp3"
        out_path = os.path.join(tmp_dir, filename)
        try:
            tts = gTTS(text=narration, lang=language_code)
            tts.save(out_path)
            audio = AudioSegment.from_file(out_path)
            duration = len(audio) / 1000.0
        except Exception:
            duration = estimate_duration_seconds_for_text(narration)
            silent = AudioSegment.silent(duration=max(1000, int(duration * 1000)))
            silent.export(out_path, format="mp3")
            duration = len(silent) / 1000.0
        results.append({"path": out_path, "duration_s": duration})
    return results


def compose_video(
    segments: List[Dict[str, Any]],
    audio_infos: List[Dict[str, Any]],
    out_path: str,
    target_total_seconds: float = 120.0,
    size: Tuple[int, int] = (1280, 720),
) -> None:
    clips = []
    total_audio = sum(a["duration_s"] for a in audio_infos)
    speed_factor = max(0.5, min(2.0, total_audio / target_total_seconds)) if total_audio > 0 else 1.0

    for idx, (seg, ainfo) in enumerate(zip(segments, audio_infos)):
        title = seg.get("title", f"Segment {idx+1}")
        narration = seg.get("narration", seg.get("text", ""))
        visual = seg.get("visual", "")
        color = _parse_color(seg.get("color", ""), title + visual)

        bullet_text = narration
        img = build_slide_image(title=title, bullet_text=bullet_text, color=color, size=size)
        frame = np.array(img)

        img_clip = mpe.ImageClip(frame)

        audio_clip = mpe.AudioFileClip(ainfo["path"]) if os.path.exists(ainfo["path"]) else None
        if audio_clip is not None and speed_factor != 1.0:
            # This calls the globally defined audio_speedx function
            audio_clip = audio_speedx(audio_clip, speed_factor)

        if audio_clip is not None:
            duration = max(1.0, audio_clip.duration)
            clip = img_clip.set_duration(duration).set_audio(audio_clip)
        else:
            est = estimate_duration_seconds_for_text(narration)
            duration = max(1.0, est / speed_factor)
            clip = img_clip.set_duration(duration)

        clips.append(clip)

    if not clips:
        raise RuntimeError("No clips to compose.")

    video = mpe.concatenate_videoclips(clips, method="compose")

    if video.duration > target_total_seconds * 1.05:
        factor = video.duration / target_total_seconds
        try:
            video = video.fx(mpe.vfx.speedx, factor)
        except AttributeError:
            video = video.speedx(factor)

    video.write_videofile(
        out_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=os.path.join(os.path.dirname(out_path), "temp-audio.m4a"),
        remove_temp=True,
        threads=2,
        verbose=False,
        logger=None,
    )


def generate_script_with_gemini(topic: str, api_key: str, target_seconds: int = 120) -> Dict[str, Any]:
    import google.generativeai as genai

    genai.configure(api_key="AIzaSyC9mr7-JTjX6ZlHVfGzxRZ1StM2QCBIKCg")
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        generation_config={
            "temperature": 0.6,
            "top_p": 0.9,
            "top_k": 50,
            "response_mime_type": "application/json",
        },
    )

    sys_prompt = {
        "role": "user",
        "parts": [
            {
                "text": (
                    "You are an expert teacher. Create a concise 2-minute lesson script on the given topic.\n"
                    "Return STRICT JSON only with this schema: {\n"
                    "  \"topic\": string,\n"
                    "  \"target_duration_seconds\": number,\n"
                    "  \"segments\": [\n"
                    "    {\n"
                    "      \"title\": string,\n"
                    "      \"narration\": string,  // 1-2 sentences\n"
                    "      \"visual\": string,     // describe a simple 2D visual\n"
                    "      \"keywords\": [string, ...],\n"
                    "      \"color\": string       // hex like #336699 (optional)\n"
                    "    }\n"
                    "  ]\n"
                    "}.\n"
                    "Constraints: 10-14 segments; simple language; keep narration concise."
                )
            }
        ],
    }

    user_topic = {
        "role": "user",
        "parts": [{"text": f"TOPIC: {topic}\nTARGET_SECONDS: {target_seconds}"}],
    }

    response = model.generate_content([sys_prompt, user_topic])
    text = response.text or "{}"
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(line for line in cleaned.splitlines() if not line.strip().startswith("```"))
        data = json.loads(cleaned)

    segments = data.get("segments", [])
    cleaned_segments: List[Dict[str, Any]] = []
    for seg in segments:
        title = str(seg.get("title", "")).strip() or "Untitled"
        narration = str(seg.get("narration", seg.get("text", ""))).strip()
        visual = str(seg.get("visual", "")).strip()
        keywords = seg.get("keywords", []) or []
        color = seg.get("color", "")
        cleaned_segments.append({
            "title": title,
            "narration": narration,
            "visual": visual,
            "keywords": keywords,
            "color": color,
        })

    return {
        "topic": data.get("topic", topic),
        "target_duration_seconds": int(data.get("target_duration_seconds", target_seconds)),
        "segments": cleaned_segments,
    }


def main() -> None:
    st.set_page_config(page_title="2-Min AI Tutor", page_icon="🎓", layout="wide")
    st.title("🎓 2-Minute AI Tutor")
    st.write("Enter a topic, question, or paste notes. The app will generate a concise 2-minute lesson with audio and simple 2D visuals, and produce a downloadable MP4 video.")

    with st.sidebar:
        st.header("Settings")
        api_key_input = st.text_input("Gemini API Key", type="password", help="If empty, the app will use the GEMINI_API_KEY environment variable.")
        language_code = st.selectbox("TTS Language", options=["en"], index=0)
        target_seconds = st.slider("Target Duration (seconds)", min_value=60, max_value=180, value=120, step=10)
        video_width = st.selectbox("Video Width", options=[1280, 1920], index=0)
        video_height = 720 if video_width == 1280 else 1080

    tab_gen, tab_script = st.tabs(["Generate", "Use Script JSON"])

    with tab_gen:
        topic = st.text_area("Topic or paste your notes/question", height=160, placeholder="e.g., Newton's Laws of Motion")
        generate_btn = st.button("Generate Lesson with Gemini", type="primary", use_container_width=True)

    with tab_script:
        st.write("If you already have a script JSON matching the schema, upload it.")
        uploaded = st.file_uploader("Upload script.json", type=["json"])
        load_btn = st.button("Load Uploaded Script", use_container_width=True)

    outputs_dir = os.path.join(os.getcwd(), "outputs")
    _ensure_dir(outputs_dir)

    if generate_btn:
        if not topic.strip():
            st.error("Please enter a topic or notes.")
            return
        api_key = api_key_input.strip() or os.getenv("GEMINI_API_KEY")
        if not api_key:
            st.error("Gemini API key is required. Provide it in the sidebar or set GEMINI_API_KEY.")
            return

        with st.spinner("Contacting Gemini and drafting the lesson script..."):
            try:
                script = generate_script_with_gemini(topic=topic.strip(), api_key=api_key, target_seconds=target_seconds)
            except Exception as e:
                st.exception(e)
                return

        st.success("Script generated.")
        with st.expander("View Script JSON"):
            st.json(script)

        st.info("Synthesizing audio and composing video... this may take ~1-2 minutes.")
        tmp_dir = tempfile.mkdtemp(prefix="ai_tutor_")
        try:
            audio_infos = tts_generate_segments(script["segments"], language_code=language_code, tmp_dir=tmp_dir)
            base = _safe_filename(script.get("topic", "lesson"))
            video_path = os.path.join(outputs_dir, f"{base}.mp4")
            compose_video(script["segments"], audio_infos, out_path=video_path, target_total_seconds=float(target_seconds), size=(video_width, video_height))

            st.video(video_path)

            json_bytes = json.dumps(script, indent=2).encode("utf-8")
            st.download_button("Download Script JSON", data=json_bytes, file_name=f"{base}.json", mime="application/json")
            with open(video_path, "rb") as f:
                st.download_button("Download MP4 Video", data=f, file_name=f"{base}.mp4", mime="video/mp4")

        finally:
            pass

    if load_btn and uploaded is not None:
        try:
            script = json.load(uploaded)
        except Exception as e:
            st.error(f"Failed to parse JSON: {e}")
            return

        st.success("Script loaded.")
        with st.expander("View Script JSON"):
            st.json(script)

        st.info("Synthesizing audio and composing video... this may take ~1-2 minutes.")
        tmp_dir = tempfile.mkdtemp(prefix="ai_tutor_")
        try:
            audio_infos = tts_generate_segments(script["segments"], language_code=language_code, tmp_dir=tmp_dir)
            base = _safe_filename(script.get("topic", "lesson"))
            video_path = os.path.join(outputs_dir, f"{base}.mp4")
            compose_video(script["segments"], audio_infos, out_path=video_path, target_total_seconds=float(target_seconds), size=(video_width, video_height))

            st.video(video_path)

            json_bytes = json.dumps(script, indent=2).encode("utf-8")
            st.download_button("Download Script JSON", data=json_bytes, file_name=f"{base}.json", mime="application/json")
            with open(video_path, "rb") as f:
                st.download_button("Download MP4 Video", data=f, file_name=f"{base}.mp4", mime="video/mp4")
        finally:
            pass


if __name__ == "__main__":
    main()