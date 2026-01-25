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
          **TASK:** Create a **HYPER-REALISTIC** photograph of Democracy Monument (Bangkok 1960s) with **PRECISE HISTORICAL COLORS**.

          **📸 1. ABSOLUTE PERSPECTIVE LOCK (NON-NEGOTIABLE):**
          - **MASTER BLUEPRINT:** The uploaded image is the rigid geometric skeleton. You MUST map the 1960s textures directly onto the *exact* shapes and outlines of the current structure.
          - **NO DEVIATION:** **DO NOT ROTATE. DO NOT ZOOM. DO NOT SHIFT VIEW.** The geometry must align perfectly with the input image.

          **🎨 2. HISTORICAL COLOR PALETTE (STRICT ACCURACY):**
          - **CONSTITUTION TRAY (PHAN):** The tray holding the constitution on the very top is **METALLIC BLACK / DARK BRONZE**.  It is **NOT** gold change the color of it to black**.
          - **TURRET DOORS:** The small doors embedded at the base of the central turret are **VIBRANT THAI RED (See-Daeng-Chad)**.
          - **WINGS & BODY:** The 4 wings and central tower are **WEATHERED CREAM / OFF-WHITE STUCCO**. They look aged and textured, not bright clean white.
          - **BASE:** The circular base is **Bare Grey Concrete** with **Black Iron Chains** looping around the perimeter (NO Cannons).

          **🏘️ 3. SURROUNDINGS & CONTEXT (ADAPT WHAT IS SEEN):**
          - **VISIBILITY RULE (CRITICAL):** Analyze the input image. **ONLY** transform the buildings, road medians, and pavement *actually visible* in the frame. **DO NOT invent new structures or background elements that are not currently there.**
          - **BUILDING TRANSFORMATION:** Identify modern building facades in the background/foreground. Transform their surfaces into **1960s Ratchadamnoen Style architecture** (weathered stucco, Art Deco influence). Apply the **Aged Terracotta/Brick Orange** color palette.
          - **MEDIANS & HARDSCAPE:** If road medians, footpaths, or curbs are visible in the input, change modern concrete to **aged, weathered stone or simple concrete curbs** appropriate for the era.
          - **CLEAN UP:** Erase modern air conditioners, large billboards, and LED signs from the visible buildings.

          **🛣️ 4. GRAND OPEN AVENUE (ZERO VEHICLES):**
          - **TRAFFIC REMOVAL (CRITICAL):** The wide avenue is **MAJESTICALLY EMPTY**. Absolutely **NO CARS, NO BUSES, NO TUK-TUKS**. The road must be clear, weathered asphalt.
          **⛔ NEGATIVE PROMPT:** gold constitution, white doors, modern cars, traffic, skyscrapers, flowers on monument, cannons, fantasy elements, distortion, modern signs, air conditioners, glass buildings.
      """,
      # Light Brown / Brick Orange เผื่อเปลี่ยนกลับ

    "Sala Chalermkrung": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Sala Chalermkrung Theatre (1967).
        
        **📸 1. PERSPECTIVE & SKYLINE LOCK:**
        - **BLUEPRINT:** Maintain the exact camera angle of [IMAGE 1].
        - **SKYLINE PURGE (CRITICAL):** Identify all high-rise buildings, skyscrapers, and modern concrete towers and houses or big houses in the background of [IMAGE 1]. You MUST **DELETE and ERASE** them.
        - **REPLACE BACKGROUND:** Replace the modern skyline and adjacent building like houses with a **clear, open tropical sky**. The theater must be the tallest, most prominent structure in the scene.
        
        **🚫 2. MODERN REMOVAL:**
        - **ERASE INFRASTRUCTURE:** Remove all modern traffic lights, LED street lamps, concrete utility poles, and tangled black cables.
        - **BRANDING:** Delete all modern bank logos like SCB, Kasikorn, Krungthep-Bank, ATM signs, and digital billboards.
        
        **🎭 3. THE MOVIE POSTER:**
        - **Visual:** Large hand-painted cutout poster. Two men back-to-back. One in a sharp **black suit** (half-Chinese), one in a white shirt. Both look like 1960s gentlemen.
        - **Text:** Title "**บางกอกทวิกาล**". Starring "**มาดามพงษ์ และ ณัฐภัทร**".
        
        **🚶 4. PEDESTRIAN CONTEXT:**
        - **STREET:** Wide asphalt avenue, **COMPLETELY EMPTY OF CARS**.
        - **CROWD:** A lively, crowd of Thai locals in 1960s fashion (white shirts, skirts, slacks) walking and gathered for a premiere.
        
        **🎨 5. STYLE:**
        - **Look:** 1960s Kodachrome film with warm natural light and soft grain.

        **NEGATIVE PROMPT:** skyscrapers, high-rise buildings, modern towers, glass facades, urban sprawl, cars, traffic, street lights, electric wires.
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
        **TASK:** TRANSFORM [IMAGE 1] into a **1960s Phra Nakhon Era** scene using strict structural preservation.

        **🔒 1. ABSOLUTE GEOMETRY & SPATIAL LOCK (THE "STENCIL" RULE):**
        - **FIXED LAYOUT:** The input image is a rigid map. **DO NOT CHANGE THE SPACING** between buildings.
        - **PRESERVE GAPS:** If there is empty sky or space between buildings in the source, **KEEP IT EMPTY**. Do not fill gaps with new shophouses.
        - **CAMERA FREEZE:** **DO NOT ROTATE. DO NOT ZOOM. DO NOT PAN.** The perspective must perfectly overlay the original image.

        **🔄 2. ARCHITECTURAL RE-SKINNING (NO NEW BUILDINGS):**
        - **STRICT TRANSFORMATION:** Detect *only* the buildings currently present. Transform their **surfaces** to match the **1960s Phra Nakhon style** (Weathered Cream Stucco, Wooden Shutters, Clay Tiles).
        - **MODERN TO VINTAGE:** If a visible building looks modern, keep its size/shape but change its texture to old masonry/wood. **DO NOT ADD** extra floors or extensions.

        **⛩️ 3. THE GIANT SWING (HISTORICAL TWO-TIER BASE):**
        - **PILLARS:** Massive **Aged Red Teak** pillars.
        - **DUAL-LAYER BASE (CRITICAL):** Render the base structure accurately with **TWO DISTINCT CONCRETE LEVELS**:
            1. **The Plinths:** Concrete blocks directly supporting the red teak legs.
            2. **The Island Platform:** A wider, raised **curbed concrete island (Traffic Island)** that the whole structure sits upon.
        - **DECORATION BAN:** The base must be **BARE, CLEAN WHITE/GREY CONCRETE**. Absolutely **NO FLOWERS**, no garlands, no fabric wrappings, and no ornate carvings.

        **🛣️ 4. CLEAN ROAD (ZERO VEHICLES):**
        - **REMOVE TRAFFIC:** The road must be **MAJESTICALLY EMPTY**. Remove all cars, tuk-tuks, and buses.
        - **SURFACE:** Reveal the road surface underneath. Render it as **Clean, Weathered Grey Asphalt**.

        **⛔ NEGATIVE PROMPT:** modern cars, traffic, vehicles, people in middle of road, **added buildings**, **filling gaps**, **crowded skyline**, **flowers on base**, garlands, fantasy decorations, changing angle.
    """,

    "Yaowarat": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Yaowarat Road (1968).

        **📸 1. ABSOLUTE PERSPECTIVE & GEOMETRY LOCK (NON-NEGOTIABLE):**
        - **MASTER BLUEPRINT (THE STENCIL RULE):** The uploaded image is a rigid stencil. You must only change the *texture* and *content* within the existing geometric shapes.
        - **CAMERA FREEZE (CRITICAL):** The camera position, angle, height, and focal length are **FROZEN** to match the input image exactly. **DO NOT ROTATE, DO NOT ZOOM, DO NOT PAN.**
        - **VIEWPOINT DEPENDENCY:** Do NOT use a default generic angled street view. You MUST analyze the input's specific angle:
            - If input is **Straight-on (Frontal view)** -> Output MUST be **Straight-on**.
            - If input is **Angled from the Left** -> Output MUST be **Angled from the Left**.
            - If input is **Angled from the Right** -> Output MUST be **Angled from the Right**.
        - **HORIZON ALIGNMENT:** The horizon line and eye level must remain identical to the source image.

        **🏘️ 2. ARCHITECTURAL TRANSFORMATION (CRITICAL):**
        - **REPLACE ALL MODERN BUILDINGS:** Turn all glass/modern concrete structures into **2-4 story Chinese-Colonial shophouses**.
        - **TEXTURE:** Walls must be off-white or faded grey with heavy **soot stains and humidity streaks**.
        - **WINDOWS & DOORS:** Use dark **Wooden Folding Doors (Ban-Fiam)** on the ground floor and **Wooden Louvered Shutters** on upper floors.

        **🔤 3. SIGNAGE & TYPOGRAPHY (ORGANIC CLUSTERING):**
        - **CANTILEVERED SIGNS (PRIORITY):** Most signs should be large, hand-painted wooden signs hanging horizontally or vertically from brackets, jutting out over the street.
        - **LEGIBILITY:** All text must be **CORRECT, READABLE Thai & Chinese characters**. Absolutely NO gibberish.
        - **STYLE:** Matte, hand-painted finish. NO neon glow, NO internal lighting.

        **🚋 4. TRAM & ROAD (SINGLE TRACK WITH SAFETY GAP):**
        - **TRACK CONFIGURATION:** **ONE SINGLE TRAM TRACK ONLY.**
        - **POSITIONING:** The track runs along the **RIGHT SIDE** of the road (relative to the camera view).
        - **SPACING:** Leave a realistic **small safety gap** between the track and the sidewalk/building fronts.
        - **TRAM:** A weathered Yellow/Red wooden tram runs on this track.
        
        **🚦 5. ATMOSPHERE (MINIMAL TRAFFIC):**
        - **VEHICLE RESTRICTION:** **NO MOTORIZED TUK-TUKS.** NO CARS.
        - **ALLOWED TRANSPORT:** Only a few **Pedal Samlors (Tricycles)** allowed.
        - **Road Surface:** Worn asphalt with the embedded single rail.
        - **Crowd:** A lively scene of pedestrians walking and shopping.

        **⛔ NEGATIVE PROMPT:** motorized tuk-tuks, taxi cars, traffic jams, modern skyscrapers, glass windows, LED signs, neon glow, plastic banners, air conditioners, traffic lights, modern street lamps, tourists, banks, modern building, double tracks, changing perspective, zooming, shifting angle, Dutch angle, tilted camera, reorienting street.
    """,

    "Khaosan Road": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Bang Lamphu / Khaosan Road (1962).

        **🔒 PERSPECTIVE LOCK (CRITICAL):**
        - **Blueprint:** Use the Uploaded Image as the **LAYOUT REFERENCE** for street path and alignment.

        **🏘️ ARCHITECTURAL HEIGHT RESTRICTION (STRICT):**
        - **2-STORY LIMIT:** Force ALL buildings in the scene to be **LOW-RISE (Maximum 2 stories)**.
        - **REMOVE MODERN VERTICALITY:** If the input image contains tall hotels, skyscrapers, or modern concrete towers in the background, **DELETE THEM** or **REDUCE** them into sky/clouds. Do not allow any modern high-rises to peek through.
        - **UNIFORM STYLE:** Every building structure must be transformed into **Wooden Row Houses (Yellow wood / Green frames)**. No modern concrete styles allowed.

        **🚫 STRICT 1960s TIME-CAPSULE RULE:**
        - **NO MODERN ELEMENTS:** Absolutely NO air conditioners, NO satellite dishes, NO 7-Eleven signs, NO plastic chairs, NO electrical tangles.
        - **AUTHENTIC HISTORY:** The scene must strictly follow the oral history of the area: a quiet residential rice-trading community, NOT a tourist hub.

        **🚶 PEOPLE & TRAFFIC (QUIET COMMUNITY):**
        - **ZERO VEHICLES:** The narrow street is **COMPLETELY EMPTY OF CARS**, tuk-tuks, and samlors. It is a walking street for locals only.
        - **Locals Only:** Authentic Thai residents (tan skin, black hair) in 1960s attire.
        - **Activity:** Neighbors chatting in front of houses. **NO BACKPACKERS. NO TOURISTS.**

        **🍚 PROPS:**
        - Rice sacks (White/Hemp) stacked neatly in front of **ONLY 2-3 houses**.

        **⛔ NEGATIVE PROMPT:** **skyscrapers**, **high-rise buildings**, **modern hotels**, **tall concrete towers**, cars, vehicles, motorcycles, backpackers, foreigners, tourists, hostels, bars, neon lights, 7-Eleven.
    """,

    "Phra Sumen Fort": """
        **TASK:** TRANSFORM [IMAGE 1] to match the historical ruined style of [IMAGE 2], but place it in a CLEANER urban setting.

        **🧠 1. VISUAL LEARNING (FORT TEXTURE & STATE ONLY):**
        - **SOURCE OF TRUTH:** Study [IMAGE 2] intently *only* for the fort's texture and structural ruin state.
        - **STYLE TRANSFER:** Apply the heavily weathered white plaster, black mold/soot stains, and jagged ruined edges visible in [IMAGE 2] onto the structure in [IMAGE 1].

        **📸 2. ABSOLUTE PERSPECTIVE LOCK (CRITICAL & FROZEN):**
        - **PIXEL-PERFECT MATCH:** The input image [IMAGE 1] is the immutable frame. The final output MUST perfectly overlay the input's geometry.
        - **CAMERA FREEZE:** The camera angle, eye level, horizon line, and focal length are **FROZEN**. **DO NOT ROTATE. DO NOT ZOOM. DO NOT PAN.** Do not shift the view even slightly.

        **✂️ 3. STRUCTURAL EDIT (DECAPITATION):**
        - **ACTION:** **REMOVE THE ENTIRE UPPER HALF** of the fort structure.
        - **TARGET:** Delete the wooden pavilion, roof, spire, and the upper masonry section. The fort must be a massive, truncated stump with a jagged top edge.

        **🧹 4. ENVIRONMENT CLEANUP (URBAN & TIDY):**
        - **CLEAN ROAD:** The road or ground surface around the fort must be **clean, functional, and tidy** (e.g., smooth asphalt or compacted dirt). **NO MUD, NO RUBBLE, NO DEBRIS** on the street. It should look like a normal city road, not a disaster zone.
        - **VEGETATION REDUCTION:** **DRASTICALLY REDUCE** trees and green plants. Remove overgrown grass and dense foliage. It should NOT look like a jungle or forest. It must feel like an urban street corner with minimal, controlled greenery.

        **⛔ NEGATIVE PROMPT:** modern park, restored roof, golden spire, modern cars, tourists, **jungle, forest, overgrown vegetation, heavy foliage, muddy road, dirty ground, rubble on street, broken pavement**.
    """,

    "Sanam Luang": """
        **TASK:** TRANSFORM [IMAGE 1] into a **VIBRANT & LIVELY** 1968 photograph of Sanam Luang.

        **📸 1. PERSPECTIVE LOCK:**
        - **STRICT MATCH:** Use [IMAGE 1] as the rigid layout. **Do NOT shift or change the camera angle**.

        **🎪 2. DEPTH-BASED ZONING (CRITICAL):**
        - **IMMEDIATE FOREGROUND (BOTTOM OF IMAGE):** This area MUST be **100% CLEAR** of any market stalls, umbrellas, tents, or permanent structures. It should only be dry red dirt, dust, and people walking, riding bicycles, or sitting.
        - **THE PERIMETER (FAR LEFT, FAR RIGHT, & DISTANCE):** All makeshift stalls, tent shanties, and disorganized clusters of umbrellas MUST be pushed to the **EXTREME LEFT and RIGHT EDGES** of the frame, and the far distant boundary near the trees.
        - **THE CENTRAL CORE:** Maintain a wide, open corridor from the bottom-center of the image all the way to the Wat Phra Kaew in the background. No stalls allowed in this central viewing lane.

        **🏃 3. POPULATION & ACTIVITY (MINIMAL KITES):**
        - **VIBRANT CENTER:** Fill the foreground and middle ground with **DOZENS of people scattered throughout**. Focus on activities like riding **vintage bicycles**, sitting in groups on mats, strolling, and socializing.
        - **KITE RESTRICTION:** **VERY FEW TO ZERO KITES.** If any are present, they must be small and distant in the background sky, not dominating the scene.
        - **MOBILE VENDORS:** Include **Mobile Hawkers (Mae-Ka-Hab-Ray)** with shoulder poles walking in the foreground to add life without blocking the view.

        **🏜️ 4. TERRAIN & LIGHTING:**
        - **SURFACE:** Dry red dirt and fine dust. Absolutely **NO ASPHALT, NO CONCRETE, and NO ROADS**.
        - **DYNAMIC LIGHTING:** Strictly follow the lighting and time of day (Day/Night) from [IMAGE 1].

        **⛔ NEGATIVE PROMPT:** stalls in foreground, umbrellas near camera, market structures at the bottom of the image, empty field, ghost town, asphalt, roads, **many kites**, **large kites**.
    """,

    "National Museum": """
        **TASK:** TRANSFORM [IMAGE 1] into a **CLEAN & MAJESTIC 1960s** view of the National Museum Bangkok.

        **📸 1. ABSOLUTE PERSPECTIVE LOCK (CRITICAL & FROZEN):**
        - **MASTER BLUEPRINT:** [IMAGE 1] is the rigid geometric skeleton. You must map the 1960s textures directly onto the *exact* perspective of the input.
        - **CAMERA FREEZE:** **DO NOT ROTATE. DO NOT ZOOM. DO NOT PAN.** The eye level, horizon line, and object placement must be **IDENTICAL** to the source image. Do not create a new angle.

        **🧱 2. HISTORICAL FENCE RECONSTRUCTION (FLAT PILLARS):**
        - **TARGET STYLE:** Transform the fence to match the 1960s style: **Simple Masonry Pillars + Vertical Iron Bars**.
        - **PILLAR SHAPE:** All fence pillars must be **MASSIVE RECTANGULAR BLOCKS**.
        - **DECAPITATION (IMPORTANT):** **REMOVE ALL POINTED FINIALS, SPIRES, OR LOTUS BUDS** from the top of the pillars. The pillar tops must be **COMPLETELY FLAT** or very low-profile caps (Plain White/Cream Stucco).
        - **INTEGRITY:** The fence line must be solid and continuous.

        **🪓 3. VEGETATION CLEANUP (REVEAL THE BUILDING):**
        - **DEFORESTATION:** **REMOVE** large, messy trees that obstruct the view of the museum building.
        - **VISIBILITY:** The beautiful Thai architecture (roofs, gables) must be clearly visible, not hidden behind branches or dense leaves.
        - **TIDY GROUNDS:** The area should look like a well-maintained royal ground, not a jungle. Keep only minimal, neat greenery if necessary.

        **🚧 4. ROAD & SURFACE:**
        - **ROAD:** Clean, dark asphalt or smooth concrete. No modern traffic lines (zebra crossings).
        - **CLEANLINESS:** No rubble, no dirt piles. A civilized, prestigious atmosphere.

        **⛔ NEGATIVE PROMPT:** pointed pillars, lotus bud finials, decorative spires on fence, overgrown jungle, tree blocking view, forest, mess, moss, modern cars, traffic cones, distortion, changing angle, grass on the floor.
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

SIMILARITY_THRESHOLD = 0.6
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

    elif location_key == "Yaowarat":
        extra_instructions = """
    - **SIGNAGE LOGIC:** Prioritize cantilevered signs that hang over the street. 
    - **PILLAR OVERRIDE:** Do NOT treat every building pillar as a location for a sign. Keep at least 70 percent of the pillars bare to show the weathered stucco texture.
        """

    elif location_key == "National Museum":
        extra_instructions = """
    - **GEOMETRY ANOMALY DETECTED:** Identify any small pedestrian gates or side openings in [IMAGE 1]. 
    - **TASK:** You MUST **DELETE** these openings. Fill the gaps with a **SOLID MASONRY BASE** and a **CONTINUOUS IRON FENCE**.
    - **WALL INTEGRITY:** The fence must be an unbroken line from the frame edge to the central gate.
    - **PILLAR OVERRIDE:** Every pillar must be a simple rectangular block. **SURGICALLY REMOVE** any pointed finials or decorative caps.
    - **Signage Removal:** Erase any modern signs or plaques on the wall pillars.
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

# ==========================================
# ปิดการใช้งาน RUNWAY ML ไว้แปป
# ==========================================
def generate_video_runway(image_bytes, location_key):
    # --- 🔴 ปิดการใช้งานชั่วคราว ---
    print("⚠️ Runway Video Generation is currently DISABLED.")
    return None

    # runway_key = os.getenv("RUNWAYML_API_KEY")
    # if not runway_key:
    #     print("❌ Error: RUNWAYML_API_KEY not found in .env")
    #     return None

    # try:
    #     print("🎬 Starting Runway Gen-3 Video Generation (Strict Living Photo)...")
        
    #     # 1. Prepare Base64
    #     base64_str = base64.b64encode(image_bytes).decode('utf-8')

    #     # 2. UNIVERSAL PROMPT (Living Photo / Motion Graphic Style)
    #     final_prompt = """
    #     Style: High-end Motion Graphic / Living Photo. Extreme slow motion (0.25x speed).
    #     CAMERA: Smooth, constant, slow horizontal pan. NO ZOOM.
        
    #     CRITICAL CONSTRAINTS (ZERO TOLERANCE):
    #     - ANIMATE ONLY EXISTING PIXELS: Use only the visual data provided in the source image.
    #     - DO NOT ADD ANYTHING: Absolutely NO new people, NO new cars, NO new trees, and NO new leaves.
    #     - IF IT'S NOT THERE, DON'T MOVE IT: If the image is empty, keep it empty.

    #     MOVEMENT DYNAMICS:
    #     - STATIC WORLD: Architecture, text, ground, and background must remain 100% RIGID and FROZEN. No warping or morphing.
    #     - MICRO-MOTION: Only IF living beings or vehicles are ALREADY present, apply very subtle breathing or slight shifting movements.
        
    #     Atmosphere: Realistic, frozen moment in time, high fidelity.
    #     """
        
    #     # ตรวจสอบความยาว Prompt
    #     if len(final_prompt) > 990:
    #         print(f"⚠️ Warning: Prompt length {len(final_prompt)} is close to limit!")

    #     print(f"📝 Video Prompt ({len(final_prompt)} chars): {final_prompt.strip()}")

    #     # 3. Call Runway API directly
    #     url = "https://api.dev.runwayml.com/v1/image_to_video"
    #     payload = {
    #         "promptImage": f"data:image/png;base64,{base64_str}",
    #         "model": "gen3a_turbo", 
    #         "promptText": final_prompt.strip(),
    #         "duration": 5,
    #         "ratio": "1280:768"
    #     }
        
    #     headers = {
    #         "Authorization": f"Bearer {runway_key}",
    #         "X-Runway-Version": "2024-11-06",
    #         "Content-Type": "application/json"
    #     }
        
    #     # Send Request
    #     response = requests.post(url, json=payload, headers=headers)
        
    #     if response.status_code != 200:
    #         print(f"❌ Runway API Failed ({response.status_code}): {response.text}")
    #         return None
            
    #     task_id = response.json().get('id')
    #     print(f"⏳ Runway Task ID: {task_id}")
        
    #     # Polling Loop
    #     for i in range(30):
    #         time.sleep(3)
    #         status_res = requests.get(f"https://api.dev.runwayml.com/v1/tasks/{task_id}", headers=headers)
    #         if status_res.status_code == 200:
    #             data = status_res.json()
    #             if data.get('status') == "SUCCEEDED":
    #                 print("✅ Video Generation Complete!")
    #                 return data.get('output', [None])[0]
    #             elif data.get('status') == "FAILED":
    #                 print(f"❌ Video Generation FAILED: {data.get('failure', 'Unknown error')}")
    #                 return None
    #         else:
    #             print(f"⚠️ Polling Error: {status_res.status_code}")
                
    #     print("❌ Timeout: Runway took too long.")
    #     return None

    # except Exception as e:
    #     print(f"❌ Critical Runway Error: {e}")
    #     return None
    
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
    # --- 🔴 ส่งคืนค่าว่างทันที เพื่อไม่ให้โปรแกรมพัง ---
    return jsonify({'status': 'skipped', 'message': 'Video generation is temporarily disabled.'})

    # try:
    #     print("🚀 [Step 2] Animating Video...")
    #     data = request.json
    #     image_data = data.get('image') # Base64 Image
    #     location_key = data.get('location_key')

    #     if not image_data: return jsonify({'error': 'No image provided'}), 400
        
    #     # Clean Base64 header
    #     if "," in image_data: image_data = image_data.split(",")[1]
    #     image_bytes = base64.b64decode(image_data)

    #     # 1. เรียก Runway ให้สร้างวิดีโอ
    #     video_url = generate_video_runway(image_bytes, location_key)
        
    #     if video_url:
    #         print(f"✅ Runway Success! URL: {video_url}")
            
    #         # 2. พยายามบันทึกลงเครื่อง (Local Save)
    #         vid_filename, vid_path = save_generated_video(video_url, location_key)
            
    #         final_video_src = video_url # Default: ใช้ URL ตรงจาก Runway (เผื่อ Save พัง)

    #         # 3. ถ้า Save สำเร็จ ให้แปลงเป็น Base64 (เพื่อความเร็วในการโหลด Local)
    #         if vid_path and os.path.exists(vid_path):
    #             try:
    #                 with open(vid_path, "rb") as f:
    #                     vid_b64 = base64.b64encode(f.read()).decode('utf-8')
    #                     final_video_src = f"data:video/mp4;base64,{vid_b64}"
    #                     print("📦 Sending Video as Base64")
    #                 except Exception as e:
    #                     print(f"⚠️ Read File Error: {e} -> Sending Remote URL instead")
    #         else:
    #             print("⚠️ Save failed or File not found -> Sending Remote URL directly")

    #         # 4. ส่งผลลัพธ์กลับ Frontend (ไม่ว่า Save ได้หรือไม่ได้ User ต้องเห็นวิดีโอ)
    #         return jsonify({
    #             'status': 'success',
    #             'video': final_video_src
    #         })
    #     else:
    #         return jsonify({'error': 'Video generation failed (Runway returned None)'}), 500

    # except Exception as e:
    #     print(f"❌ Critical Animate Error: {e}")
    #     return jsonify({'error': str(e)}), 500

@app.route('/videos/<path:filename>')
def serve_video(filename):
    return send_from_directory(VIDEO_FOLDER, filename)

if __name__ == '__main__':
    app.run(debug=True, port=5000)