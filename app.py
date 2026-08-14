import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import json
import os
import tempfile
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import subprocess

# Configure Gemini API
GEMINI_API_KEY = "AIzaSyC9mr7-JTjX6ZlHVfGzxRZ1StM2QCBIKCg"
genai.configure(api_key=GEMINI_API_KEY)

# Page config
st.set_page_config(
    page_title="AI Learning Video Generator",
    page_icon="🎓",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
        background-color: #1f77b4;
        color: white;
        font-size: 1.2rem;
        padding: 0.75rem;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

def check_ffmpeg():
    """Check if ffmpeg is installed"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except:
        return False

def generate_script(topic):
    """Generate educational script using Gemini Pro"""
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    Create a concise 2-minute educational script about: {topic}
    
    Format the response as a JSON array with exactly 6-8 segments. Each segment should have:
    - "scene": A number (1-8)
    - "narration": Text to be spoken (20-30 words max)
    - "visual_description": Description of what to show (simple, clear visual)
    - "duration": Duration in seconds (15-20 seconds)
    
    Make it engaging, educational, and suitable for students. Focus on key concepts.
    Start with an introduction and end with a summary.
    
    Return ONLY the JSON array, no additional text.
    """
    
    response = model.generate_content(prompt)
    
    try:
        # Clean the response text
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        script_data = json.loads(text)
        return script_data
    except json.JSONDecodeError:
        st.error("Failed to parse script. Generating simplified version...")
        return generate_fallback_script(topic)

def generate_fallback_script(topic):
    """Generate a simple fallback script"""
    return [
        {
            "scene": 1,
            "narration": f"Welcome! Today we'll learn about {topic}.",
            "visual_description": "Title screen with topic name",
            "duration": 10
        },
        {
            "scene": 2,
            "narration": f"Let's explore the key concepts of {topic}.",
            "visual_description": "Main concept visualization",
            "duration": 15
        },
        {
            "scene": 3,
            "narration": "This is an important fundamental principle to understand.",
            "visual_description": "Key principle illustration",
            "duration": 15
        },
        {
            "scene": 4,
            "narration": "Here's a practical example to help you understand better.",
            "visual_description": "Example demonstration",
            "duration": 15
        },
        {
            "scene": 5,
            "narration": "Let's look at why this matters in real-world applications.",
            "visual_description": "Application examples",
            "duration": 15
        },
        {
            "scene": 6,
            "narration": f"Remember these key points about {topic} for your exam.",
            "visual_description": "Summary points",
            "duration": 15
        },
        {
            "scene": 7,
            "narration": "Practice these concepts and you'll master this topic!",
            "visual_description": "Conclusion screen",
            "duration": 10
        }
    ]

def create_audio(text, filename):
    """Generate audio from text using gTTS"""
    tts = gTTS(text=text, lang='en', slow=False)
    tts.save(filename)
    return filename

def get_audio_duration(audio_file):
    """Get duration of audio file using ffmpeg"""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
             '-of', 'default=noprint_wrappers=1:nokey=1', audio_file],
            capture_output=True,
            text=True
        )
        return float(result.stdout.strip())
    except:
        return 15.0  # Default duration

def create_visual_frame(text, scene_num, color_scheme, width=1280, height=720):
    """Create a visual frame with text and simple graphics"""
    
    colors = {
        1: ("#1f77b4", "#ffffff"),  # Blue
        2: ("#ff7f0e", "#ffffff"),  # Orange
        3: ("#2ca02c", "#ffffff"),  # Green
        4: ("#d62728", "#ffffff"),  # Red
        5: ("#9467bd", "#ffffff"),  # Purple
        6: ("#8c564b", "#ffffff"),  # Brown
        7: ("#e377c2", "#ffffff"),  # Pink
        8: ("#7f7f7f", "#ffffff"),  # Gray
    }
    
    bg_color, text_color = colors.get(scene_num % 8 + 1, ("#1f77b4", "#ffffff"))
    
    # Create image
    img = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    # Try to load a font, fallback to default
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 60)
        text_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
    except:
        try:
            title_font = ImageFont.truetype("arial.ttf", 60)
            text_font = ImageFont.truetype("arial.ttf", 40)
        except:
            title_font = ImageFont.load_default()
            text_font = ImageFont.load_default()
    
    # Draw scene number circle
    circle_radius = 80
    circle_center = (width // 2, 150)
    draw.ellipse(
        [circle_center[0] - circle_radius, circle_center[1] - circle_radius,
         circle_center[0] + circle_radius, circle_center[1] + circle_radius],
        fill=text_color
    )
    
    # Draw scene number
    scene_text = f"Scene {scene_num}"
    try:
        bbox = draw.textbbox((0, 0), scene_text, font=text_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    except:
        text_width = len(scene_text) * 20
        text_height = 30
    
    draw.text(
        (circle_center[0] - text_width // 2, circle_center[1] - text_height // 2),
        scene_text,
        fill=bg_color,
        font=text_font
    )
    
    # Draw main text with word wrap
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        current_line.append(word)
        line_text = ' '.join(current_line)
        try:
            bbox = draw.textbbox((0, 0), line_text, font=text_font)
            line_width = bbox[2] - bbox[0]
        except:
            line_width = len(line_text) * 20
            
        if line_width > width - 200:
            current_line.pop()
            lines.append(' '.join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    # Draw text lines
    y_offset = 300
    line_spacing = 60
    
    for line in lines[:5]:  # Max 5 lines
        try:
            bbox = draw.textbbox((0, 0), line, font=text_font)
            text_width = bbox[2] - bbox[0]
        except:
            text_width = len(line) * 20
            
        draw.text(
            ((width - text_width) // 2, y_offset),
            line,
            fill=text_color,
            font=text_font
        )
        y_offset += line_spacing
    
    return img

def create_video_with_ffmpeg(image_file, audio_file, output_file, duration):
    """Create video using ffmpeg directly"""
    try:
        cmd = [
            'ffmpeg',
            '-loop', '1',
            '-i', image_file,
            '-i', audio_file,
            '-c:v', 'libx264',
            '-tune', 'stillimage',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-pix_fmt', 'yuv420p',
            '-shortest',
            '-y',
            output_file
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        return True
    except Exception as e:
        st.error(f"Error creating video segment: {str(e)}")
        return False

def concatenate_videos(video_files, output_file):
    """Concatenate multiple videos using ffmpeg"""
    # Create concat file
    concat_file = os.path.join(tempfile.gettempdir(), 'concat_list.txt')
    with open(concat_file, 'w') as f:
        for video in video_files:
            f.write(f"file '{video}'\n")
    
    try:
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-c', 'copy',
            '-y',
            output_file
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        return True
    except Exception as e:
        st.error(f"Error concatenating videos: {str(e)}")
        return False

def create_full_video(script_data, output_file, progress_bar):
    """Create full video from script data"""
    
    temp_dir = tempfile.mkdtemp()
    video_segments = []
    
    total_scenes = len(script_data)
    
    for i, segment in enumerate(script_data):
        progress_bar.progress((i + 1) / (total_scenes + 1), f"Creating scene {i + 1}/{total_scenes}...")
        
        scene_num = segment['scene']
        narration = segment['narration']
        visual_desc = segment['visual_description']
        
        # Create audio
        audio_file = os.path.join(temp_dir, f"audio_{scene_num}.mp3")
        create_audio(narration, audio_file)
        
        # Get audio duration
        duration = get_audio_duration(audio_file)
        
        # Create visual frame
        frame = create_visual_frame(visual_desc, scene_num, scene_num)
        frame_file = os.path.join(temp_dir, f"frame_{scene_num}.png")
        frame.save(frame_file)
        
        # Create video segment
        video_file = os.path.join(temp_dir, f"segment_{scene_num}.mp4")
        if create_video_with_ffmpeg(frame_file, audio_file, video_file, duration):
            video_segments.append(video_file)
    
    # Concatenate all segments
    progress_bar.progress(0.95, "Finalizing video...")
    success = concatenate_videos(video_segments, output_file)
    
    if success:
        progress_bar.progress(1.0, "Video created successfully!")
    
    return success

def main():
    st.markdown('<h1 class="main-header">🎓 AI Learning Video Generator</h1>', unsafe_allow_html=True)
    
    # Check for ffmpeg
    if not check_ffmpeg():
        st.error("⚠️ FFmpeg is not installed. Please install it first:")
        st.code("brew install ffmpeg  # For macOS\napt-get install ffmpeg  # For Ubuntu/Debian", language="bash")
        st.stop()
    
    st.markdown("""
    ### Transform Your Study Topics into Engaging Videos!
    Enter any topic or question, and get a 2-minute educational video with synchronized audio and visuals.
    """)
    
    # Create two columns
    col1, col2 = st.columns([2, 1])
    
    with col1:
        topic = st.text_area(
            "Enter your topic or question:",
            placeholder="E.g., Explain photosynthesis, What is Newton's Second Law?, etc.",
            height=100
        )
    
    with col2:
        st.markdown("### Features:")
        st.markdown("✅ AI-Generated Script")
        st.markdown("✅ Natural Voice Narration")
        st.markdown("✅ Visual Explanations")
        st.markdown("✅ 2-Minute Format")
    
    if st.button("🎬 Generate Learning Video"):
        if not topic.strip():
            st.error("Please enter a topic to study!")
            return
        
        with st.spinner("🤖 Generating educational script..."):
            script_data = generate_script(topic)
        
        st.success("✅ Script generated!")
        
        # Display script preview
        with st.expander("📝 View Generated Script"):
            st.json(script_data)
        
        # Create video
        st.info("🎥 Creating your educational video... This may take 1-2 minutes.")
        progress_bar = st.progress(0, "Starting video creation...")
        
        output_file = os.path.join(tempfile.gettempdir(), f"learning_video_{int(time.time())}.mp4")
        
        try:
            success = create_full_video(script_data, output_file, progress_bar)
            
            if success:
                st.success("🎉 Your learning video is ready!")
                
                # Display video
                st.video(output_file)
                
                # Download button
                with open(output_file, 'rb') as f:
                    video_bytes = f.read()
                    st.download_button(
                        label="📥 Download Video",
                        data=video_bytes,
                        file_name=f"learning_{topic[:30].replace(' ', '_')}.mp4",
                        mime="video/mp4"
                    )
            else:
                st.error("Failed to create video. Please try again.")
            
        except Exception as e:
            st.error(f"Error creating video: {str(e)}")
            st.info("Please try again or simplify your topic.")

if __name__ == "__main__":
    main()