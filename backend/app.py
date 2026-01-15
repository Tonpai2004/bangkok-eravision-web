from flask import Flask, request, jsonify, send_from_directory
import os
import base64
import time
import random
import pickle
import numpy as np
import tempfile
import datetime
import requests # จำเป็นสำหรับการยิง Runway
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
# 💾 AUTO-SAVE SYSTEM
# ==========================================
HISTORY_FOLDER = os.path.join(os.path.dirname(__file__), 'generated_history')
VIDEO_FOLDER = os.path.join(os.path.dirname(__file__), 'generated_videos')

if not os.path.exists(HISTORY_FOLDER): os.makedirs(HISTORY_FOLDER)
if not os.path.exists(VIDEO_FOLDER): os.makedirs(VIDEO_FOLDER)

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

# --- THE MASTER PROMPT DATABASE ---
LOCATION_PROMPTS = {
    "Democracy Monument": """
          **TASK:** Create a **HYPER-REALISTIC** photograph of Democracy Monument (Bangkok 1960s).
          
          **PERSPECTIVE LOCK (CRITICAL):**
          - Use the Uploaded Image as the **Absolute Layout Blueprint**.
          - Keep the exact camera angle and composition.
          
          **ARCHITECTURAL ACCURACY:**
          - **Wings:** 4 Concrete wings, concave curve, bas-reliefs at base. Color: Weathered Cream/Grey Stucco.
          - **Center:** Solid turret with **Dark Bronze/Black Metal Tray**.
          - **Base:** The circular steps are **BARE CONCRETE**. NO FLOWERS. NO GRASS.

          **LOGIC & SAFETY RULES:**
          - **PEDESTRIANS:** Pedestrians must be strictly on the **far sidewalks** only.
          
          **SURROUNDINGS:**
          - **Buildings:** Aged Terracotta/Brick Orange Ratchadamnoen buildings.
          - **Road:** Wide Asphalt. NO modern lane markings.

          **Negative Prompt:** Tram, tram rails, skytrain, modern billboards, LED screens, motorcycles, tuk-tuks, people on road.
      """,

    "Sala Chalermkrung": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Sala Chalermkrung Theatre (1967).
        
        **PERSPECTIVE LOCK:** Maintain exact camera angle from input image.
        
        **THE MOVIE POSTER (SPECIFIC):**
        - **Visual:** Hand-painted cutout. Two men in white shirts standing back-to-back.
        - **Text (THAI ONLY):** Title "**บางกอกทวิกาล**". Starring "**มาดามพงษ์ และ ณัฐภัทร**".
        
        **CONTEXT:**
        - **Street:** Wide asphalt avenue.
        - **Surroundings:** Authentic 1960s shophouses.
    """,

    "Giant Swing": """
        **TASK:** Create a **SHARP, PHOTOREALISTIC COLOR PHOTOGRAPH** of The Giant Swing (1965).

        **PERSPECTIVE & VISIBILITY RULE:**
        - If the original image shows Wat Suthat, render it as aged/weathered.
        - **IF THE ORIGINAL IMAGE DOES NOT SHOW THE TEMPLE, DO NOT ADD IT.**

        **DETAILS:**
        - **The Swing:** Two towering **Vibrant Red Teak Pillars** standing on a clean White Stone Plinth.
        - **Structure:** intricate carved crossbar at the top. **NO SWINGING CEREMONY**.
        - **Road Layout:** The Giant Swing acts as a long roundabout.
        - **Traffic:** Vintage 1960s sedans, Samlors, and round-nose trucks.

        **NEGATIVE PROMPT:** Men swinging, modern traffic lights, 7-Eleven, tourists in shorts.
    """,
    
    "Yaowarat": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Yaowarat Road (1968).
        
        **STRICT TEXT & SIGNS:**
        - **Text:** Hand-painted signs. **LEGIBLE Thai & Chinese**.
        - **Mandatory Texts:** "**ห้างทอง ฮั่วเซ่งเฮง**", "**ภัตตาคาร หูฉลาม**", "**ขายยาจีน**".
        - **Lighting:** DAYLIGHT only. **NO NEON GLOW**. NO LED.
        
        **TRAM REALISM:**
        - **Tram:** Weathered Yellow/Red wooden tram.
        - **Position:** Running on rails **HUGGING THE RIGHT CURB**.
    """,

    "Khaosan Road": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Bang Lamphu / Khaosan Road (1962).

        **PERSPECTIVE LOCK (CRITICAL):**
        - **Blueprint:** Use the Uploaded Image as the **ABSOLUTE LAYOUT REFERENCE**.
        
        **VISUALS & COLORS:**
        - **Houses:** Wooden row houses painted **YELLOW WOOD** with **GREEN WINDOWS**.
        - **Signage:** **NO SIGNS** on the house fronts. Residential look only.
        
        **LIFE:**
        - **Atmosphere:** Vibrant community. Locals chatting.
        - **Props:** Rice sacks stacked at **ONLY 2-3 HOUSES**.

        **NEGATIVE PROMPT:** Backpackers, foreigners in shorts, neon signs, bars, hostels.
    """,

    "Phra Sumen Fort": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Phra Sumen Fort (1960).
        
        **CRITICAL ACCURACY: HEADLESS FORT:**
        - **Status:** The top wooden roof spire is **COMPLETELY MISSING**. The white tower is truncated/severed.
        - **Structure:** Hexagonal white plaster fort, stained with black mold.
    """,

    "Sanam Luang": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Sanam Luang (Weekend Market 1968).
        
        **MARKET REALISM:**
        - **Stalls:** Vendors sitting on **WOVEN MATS** on the red dust ground. Bamboo parasols.
        - **Density:** Lively but not overcrowded.
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

# --- Friendly Error Message ---
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

# --- CLIP Logic ---
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

# --- Gemini Generation Logic ---
def step1_analyze(client, img_bytes):
    prompt = "Analyze the precise geometry, camera angle, and structural layout..."
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-1.5-flash", # Stable model for analysis
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

    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"🎨 Generating Image (Attempt {attempt+1})...")
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
                print(f"❌ Critical Gen Error: {e}")
                return None
    return None

# ==========================================
# 🎬 RUNWAY ML INTEGRATION (NEW)
# ==========================================
def generate_video_runway(image_bytes, location_key):
    runway_key = os.getenv("RUNWAYML_API_KEY")
    if not runway_key:
        print("❌ Error: ไม่เจอ RUNWAYML_API_KEY ในไฟล์ .env")
        return None

    try:
        print("🎬 Starting Runway Video Generation...")
        
        # PRE-PROCESS: แก้ Aspect Ratio อัตโนมัติ
        try:
            img = Image.open(io.BytesIO(image_bytes))
            width, height = img.size
            ratio = width / height
            
            # ถ้าภาพกว้างเกิน 1.8 (ใกล้เคียง 16:9 คือ 1.77) ให้ตัดขอบออก
            # Runway รับได้สูงสุด 2.0 แต่เอา 1.77 (16:9) เพื่อความปลอดภัยและสวยงาม
            MAX_RATIO = 1.78 
            
            if ratio > MAX_RATIO:
                print(f"⚠️ Image ratio {ratio:.2f} is too wide (Limit {MAX_RATIO}). Auto-cropping center...")
                
                new_width = int(height * MAX_RATIO)
                left = (width - new_width) / 2
                top = 0
                right = (width + new_width) / 2
                bottom = height
                
                img = img.crop((left, top, right, bottom))
                
                # แปลงกลับเป็น Bytes เพื่อส่งต่อ
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                image_bytes = buffered.getvalue()
                print(f"✅ Cropped to {img.size} (Ratio: {img.size[0]/img.size[1]:.2f})")
                
        except Exception as crop_err:
            print(f"⚠️ Warning: Auto-crop failed ({crop_err}). Sending original image.")
        # ==========================================

        base64_str = base64.b64encode(image_bytes).decode('utf-8')
        
        base_prompt = "Photorealistic 8k video, sharp focus. static camera with a gentle smooth zoom-in. Coherent motion, object permanence, physics-abiding. 1960s vintage atmosphere. No floating objects, no glitch."

        # 2. SPECIFIC PROMPT (แก้บั๊กของแต่ละที่):
        location_prompts = {
            "Democracy Monument": "Clouds moving slowly in the sky. Vintage cars driving smoothly in lanes in the distance.",
            
            "Sala Chalermkrung": "People standing naturally in front of the theater, subtle movements. Vintage cars passing by smoothly.",
            
            "Giant Swing": "Vintage cars driving slowly around the giant swing in a smooth curve, maintaining distance. Clear weather.",
            
            "Yaowarat": "A yellow tram moving slowly on fixed rails. Pedestrians walking on sidewalks only. Vibrant street atmosphere.",
            
            "Khaosan Road": "Locals sitting and chatting in front of wooden houses. Trees swaying gently in the wind. Peaceful vibe.",
            
            "Phra Sumen Fort": "Trees swaying gently near the white fort. Sunlight shifting naturally. Realistic shadows.",
            
            "Sanam Luang": "Canvas umbrellas swaying slightly in the breeze. People walking slowly in the market.",
            
            "National Museum": "Sunlight filtering through tamarind trees. Leaves rustling gently. Serene atmosphere."
        }

        specific_action = location_prompts.get(location_key, "Natural lighting changes, realistic texture rendering.")
        
        final_prompt = f"{base_prompt} {specific_action}"
        print(f"📝 Prompt Used: {final_prompt}")

        url = "https://api.dev.runwayml.com/v1/image_to_video"
        
        payload = {
            "promptImage": f"data:image/png;base64,{base64_str}",
            "model": "gen3a_turbo",
            "promptText": final_prompt,
            "duration": 5,
            "ratio": "1280:768"
        }
        
        headers = {
            "Authorization": f"Bearer {runway_key}",
            "X-Runway-Version": "2024-11-06",
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Runway API Failed ({response.status_code}): {response.text}")
            return None
            
        task_id = response.json().get('id')
        print(f"⏳ Runway Task ID: {task_id} (Waiting for result...)")
        
        # Polling Loop
        for i in range(30):
            time.sleep(3)
            status_res = requests.get(f"https://api.dev.runwayml.com/v1/tasks/{task_id}", headers=headers)
            
            if status_res.status_code == 200:
                data = status_res.json()
                status = data.get('status')
                
                if status == "SUCCEEDED":
                    print("✅ Video Generation Complete!")
                    return data.get('output', [None])[0]
                elif status == "FAILED":
                    print(f"❌ Video Generation FAILED: {data.get('failure', 'Unknown error')}")
                    return None
                else:
                    print(f"   ...processing ({i+1}/30)")
            else:
                print(f"⚠️ Polling Error: {status_res.status_code}")

        print("❌ Timeout: Runway took too long.")
        return None
        
    except Exception as e:
        print(f"❌ Critical Runway Error: {e}")
        return None
    
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

def save_generated_video(video_url, location_key):
    try:
        # ตรวจสอบและสร้างโฟลเดอร์ให้ชัวร์
        if not os.path.exists(VIDEO_FOLDER):
            os.makedirs(VIDEO_FOLDER)
            print(f"📁 Created video folder at: {VIDEO_FOLDER}")

        print(f"⬇️ Downloading video from: {video_url}")
        response = requests.get(video_url, stream=True)
        
        if response.status_code == 200:
            file_prefix = location_key.replace(" ", "").lower()
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{file_prefix}_video_{timestamp}.mp4"
            filepath = os.path.join(VIDEO_FOLDER, filename)
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk: f.write(chunk)
            
            print(f"🎥 Auto-saved video to: {filepath}")
            return filename, filepath
        else:
            print(f"❌ Download Failed. Status: {response.status_code}")
            return None, None
    except Exception as e:
        print(f"⚠️ Save Video Failed: {e}")
        return None, None

# ==========================================
# 🚀 ROUTES
# ==========================================

@app.route('/verify', methods=['POST'])
def verify_image_route():
    try:
        if 'image' not in request.files: return jsonify({'error': 'No image'}), 400
        file = request.files['image']
        location_th = request.form['location']
        lang = request.form.get('language', 'TH').upper() # รับค่าภาษามาด้วย
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp:
            file.save(temp.name)
            temp_path = temp.name
            
        detected_place, score, is_valid = classify_image(temp_path)
        os.remove(temp_path)
        
        expected_en = LOCATION_MAPPING_TH_TO_EN.get(location_th)
        
        analysis_report = {
            "status": "success" if is_valid else "rejected",
            "detected_place": detected_place,
            "score": round(score * 100, 2),
            "is_valid": is_valid
        }
        
        if not is_valid: 
            friendly_message = get_friendly_error_message(detected_place, lang)
            return jsonify({'status': 'rejected', 'details': friendly_message, 'analysis_report': analysis_report}), 200
            
        if detected_place != expected_en: 
             if lang == 'ENG':
                 detected_name = detected_place
                 selected_name = LOCATION_MAPPING_TH_TO_EN.get(location_th, location_th)
                 msg = f"AI detected: '{detected_name}'\nwhich does not match your selection ({selected_name})"
             else:
                 detected_name = LOCATION_MAPPING_EN_TO_TH.get(detected_place, detected_place)
                 msg = f"AI ตรวจพบ: '{detected_name}'\nซึ่งไม่ตรงกับที่คุณเลือก ({location_th})"
             return jsonify({'status': 'rejected', 'details': msg, 'analysis_report': analysis_report}), 200

        return jsonify({'status': 'success', 'analysis_report': analysis_report})
    except Exception as e: return jsonify({'error': str(e)}), 500

# ENDPOINT 1: GENERATE IMAGE
@app.route('/generate', methods=['POST'])
def generate_image_route():
    try:
        print("🚀 [Step 1] Generative Image...")
        file = request.files['image']
        location_th = request.form['location']
        img_bytes = file.read()
        
        ref_bytes = get_best_match_reference(location_th, img_bytes)
        client = get_client()
        structure = step1_analyze(client, img_bytes)
        
        prompt_key = LOCATION_INFO.get(location_th, {}).get('prompt_key', "Democracy Monument")
        result_bytes = step2_generate(client, structure, prompt_key, img_bytes, ref_bytes)
        
        if result_bytes:
            save_generated_image(result_bytes, location_th)
            result_b64 = base64.b64encode(result_bytes).decode('utf-8')
            desc = LOCATION_INFO.get(location_th, {}).get('desc_60s', "")
            
            # ✅ คืนค่า location_key ไปด้วย เพื่อให้ Frontend ส่งไปทำ Video ต่อได้
            return jsonify({
                'status': 'success',
                'image': f"data:image/png;base64,{result_b64}",
                'location_name': location_th,
                'location_key': prompt_key, 
                'description': desc
            })
        else:
            return jsonify({'error': 'AI Model Busy. Please try again.'}), 503
    except Exception as e:
        print(f"❌ Gen Error: {e}")
        return jsonify({'error': str(e)}), 500

# ENDPOINT 2: ANIMATE VIDEO
@app.route('/animate', methods=['POST'])
def animate_video_route():
    try:
        print("🚀 [Step 2] Animating Video...")
        data = request.json
        image_data = data.get('image') # Base64 Image
        location_key = data.get('location_key')

        if not image_data: return jsonify({'error': 'No image provided'}), 400
        
        # Clean Base64 header
        if "," in image_data: image_data = image_data.split(",")[1]
        image_bytes = base64.b64decode(image_data)

        # 1. เรียก Runway ให้สร้างวิดีโอ
        video_url = generate_video_runway(image_bytes, location_key)
        
        if video_url:
            print(f"✅ Runway Success! URL: {video_url}")
            
            # 2. พยายามบันทึกลงเครื่อง (Local Save)
            vid_filename, vid_path = save_generated_video(video_url, location_key)
            
            final_video_src = video_url # Default: ใช้ URL ตรงจาก Runway (เผื่อ Save พัง)

            # 3. ถ้า Save สำเร็จ ให้แปลงเป็น Base64 (เพื่อความเร็วในการโหลด Local)
            if vid_path and os.path.exists(vid_path):
                try:
                    with open(vid_path, "rb") as f:
                        vid_b64 = base64.b64encode(f.read()).decode('utf-8')
                        final_video_src = f"data:video/mp4;base64,{vid_b64}"
                        print("📦 Sending Video as Base64")
                except Exception as e:
                    print(f"⚠️ Read File Error: {e} -> Sending Remote URL instead")
            else:
                print("⚠️ Save failed or File not found -> Sending Remote URL directly")

            # 4. ส่งผลลัพธ์กลับ Frontend (ไม่ว่า Save ได้หรือไม่ได้ User ต้องเห็นวิดีโอ)
            return jsonify({
                'status': 'success',
                'video': final_video_src
            })
        else:
            return jsonify({'error': 'Video generation failed (Runway returned None)'}), 500

    except Exception as e:
        print(f"❌ Critical Animate Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/videos/<path:filename>')
def serve_video(filename):
    return send_from_directory(VIDEO_FOLDER, filename)

if __name__ == '__main__':
    app.run(debug=True, port=5000)