from flask import Flask, request, jsonify
import os
import base64
import time
import random
import pickle
import numpy as np
import tempfile
import datetime # เพิ่ม datetime เข้ามาสำหรับ timestamp
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
# ส่วนนี้เพิ่มเข้ามาใหม่สำหรับการบันทึกไฟล์อัตโนมัติ
HISTORY_FOLDER = os.path.join(os.path.dirname(__file__), 'generated_history')

def save_generated_image(image_bytes, location_name_th):
    """
    ฟังก์ชันบันทึกรูปผลลัพธ์ลง Local Folder เพื่อการ Debug/Dev
    """
    try:
        # 1. สร้างโฟลเดอร์ถ้ายังไม่มี
        if not os.path.exists(HISTORY_FOLDER):
            os.makedirs(HISTORY_FOLDER)
            print(f"📂 Created history folder at: {HISTORY_FOLDER}")

        # 2. แปลงชื่อสถานที่ให้เป็นภาษาอังกฤษแบบง่าย (สำหรับชื่อไฟล์)
        file_prefix = LOCATION_MAPPING_TH_TO_EN.get(location_name_th, "unknown_location")
        
        # ตัดแต่งชื่อให้สั้นลงและปลอดภัยกับชื่อไฟล์
        safe_name = "place"
        if "Democracy" in file_prefix: safe_name = "democracymonument"
        elif "Sala" in file_prefix: safe_name = "salachalermkrung"
        elif "Swing" in file_prefix: safe_name = "giantswing"
        elif "Yaowarat" in file_prefix: safe_name = "yaowarat"
        elif "Khao San" in file_prefix: safe_name = "khaosan"
        elif "Phra Sumen" in file_prefix: safe_name = "phrasumenfort"
        elif "Sanam Luang" in file_prefix: safe_name = "sanamluang"
        elif "National Museum" in file_prefix: safe_name = "nationalmuseum"
        
        # 3. สร้างชื่อไฟล์: [place]_1960s_[timestamp].png
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_name}_1960s_{timestamp}.png"
        filepath = os.path.join(HISTORY_FOLDER, filename)

        # 4. บันทึกไฟล์
        with open(filepath, "wb") as f:
            f.write(image_bytes)
        
        print(f"💾 Auto-saved result to: {filename}")
        return filepath

    except Exception as e:
        print(f"⚠️ Failed to auto-save image: {e}")
        return None

# ==========================================
# 🧠 AI MEMORY LOADING (FROM PROCESSING)
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

# Mapping สำหรับแปลชื่อกลับเป็นไทยตอน Error Message
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

# --- THE MASTER PROMPT DATABASE (REFINED V.4 - USER FEEDBACK FIX) ---
LOCATION_PROMPTS = {
    "Democracy Monument": """
          **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of the 1960s Democracy Monument.
          **STRUCTURAL LOCK:** Maintain original perspective and geometry 100%. Aspect Ratio must match input.
          
          **GEOMETRY FIX (IMPORTANT):**
          - The four wings must look like **SOLID, HEAVY CONCRETE MASS**. They are NOT flat sheets; they have thickness and curve inward.
          - The surface is **Smooth Plaster/Concrete**, painted Off-white/Cream.
          
          **COLOR & DETAIL:**
          - **The Phan (Top Tray ONLY):** Dark Black/Bronze Metal.
          - **The Turret (Center):** Cream body with **Red Ochre Doors**.
          
          **CONTEXT:**
          - **Street:** Wide **Asphalt** road. Clean, NOT muddy. NO traffic lines.
          - **Vehicles:** White 'Nai Lert' Buses (Rounded shape), Austin/Fiat cars.
          - **Vibe:** Bright tropical daylight, film grain.
      """,

    "Sala Chalermkrung": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Sala Chalermkrung Theatre (1967).

        **ABSOLUTE STRUCTURE LOCK (DO NOT CHANGE):**
        - The main building shape and the wire-frame **"ศาลาเฉลิมกรุง"** sign on the roof MUST remain **100% IDENTICAL** to the original reference image. 
        - DO NOT transform, warp, or redesign the architecture. Keep it exactly as it appears in the 1960s reference.

        **THE MOVIE POSTER (ADD-ON):**
        - **Placement:** Overlay a **Hand-painted Cut-out Billboard** ABOVE the entrance marquee. It should look like an added layer, not part of the wall.
        - **Visuals:** Two men standing back-to-back (One with glasses, one without). White shirts.
        - **Thai Text:** Title "**บางกอกทวิกาล**", Starring "ม.ร.ว.มาดามพงษ์ และ ณัฐภัทร", Director "ตอตุ้ม".

        **CONTEXT:**
        - **Surroundings:** Keep the surrounding shophouses visible but ensure they look like the 1960s era. Do not leave the sides empty.
        - **Street:** **Asphalt Road**. Vintage Taxis/Pedestrians. NO TRAMS.
    """,

    "Giant Swing": """
        **TASK:** Create a **SHARP, PHOTOREALISTIC COLOR PHOTOGRAPH** of The Giant Swing.
        **STRUCTURAL LOCK:** Keep exact perspective. Focus on the Red Pillars.

        **VISUAL ELEMENTS:**
        - **Swing:** Vibrant **Red Teak Logs** standing on a **White Stone Plinth**.
        - **Wat Suthat (Back):** Must look sharp and aged (weathered roof tiles).
        - **Ground:** **Paved Asphalt or Stone**. CLEAN road. **NOT muddy/dilapidated**.
        - **Traffic:** Cars drive AROUND the plinth. NO vehicles under the red pillars.
    """,

    "Yaowarat": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Yaowarat Road (1968).
        
        **TRAM SYSTEM:**
        - **The Tram:** A vintage **Yellow & Red Wooden Tram**.
        - **Position:** Running **Close to the sidewalk**.
        
        **CLEAN UP INSTRUCTION:**
        - **REDUCE SIGNAGE:** Remove excessive signs. The street should look **OPEN and WIDE**.
        - **Text Rule:** **THAI SCRIPT ONLY** for the remaining signs. Hand-painted style.
        
        **ATMOSPHERE:**
        - **Road:** Asphalt.
        - **Lighting:** Warm "Golden Hour" sunlight. NO LED/Neon glow.
    """,

    "Khaosan Road": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Bang Lamphu / Khaosan Road (1962).
        **CONTEXT:** A quiet **Rice Trading Residential Community**. 
        
        **VISUALS:**
        - **Architecture:** Wooden row houses painted **YELLOWISH WOOD** with **GREEN WINDOWS**.
        - **Street:** **WIDE ASPHALT ROAD**. Clean and orderly. NOT muddy.
        - **Clean Up:** **REMOVE SIGNS** from the front of the houses. Keep it minimal.
        - **Props:** **White Hemp Rice Sacks** stacked neatly.
        - **Vibe:** Domestic, sleepy, non-tourist.
    """,

    "Phra Sumen Fort": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Phra Sumen Fort (1960).
        
        **CONDITION FIX (NOT A RUIN):**
        - **Status:** The fort is **STRUCTURALLY INTACT**. It should look **AGED** with black mold/stains on white plaster, but NOT crumbled or abandoned like a jungle ruin.
        
        **SURROUNDINGS (STREET VIEW):**
        - **Viewpoint:** From the street level.
        - **Community:** Show **Wooden Residential Houses** built near the fort.
        - **Environment:** **NO Jungle/Forest.** Minimize the canal view if it distracts.
        - **Road:** **Asphalt/Dirt Road**. Not a swamp.
    """,

    "Sanam Luang": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Sanam Luang (Weekend Market 1968).
        
        **VISUALS:**
        - **Market:** **Canvas Parasols** (Red, White, Blue stripes) spaced out.
        - **Sky:** Many **Thai Kites** (Chula/Pakpao) floating.
        - **Ground:** **Red Dust/Dirt (Laterite)** mixed with dry grass.
        - **Road:** Surrounding roads are **Asphalt**.
    """,

    "National Museum": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of National Museum Bangkok (1960).
        **FOCUS:** Authentic Thai Architecture.
        
        **DETAILS:**
        - **Building:** Traditional Thai gable roof (dark tiles). White walls with rain streaks.
        - **Garden:** Large shade trees.
        - **Ground:** Gravel/Dirt paths. Clean and swept.
        - **Fence:** Black iron spearhead fence.
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
                model="gemini-2.0-flash", 
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
    - **FILM LOOK:** Imitate 1960s Kodachrome slide film aesthetic (rich colors, warm cast, natural grain).
    - **ASPECT RATIO:** The output image must maintain the same aspect ratio and framing as the input image.
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

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="nano-banana-pro-preview", 
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
                t = (2 ** attempt) + random.uniform(0, 1)
                print(f"⚠️ Busy ({e}) -> Waiting {t:.1f}s")
                time.sleep(t)
            else:
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

# 2. GENERATE (Logic from Processing Branch)
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
        
        print(f"🎨 2. Generating Image...")
        prompt_key = LOCATION_INFO.get(location_th, {}).get('prompt_key', "Democracy Monument")
        result_bytes = step2_generate(client, structure, prompt_key, img_bytes, ref_bytes)
        
        if result_bytes:
            print("🎉 Success!")
            
            # --- AUTO-SAVE LOGIC (NEW) ---
            # บันทึกไฟล์ลง Folder ทันทีที่ Gen เสร็จ
            save_generated_image(result_bytes, location_th)
            # -----------------------------

            result_b64 = base64.b64encode(result_bytes).decode('utf-8')
            desc = LOCATION_INFO.get(location_th, {}).get('desc_60s', "")
            return jsonify({
                'status': 'success',
                'image': f"data:image/png;base64,{result_b64}",
                'location_name': location_th,
                'description': desc
            })
        else:
            print("❌ Generation Failed (Retries exhausted)")
            return jsonify({'error': 'AI Model Overloaded. Please try again.'}), 503
            
    except Exception as e:
        print(f"❌ Critical Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/')
def home():
    return "✅ Bangkok EraVision Backend (Merged with Classifier & Detailed Poster Prompts) is Running!"

if __name__ == '__main__':
    app.run(debug=True, port=5000)