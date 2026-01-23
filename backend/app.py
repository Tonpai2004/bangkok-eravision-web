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
        SEARCH_MODEL = SentenceTransformer('clip-ViT-L-14')
        
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

          **📸 PERSPECTIVE LOCK (ABSOLUTE PRIORITY):**
          - **STRICT MATCH:** The output image MUST MATCH the camera angle, focal length, and composition of the Uploaded Image exactly.
          - **NO DEVIATION:** **DO NOT ROTATE. DO NOT ZOOM. DO NOT SHIFT VIEW.** The geometry of the monument must align perfectly with the input image.

          **FORBIDDEN STRUCTURAL CHANGES (STRICT):**
          - **NO DISTORTION:** Do NOT twist, bend, or warp the shape of the four wings or the central turret.
          - **NO STRANGE ADDITIONS:** Do NOT add extra statues, spires, or fantasy elements.

          **ARCHITECTURAL ACCURACY:**
          - **Wings:** 4 Concrete wings, concave curve, bas-reliefs at base. Color: Weathered Cream/Grey Stucco.
          - **Constitution Pedestal:** Metallic dark grey/black Constitution on top of round pedestal. Red door at base.
          - **Base & Chain Barrier (NO CANNONS):** The circular tiered base is BARE CONCRETE. Around the **OUTER PERIMETER** (at ground level), render a barrier of **HEAVY IRON CHAINS** looping low to the ground. **REMOVE CANNON BARRELS:** Do not render the cannons themselves, only the chain barrier system.
          - **NEGATIVE PROMPT:** flowers, grass on the monument, cannons, artillery weapons.

          **TRAFFIC (CLEAR ROAD):**
          - **ZERO VEHICLES:** The wide asphalt road surrounding the monument is **COMPLETELY EMPTY**. No cars, no buses, no tuk-tuks.
          
          **SURROUNDINGS:**
          - **Buildings:** Aged Terracotta/Brick Orange color Ratchadamnoen buildings.
          - **Road Surface:** Wide, weathered Asphalt. NO modern lane markings.
      """,

    "Sala Chalermkrung": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Sala Chalermkrung Theatre (1967).
        
        **PERSPECTIVE LOCK:** Maintain exact camera angle from input image.
        
        **CLEAN FOREGROUND:**
        - **REMOVE** any wooden shophouses or obstructing buildings in the immediate foreground/opposite side. Keep the view of the theater open and grand.
        
        **THE MOVIE POSTER (SPECIFIC):**
        - **Visual:** Hand-painted cutout. Two men in white shirts standing back-to-back. One wears glasses, one doesn't. Both look smart/gentlemen.
        - **Text (THAI ONLY - LEGIBLE):** Title "**บางกอกทวิกาล**". Starring "**มาดามพงษ์ และ ณัฐภัทร**". Text: "**ฉายพฤษภาคมนี้ ที่เฉลิมกรุง**".
        
        **CONTEXT:**
        - **Street:** Wide asphalt avenue.
        - **Traffic:** Vintage **Datsun Bluebird taxis** and classic sedans. No Trams.
    """,

    # "Giant Swing": """
    #     **TASK:** Create an **AUTHENTIC 1965 KODACHROME SCAN** of The Giant Swing.

    #     **🏘️ 1960s SHOPHOUSE ARCHITECTURE (STRICT):**
    #     - **Structure:** Long, continuous rows of **two-story colonial-style shophouses**.
    #     - **Ground Floor:** Features dark, weathered **Wooden Folding Doors (Ban-Fiam)**.
    #     - **Upper Floor:** Symmetrical **Wooden Shuttered Windows**. NO glass modern windows.
    #     - **Texture:** Walls are aged white or grey plaster with heavy **humidity stains, soot, and peeling paint**. NO clean modern white.
    #     - **Roofs:** Slanted roofs with **weathered brown/terracotta tiles**.

    #     **📍 PERSPECTIVE & ROUTE LOGIC:**
    #     - **TRAM CHECK:** If the road next to Wat Suthat is visible, render the **Yellow-Red Wooden Tram** on embedded steel tracks.
    #     - **ROAD SURFACE:** Replace modern pavement with **weathered grey concrete** and layers of tropical dust. Erase all traffic paint.

    #     **NEGATIVE PROMPT:** modern glass windows, rolling steel shutters, clean white paint, plastic signage, air conditioners, 7-Eleven, traffic lines, red pavement tiles, digital sharpness.
    # """,

    "Giant Swing": """
        **TASK:** Perform a **STRICT 1960s HISTORICAL RETRO-FIT** on the uploaded image of the Giant Swing area.

        **🔒 1. PERSPECTIVE & GEOMETRY LOCK (ABSOLUTE PRIORITY):**
        - **ANCHOR:** The uploaded image is the rigid skeleton. You MUST map the 1960s textures directly onto the *exact* positions of the current buildings and roads.
        - **NO SHIFTING:** Do NOT change the camera angle, do NOT rotate, do NOT move the Giant Swing.

        **🔄 2. TRANSFORMATION RULES (MODERN -> 1960s):**
        - **BUILDINGS:** Look for modern commercial buildings in the photo and **TRANSFORM** them into **1960s Colonial-style Shophouses**.
            - **Texture:** Painted masonry (Cream, Light Yellow, or White). **Condition: Aged but CIVILIZED and INTACT (Not ruined, not a slum).**
            - **Windows/Doors:** Replace glass/shutters with **Wooden Louvered Shutters** and **Folding Wooden Doors**.
        - **THE SWING:** Render the **Red Teak Pillars** vividly at the exact same spot. **REMOVE ROPES** if visible.
        - **ROAD:** The road surface is **AGED ASPHALT or CONCRETE**. It must look paved and usable for a city center. **DO NOT MAKE IT DIRT, SAND, OR MUD.**

        **📍 3. CONTEXT & ATMOSPHERE:**
        - **Road Surface:** Replace modern pavement with **worn, dusty grey asphalt**. 
        - **TRAM TRACKS (STRICT):** If the road next to Wat Suthat is visible, render **parallel steel tram tracks** embedded flush into the asphalt road. 
        - **NO TRAM CAR:** Absolutely **DO NOT render any tram car, vehicle, or trolley**. Only show the metal rails on the ground to indicate the route.
        - **Road Width Adjustment:** Slightly increase the visible width of the road surface for a more spacious feel.
        - **De-Clutter:** ERASE all air conditioners, satellite dishes, and modern signs.

        **⛔ NEGATIVE PROMPT:** dirt road, sand, mud, rubble, destroyed buildings, slum, modern cars, air conditioners, 7-Eleven, modern billboards, bright traffic lines.
    """,
    
    # "Yaowarat": """
    #     **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Yaowarat Road (1968).
        
    #     **STRICT TEXT & SIGNS:**
    #     - **Text:** Hand-painted signs. **LEGIBLE Thai & Chinese**. No gibberish.
    #     - **Mandatory Texts:** "**ห้างทอง ฮั่วเซ่งเฮง**", "**ภัตตาคาร หูฉลาม**", "**ขายยาจีน**".
    #     - **Lighting:** DAYLIGHT only. **NO NEON GLOW**. NO LED.
        
    #     **TRAM REALISM:**
    #     - **Tram:** Weathered Yellow/Red wooden tram at the middle of the road.
    #     - **Position:** Running on rails **HUGGING THE RIGHT CURB** (near houses). Not in the middle.
        
    #     **TRAFFIC:**
    #     - **Vehicles:** **Samlors (Tricycles)** and **Round-nose Trucks (Isuzu TX)**. No modern sedans.
    # """,

    "Yaowarat": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Yaowarat Road (1968).
        **LOCK:** Maintain the exact building geometry and camera height of [IMAGE 1].

        **🏘️ ARCHITECTURAL TRANSFORMATION (CRITICAL):**
        - **REPLACE ALL MODERN BUILDINGS:** Turn all glass/modern concrete structures into **2-4 story Chinese-Colonial shophouses**.
        - **TEXTURE:** Walls must be off-white or faded grey with heavy **soot stains and humidity streaks**.
        - **WINDOWS & DOORS:** Use dark **Wooden Folding Doors (Ban-Fiam)** on the ground floor and **Wooden Louvered Shutters** on upper floors.

        **STRICT TEXT & SIGNS:**
        - **Text:** Hand-painted signs. **LEGIBLE Thai & Chinese**. No gibberish must have meaning in those textds.
        - **STYLE:** Hand-painted vertical signs attached to building pillars. Matte finish, no internal glow.
        - **CONTENT:** STRICTLY NO GIBBERISH OR ILLEGIBLE TEXT. All signs must contain legible, meaningful Thai or Chinese characters. Limit the 'ห้างทอง' sign to ONE distinct, prominent location. Other signs should have different, legible names appropriate for the era (e.g., 'ร้านขายยา', 'ภัตตาคาร', 'ยา'). Ensure hand-painted textures look authentic, not generated.

        **🚋 TRAM & ROAD (SINGLE TRACK PRIORITY):**
        - **TRACK CONFIGURATION:** **GENERATE ONLY ONE SINGLE TRAM TRACK.** Do NOT create double tracks or multiple lanes of rails.
        - **TRACK LOCATION:** This single track MUST be embedded flush with the asphalt and located **EXTREMELY CLOSE TO THE RIGHT-SIDE CURB**, hugging the shophouses.
        - **TRAM ALIGNMENT:** The Yellow/Red wooden tram must be positioned **DIRECTLY ON TOP OF THIS SINGLE TRACK**. The wheels must align with the rails.
        - **SPATIAL RULE:** The tram and track take up only the far right edge of the road. The rest of the road width (center and left) must be empty asphalt for Samlors and pedestrians.
        
        **🚦 ATMOSPHERE:**
        - **Transport:** Samlors (tricycles).
        - **Road Surface:** Worn asphalt with embedded tram tracks. NO modern lane markings.
        - **Crowd:** Busy street market vibe with Thai locals in 1960s attire.

        **NEGATIVE PROMPT:** modern skyscrapers, glass windows, LED signs, neon glow, plastic banners, air conditioners, modern cars, traffic lights, modern street lamps, tourists, banks, modern building, double tracks, multiple tram lines.
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
        **TASK:** Generate a **PHOTOREALISTIC 1960s HISTORICAL RECONSTRUCTION** of the Phra Sumen Fort Ruins.

        **🔒 PERSPECTIVE LOCK (ABSOLUTE PRIORITY):**
        - **STRICT MATCH:** The output image MUST MATCH the camera angle, focal length, and perspective of the Uploaded Image exactly.
        - **NO ROTATION:** Do not change the viewpoint. Adhere strictly to the composition of the source image.
        
        **STRUCTURAL STATE (CRITICAL):**
        - **THE BASE IS ALIVE:** Keep the massive hexagonal masonry base, including the **stairs, walkways, and defensive battlements (Sema walls)** exactly as they appear in the geometry of [IMAGE 1].
        - **DECAPITATED TOP:** The entire upper structure—including the smaller tower room, battlements, windows, roof, and spire—is **COMPLETELY MISSING**.
        - **TOP EDGE:** The top of the walls must look jagged and broken, showing exposed red bricks and crumbling old mortar.
        - **PATINA:** The white-washed walls are heavily weathered with **thick black mold, green moss, and humidity streaks**.

        **🏚️ 2. STRUCTURAL REFERENCE (FROM REFERENCE [IMAGE 2]):**
        - **ADOPT THE RUINED STATE:** The structural condition of the fort (e.g., missing roof, weathered state, damaged top, patina) must **STRICTLY FOLLOW the visual evidence provided in the historical reference image [IMAGE 2]**.
        - **NO RECONSTRUCTION:** Do NOT rebuild or restore any part of the fort that appears ruined or missing in the reference image. Trust the reference image for the building's physical state.

        **📍 3. 1960s ENVIRONMENT & ATMOSPHERE:**
        - **REMOVE MODERN PARK:** Erase the modern "Santi Chai Prakan Park", manicured lawns, and modern concrete paving.
        - **HISTORICAL GROUND:** Replace modern landscaping with unkempt grass, wild weeds, dirt patches, and natural overgrowth appropriate for a neglected historical site in the 1960s.
        - **VIBE:** aged film grain, natural light, historical authenticity.

        **⛔ NEGATIVE PROMPT:** modern park, manicured lawn, modern streetlights, tourists, cars, modern fences, flags, restored condition (unless visible in ref image).
    """,

    "Sanam Luang": """
        **TASK:** TRANSFORM [IMAGE 1] into a **VIBRANT & LIVELY** 1968 photograph of Sanam Luang.

        **📸 1. PERSPECTIVE LOCK:**
        - **STRICT MATCH:** Use [IMAGE 1] as the rigid layout. **Do NOT shift or change the camera angle**.

        **🎪 2. DEPTH-BASED ZONING (CRITICAL):**
        - **IMMEDIATE FOREGROUND (BOTTOM OF IMAGE):** This area MUST be **100% CLEAR** of any market stalls, umbrellas, tents, or permanent structures. It should only be dry red dirt, dust, and people walking, riding bicycles, or sitting.
        - **THE PERIMETER (FAR LEFT, FAR RIGHT, & DISTANCE):** All makeshift stalls, tent shanties, and disorganized clusters of umbrellas MUST be pushed to the **EXTREME LEFT and RIGHT EDGES** of the frame, and the far distant boundary near the trees.
        - **THE CENTRAL CORE:** Maintain a wide, open corridor from the bottom-center of the image all the way to the Wat Phra Kaew in the background. No stalls allowed in this central viewing lane.

        **🏃 3. POPULATION & ACTIVITY:**
        - **VIBRANT CENTER:** Fill the foreground and middle ground with **DOZENS of people scattered throughout**. They should be flying **Thai Kites (Chula/Pakpao)**, riding **vintage bicycles**, or sitting together.
        - **MOBILE VENDORS:** Include **Mobile Hawkers (Mae-Ka-Hab-Ray)** with shoulder poles walking in the foreground to add life without blocking the view.

        **🏜️ 4. TERRAIN & LIGHTING:**
        - **SURFACE:** Dry red dirt and fine dust. Absolutely **NO ASPHALT, NO CONCRETE, and NO ROADS**.
        - **DYNAMIC LIGHTING:** Strictly follow the lighting and time of day (Day/Night) from [IMAGE 1].

        **⛔ NEGATIVE PROMPT:** stalls in foreground, umbrellas near camera, market structures at the bottom of the image, empty field, ghost town, asphalt, roads.
    """,

    "National Museum": """
        **TASK:** Create a **VINTAGE 1960s** color photograph of the National Museum Bangkok.

        **🧱 1. FENCE & FLAT PILLARS (DESTRUCTION & RECONSTRUCTION):**
        - **NO SIDE GATES (ABSOLUTE):** You MUST **ERASE and REMOVE** the two smaller pedestrian side-gates visible in [IMAGE 1]. 
        - **CONTINUOUS FENCE:** Replace the areas where the side-gates were with a **SOLID, CONTINUOUS IRON FENCE** that matches the rest of the wall. There must be NO gaps or openings until the main central gate.
        - **FLAT TOPS:** Every single pillar along the fence MUST be a **SIMPLE RECTANGULAR BLOCK** with a **COMPLETELY FLAT TOP**.
        - **NO FINIALS:** Absolutely **NO spires, pointed tops, or decorative stone caps** on any pillar. If [IMAGE 1] has them, DELETE them.

        **🚧 2. ROAD & CURB:**
        - **SURFACE:** Clean, formal **DARK ASPHALT**. No raised curb, no paint markings.

        **🏛️ 3. ATMOSPHERE:**
        - **Vibe:** Quiet, Royal, and Prestigious.
        - **Background:** Faded orange chapel roof visible through dense, messy tamarind trees.

        **⛔ NEGATIVE PROMPT:** side gates, pedestrian doors, fence openings, secondary gates, pointed pillars, spires, finials, stone caps, red and white curb, zebra crossing.
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

SIMILARITY_THRESHOLD = 0.4
# --- CLIP Logic ---
def get_best_match_reference(location_th, user_img_bytes):
    # ✅ เพิ่ม "เสาชิงช้า & วัดสุทัศน์" ลงไปในเงื่อนไขนี้ เพื่อไม่ต้องใช้ไฟล์ .pkl
    if location_th == "ถนนข้าวสาร" or location_th == "เสาชิงช้า & วัดสุทัศน์":
        return None

    mapped_key = LOCATION_KEY_MAP.get(location_th)
    if not mapped_key or not SEARCH_MODEL or mapped_key not in LOCATION_INDICES:
        return None
    
    try:
        data = LOCATION_INDICES[mapped_key]
        user_img = Image.open(io.BytesIO(user_img_bytes))
        user_vector = SEARCH_MODEL.encode(user_img)
        
        distances = cdist([user_vector], data['vectors'], metric='cosine')[0]
        best_idx = np.argmin(distances)
        min_distance = distances[best_idx]
        
        # --- เพิ่ม Logic ตรงนี้ ---
        if min_distance > SIMILARITY_THRESHOLD:
            print(f"⚠️ No close match found (Dist: {min_distance:.2f}). Skipping Reference Image.")
            return None
            
        best_filename = data['filenames'][best_idx]
        print(f"🎯 Smart Match ({mapped_key}): Dist {min_distance:.2f} -> {best_filename}")
        file_path = os.path.join(os.path.dirname(__file__), "reference_images", mapped_key, best_filename)
        with open(file_path, "rb") as f:
            return f.read()
            
    except Exception as e:
        print(f"❌ Smart Match Error: {e}")
        return None

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
    # ปรับ Prompt ให้เป็น Structured Analysis
    prompt = """
    Analyze this modern-day image of a Bangkok landmark for a historical 1960s reconstruction:
    
    1. **Perspective Type**: Identify the camera angle (e.g., Eye-level, High-angle, Ground-level POV, Wide-angle, or Close-up).
    2. **Visible Landmark Parts**: List ONLY the parts of the landmark actually visible in this frame (e.g., 'only the left wing', 'top of the turret', 'no ground visible').
    3. **Spatial Layout**: Describe where the main structure sits (e.g., 'Centered', 'Leading from bottom-right to top-left').
    4. **Modern Elements to Remove**: Identify specific modern objects and their positions (e.g., 'Blue bus on the left', 'CCTV on the pole', 'Traffic lights in foreground').
    
    Output this as a concise summary to be used as a 'Geometry Constraint' for an image generation model.
    """
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash-001", 
                contents=[prompt, types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")]
            )
            # เราจะได้คำบรรยายที่ระบุมุมมองชัดเจน เช่น "POV from sidewalk, only the base visible..."
            return response.text 
        except Exception as e:
            if "429" in str(e) or "503" in str(e):
                # สูตรใหม่: (2 ยกกำลัง attempt) * 2
                # Attempt 0: (1)*2 = 2 วินาที
                # Attempt 1: (2)*2 = 4 วินาที
                # Attempt 2: (4)*2 = 8 วินาที
                wait_time = (2 ** attempt) * 2 + random.uniform(1, 3) 
                print(f"⚠️ API Busy (Analysis). Waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
            else:
                break
    return "Maintain original perspective and visible structures exactly."

def step2_generate(client, structure_desc, location_key, original_img_bytes, ref_img_bytes=None):
    specific_prompt = LOCATION_PROMPTS.get(location_key, "")
    
    # 1. สร้างฐานคำสั่งกลางสำหรับทุกสถานที่ (Standard Instruction)
    perspective_instr = f"""
    **MANDATORY PERSPECTIVE INSTRUCTION:**
    - {structure_desc}
    - **GEOMETRY SOURCE:** Use [IMAGE 1] as the ONLY source for composition and angle.
    - **CONSTRAINT:** Do NOT rotate, shift, or zoom. The output MUST be a perfect overlay of [IMAGE 1].
    """
    
    # 2. เพิ่ม Logic พิเศษเฉพาะป้อมพระสุเมรุ (Conditional Deletion)
    # ใช้ชื่อ Key ให้ตรงกับใน LOCATION_PROMPTS
    if location_key == "Phra Sumen Fort":
        perspective_instr += """
    - **SPECIAL TASK (DELETION):** Look at the upper watchtower room on top of the fort in [IMAGE 1]. You MUST **ERASE and DELETE** it.
    - **REPLACE:** Replace that specific upper area with **EMPTY BLUE SKY**. 
    - **STRICT:** The base remains, but the tower part must be GONE to show the ruin state.
        """

    elif location_key == "National Museum":
        extra_instructions = """
    - **GEOMETRY ANOMALY DETECTED:** Identify any small pedestrian gates or side openings in [IMAGE 1]. 
    - **TASK:** You MUST **DELETE** these openings. Fill the gaps with a **SOLID MASONRY BASE** and a **CONTINUOUS IRON FENCE**.
    - **WALL INTEGRITY:** The fence must be an unbroken line from the frame edge to the central gate.
    - **PILLAR OVERRIDE:** Every pillar must be a simple rectangular block. **SURGICALLY REMOVE** any pointed finials or decorative caps.
        """

    # 3. ประกอบเป็น Global Style
    global_style = f"""
    {perspective_instr}
    
    **GLOBAL STYLE:**
    - Output: Photorealistic color 1960s Kodachrome filter photograph.
    - **IGNORE STRUCTURE:** If [IMAGE 2] is provided, DISCARD its architecture entirely.
    - Remove all modern objects identified in the analysis.
    """
    
    # ส่วนที่เหลือของฟังก์ชัน (การประกอบ parts และการเรียก AI) ให้คงเดิมไว้ครับ
    parts = [f"{specific_prompt}\n{global_style}\n\n**[IMAGE 1] THE STRUCTURAL BLUEPRINT (PRIMARY):**"]
    parts.append(types.Part.from_bytes(data=original_img_bytes, mime_type="image/jpeg"))
    max_retries = 5

    # ก้อนที่ 2: คำสั่งสำหรับภาพอ้างอิง (ถ้ามี)
    if ref_img_bytes:
        style_instruction = """
        **[IMAGE 2] THE STYLE REFERENCE (SECONDARY):**
        - USE ONLY for: Color grading, film grain, and 1960s lighting.
        - **DANGER:** DO NOT follow the camera angle or building placement of [IMAGE 2]. 
        - TASK: Apply the 'Skin' of [IMAGE 2] onto the 'Skeletal Structure' of [IMAGE 1].
        """
        parts.append(style_instruction)
        parts.append(types.Part.from_bytes(data=ref_img_bytes, mime_type="image/jpeg"))

    # 3. เรียกโมเดลด้วยค่าความสร้างสรรค์ต่ำที่สุด (Locking the result)
    model_name = "gemini-3-pro-image-preview" 

    for attempt in range(max_retries):
        try:
            print(f"🎨 Generating Image (Attempt {attempt+1}) using {model_name}...")
            response = client.models.generate_content(
                model=model_name, 
                contents=parts, # ส่งแบบ List ที่แยกคำสั่งกับรูปสลับกัน
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    temperature=0.0 # ลดเหลือ 0.1 เพื่อให้ทำตามโครงสร้างเดิมเป๊ะขึ้น
                )
            )
            for part in response.candidates[0].content.parts:
                if part.inline_data: return part.inline_data.data
            
            print(f"⚠️ Warning: Model returned no image (Attempt {attempt+1})")
            
        except Exception as e:
            if "not found" in str(e).lower() and model_name == "gemini-3-pro-image-preview":
                print("⚠️ Switching model to gemini-3-pro-image-preview...")
                model_name = "gemini-2.0-flash-exp-image-generation" # ถ้าไม่ได้ปรับไปตัวกากๆ(ประหยัดงบ)
                time.sleep(1)
                continue

            if "429" in str(e) or "503" in str(e):
                t = (5 * (2 ** attempt)) + random.uniform(1, 5) 
                print(f"⚠️ Server Busy ({model_name}) -> Waiting {t:.1f}s before retry...")
                time.sleep(t)

            if "503" in str(e).lower() and model_name == "gemini-3-pro-image-preview":
                print("⚠️ Switching model to nano-banana-pro-preview...")
                model_name = "nano-banana-pro-preview" # ถ้าไม่ได้ปรับไปตัวกากๆ(ประหยัดงบ)
                time.sleep(1)
                continue

            else:
                print(f"❌ Critical Gen Error: {e}")
                if model_name != "gemini-3-pro-image-preview":
                     model_name = "gemini-3-pro-image-preview"
                     continue
                return None
                
    return None

# ==========================================
# 🎬 RUNWAY ML INTEGRATION (STRICT & REALISTIC)
# ==========================================

# import os
# import io
# import time
# import base64
# import datetime
# import requests
# from PIL import Image

# def generate_video_runway(image_bytes, location_key):
#     runway_key = os.getenv("RUNWAYML_API_KEY")
#     if not runway_key:
#         print("❌ Error: ไม่เจอ RUNWAYML_API_KEY ในไฟล์ .env")
#         return None

#     try:
#         print("🎬 Starting Runway Video Generation (V.17 - Ultimate Polishing)...")
        
#         # 1. Image Pre-processing
#         try:
#             img = Image.open(io.BytesIO(image_bytes))
#             width, height = img.size
#             ratio = width / height
#             MAX_RATIO = 1.78
            
#             if ratio > MAX_RATIO:
#                 print(f"⚠️ Image ratio {ratio:.2f} is too wide (Limit {MAX_RATIO}). Auto-cropping center...")
#                 new_width = int(height * MAX_RATIO)
#                 left = (width - new_width) / 2
#                 top = 0
#                 right = (width + new_width) / 2
#                 bottom = height
#                 img = img.crop((left, top, right, bottom))
                
#                 buffered = io.BytesIO()
#                 img.save(buffered, format="PNG")
#                 image_bytes = buffered.getvalue()
#                 print(f"✅ Cropped to {img.size}")
#         except Exception as crop_err:
#             print(f"⚠️ Warning: Auto-crop failed ({crop_err}). Sending original image.")

#         base64_str = base64.b64encode(image_bytes).decode('utf-8')
        
#         # 2. RUNWAY PROMPT ENGINEERING (FLAWLESS & GLITCH-FREE)
#         # Goal: Static camera, realistic physics, no filters, no glitches.
#         base_prompt = """
#         Static tripod camera shot, absolutely NO panning, NO zooming, NO rotation.
#         Hyper-realistic 8k video, high fidelity.
#         Subtle environmental motion only. Stable structures, no morphing buildings.
#         Natural 1960s lighting with very subtle film grain. No visual glitches.
#         """

#         location_prompts = {
#             "Democracy Monument": "Static shot. Cars are parked still on the road. ONLY clouds in the sky move slowly. Subtle heat haze on the asphalt. No car movement at all. **CRITICAL: The monument structure MUST REMAIN PERFECTLY STATIC and RIGID. No morphing, warping, twisting, or glitching of the concrete wings or base throughout the video.**",
#             "Sala Chalermkrung": "Atmospheric dust motes dancing in the sunlight. Subtle shadows shifting on the theater facade. Flags on the roof swaying very gently in the breeze.",
#             "Giant Swing": "The red pillars remain perfectly still and solid. Background tree leaves rustling gently. Atmospheric haze in the distance. No movement on the swing itself.",
#             "Yaowarat": "Heat haze shimmering slightly above the asphalt. Subtle flickering of sunlight reflecting off aged glass windows. Very slow cloud movement overhead.",
#             "Khaosan Road": "Leaves of trees sways gently in the breeze. Natural shadows of trees moving slowly on the wooden house fronts. Calm and still residential atmosphere.",
#             "Phra Sumen Fort": "Sunlight filtering through trees, creating moving dappled shadows on the white stone ruins. Overgrown grass on top of the ruin swaying slightly. No reconstruction of the fort.",
#             "Sanam Luang": "Canvas umbrellas fluttering very subtly in the wind. Kites in the far distance moving slightly against the clouds. The ground remains stable and clear.",
#             "National Museum": "A very calm, Zen-like atmosphere. Dappled sunlight and shadows shifting slowly on the white walls and gravel ground. Tree branches swaying gently."
#         }

#         specific_action = location_prompts.get(location_key, "Natural lighting changes, realistic texture rendering.")
#         final_prompt = f"{base_prompt} {specific_action}"
#         print(f"📝 Video Prompt: {final_prompt}")

#         url = "https://api.dev.runwayml.com/v1/image_to_video"
#         payload = {
#             "promptImage": f"data:image/png;base64,{base64_str}",
#             "model": "gen3a_turbo",
#             "promptText": final_prompt,
#             "duration": 5,
#             "ratio": "1280:768"
#         }
#         headers = {
#             "Authorization": f"Bearer {runway_key}",
#             "X-Runway-Version": "2024-11-06",
#             "Content-Type": "application/json"
#         }
        
#         # 3. Send Request
#         response = requests.post(url, json=payload, headers=headers)
#         if response.status_code != 200:
#             print(f"❌ Runway API Failed ({response.status_code}): {response.text}")
#             return None
            
#         task_id = response.json().get('id')
#         print(f"⏳ Runway Task ID: {task_id}")
        
#         # 4. Polling
#         for i in range(30):
#             time.sleep(3)
#             status_res = requests.get(f"https://api.dev.runwayml.com/v1/tasks/{task_id}", headers=headers)
#             if status_res.status_code == 200:
#                 data = status_res.json()
#                 status = data.get('status')
                
#                 if status == "SUCCEEDED":
#                     print("✅ Video Generation Complete!")
#                     return data.get('output', [None])[0]
#                 elif status == "FAILED":
#                     print(f"❌ Video Generation FAILED: {data.get('failure', 'Unknown error')}")
#                     return None
#                 else:
#                     print(f" ...processing ({i+1}/30)")
#             else:
#                 print(f"⚠️ Polling Error: {status_res.status_code}")

#         print("❌ Timeout: Runway took too long.")
#         return None

#     except Exception as e:
#         print(f"❌ Critical Runway Error: {e}")
#         return None

# def save_generated_image(image_bytes, location_name_th):
#     try:
#         if not os.path.exists(HISTORY_FOLDER):
#             os.makedirs(HISTORY_FOLDER)

#         file_prefix = LOCATION_MAPPING_TH_TO_EN.get(location_name_th, "unknown_location")
#         safe_name = "place"
        
#         if "Democracy" in file_prefix: safe_name = "democracymonument"
#         elif "Sala" in file_prefix: safe_name = "salachalermkrung"
#         elif "Swing" in file_prefix: safe_name = "giantswing"
#         elif "Yaowarat" in file_prefix: safe_name = "yaowarat"
#         elif "Khao San" in file_prefix: safe_name = "khaosan"
#         elif "Phra Sumen" in file_prefix: safe_name = "phrasumenfort"
#         elif "Sanam Luang" in file_prefix: safe_name = "sanamluang"
#         elif "National Museum" in file_prefix: safe_name = "nationalmuseum"
        
#         timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
#         filename = f"{safe_name}_1960s_{timestamp}.png"
#         filepath = os.path.join(HISTORY_FOLDER, filename)

#         with open(filepath, "wb") as f:
#             f.write(image_bytes)
        
#         print(f"💾 Auto-saved result to: {filename}")
#         return filepath 

#     except Exception as e:
#         print(f"⚠️ Failed to auto-save image: {e}")
#         return None

def generate_video_runway(image_bytes, location_key):
    runway_key = os.getenv("RUNWAYML_API_KEY")
    if not runway_key:
        print("❌ Error: RUNWAYML_API_KEY not found in .env")
        return None

    try:
        print("🎬 Starting Runway Gen-3 Video Generation (Strict Source Fidelity)...")
        
        # 1. Prepare Base64
        base64_str = base64.b64encode(image_bytes).decode('utf-8')

        # 2. UNIVERSAL PROMPT (ปรับปรุงใหม่ตามรีเควส)
        # เน้น: ขยับแค่นิดเดียว (Minimal), แพนกล้องช้าๆ, ห้ามเติมของ, ห้ามเปลี่ยนโครงสร้าง
        final_prompt = """
        **CAMERA MOTION:**
        - Slow, smooth, cinematic horizontal pan. Very subtle movement.
        - **NO ZOOM.** Keep the focal length locked.

        **SCENE MOVEMENT (MICRO-MOTION ONLY):**
        - **NATURE:** Gentle rustling of leaves, slow drifting clouds, subtle atmospheric dust/haze floating in the light.
        - **PEOPLE/TRAFFIC:** **MINIMAL MOVEMENT.** People and cars should appear almost static or move very slightly and naturally. No fast walking or driving.
        
        **STRICT CONSTRAINTS (DO NOT BREAK):**
        - **FROZEN STRUCTURES:** Buildings, roads, and monuments must remain 100% STATIC and RIGID. No morphing, breathing, or warping.
        - **SOURCE FIDELITY:** animate ONLY what is visible in the input image. **DO NOT ADD** new people, vehicles, or objects.
        - **VIBE:** Peaceful, slow-motion vintage atmosphere.
        """
        
        print(f"📝 Video Prompt: {final_prompt}")

        # 3. Call Runway API directly
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
        
        # Send Request
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Runway API Failed ({response.status_code}): {response.text}")
            return None
            
        task_id = response.json().get('id')
        print(f"⏳ Runway Task ID: {task_id}")
        
        # Polling Loop
        for i in range(30):
            time.sleep(3)
            status_res = requests.get(f"https://api.dev.runwayml.com/v1/tasks/{task_id}", headers=headers)
            if status_res.status_code == 200:
                data = status_res.json()
                if data.get('status') == "SUCCEEDED":
                    print("✅ Video Generation Complete!")
                    return data.get('output', [None])[0]
                elif data.get('status') == "FAILED":
                    print(f"❌ Video Generation FAILED: {data.get('failure', 'Unknown error')}")
                    return None
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