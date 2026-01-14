from flask import Flask, request, jsonify
import os
import base64
import time
import random
import pickle
import numpy as np
import tempfile
import datetime
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

# --- THE MASTER PROMPT DATABASE (V.11 - ULTIMATE REALISM & STRICT PERSPECTIVE) ---
LOCATION_PROMPTS = {
    # ========================================= Prompt อนุสาวรีย์ประชาธิปไตย (ใช้งานจริง) ========================================= #
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
      # === เพิ่ม Negative Prompt เข้ามาเพื่อลดการเกิดสิ่งที่ไม่ต้องการ, เพิ่ม Logic เข้ามาเพื่อพยายามล๊อคคนไม่ให้ไปเดินเล่นที่อนุสาวรีย์, เพิ่มรายละเอียดตึกรอบๆเข้าไปนิดหน่อย(Low-rise Art Deco buildings) === #

    # ========================================= Prompt เฉลิมกรุง (ใช้งานจริง) ========================================= #
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

    # ========================================= Prompt เฉลิมกรุง (เผื่อเลือกใช้) ========================================= #
    # "Sala Chalermkrung": """
    #     **SUBJECT:** A historically accurate 1960s exterior shot of Sala Chalermkrung Royal Theatre (Bangkok).

    #     **ARCHITECTURAL ACCURACY:**
    #     - **Building Style:** Early Modernist architecture, painted in **Clean Cream/Off-White**. It looks grand and solid.
    #     - **Condition:** Well-maintained but showing slight texture of age (1967 era).

    #     **THE GIANT CUTOUT (CRITICAL FOCUS):**
    #     - **Type:** A **MASSIVE Hand-Painted Cinema Cutout** (Billboard size) mounted on the front facade. It looks like a vibrant oil painting.
    #     - **Visual:** Two Thai gentlemen standing back-to-back. One wears glasses, the other does not. Both dressed in smart 1960s white shirts/suits.
    #     - **Text Content:** "บางกอกทวิกาล" (Main Title), "มาดามพงษ์ และ ณัฐภัทร" (Stars), "กำกับโดย ตอตุ้ม" (Director).

    #     **ATMOSPHERE - RELAXED & COOL (NOT CROWDED):**
    #     - **People:** **SPARSE.** Only a few stylish teenagers (Ko Lang Wang style) standing in small, distinct groups or walking casually. **ABSOLUTELY NO LARGE CROWDS.**
    #     - **Fashion:** Men in grease-styled hair (Elvis look). Women in Mod dresses.
    #     - **Traffic:** A few vintage taxis passing by. Road is open and clear.
    #     - **Vibe:** Chill, cinematic, high-fashion 60s street photography.

    #     **NEGATIVE PROMPT:**
    #     - Crowds, traffic jam, busy street, modern LED signs, air conditioning units, modern cars, backpackers, rundown slums.
    # """,
    # === หลักๆเน้นเพิ่มรายละเอียดของตึกและบรรยากาศรอบๆ, เน้นล๊อคมุมกล้อง, เน้นล๊อคคนไม่ให้เยอะเกินไป === #

    # ========================================= Prompt เสาชิงช้า (ใช้งานจริง) ========================================= #
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
    # === เพิ่ม Negative Prompt เข้ามาเพื่อลดการเกิดสิ่งที่ไม่ต้องการ, เพิ่มรายละเอียดร้านค้า/บ้านรอบๆ === # 
    # === อาจจะต้องปรับเพิ่ม ดูไม่ค่อยแม่นเท่าไหร่ตัวนี้ === #
    
    # ========================================= Prompt เยาวราช (ใช้งานจริง) ========================================= #
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

    # ========================================= Prompt เยาวราช (เผื่อเลือกใช้) ========================================= #
    # "Yaowarat": """
    #     **SUBJECT:** A historically accurate 1960s photograph of Yaowarat Road (Bangkok Chinatown) during the day.

    #     **THE "FOREST OF SIGNS" (CRITICAL VISUAL):**
    #     - **Density:** The street is densely packed with **HUNDREDS of Vertical Signs hanging over the road** from both sides, creating a tunnel-like perspective.
    #     - **Color Palette:** Dominant **RED backgrounds with GOLD lettering**.
    #     - **Text Accuracy:** Hand-painted signs in **Chinese Characters (Large)** and **Thai (Smaller)**.
    #     - **Key Signs:** "**ห้างทอง ฮั่วเซ่งเฮง (和成興大金行)**", "**ภัตตาคาร หูฉลาม**", "**ขายยาจีน**".
    #     - **Material:** Painted wood and metal boxes. **NO LED. NO GLOWING NEON (Daytime).**

    #     **1968 TRAFFIC REVOLUTION:**
    #     - **Tuk-Tuks:** MUST include **"Daihatsu Midget" (Frog-faced Tuk-Tuks)** which replaced pedicabs in this era.
    #     - **Cars:** Vintage 1960s sedans and delivery trucks.
    #     - **NO SAMLORS:** (Pedicabs were banned on main roads in the 60s).

    #     **THE LAST TRAM:**
    #     - **Vehicle:** A weathered, dusty **Yellow & Red Wooden Tram** (The final year of operation).
    #     - **Position:** Running on tracks embedded in the asphalt, sharing the road with cars.

    #     **ATMOSPHERE:**
    #     - **Vibe:** Extremely busy, chaotic, commercial energy. Hazy tropical sunlight filtering through the signs.
    #     - **Road:** Asphalt road, slightly wet/oily texture.

    #     **NEGATIVE PROMPT:**
    #     - LED screens, digital billboards, modern Toyota/Honda cars, BTS skytrain, pedestrians wearing modern fashion, English signs, empty street.
    # """,

    # ========================================= Prompt ถนนข้าวสาร (ใช้งานจริง) ========================================= #
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
    # === เพิ่ม Negative Prompt เข้ามาเพื่อลดการเกิดสิ่งที่ไม่ต้องการ, เพิ่มการล๊อคมุมภาพ === # 

    # ========================================= Prompt ป้อมพระสุเมรุ (ใช้งานจริง) ========================================= #
    "Phra Sumen Fort": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Phra Sumen Fort (1960).
        
        **CRITICAL ACCURACY: HEADLESS FORT:**
        - **Status:** The top wooden roof spire is **COMPLETELY MISSING**. The white tower is truncated/severed. It is a flat, weathered stump.
        - **Structure:** Hexagonal white plaster fort, stained with black mold.
    """,

    # ========================================= Prompt สนามหลวง (ใช้งานจริง) ========================================= #
    "Sanam Luang": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Sanam Luang (Weekend Market 1968).
        
        **MARKET REALISM:**
        - **Stalls:** Vendors sitting on **WOVEN MATS** on the red dust ground. Bamboo parasols.
        - **Density:** Lively but not overcrowded. Open spaces visible.
        - **Sky:** Only **A FEW** scattered kites.
    """,

    # ========================================= Prompt สนามหลวง (เผื่อเลือกใข้) ========================================= #
    # "Sanam Luang": """
    #     **SUBJECT:** A historically accurate 1960s photograph of Sanam Luang (The Sunday Weekend Market).

    #     **THE GROUND (GREEN GRASS VER.):**
    #     - **Ground Surface:** **Green Grass Field (Sanam Luang Lawns)**. Although it was a market, render it with **Green Grass** to maintain the iconic look of the Royal Ground.
    #     - **Condition:** The grass can have some worn patches (dirt paths) for realism, but the overall tone must be **GREEN**, not red dirt.

    #     **THE MARKET ATMOSPHERE:**
    #     - **The Setup:** Vendors sitting on **Woven Mats** spread directly on the grass.
    #     - **The Umbrellas:** A sea of **Canvas Parasols (Rom Pha Bai)**. Colors: Striped Red/White, Blue/White, or dirty White.
    #     - **Goods:** Second-hand Books (piles of old paper), Antiques, Amulets, and Potted Plants.

    #     **LANDMARKS:**
    #     - **Framing:** Large, shady **Tamarind Trees (Ton Makam)**.
    #     - **Background:** **Wat Phra Kaew (Grand Palace)** spires visible in the distance.

    #     **NEGATIVE PROMPT:**
    #     - Red laterite, red dust, muddy ground, large concrete plaza, modern tents, plastic chairs, skyscrapers.
    # """,

    # ========================================= Prompt พิพิธภัณฑสถานแห่งชาติ (ใช้งานจริง) ========================================= #
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

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="nano-banana-pro-preview", # Stronger model for image gen (or change to imagen-3.0-generate-001 if available)
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
            
            # --- AUTO-SAVE LOGIC ---
            save_generated_image(result_bytes, location_th)
            # ---------------------

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