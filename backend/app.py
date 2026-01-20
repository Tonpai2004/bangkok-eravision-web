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

# --- THE MASTER PROMPT DATABASE (V.17 - FLAWLESS & HISTORICAL) ---
LOCATION_PROMPTS = {
    # 🏛️ อนุสาวรีย์ประชาธิปไตย: ปืนใหญ่ 75 กระบอก (ฝังดินรอบนอก) + รถวิ่งวนซ้าย (ไทยขับชิดซ้าย)
    "Democracy Monument": """
          **TASK:** Create a **HYPER-REALISTIC** photograph of Democracy Monument (Bangkok 1960s).
          
          **PERSPECTIVE LOCK (CRITICAL):**
          - Use the Uploaded Image as the **Absolute Layout Blueprint**.
          - Keep the exact camera angle and composition. DO NOT ROTATE.
          
          **ARCHITECTURAL ACCURACY:**
          - **Wings:** 4 Concrete wings, concave curve, bas-reliefs at base. Color: Weathered Cream/Grey Stucco.
          - **Center:** Solid turret with **Dark Bronze/Black Metal Tray**.
          - **Base & Cannons (CRITICAL FIX):** The circular tiered base is BARE CONCRETE. Around the **OUTER PERIMETER** (at ground level, NOT on the steps), there are **75 SMALL BLACK CANNONS** buried muzzle-up in the ground, connected by **HEAVY IRON CHAINS**.
          - **NEGATIVE PROMPT:** No cannons on the steps, no flowers, no grass on the monument.

          **TRAFFIC RULES (CRITICAL):**
          - **One-Way Circle:** Cars drive **CLOCKWISE** around the circle (Thai left-hand traffic rule means roundabout flow is clockwise).
          - **Vehicle Models:** **Fiat 1100, Austin Cambridge, Morris Minor**. NO MODERN CARS.
          - **Safety:** **NO CARS ON THE MONUMENT BASE.** Keep them on the asphalt road.
          
          **SURROUNDINGS:**
          - **Buildings:** Aged Terracotta/Brick Orange Ratchadamnoen buildings.
          - **Road:** Wide Asphalt. NO modern lane markings.
      """,

    "Sala Chalermkrung": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Sala Chalermkrung Theatre (1967).
        
        **PERSPECTIVE LOCK:** Maintain exact camera angle from input image.
        
        **CLEAN FOREGROUND:**
        - **REMOVE** any wooden shophouses or obstructing buildings in the immediate foreground/opposite side. Keep the view of the theater open and grand.
        
        **THE MOVIE POSTER (SPECIFIC):**
        - **Visual:** Hand-painted cutout. Two men in white shirts standing back-to-back. One wears glasses, one doesn't. Both look smart/gentlemen.
        - **Text (THAI ONLY - LEGIBLE):** Title "**บางกอกทวิกาล**". Starring "**มาดามพงษ์ และ ณัฐภัทร**". Director "**ตอตุ้ม**". Text: "**ฉายพฤษภาคมนี้ ที่เฉลิมกรุง**".
        
        **CONTEXT:**
        - **Street:** Wide asphalt avenue.
        - **Traffic:** Vintage **Datsun Bluebird taxis** and classic sedans. No Trams.
    """,

    "Giant Swing": """
        **TASK:** Create a **SHARP, PHOTOREALISTIC COLOR PHOTOGRAPH** of The Giant Swing (1965).

        **PERSPECTIVE & VISIBILITY RULE (CRITICAL):**
        - **IF the original image shows Wat Suthat:** Render it clearly with aged, weathered roof tiles and white walls.
        - **IF the original image DOES NOT show the temple:** **DO NOT ADD IT.** Focus solely on transforming the surrounding shophouses to be historically accurate (1960s style, aged wood/concrete, tile roofs).

        **DETAILS:**
        - **The Swing:** Two towering **Vibrant Red Teak Pillars** standing on a clean White Stone Plinth.
        - **Structure:** Intricate carved crossbar at the top. **NO ROPES HANGING DOWN**. It is empty.
        
        **TRAFFIC REALISM:**
        - **Cars:** **Fiat 1100 and Austin Cambridge**. Driving straight on the road alongside the swing.
        - **Clean Image:** **NO SPEED LINES, NO MOTION BLUR LINES, NO GLITCHES** following the cars. The air must be clear.

        **NEGATIVE PROMPT:** Ropes hanging from swing, men swinging, modern traffic lights, 7-Eleven, tourists in shorts, speed lines, motion trails.
    """,
    
    "Yaowarat": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Yaowarat Road (1968).
        
        **STRICT TEXT & SIGNS:**
        - **Text:** Hand-painted signs. **LEGIBLE Thai & Chinese**. No gibberish.
        - **Mandatory Texts:** "**ห้างทอง ฮั่วเซ่งเฮง**", "**ภัตตาคาร หูฉลาม**", "**ขายยาจีน**".
        - **Lighting:** DAYLIGHT only. **NO NEON GLOW**. NO LED.
        
        **TRAM REALISM:**
        - **Tram:** Weathered Yellow/Red wooden tram.
        - **Position:** Running on rails **HUGGING THE RIGHT CURB** (near houses). Not in the middle.
        
        **TRAFFIC:**
        - **Vehicles:** **Samlors (Tricycles)** and **Round-nose Trucks (Isuzu TX)**. No modern sedans.
    """,

    "Khaosan Road": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Bang Lamphu / Khaosan Road (1962).

        **PERSPECTIVE LOCK (CRITICAL):**
        - **Blueprint:** Use the Uploaded Image as the **ABSOLUTE LAYOUT REFERENCE**.
        
        **VISUALS & COLORS:**
        - **Houses:** Wooden row houses painted **YELLOW WOOD** with **GREEN WINDOWS**.
        - **Signage:** **NO SIGNS** on the house fronts. Residential look only.
        
        **PEOPLE (THAI LOCALS):**
        - **Faces:** Authentic **THAI FACES** (South East Asian features, tan skin, black hair).
        - **Clothing:** White shirts, simple trousers/sarongs. **NO FOREIGNERS/BACKPACKERS**.
        
        **LIFE:**
        - **Atmosphere:** Vibrant community. Locals chatting.
        - **Props:** Rice sacks stacked at **ONLY 2-3 HOUSES**.

        **NEGATIVE PROMPT:** Backpackers, foreigners in shorts, neon signs, bars, hostels, Caucasian faces.
    """,

    "Phra Sumen Fort": """
        **TASK:** Create a **HYPER-REALISTIC COLOR PHOTOGRAPH** of the **RUINS** of Phra Sumen Fort (Bangkok 1960).
        
        **STRUCTURAL STATE (CRITICAL):**
        - **NOT A FULL TOWER:** The fort is a **DECAPITATED RUIN**. 
        - **HEIGHT:** It must be **ONLY 1 STORY HIGH**. It is just a wide, white hexagonal stone base (stump).
        - **TOP PART:** The entire upper tower, all windows on the second floor, and the conical roof are **TOTALLY REMOVED/NON-EXISTENT**. 
        - **SURFACE:** The top of the ruin is jagged, flat.
        - **STAINING:** Heavily weathered with black mold, moss, and humidity stains on aged white plaster.

        **ENVIRONMENT (1960s CONTEXT):**
        - **NO PARK:** There is no "Santi Chai Prakan Park." No green lawn.
        - **STREET:** Narrow asphalt road.

        **NEGATIVE PROMPT:** complete fort, restored tower, high walls, roof, spire, pointed top, windows on upper floor, public park, green lawn, manicured trees, modern railings, cars.
    """,

    "Sanam Luang": """
        **TASK:** Create a **HYPER-REALISTIC** color photograph of the Sanam Luang Weekend Market (Bangkok 1968).

        **SPATIAL LOGIC (THE ORGANIC CHAOS):**
        - **Perimeter:** Large canvas-covered stalls and heavy parasols (Red, Blue, White) are clustered under the massive tamarind trees.
        - **Central Field:** An **ORGANIC SPRAWL**. Messy and scattered clusters of people sitting on woven bamboo mats (Sua Phra) or cardboard.
        - **Itinerant Vendors:** Scattered throughout are **Walking Vendors** with bamboo shoulder poles (Kanh-Chab) and small wooden pushcarts selling snacks.

        **GROUND & ATMOSPHERE:**
        - **Surface:** A realistic mix of **scorched yellow grass** and **dusty dry red dirt**. Sharp focus on the uneven, trodden ground.
        - **Horizon:** Hazy, golden rooftops of **Wat Phra Kaew** visible in the distance under a bright tropical sun.
        - **Lighting:** Dappled sunlight filtering through tamarind trees creating high-contrast shadows.

        **MARKET DETAILS:**
        - **Goods:** Amulets on red cloth, stacks of old books, clay pots, and traditional enamel basins.
        - **Props:** Use only **Large Canvas/Bamboo Parasols**. Add vintage hand-painted billboards at the edges.

        **PEOPLE & ATTIRE:**
        - **Vibe:** A dense, unorganized crowd of 1960s Thai locals in simple white shirts and sarongs, moving in all directions.

        **NEGATIVE PROMPT:** modern blue plastic tents, plastic chairs, neat rows, modern street furniture, digital signage, motion blur, modern cars.
    """,

    # "National Museum": """
    #     **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of the **FRONT** of National Museum Bangkok (1960).
        
    #     **FRONT ATMOSPHERE:**
    #     - **Vibe:** Serene, shady, well-maintained.
    #     - **Grounds:** Swept gravel, manicured grass, large trees. NOT overgrown.
    #     - **Perspective:** Keep the exact view of the front facade from the input image.
    # """,

    "National Museum": """
        **TASK:** Create an **AUTHENTIC 1960s VINTAGE PHOTOGRAPH** of the National Museum Bangkok.
        
        **BACKGROUND PURGE (CRITICAL):**
        - **REMOVE ALL MODERN BUILDINGS:** Absolutely NO skyscrapers, NO office buildings, NO modern concrete structures visible behind the temple or trees. The horizon must be only sky and tree canopies.
        
        **HISTORICAL TEXTURES (STRICT):**
        - **The Fence:** A low, thick white-washed masonry base. The **SQUARE PILLARS** must look aged with **cracks, peeling lime-wash, and dark grey humidity stains**. The iron bars between them must be dark, rusty black.
        - **Architecture:** The main buildings must have **DULL, MATTE walls** (not bright white). Add heavy weathering on the stucco. Roof tiles should be faded, dusty orange.
        
        **ATMOSPHERIC DEPTH:**
        - **Haze & Dust:** Add a very subtle tropical haze in the air to soften the background. 
        - **Lighting:** Warm, late-afternoon sun. Create long, soft shadows.
        - **Film Aesthetic:** 1960s warm-toned print, low saturation, visible organic film grain. NO digital sharpness.

        **NEGATIVE PROMPT:** modern skyscrapers, modern buildings in background, bright white paint, vibrant orange, digital sharpness, 3D render look, flags, modern signs, motion blur.
    """,
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
    prompt = """Analyze this image of the National Museum Bangkok:
    1. Identify all permanent structures.
    2. PERSPECTIVE CHECK: Is this a view from the OUTSIDE (looking at the perimeter fence) or from the INSIDE (the courtyard/throne hall area)?
    3. FENCE DETECTED: Answer 'YES' if a perimeter fence/gate is visible, or 'NO' if it is an inner courtyard.
    4. Provide a structural description based on this perspective."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-1.5-flash", 
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
    - **GLOBAL NEGATIVE PROMPT:** modern logos (7-Eleven, Starbucks, Apple, etc.), brand names, QR codes, CCTV cameras, satellite dishes, air conditioning units, modern cars (Toyota, Honda, Tesla), motorcycles, LED signs, concrete barriers, plastic chairs, watermarks, text overlay, glitch text, distorted letters.
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
    
    # 🔴 เลือกโมเดลที่มีในบัญชีจริง
    # === เรียงลิสต์ ===
    # gemini-2.0-flash-exp-image-generation
    # gemini-2.5-flash-image
    # gemini-3-flash-preview
    # === Premium ===
    # gemini-3-pro-preview
    # gemini-3-pro-image-preview

    model_name = "gemini-2.5-flash-image" # เริ่มต้นด้วยโมเดลกลางๆ

    for attempt in range(max_retries):
        try:
            print(f"🎨 Generating Image (Attempt {attempt+1}/{max_retries}) using {model_name}...")
            
            response = client.models.generate_content(
                model=model_name, 
                contents=parts,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    temperature=0.2
                )
            )
            for part in response.candidates[0].content.parts:
                if part.inline_data: return part.inline_data.data
            
            print(f"⚠️ Warning: Model returned no image (Attempt {attempt+1})")
            
        except Exception as e:
            if "not found" in str(e).lower() and model_name == "gemini-2.0-flash-exp-image-generation":
                print("⚠️ Switching model to nano-banana-pro-preview...")
                model_name = "gemini-2.0-flash-exp-image-generation" # ถ้าไม่ได้ปรับไปตัวกากๆ(ประหยัดงบ)
                time.sleep(1)
                continue

            if "429" in str(e) or "503" in str(e):
                t = (2 ** attempt) + random.uniform(1, 3)
                print(f"⚠️ Server Busy ({model_name}) -> Waiting {t:.1f}s...")
                time.sleep(t)
            else:
                print(f"❌ Critical Gen Error: {e}")
                if model_name != "nano-banana-pro-preview":
                     model_name = "nano-banana-pro-preview"
                     continue
                return None
                
    return None

# ==========================================
# 🎬 RUNWAY ML INTEGRATION (STRICT & REALISTIC)
# ==========================================
def generate_video_runway(image_bytes, location_key):
    runway_key = os.getenv("RUNWAYML_API_KEY")
    if not runway_key:
        print("❌ Error: ไม่เจอ RUNWAYML_API_KEY ในไฟล์ .env")
        return None

    try:
        print("🎬 Starting Runway Video Generation (V.17 - Ultimate Polishing)...")
        
        # 1. Image Pre-processing
        try:
            img = Image.open(io.BytesIO(image_bytes))
            width, height = img.size
            ratio = width / height
            MAX_RATIO = 1.78 
            
            if ratio > MAX_RATIO:
                print(f"⚠️ Image ratio {ratio:.2f} is too wide (Limit {MAX_RATIO}). Auto-cropping center...")
                new_width = int(height * MAX_RATIO)
                left = (width - new_width) / 2
                top = 0
                right = (width + new_width) / 2
                bottom = height
                img = img.crop((left, top, right, bottom))
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                image_bytes = buffered.getvalue()
                print(f"✅ Cropped to {img.size}")
                
        except Exception as crop_err:
            print(f"⚠️ Warning: Auto-crop failed ({crop_err}). Sending original image.")

        base64_str = base64.b64encode(image_bytes).decode('utf-8')
        
        # 2. RUNWAY PROMPT ENGINEERING (FLAWLESS & GLITCH-FREE)
        # Goal: Static camera, realistic physics, no filters, no glitches.

        # base_prompt = """
        # Static tripod camera shot, absolutely NO panning, NO zooming, NO rotation. 
        # Hyper-realistic 8k video, high fidelity, sharp focus. 
        # Clear daylight, natural colors (NO vintage filter, NO sepia, NO grain). 
        # Physics-based motion: cars driving straight in lanes, people walking naturally (no sliding).
        # Stable structures, no morphing buildings. No visual glitches.
        # """

        base_prompt = """
        Static tripod camera shot, absolutely NO panning, NO zooming, NO rotation. 
        Hyper-realistic 8k video, high fidelity. 
        Subtle environmental motion only. Stable structures, no morphing buildings. 
        Natural 1960s lighting with very subtle film grain. No visual glitches.
        """

        location_prompts = {
            "Democracy Monument": "Static shot. Cars are parked still on the road. ONLY clouds in the sky move slowly. Subtle heat haze on the asphalt. No car movement at all.",
            
            "Sala Chalermkrung": "Atmospheric dust motes dancing in the sunlight. Subtle shadows shifting on the theater facade. Flags on the roof swaying very gently in the breeze.",
            
            "Giant Swing": "The red pillars remain perfectly still and solid. Background tree leaves rustling gently. Atmospheric haze in the distance. No movement on the swing itself.",
            
            "Yaowarat": "Heat haze shimmering slightly above the asphalt. Subtle flickering of sunlight reflecting off aged glass windows. Very slow cloud movement overhead.",
            
            "Khaosan Road": "Leaves of trees sways gently in the breeze. Natural shadows of trees moving slowly on the wooden house fronts. Calm and still residential atmosphere.",
            
            "Phra Sumen Fort": "Sunlight filtering through trees, creating moving dappled shadows on the white stone ruins. Overgrown grass on top of the ruin swaying slightly. No reconstruction of the fort.",
            
            "Sanam Luang": "Canvas umbrellas fluttering very subtly in the wind. Kites in the far distance moving slightly against the clouds. The ground remains stable and clear.",
            
            "National Museum": "A very calm, Zen-like atmosphere. Dappled sunlight and shadows shifting slowly on the white walls and gravel ground. Tree branches swaying gently."
        }

        specific_action = location_prompts.get(location_key, "Natural lighting changes, realistic texture rendering.")
        final_prompt = f"{base_prompt} {specific_action}"
        print(f"📝 Video Prompt: {final_prompt}")

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
        
        # 3. Send Request
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Runway API Failed ({response.status_code}): {response.text}")
            return None
            
        task_id = response.json().get('id')
        print(f"⏳ Runway Task ID: {task_id}")
        
        # 4. Polling
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
        if not os.path.exists(VIDEO_FOLDER):
            os.makedirs(VIDEO_FOLDER)

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