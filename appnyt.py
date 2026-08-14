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
import requests
from io import BytesIO

# Configure APIs
GEMINI_API_KEY = "AIzaSyC9mr7-JTjX6ZlHVfGzxRZ1StM2QCBIKCg"
INFIP_API_KEY = "infip-5a50d7ac"
INFIP_API_URL = "https://api.infip.pro/v1/images/generations"

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

def generate_image_from_prompt(prompt, retries=3):
    """Generate image using Infip API"""
    headers = {
        "Authorization": f"Bearer {INFIP_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Simplified and optimized prompt
    payload = {
        "model": "img3",
        "prompt": f"Educational illustration: {prompt}. Simple, clear, high quality.",
        "n": 1,
        "size": "1024x1024"
    }
    
    for attempt in range(retries):
        try:
            # Increased timeout
            response = requests.post(INFIP_API_URL, headers=headers, json=payload, timeout=90)
            
            # Debug: Print response
            if response.status_code != 200:
                st.warning(f"API returned status {response.status_code}: {response.text}")
                time.sleep(3)
                continue
            
            data = response.json()
            
            # Debug: Show what we got
            st.write(f"API Response keys: {list(data.keys())}")
            
            # Check for images in response
            if "images" in data and len(data["images"]) > 0:
                image_url = data["images"][0]
                st.info(f"Got image URL: {image_url[:50]}...")
                
                # Download the image
                img_response = requests.get(image_url, timeout=30)
                img_response.raise_for_status()
                
                image = Image.open(BytesIO(img_response.content))
                return image
            
            # Check alternative response formats
            elif "data" in data and len(data["data"]) > 0:
                if "url" in data["data"][0]:
                    image_url = data["data"][0]["url"]
                    st.info(f"Got image URL from data: {image_url[:50]}...")
                    
                    img_response = requests.get(image_url, timeout=30)
                    img_response.raise_for_status()
                    
                    image = Image.open(BytesIO(img_response.content))
                    return image
            
            else:
                st.warning(f"Unexpected response format (attempt {attempt + 1}/{retries}): {json.dumps(data)[:200]}")
                time.sleep(3)
                
        except requests.exceptions.Timeout:
            st.warning(f"Image generation timeout (attempt {attempt + 1}/{retries})")
            if attempt < retries - 1:
                time.sleep(3)
        except requests.exceptions.RequestException as e:
            st.warning(f"Request error (attempt {attempt + 1}/{retries}): {str(e)}")
            if attempt < retries - 1:
                time.sleep(3)
        except Exception as e:
            st.warning(f"Error generating image (attempt {attempt + 1}/{retries}): {str(e)}")
            if attempt < retries - 1:
                time.sleep(3)
    
    return None

def generate_script(topic):
    """Generate educational script using Gemini Pro"""
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    Create a concise 2-minute educational script about: {topic}
    
    Format the response as a JSON array with exactly 6-8 segments. Each segment should have:
    - "scene": A number (1-8)
    - "narration": Text to be spoken (20-30 words max)
    - "visual_description": Description of what to show as an image (be specific and descriptive for image generation, include details like colors, composition, style)
    - "duration": Duration in seconds (15-20 seconds)
    
    Make it engaging, educational, and suitable for students. Focus on key concepts.
    Start with an introduction and end with a summary.
    
    For visual_description, be very specific and detailed to help generate relevant educational images.
    Example: "A detailed diagram showing the process of photosynthesis with labeled chloroplasts, sunlight rays, and chemical formulas"
    
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
            "visual_description": f"Title card with '{topic}' in large bold letters, educational theme with books and learning symbols",
            "duration": 10
        },
        {
            "scene": 2,
            "narration": f"Let's explore the key concepts of {topic}.",
            "visual_description": f"Conceptual diagram illustrating the main ideas of {topic}, colorful and clear",
            "duration": 15
        },
        {
            "scene": 3,
            "narration": "This is an important fundamental principle to understand.",
            "visual_description": f"Infographic showing the fundamental principles of {topic} with icons and arrows",
            "duration": 15
        },
        {
            "scene": 4,
            "narration": "Here's a practical example to help you understand better.",
            "visual_description": f"Real-world example or application of {topic}, practical and relatable",
            "duration": 15
        },
        {
            "scene": 5,
            "narration": "Let's look at why this matters in real-world applications.",
            "visual_description": f"Modern applications and uses of {topic} in everyday life, contemporary style",
            "duration": 15
        },
        {
            "scene": 6,
            "narration": f"Remember these key points about {topic} for your exam.",
            "visual_description": f"Summary infographic with bullet points highlighting key takeaways about {topic}",
            "duration": 15
        },
        {
            "scene": 7,
            "narration": "Practice these concepts and you'll master this topic!",
            "visual_description": "Motivational image with a student successfully learning, bright and encouraging",
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

def add_text_overlay_to_image(image, text, scene_num):
    """Add text overlay to generated image"""
    # Create a copy to draw on
    img = image.copy()
    img = img.resize((1280, 720), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(img)
    
    # Try to load a font
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 50)
        text_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 35)
    except:
        try:
            title_font = ImageFont.truetype("arial.ttf", 50)
            text_font = ImageFont.truetype("arial.ttf", 35)
        except:
            title_font = ImageFont.load_default()
            text_font = ImageFont.load_default()
    
    # Add semi-transparent overlay at bottom for text
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    
    # Draw semi-transparent black rectangle at bottom
    overlay_draw.rectangle([(0, 570), (1280, 720)], fill=(0, 0, 0, 180))
    
    # Composite overlay onto image
    img = img.convert('RGBA')
    img = Image.alpha_composite(img, overlay)
    img = img.convert('RGB')
    
    # Draw text on the overlay area
    draw = ImageDraw.Draw(img)
    
    # Word wrap for text
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
            
        if line_width > 1200:
            current_line.pop()
            lines.append(' '.join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    # Draw text lines
    y_offset = 590
    line_spacing = 40
    
    for line in lines[:3]:  # Max 3 lines
        try:
            bbox = draw.textbbox((0, 0), line, font=text_font)
            text_width = bbox[2] - bbox[0]
        except:
            text_width = len(line) * 20
            
        draw.text(
            ((1280 - text_width) // 2, y_offset),
            line,
            fill=(255, 255, 255),
            font=text_font
        )
        y_offset += line_spacing
    
    # Add scene number badge in top-left corner
    badge_size = 60
    draw.ellipse([(20, 20), (20 + badge_size, 20 + badge_size)], fill=(255, 255, 255))
    scene_text = f"{scene_num}"
    try:
        bbox = draw.textbbox((0, 0), scene_text, font=title_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    except:
        text_width = 30
        text_height = 30
    
    draw.text(
        (20 + badge_size // 2 - text_width // 2, 20 + badge_size // 2 - text_height // 2),
        scene_text,
        fill=(0, 0, 0),
        font=title_font
    )
    
    return img

def create_fallback_visual(text, scene_num):
    """Create a fallback visual if image generation fails"""
    colors = [
        ("#1f77b4", "#ffffff"),  # Blue
        ("#ff7f0e", "#ffffff"),  # Orange
        ("#2ca02c", "#ffffff"),  # Green
        ("#d62728", "#ffffff"),  # Red
        ("#9467bd", "#ffffff"),  # Purple
        ("#8c564b", "#ffffff"),  # Brown
        ("#e377c2", "#ffffff"),  # Pink
        ("#7f7f7f", "#ffffff"),  # Gray
    ]
    
    bg_color, text_color = colors[(scene_num - 1) % len(colors)]
    
    img = Image.new('RGB', (1280, 720), color=bg_color)
    draw = ImageDraw.Draw(img)
    
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
    
    # Draw scene number
    scene_text = f"Scene {scene_num}"
    try:
        bbox = draw.textbbox((0, 0), scene_text, font=title_font)
        text_width = bbox[2] - bbox[0]
    except:
        text_width = len(scene_text) * 30
    
    draw.text((640 - text_width // 2, 150), scene_text, fill=text_color, font=title_font)
    
    # Draw description text
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
            
        if line_width > 1100:
            current_line.pop()
            lines.append(' '.join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    y_offset = 300
    for line in lines[:6]:
        try:
            bbox = draw.textbbox((0, 0), line, font=text_font)
            text_width = bbox[2] - bbox[0]
        except:
            text_width = len(line) * 20
            
        draw.text((640 - text_width // 2, y_offset), line, fill=text_color, font=text_font)
        y_offset += 60
    
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
        
        # Generate image using AI
        st.info(f"🎨 Generating image for scene {scene_num}: {visual_desc[:50]}...")
        generated_image = generate_image_from_prompt(visual_desc)
        
        if generated_image:
            # Add text overlay to the generated image
            frame = add_text_overlay_to_image(generated_image, visual_desc, scene_num)
            st.success(f"✅ Image generated for scene {scene_num}")
        else:
            # Fallback to simple visual
            st.warning(f"⚠️ Using fallback visual for scene {scene_num}")
            frame = create_fallback_visual(visual_desc, scene_num)
        
        # Save frame
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
    Enter any topic or question, and get a 2-minute educational video with AI-generated images, synchronized audio and visuals.
    """)
    
    # Create two columns
    col1, col2 = st.columns([2, 1])
    
    with col1:
        topic = st.text_area(
            "Enter your topic or question:",
            placeholder="E.g., Explain photosynthesis, What is Newton's Second Law?, The water cycle, etc.",
            height=100
        )
    
    with col2:
        st.markdown("### Features:")
        st.markdown("✅ AI-Generated Script")
        st.markdown("✅ AI-Generated Images")
        st.markdown("✅ Natural Voice Narration")
        st.markdown("✅ Visual Explanations")
        st.markdown("✅ 2-Minute Format")
    
    # Add API test button
    with st.expander("🔧 Test Image Generation API"):
        if st.button("Test API"):
            st.info("Testing API connection...")
            test_image = generate_image_from_prompt("A simple red apple on white background")
            if test_image:
                st.success("API is working!")
                st.image(test_image, caption="Test Image", width=300)
            else:
                st.error("API test failed. Check your API key and connection.")
    
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
        st.info("🎥 Creating your educational video with AI-generated images... This may take 3-5 minutes.")
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