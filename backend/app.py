from flask import Flask, request, jsonify, send_from_directory
import os
import base64
import time
import random
import pickle
import numpy as np
import tempfile
import datetime
import requests # เพิ่มเข้ามา
from scipy.spatial.distance import cdist
from sentence_transformers import SentenceTransformer
from PIL import Image
import io
from dotenv import load_dotenv
from google import genai
from google.genai import types
from flask_cors import CORS

# Import Classifier Logic
from classifier import classify_image

# --- 1. Setup ---
load_dotenv()
app = Flask(__name__)
CORS(app)

# ==========================================
# 💾 AUTO-SAVE SYSTEM (DEV ONLY)
# ==========================================
HISTORY_FOLDER = os.path.join(os.path.dirname(__file__), 'generated_history')
VIDEO_FOLDER = os.path.join(os.path.dirname(__file__), 'generated_videos') # เพิ่มโฟลเดอร์วิดีโอ

# สร้างโฟลเดอร์วิดีโอถ้ายังไม่มี
if not os.path.exists(VIDEO_FOLDER):
    os.makedirs(VIDEO_FOLDER)

def save_generated_image(image_bytes, location_name_th):
    try:
        if not os.path.exists(HISTORY_FOLDER):
            os.makedirs(HISTORY_FOLDER)

        file_prefix = LOCATION_MAPPING_TH_TO_EN.get(location_name_th, "unknown_location")
        
        safe_name = "place"
        if "Democracy" in file_prefix: safe_name = "democracymonument"
        elif "Sala" in file_prefix: safe_name = "salachalermkrung"
        elif "Swing" in file_prefix: safe_name = "giantswing"
        elif "Yaowarat" in file_prefix: safe_name = "yaowarat"
        elif "Khao San" in file_prefix: safe_name = "khaosan"
        elif "Phra Sumen" in file_prefix: safe_name = "phrasumenfort"
        elif "Sanam Luang" in file_prefix: safe_name = "sanamluang"
        elif "National Museum" in file_prefix: safe_name = "nationalmuseum"
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_name}_1960s_{timestamp}.png"
        filepath = os.path.join(HISTORY_FOLDER, filename)

        with open(filepath, "wb") as f:
            f.write(image_bytes)
        
        print(f"💾 Auto-saved result to: {filename}")
        return filepath

    except Exception as e:
        print(f"⚠️ Failed to auto-save image: {e}")
        return None

def save_generated_video(video_url, location_name_th):
    """
    ดาวน์โหลดและบันทึกวิดีโอจาก Runway
    """
    try:
        response = requests.get(video_url, stream=True)
        if response.status_code == 200:
            file_prefix = LOCATION_MAPPING_TH_TO_EN.get(location_name_th, "unknown_location")
            safe_name = "place"
            # (ใช้ logic ตั้งชื่อเดิม)
            if "Democracy" in file_prefix: safe_name = "democracymonument"
            elif "Sala" in file_prefix: safe_name = "salachalermkrung"
            elif "Swing" in file_prefix: safe_name = "giantswing"
            elif "Yaowarat" in file_prefix: safe_name = "yaowarat"
            elif "Khao San" in file_prefix: safe_name = "khaosan"
            elif "Phra Sumen" in file_prefix: safe_name = "phrasumenfort"
            elif "Sanam Luang" in file_prefix: safe_name = "sanamluang"
            elif "National Museum" in file_prefix: safe_name = "nationalmuseum"

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{safe_name}_1960s_{timestamp}.mp4"
            filepath = os.path.join(VIDEO_FOLDER, filename)

            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
            
            print(f"🎥 Auto-saved video to: {filename}")
            return filename, filepath # Return filename, fullpath
    except Exception as e:
        print(f"⚠️ Failed to save video: {e}")
    return None, None

# ==========================================
# 🧠 AI MEMORY LOADING
# ==========================================
print("⏳ Initializing System...")
SEARCH_MODEL = None
LOCATION_INDICES = {}

def load_ai_memory():
    global SEARCH_MODEL, LOCATION_INDICES
    try:
        print("👁️  Loading CLIP Vision Model...")
        SEARCH_MODEL = SentenceTransformer('clip-ViT-B-32')
        
        indices_path = os.path.join(os.path.dirname(__file__), 'indices')
        if os.path.exists(indices_path):
            print("🧠 Loading Location Indices...")
            for filename in os.listdir(indices_path):
                if filename.endswith('.pkl'):
                    location_key = filename.replace('.pkl', '')
                    with open(os.path.join(indices_path, filename), 'rb') as f:
                        LOCATION_INDICES[location_key] = pickle.load(f)
                    print(f"  - Loaded Memory: {location_key}")
            print("✅ AI System Ready: Smart Match Enabled!")
        else:
            print("⚠️ 'indices' folder not found. ML features will be disabled.")
            
    except Exception as e:
        print(f"⚠️ Warning: AI System Failed. ({e})")
        SEARCH_MODEL = None

load_ai_memory()

# ==========================================
# 📍 MAPPINGS & DATA
# ==========================================

LOCATION_MAPPING_TH_TO_EN = {
    "อนุสาวรีย์ประชาธิปไตย": "Ratchadamnoen Avenue – Democracy Monument",
    "ศาลาเฉลิมกรุง": "Sala Chalermkrung Royal Theatre",
    "เสาชิงช้า & วัดสุทัศน์": "Giant Swing – Wat Suthat",
    "เยาวราช": "Yaowarat (Chinatown)",
    "ถนนข้าวสาร": "Khao San Road",
    "ป้อมพระสุเมรุ": "Phra Sumen Fort – Santichaiprakan Park",
    "สนามหลวง": "Sanam Luang (Royal Field)",
    "พิพิธภัณฑสถานแห่งชาติ": "National Museum Bangkok"
}

LOCATION_MAPPING_EN_TO_TH = {v: k for k, v in LOCATION_MAPPING_TH_TO_EN.items()}

LOCATION_KEY_MAP = {
    "อนุสาวรีย์ประชาธิปไตย": "Democracy Monument",
    "ศาลาเฉลิมกรุง": "Sala Chalermkrung Royal Theatre",
    "เสาชิงช้า & วัดสุทัศน์": "Giant Swing – Wat Suthat",
    "เยาวราช": "Yaowarat (Chinatown)",
    "ป้อมพระสุเมรุ": "Phra Sumen Fort – Santichaiprakarn Park",
    "สนามหลวง": "Sanam Luang (Royal Field)",
    "พิพิธภัณฑสถานแห่งชาติ": "Phra Nakhon National Museum"
}

LOCATION_INFO = {
    "อนุสาวรีย์ประชาธิปไตย": { "prompt_key": "Democracy Monument", "desc_60s": "ตัวอนุสาวรีย์สีครีมปูนชัดเจน พานรัฐธรรมนูญสีโลหะรมดำ ประตูสีแดงชาด อาคารราชดำเนินสีส้มอิฐ ถนนกว้างไร้เส้นจราจร" },
    "ศาลาเฉลิมกรุง": { "prompt_key": "Sala Chalermkrung", "desc_60s": "โรงมหรสพหลวงยุคโก๋หลังวัง อาคารสีขาวครีมที่มีคราบฝน โดดเด่นด้วย 'คัตเอาท์ยักษ์วาดมือ' เรื่อง 'บางกอกทวิกาล' หน้าโรง พร้อมดารานำชายสองสไตล์ บรรยากาศรอบข้างคึกคักด้วยวัยรุ่นยุค 60s รถแท็กซี่เฟียต และรถรางวิ่งผ่านหน้าโรง" },
    "เสาชิงช้า & วัดสุทัศน์": { "prompt_key": "Giant Swing", "desc_60s": "เสาชิงช้ามีฐานปูนชัดเจน รถวิ่งอ้อมฐานห้ามลอดผ่าน ไม่มีรถราง ถนนลูกรัง วัดสุทัศน์ดูเก่าแก่ตามกาลเวลา" },
    "เยาวราช": { "prompt_key": "Yaowarat", "desc_60s": "รถรางโปร่งแบบเปิดข้างวิ่งชิดขอบทาง ป้ายร้านค้าแนบตึกไม่ยื่นรกตา ตึกแถวเก่าแก่ บรรยากาศการค้าขายแบบดั้งเดิม" },
    "ถนนข้าวสาร": { "prompt_key": "Khaosan Road", "desc_60s": "ชุมชนบางลำพูย่านค้าข้าวสาร ห้องแถวไม้ประตูบานเฟี้ยม มีกระสอบข้าววางหน้าร้าน บรรยากาศเงียบสงบแบบย่านพักอาศัย ไม่ใช่ย่านท่องเที่ยว" },
    "ป้อมพระสุเมรุ": { "prompt_key": "Phra Sumen Fort", "desc_60s": "ป้อมสีขาวขุ่นทรุดโทรมมีคราบตะไคร่ บ้านเรือนไม้สังกะสีสร้างเบียดเสียดติดตัวป้อม ไม่เห็นมุมคลองมากนัก ไม่มีสวนสาธารณะ" },
    "สนามหลวง": { "prompt_key": "Sanam Luang", "desc_60s": "ตลาดนัดสนามหลวง พื้นดินแดงปนหญ้าแห้ง ร่มผ้าใบสีขาวสลับแดง/น้ำเงิน รถเข็นขายน้ำอ้อยสีฟ้า ว่าวไทยลอยเต็มฟ้า ฉากหลังวัดพระแก้ว" },
    "พิพิธภัณฑสถานแห่งชาติ": { "prompt_key": "National Museum", "desc_60s": "อาคารทรงไทยสีขาวหมองมีคราบตะไคร่ดำ สภาพรกรั้วด้วยต้นไม้ใหญ่เหมือนวัดป่า ถนนหน้าพระธาตุลาดยางเงียบสงบ รั้วเหล็กดัดหัวลูกศร" }
}

# --- THE MASTER PROMPT DATABASE (V.11) ---
# ... (คงเดิมตามที่คุณส่งมาล่าสุด ไม่ต้องแก้ส่วนนี้) ...
LOCATION_PROMPTS = {
    "Democracy Monument": """
          **TASK:** Create a **HYPER-REALISTIC** photograph of Democracy Monument (Bangkok 1960s).
          
          **PERSPECTIVE LOCK (CRITICAL):**
          - Use the Uploaded Image as the **Absolute Layout Blueprint**.
          - Keep the exact camera angle and composition.
          
          **ARCHITECTURAL ACCURACY:**
          - **Wings:** 4 Concrete wings, concave curve, bas-reliefs at base. Color: Weathered Cream/Grey Stucco (Not white plastic).
          - **Center:** Solid turret with **Dark Bronze/Black Metal Tray**.
          - **Base:** The circular steps are **BARE CONCRETE**. NO FLOWERS. NO GRASS. NO WEEDS.

          **LOGIC & SAFETY RULES (CRITICAL):**
          - **PEDESTRIANS:** Pedestrians must be strictly on the **far sidewalks** only. **ABSOLUTELY NO PEOPLE walking in the middle of the road or standing on the monument's island.** The road is for cars only.
          
          **SURROUNDINGS:**
          - **Buildings:** Aged Terracotta/Brick Orange Ratchadamnoen buildings and Low-rise Art Deco buildings along Ratchadamnoen Avenue.
          - **Road:** Wide Asphalt. NO modern lane markings.

          **Negative Prompt (CRITICAL):**}
          - **Negative Prompt:** Tram, tram rails, tramway, skytrain, modern billboards, LED screens, plastic barriers, motorcycles, tuk-tuks, people on road, tourists taking selfies.
      """,

    "Sala Chalermkrung": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Sala Chalermkrung Theatre (1967).
        
        **PERSPECTIVE LOCK:** Maintain exact camera angle from input image.
        
        **THE MOVIE POSTER (SPECIFIC):**
        - **Visual:** Hand-painted cutout. Two men in white shirts standing back-to-back. One wears glasses, one doesn't. Both look smart/gentlemen.
        - **Text (THAI ONLY):** Title "**บางกอกทวิกาล**". Starring "**มาดามพงษ์ และ ณัฐภัทร**". Director "**ตอตุ้ม**". Text: "**ฉายพฤษภาคมนี้ ที่เฉลิมกรุง**".
        
        **CONTEXT:**
        - **Street:** Wide asphalt avenue.
        - **Surroundings:** Authentic 1960s shophouses (weathered wood/concrete). Realistic atmosphere.
    """,

    "Giant Swing": """

        **TASK:** Create a **SHARP, PHOTOREALISTIC COLOR PHOTOGRAPH** of The Giant Swing (1965).

        **PERSPECTIVE & VISIBILITY RULE:**
        - If the original image shows Wat Suthat, render it as aged/weathered.
        - **IF THE ORIGINAL IMAGE DOES NOT SHOW THE TEMPLE, DO NOT ADD IT.** Respect the input frame.

        **DETAILS:**
        - **The Swing:** Two towering **Vibrant Red Teak Pillars** standing on a clean White Stone Plinth.
        - **Structure:** intricate carved crossbar at the top. **NO SWINGING CEREMONY**.
        - **Surroundings:** Shophouses must look lived-in and realistic for the era (not ruined, not new).
        - **Road Layout:** The Giant Swing acts as a long roundabout. Vintage cars and Samlors drive **AROUND** the plinth.
        - **Traffic:** Vintage 1960s sedans (Fiat 1100, Austin), Samlors (Tricycles), and round-nose trucks.

        **NEGATIVE PROMPT:**
        - Men swinging on the swing (Historical inaccuracy), modern traffic lights, 7-Eleven, air conditioning units, plastic awnings, tourists in shorts.
    """,
    
    "Yaowarat": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Yaowarat Road (1968).
        
        **STRICT TEXT & SIGNS:**
        - **Text:** Hand-painted signs. **LEGIBLE Thai & Chinese**.
        - **Mandatory Texts:** "**ห้างทอง ฮั่วเซ่งเฮง (和成興大金行)**", "**ภัตตาคาร หูฉลาม**", "**ขายยาจีน**".
        - **Lighting:** DAYLIGHT only. **NO NEON GLOW**. NO LED.
        
        **TRAM REALISM:**
        - **Tram:** Weathered Yellow/Red wooden tram.
        - **Position:** Running on rails **HUGGING THE RIGHT CURB** (near houses). Not in the middle.
    """,

    "Khaosan Road": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Bang Lamphu / Khaosan Road (1962).

        **PERSPECTIVE LOCK (CRITICAL):**
        - **Blueprint:** Use the Uploaded Image as the **ABSOLUTE LAYOUT REFERENCE**.
        - **Camera Angle:** Maintain the **EXACT** camera angle, perspective, and depth of the original image.
        - **Composition:** Do not add new buildings or change the street width. Keep the structural geometry 100% identical to the input.
        
        **VISUALS & COLORS:**
        - **Houses:** Wooden row houses painted **YELLOW WOOD** with **GREEN WINDOWS**.
        - **Signage:** **NO SIGNS** on the house fronts. Residential look only.
        
        **LIFE:**
        - **Atmosphere:** Vibrant community. Locals chatting, kids playing.
        - **Props:** Rice sacks stacked at **ONLY 2-3 HOUSES**. Not everywhere.

        **NEGATIVE PROMPT:**
        - Backpackers, foreigners in shorts, neon signs, bars, alcohol advertisements, modern hostels, tattoos, dreadlocks, electronic music vibes, changing camera angle, wide angle lens distortion.
    """,

    "Phra Sumen Fort": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Phra Sumen Fort (1960).
        
        **CRITICAL ACCURACY: HEADLESS FORT:**
        - **Status:** The top wooden roof spire is **COMPLETELY MISSING**. The white tower is truncated/severed. It is a flat, weathered stump.
        - **Structure:** Hexagonal white plaster fort, stained with black mold.
    """,

    "Sanam Luang": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Sanam Luang (Weekend Market 1968).
        
        **MARKET REALISM:**
        - **Stalls:** Vendors sitting on **WOVEN MATS** on the red dust ground. Bamboo parasols.
        - **Density:** Lively but not overcrowded. Open spaces visible.
        - **Sky:** Only **A FEW** scattered kites.
    """,

    "National Museum": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of the **FRONT** of National Museum Bangkok (1960).
        
        **FRONT ATMOSPHERE:**
        - **Vibe:** Serene, shady, well-maintained.
        - **Grounds:** Swept gravel, manicured grass, large trees. NOT overgrown.
        - **Perspective:** Keep the exact view of the front facade from the input image.
    """
}

# ==========================================
# 🛠️ HELPER FUNCTIONS
# ==========================================

def get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: raise ValueError("GEMINI_API_KEY not found")
    return genai.Client(api_key=api_key)

# --- Friendly Error Message (From Classifier Branch) ---
def get_friendly_error_message(raw_reason, lang='TH'):
    raw_reason = raw_reason.lower()
    is_eng = (lang == 'ENG')

    if any(x in raw_reason for x in ['night', 'dark', 'sunset', 'evening']):
        return "The image is too dark or taken at night." if is_eng else "ภาพมืดหรือเป็นเวลากลางคืน (AI ต้องการแสงธรรมชาติ)"
    if any(x in raw_reason for x in ['person', 'selfie', 'face', 'crowd', 'body']):
        return "People are obstructing the view." if is_eng else "ตรวจพบบุคคลหรือฝูงชนบดบังทัศนียภาพ"
    if any(x in raw_reason for x in ['close-up', 'detail', 'macro', 'texture', 'wall']):
        return "The shot is too close or detailed." if is_eng else "ภาพถ่ายระยะใกล้เกินไป กรุณาถ่ายมุมกว้าง"
    if any(x in raw_reason for x in ['vehicle', 'bus', 'truck', 'car', 'traffic']):
        return "Vehicles are blocking the architecture." if is_eng else "มียานพาหนะบดบังตัวอาคารมากเกินไป"
    if any(x in raw_reason for x in ['text', 'screenshot', 'map', 'drawing']):
        return "This image does not appear to be a real photo." if is_eng else "ภาพนี้ไม่ใช่ภาพถ่ายสถานที่จริง"
    if "other" in raw_reason:
        guess = raw_reason.replace("other", "").replace("(", "").replace(")", "").strip()
        if guess:
            return f"System identifies this as: {guess}" if is_eng else f"ระบบระบุว่าเป็น: {guess} ซึ่งไม่ตรงกับที่เลือก"
        return "System could not identify the location." if is_eng else "ระบบไม่สามารถระบุสถานที่ในภาพได้"
    
    return "Image composition is unclear." if is_eng else "องค์ประกอบภาพยังไม่ชัดเจน"

# --- CLIP Logic (From Processing Branch) ---
def get_best_match_reference(location_th, user_img_bytes):
    if location_th == "ถนนข้าวสาร":
        print(f"🌾 Khaosan Road: Using Prompt Only.")
        return None

    mapped_key = LOCATION_KEY_MAP.get(location_th)
    if not mapped_key: return None 

    if not SEARCH_MODEL or mapped_key not in LOCATION_INDICES:
        print(f"⚠️ No AI Index for '{mapped_key}'. Fallback to Random.")
        return get_random_reference(mapped_key)
    
    try:
        data = LOCATION_INDICES[mapped_key]
        user_img = Image.open(io.BytesIO(user_img_bytes))
        user_vector = SEARCH_MODEL.encode(user_img)
        
        distances = cdist([user_vector], data['vectors'], metric='cosine')[0]
        best_idx = np.argmin(distances)
        best_filename = data['filenames'][best_idx]
        
        print(f"🎯 Smart Match ({mapped_key}): Matches -> {best_filename}")
        file_path = os.path.join(os.path.dirname(__file__), "reference_images", mapped_key, best_filename)
        with open(file_path, "rb") as f:
            return f.read()
            
    except Exception as e:
        print(f"❌ Smart Match Error: {e}. Fallback to random.")
        return get_random_reference(mapped_key)

def get_random_reference(folder_name):
    base_path = os.path.join(os.path.dirname(__file__), "reference_images", folder_name)
    if not os.path.exists(base_path): return None
    
    images = []
    for ext in ['*.jpg', '*.jpeg', '*.png']:
        import glob
        images.extend(glob.glob(os.path.join(base_path, ext)))
        
    if not images: return None
    selected = random.choice(images)
    print(f"🎲 Random Ref ({folder_name}): {os.path.basename(selected)}")
    with open(selected, "rb") as f:
        return f.read()

# --- Gemini Generation Logic (From Processing Branch) ---
def step1_analyze(client, img_bytes):
    prompt = "Analyze the precise geometry, camera angle, and structural layout..."
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-1.5-flash", # Stable model
                contents=[prompt, types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")]
            )
            return response.text
        except Exception as e:
            if "429" in str(e) or "503" in str(e):
                time.sleep((2 ** attempt) + random.uniform(0, 1))
            else:
                break
    return "Keep original perspective rigid."

def step2_generate(client, structure_desc, location_key, original_img_bytes, ref_img_bytes=None):
    specific_prompt = LOCATION_PROMPTS.get(location_key, "")
    
    global_style = """
    **GLOBAL STYLE INSTRUCTION (MUST FOLLOW):**
    - **OUTPUT MUST BE A PHOTOREALISTIC COLOR PHOTOGRAPH.** Do not generate black and white images.
    - **FILM LOOK:** Imitate 1960s Kodachrome slide film aesthetic.
    - **ASPECT RATIO & PERSPECTIVE:** The output image must maintain the same aspect ratio, framing, and camera angle as the input image. DO NOT ROTATE. DO NOT ZOOM.
    - **GLOBAL NEGATIVE PROMPT:** modern logos (7-Eleven, Starbucks, Apple, etc.), brand names, QR codes, CCTV cameras, satellite dishes, air conditioning units, modern cars (post-1970), motorcycles, LED signs, concrete barriers, plastic chairs.
    """
    
    parts = []
    if ref_img_bytes:
        style_instruction = """
        **STYLE TRANSFER INSTRUCTION (IP-ADAPTER MODE):**
        - The second image is the **STYLE REFERENCE** (Ground Truth).
        - **COPY the color palette, lighting, and historical atmosphere** from the Reference Image.
        - **CRITICAL:** Use the Reference mainly for COLOR/VIBE. Use the Prompt for STRUCTURAL details.
        """
        parts = [
            f"{specific_prompt}\n{global_style}\n{style_instruction}\n**GEOMETRY CONSTRAINT:**\nReference Analysis: {structure_desc}",
            types.Part.from_bytes(data=original_img_bytes, mime_type="image/jpeg"),
            types.Part.from_bytes(data=ref_img_bytes, mime_type="image/jpeg") 
        ]
    else:
        parts = [
            f"{specific_prompt}\n{global_style}\n**GEOMETRY CONSTRAINT:**\nReference Analysis: {structure_desc}",
            types.Part.from_bytes(data=original_img_bytes, mime_type="image/jpeg")
        ]

    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-1.5-flash", 
                contents=parts,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    temperature=0.4
                )
            )
            for part in response.candidates[0].content.parts:
                if part.inline_data: return part.inline_data.data
            print(f"⚠️ Warning: Model returned no image (Attempt {attempt+1})")
        except Exception as e:
            if "429" in str(e) or "503" in str(e):
                # 👈 สูตรคำนวณเวลารอแบบ Exponential Backoff (รอทวีคูณ: 2วิ, 4วิ, 8วิ, ...)
                wait_time = (2 ** attempt) + random.uniform(1, 3) 
                print(f"⚠️ Server Busy (Attempt {attempt+1}/{max_retries}). Waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
            else:
                return None
    return None

# ==========================================
# 🎬 RUNWAY ML INTEGRATION (NEW)
# ==========================================
def generate_video_runway(image_bytes, location_key):
    """
    ฟังก์ชันส่งภาพไปยัง RunwayML เพื่อสร้างวิดีโอ
    """
    runway_key = os.getenv("RUNWAYML_API_KEY")
    if not runway_key:
        print("⚠️ Runway API Key not found. Skipping video generation.")
        return None

    try:
        print("🎬 Starting Runway Video Generation...")
        
        # 1. แปลง Image Bytes เป็น Base64 String (Data URI)
        base64_str = base64.b64encode(image_bytes).decode('utf-8')
        mime_type = "image/png" # Gemini usually returns PNG
        data_uri = f"data:{mime_type};base64,{base64_str}"

        # 2. ตั้งค่า Prompt การเคลื่อนไหวเบาๆ ให้สมจริงตามสถานที่
        # Motion Prompt Engineering: Subtle movement to bring it to life.
        motion_prompt = "Cinematic slow motion, subtle camera push in, realistic movement of people and vehicles, atmospheric lighting, 1960s film grain."
        if location_key == "Yaowarat":
            motion_prompt += " Tram moving slowly, flags waving."
        elif location_key == "Giant Swing":
            motion_prompt += " Cars driving around the swing."
        elif location_key == "Democracy Monument":
            motion_prompt += " Clouds moving, birds flying."

        url = "https://api.runwayml.com/v1/image_to_video"
        
        payload = {
            "promptImage": data_uri,
            "model": "gen3a_turbo", # ใช้รุ่น Turbo เพื่อความเร็วและราคาประหยัด (5 วิ)
            "promptText": motion_prompt,
            "duration": 5, # บังคับ 5 วินาที
            "ratio": "1280:768" # หรือปรับตาม Aspect Ratio เดิม (Runway อาจบังคับบาง ratio) -> แนะนำปล่อย auto หรือระบุถ้าจำเป็น
        }
        
        headers = {
            "Authorization": f"Bearer {runway_key}",
            "X-Runway-Version": "2024-09-26",
            "Content-Type": "application/json"
        }

        # 3. ส่ง Request (POST)
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Runway Request Failed: {response.text}")
            return None
            
        task_id = response.json().get('id')
        print(f"⏳ Runway Task Submitted ID: {task_id}")

        # 4. Polling รอผลลัพธ์ (Check status)
        status = "PENDING"
        video_url = None
        
        # รอสูงสุดประมาณ 60-90 วินาที (Turbo เร็วแต่เผื่อไว้)
        max_wait_time = 90 
        start_time = time.time()

        while status not in ["SUCCEEDED", "FAILED"]:
            if time.time() - start_time > max_wait_time:
                print("❌ Runway Timeout")
                return None
            
            time.sleep(3) # รอ 3 วินาทีแล้วเช็คใหม่
            
            status_url = f"https://api.runwayml.com/v1/tasks/{task_id}"
            status_res = requests.get(status_url, headers=headers)
            
            if status_res.status_code == 200:
                data = status_res.json()
                status = data.get('status')
                print(f"   ...Status: {status}")
                
                if status == "SUCCEEDED":
                    video_url = data.get('output', [None])[0]
                elif status == "FAILED":
                    print(f"❌ Runway Task Failed: {data.get('failure')}")
                    return None
            else:
                print(f"⚠️ Check Status Failed: {status_res.text}")
                return None

        # 5. ได้ URL มาแล้ว (เป็น URL ชั่วคราวของ Runway)
        if video_url:
            print(f"✅ Video Generated: {video_url}")
            return video_url
            
    except Exception as e:
        print(f"❌ Critical Runway Error: {e}")
        return None
    
    return None

# ==========================================
# 🚀 ROUTES
# ==========================================

# 1. VERIFY (Logic from Classifier Branch)
@app.route('/verify', methods=['POST'])
def verify_image_route():
    temp_path = None
    try:
        if 'image' not in request.files or 'location' not in request.form:
            return jsonify({'error': 'Missing data'}), 400
        
        file = request.files['image']
        location_th = request.form['location']
        lang = request.form.get('language', 'TH').upper() # รับค่าภาษามาด้วย
        
        # ตรวจสอบชื่อสถานที่
        if location_th not in LOCATION_MAPPING_TH_TO_EN:
             return jsonify({'error': 'Invalid location selection'}), 400

        # Save Temp File for Google Vision
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            file.save(temp_file.name)
            temp_path = temp_file.name

        print(f"🕵️‍♂️ Verifying: {location_th} (Lang: {lang})...")
        
        # CALL CLASSIFIER LOGIC
        detected_place, score, is_valid = classify_image(temp_path)
        expected_place_en = LOCATION_MAPPING_TH_TO_EN.get(location_th)
        
        analysis_report = {
            "status": "success" if is_valid else "rejected",
            "detected_place": detected_place,
            "score": round(score * 100, 2),
            "is_valid": is_valid
        }

        # --- CASE 1: Rejected by Rules ---
        if not is_valid:
            friendly_message = get_friendly_error_message(detected_place, lang)
            return jsonify({
                'status': 'rejected', 
                'details': friendly_message, 
                'analysis_report': analysis_report
            }), 200
        
        # --- CASE 2: Location Mismatch ---
        if detected_place != expected_place_en:
             if lang == 'ENG':
                 detected_name = detected_place
                 selected_name = LOCATION_MAPPING_TH_TO_EN.get(location_th, location_th)
                 msg = f"AI detected: '{detected_name}'\nwhich does not match your selection ({selected_name})"
             else:
                 detected_name = LOCATION_MAPPING_EN_TO_TH.get(detected_place, detected_place)
                 msg = f"AI ตรวจพบ: '{detected_name}'\nซึ่งไม่ตรงกับที่คุณเลือก ({location_th})"
             
             return jsonify({
                'status': 'rejected', 
                'details': msg,
                'analysis_report': analysis_report
            }), 200

        # --- CASE 3: Success ---
        return jsonify({
            'status': 'success',
            'analysis_report': analysis_report
        })

    except Exception as e:
        print(f"Verify Error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if temp_path and os.path.exists(temp_path): os.remove(temp_path)

# 2. GENERATE (Logic from Processing Branch) -> Modified for Video
@app.route('/generate', methods=['POST'])
def generate_image_route():
    try:
        print("🚀 Starting Generation Process...")
        file = request.files['image']
        location_th = request.form['location']
        img_bytes = file.read()
        
        print(f"🔍 Searching for best reference for: {location_th}")
        ref_bytes = get_best_match_reference(location_th, img_bytes)
        
        client = get_client()
        
        print(f"📸 1. Analyzing Structure...")
        structure = step1_analyze(client, img_bytes)
        
        print(f"🎨 2. Generating Image (Gemini)...")
        prompt_key = LOCATION_INFO.get(location_th, {}).get('prompt_key', "Democracy Monument")
        result_bytes = step2_generate(client, structure, prompt_key, img_bytes, ref_bytes)
        
        if result_bytes:
            print("🎉 Image Generated Success!")
            
            # --- AUTO-SAVE IMAGE ---
            save_generated_image(result_bytes, location_th)
            # ---------------------

            # --- STEP 3: GENERATE VIDEO (NEW) ---
            video_url = generate_video_runway(result_bytes, prompt_key)
            
            video_b64 = None
            if video_url:
                # Save video locally
                vid_filename, vid_path = save_generated_video(video_url, location_th)
                if vid_path:
                    # Convert to Base64 to send to Frontend (Or send URL if serving static files)
                    # For simplicity/prototype: sending base64 (Note: Video base64 is large)
                    with open(vid_path, "rb") as vid_file:
                        video_b64 = base64.b64encode(vid_file.read()).decode('utf-8')

            # Prepare Response
            result_img_b64 = base64.b64encode(result_bytes).decode('utf-8')
            desc = LOCATION_INFO.get(location_th, {}).get('desc_60s', "")
            
            response_data = {
                'status': 'success',
                'image': f"data:image/png;base64,{result_img_b64}",
                'location_name': location_th,
                'description': desc
            }

            if video_b64:
                response_data['video'] = f"data:video/mp4;base64,{video_b64}" # Add video to response
                print("🎥 Video included in response.")
            else:
                print("⚠️ No video generated (Runway error or disabled). Returning image only.")

            return jsonify(response_data)
        else:
            print("❌ Generation Failed (Retries exhausted)")
            return jsonify({'error': 'AI Model Overloaded. Please try again.'}), 503
            
    except Exception as e:
        print(f"❌ Critical Error: {e}")
        return jsonify({'error': str(e)}), 500

# Route สำหรับเสิร์ฟไฟล์วิดีโอ (เผื่ออยากใช้ URL แทน Base64 ในอนาคต)
@app.route('/videos/<path:filename>')
def serve_video(filename):
    return send_from_directory(VIDEO_FOLDER, filename)

@app.route('/')
def home():
    return "✅ Bangkok EraVision Backend (Merged with Classifier & Detailed Poster Prompts) is Running!"

if __name__ == '__main__':
    app.run(debug=True, port=5000)