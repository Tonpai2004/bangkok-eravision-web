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
        - **Visual:** Large hand-painted cutout poster. Two men back-to-back. One in a sharp **black suit** (half-Chinese), one in a white shirt. Both look like 1960s gentlemen. Cover the front of the theater area.
        - **Text:** Title "**บางกอกทวิกาล**". Starring "**มาดามพงษ์ และ ณัฐภัทร**".
        - **Style:** Matte finish, hand-painted look. No neon glow or digital effects.
        - **Remove ads:** Delete any modern ads, posters, banners or Thai banks logos around the theater entrance.
        
        **🚶 4. PEDESTRIAN CONTEXT:**
        - **STREET:** Wide asphalt avenue, **COMPLETELY EMPTY OF CARS**.
        - **CROWD:** A lively, crowd of Thai locals in 1960s fashion (white shirts, skirts, slacks) walking and gathered for a premiere.
        
        **🎨 5. STYLE:**
        - **Look:** 1960s Kodachrome film with warm natural light and soft grain.

        **NEGATIVE PROMPT:** home, houses, skyscrapers, high-rise buildings, modern towers, glass facades, urban sprawl, cars, traffic, street lights, electric wires.
    """,

    "Giant Swing": """

        **TASK:** TRANSFORM [IMAGE 1] into a **1960s Phra Nakhon Era** scene using strict structural preservation. **Apply these rules with equal strictness from the immediate foreground to the furthest visible pixel on the horizon.**

        **🔒 1. ABSOLUTE GEOMETRY & SPATIAL LOCK (THE "STENCIL" RULE):**
        - **FIXED LAYOUT:** The input image is a rigid map. **DO NOT CHANGE THE SPACING** between buildings.
        - **PRESERVE GAPS:** If there is empty sky or space between buildings in the source, **KEEP IT EMPTY**. Do not fill gaps with new shophouses.
        - **CAMERA FREEZE:** **DO NOT ROTATE. DO NOT ZOOM. DO NOT PAN. OR ENLARGE THE IMAGE** The perspective must perfectly overlay the original image.

        **🔄 2. ARCHITECTURAL RE-SKINNING (NO NEW BUILDINGS):**
        - **DETECT SKYSCRAPERS:** Identify all modern builiding, skyscrapers/tall buildings in the image, from the nearest to the **farthest point on the horizon**. **Do NOT retain the modern silhouette of distant buildings.** **Surgically DELETE** them and replace with **clear blue sky or soft clouds**. No structure should be taller than 2-story building.
        - **STRICT TRANSFORMATION:** Detect ALL buildings present. Transform their **surfaces** to match the **1960s COLONIAL STYLE** (SINGLE MASSING of 2-story masonry structures with **rectangle Windows** and **Weathered Cream Stucco**, **Dark Wooden Folding Doors (Ban-Fiam)**, Dark brown **CLOSED HIPPED ROOF** with Clay Tiles. **The roof structure must be a continuous lid with closed triangular ends.**). 
        - **HORIZON OVERRIDE:** You MUST **reconstruct the silhouette** of distant buildings; do not simply re-texture them. If a building at the horizon is taller than 2 stories, **You MUST overwrite these pixels with the sky and clouds.**.
        - **NO GHOST SILHOUETTES: Do not attempt to re-texture distant tall buildings. If it is not a 2-story shophouse or the Giant Swing, it MUST NOT EXIST. Paint the sky over it completely.
        - **VANISHING POINT CLEANUP: At the furthest point of the street, ensure there are NO vertical lines or box shapes peeking out. The sky must meet the shophouse roofline directly.

        
        **📍 THE SEMANTIC BOUNDARY RULE:
        -TEMPLE ISOLATION: Identify the white masonry perimeter walls (Kamphaeng Kaeo) and the ornate gate structures. These white walls are an ABSOLUTE BARRIER.
        -NO OVERLAP: Shophouses and wooden textures MUST NOT touch, cross, or overlap with any white temple walls or religious structures.
        -BUFFER ZONE: If the boundary is unclear, leave a clear Empty Asphalt Gap between the temple and the shophouses. NEVER "fill" the temple grounds with houses.

        - **CAREFULLY Identify the areas of Temple (Wat Suthat)** **PRESERVE that area** and only apply weathering effects. Do NOT convert temple walls into houses or add new structures or place the temple at the empty spaces.
        -** IF IT IS A BLANK SPACE AREA ON THE GROUND, DO NOT ADD ANY BUILDINGS OR HOUSES. LEAVE IT AS OPEN SKY.**
        
        **⛩️ 3. THE GIANT SWING (HISTORICAL TWO-TIER BASE):**
        - **PILLARS:** Massive **Aged Red Teak** pillars.
        - **DUAL-LAYER BASE (CRITICAL):** Render the base structure accurately with **TWO DISTINCT CONCRETE LEVELS**:
            1. **The Plinths:** Concrete blocks directly supporting the red teak legs.
            2. **The Island Platform:** A **Blank** wide, raised **curbed concrete island (Traffic Island)** that the whole structure sits upon.
        - **DECORATION BAN:** The base must be **BARE**, **BLANK**, CLEAN WHITE/GREY CONCRETE**. Absolutely **NO FLOWERS**, no garlands, no fabric wrappings, no pot, and no ornate carvings.

        **🛣️ 4. CLEAN ROAD (ZERO VEHICLES):**
        - **REMOVE TRAFFIC:** The road must be **MAJESTICALLY EMPTY**. Remove all cars, tuk-tuks, and buses.
        - **SURFACE:** Reveal the road surface underneath. Render it as **Clean, Weathered Grey Asphalt**.
        - **TRAM TRACKS:** Create a weathered tram tracks that locate **in front of WAT SUTHAT temple** only.

        ** 5. LIGHTING & ATMOSPHERE:**
        - **Crowd:** Add a few pedestrians in 1960s attire walking on the sidewalk or in front of the temple some standing on the island of giant swing. No one should be on the road.

        **⛔ NEGATIVE PROMPT:** modern architectural silhouettes, background blocks, distant urban noise, modern cars, traffic, vehicles, people in middle of road, **added buildings**, **filling gaps**, **crowded skyline**, **flowers on base**, garlands, fantasy decorations, changing angle, **modern windows in distance, air conditioners in background.**

    """,

    # **Building Instructions to follow to transform into:**
    #    - **ARCHITECTURAL STYLE:** Group all visible shophouses into a **SINGLE, UNBROKEN ARCHITECTURAL MASS**. 
    #    - **MONOLITHIC ROOF:** The roof MUST be a **SINGLE, CONTINUOUS HORIZONTAL SLAB** of aged brown-black clay tiles. 
    #    - **THE RIDGE LINE:** Ensure there is one **PERFECTLY STRAIGHT, SEAMLESS ridge line** running across the entire row of buildings.
    #    - **ZERO VERTICAL DIVIDERS:** You MUST **Surgically DELETE** all vertical firewalls (กำแพงกันไฟ), parapet walls, or gaps between individual units. The roof must look like one giant, unified piece of clay.
    #    - **COLONIAL STYLE:** 2-story masonry structures with **rectangle Windows** and **Weathered Cream Stucco**. Ground floors must feature **Dark Wooden Folding Doors (Ban-Fiam)**.

    "Yaowarat": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Yaowarat Road (1968).
        **LOCK:** Maintain exact building geometry and camera height of [IMAGE 1].

        **📸 1. THE "FROZEN TRIPOD" RULE & PIXEL-PERFECT PERSPECTIVE LOCK (NON-NEGOTIABLE):**
        - **THE INPUT IS THE ONLY REALITY:** Treat the uploaded image as the absolute geometric truth. Imagine your camera is physically **NAILED TO THE EXACT SPOT** where the original photo was taken.
        - **ZERO MOVEMENT POLICY (CRITICAL):**
            - **NO SHIFTING:** Do not move the camera left, right, up, or down by even a millimeter.
            - **NO ROTATION:** Do not tilt the camera, do not pan, do not change the angle.
            - **NO MIRRORING/FLIPPING:** Absolutely DO NOT flip or mirror the perspective horizontally or vertically. The left side of the street MUST remain the left side.
        - **LENS & OPTICAL LOCK:** You MUST use the **EXACT same lens focal length, distortion, and field of view (FOV)** as the input. Do not widen the shot to show more, do not zoom in to show less. The view through the lens must perfectly overlay the original.
        - **HORIZON & EYE-LEVEL RIGIDITY:** The horizon line and the viewer's eye level are frozen in place. They must match the source image's coordinates precisely on the pixel grid.

        **🏘️ 2. ARCHITECTURAL TRANSFORMATION (CRITICAL):**
        - **REPLACE ALL MODERN BUILDINGS:** Turn all glass/modern concrete structures into **2-4 story Chinese-Colonial shophouses with slight soot and humidity streaks**.
        - **TEXTURE:** Walls must be off-white or faded grey with heavy **soot stains and humidity streaks**.
        - **WINDOWS & DOORS:** Use dark **Wooden Folding Doors (Ban-Fiam)** on the ground floor and **Wooden Louvered Shutters** on upper floors.
        - **STRUCTURAL INTEGRITY:** Do not change the spacing or distance between existing buildings. Do not add new buildings in empty spaces.

        - **UTILITY POLES (NEW):** Add vintage **weathered concrete utility poles** along the sidewalks **ONLY**. Include a **realistic tangle of black electrical wires** stretching between buildings.


        **🔤 3. SIGNAGE ARTISTRY (THE "IMPRESSIONIST" RULE):**
        - **FOREGROUND LEGIBILITY:** Use clear, bold Thai script for foreground signs like: "**ห้างทอง**", "**ร้านยา**", "**โรงแรม**", "**อาหาร**", "**บริษัท**", "**โรงรับจำนำ**".
        - **BACKGROUND CHARACTER ISOLATION:** For distant signs, do NOT attempt full sentences. Instead, render **SINGLE, BOLD, HIGH-CONTRAST Chinese characters** (e.g., "**金**", "**福**", "**大**", "**吉**") or very short Thai words (e.g., "**ยา**", "**ทอง**").
        - **COLOR CONTRAST:** Use strictly high-contrast combinations for distant signs: **Bright Red backgrounds with Gold text** or **Yellow backgrounds with Black text**. This prevents AI from blurring the characters into the background.
        - **PATINA:** Signs must look aged with **peeling paint, sun-faded colors, and rust stains** on the metal brackets.


        **🚋 4. TRAM & ROAD:**
        - **TEXTURE:** The asphalt road must look **used and worn**.
        - **Trash & Debris:** Add small bits of scattered litter (paper scraps, leaves) and dust along the curb edges and road for realism.
        - **TRACK & TRAM:** Single track on the right with a weathered Yellow/Red wooden tram.
        
        **🚦 5. ATMOSPHERE:**
        - **VEHICLE:** NO motorized tuk-tuks, NO cars. Only pedal samlors.
        - **CROWD:** Lively pedestrians in 1960s fashion.
        - **HIGH DENSITY:** Fill the sidewalks and street edges with a **thick crowd of pedestrians** in 1960s Thai-Chinese fashion (white shirts, slacks, traditional dresses). make some of them look like they are shopping, walking, chatting, or carrying goods. and make the crowd look dense and busy. make some of them walk on the road but not crossing the road.
        - **STREET LIFE:** Include a few mobile street vendors with shoulder poles (Mae-Ka-Hab-Ray) weaving through the crowd.

        **⛔ NEGATIVE PROMPT:** MODERN ARCHITECTURE, aluminum facade, glass curtain wall, motorized tuk-tuks, taxi cars, traffic jams, modern skyscrapers, glass windows, LED signs, neon glow, plastic banners, air conditioners, traffic lights, modern street lamps, tourists, banks, modern building, double tracks, **changing perspective, zooming, shifting angle, Dutch angle, tilted camera, reorienting street, straightening road, mirroring image, flipping perspective, changing lens**.
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
        **TASK:** TRANSFORM [IMAGE 1] into a historical 1960s scene. **CRITICAL: INPUT-ANGLE LOCK + REF-TEXTURE MAPPING.**

        **📐 0. ABSOLUTE GEOMETRY & ANGLE LOCK (INPUT DOMINANCE):**
        - **PRIMARY RULE:** The **Camera Angle, Eye Level, and Object Orientation** are DICTATED BY [IMAGE 1] ONLY.
        - **ANGLE ANALYSIS:**
            - **Step 1:** Analyze [IMAGE 1]. Is the fort facing Front? Left-Oblique? Right-Oblique? Is the camera Low or High?
            - **Step 2:** Analyze [IMAGE 2] (Reference). Note that it might only show specific angles (e.g., Side View).
            - **Step 3 (EXECUTION):** If [IMAGE 1] is Frontal but [IMAGE 2] is Side view, **IGNORE THE REFERENCE ANGLE.** You must paint the Reference's texture onto the **FRONTAL GEOMETRY** of [IMAGE 1].
        - **PERSPECTIVE FREEZE:** The Vanishing Points and Horizon Line of the output must align **PERFECTLY** with [IMAGE 1].

        **✂️ 1. MANDATORY DECAPITATION (IMMEDIATE ACTION):**
        - **TRIGGER:** As soon as you process [IMAGE 1], identify the upper wooden pavilion, roof, and spire.
        - **EXECUTION:** **CUT THEM OFF IMMEDIATELY.**
        - **REPLACEMENT:** The area where the roof exists in the input MUST become **EMPTY SKY**.
        - **SILHOUETTE:** The fort must become a **"Headless Stump"** ending abruptly at the masonry rim, exactly matching the silhouette style of [IMAGE 2].

        **🎨 2. SMART DETAIL ADAPTATION (REALISM INJECTION):**
        - **TEXTURE PROJECTION:** Take the *mold, soot, and peeling plaster details* from [IMAGE 2] and **PROJECT** them onto the specific surfaces of [IMAGE 1], respecting the input's lighting and depth.
        - **CONTEXTUAL ELEMENTS:** Look for small details in [IMAGE 2] (fences, ground texture, wall stains). Add these elements to [IMAGE 1] to increase realism, but **PLACE THEM** according to [IMAGE 1]'s perspective grid.

        **🛣️ 3. ROAD CONDITION (CLEAN ASPHALT EXCEPTION):**
        - **SURFACE:** While the surroundings follow the reference, the **ROADWAY** itself must remain **SMOOTH, CLEAN ASPHALT**.
        - **NO MESS:** The road is functional. **NO RUBBLE. NO MUD.**

        **⛔ NEGATIVE PROMPT:** **roof**, **pavilion**, **spire**, **golden top**, **wooden structure**, restored condition, modern park, garden, inventing buildings, adding houses, creative additions, rubble on road, **shifting angle**, **changing perspective**, **zooming**, **using reference angle instead of input angle**.
    """,
    
    "Sanam Luang": """
        **TASK:** TRANSFORM [IMAGE 1] into a **VIBRANT & LIVELY** 1968 photograph of Sanam Luang.

        **📸 1. PERSPECTIVE LOCK:**
        - **STRICT MATCH:** Use [IMAGE 1] as the rigid layout. **Do NOT shift or change the camera angle**.
        
        - **BEYOND THE LENS:** Imagine the market stalls and tents are located **BEYOND the edges of the camera view**. You should only see a few stall edges peeking in from the very far left or right.
        - **NO ENCLOSURE:** Do NOT create a "street" or "alley" of tents. This is a massive open field, not a market lane.

        **🎪 2. DEPTH-BASED ZONING (CRITICAL):**
        - **IMMEDIATE FOREGROUND (BOTTOM OF IMAGE):** This area MUST be **100% CLEAR** of any market stalls, umbrellas, tents, or permanent structures. It should only be dry red dirt, dust, and people walking, riding bicycles, or sitting.
        - **THE PERIMETER (FAR LEFT, FAR RIGHT, & DISTANCE):** All makeshift stalls, tent shanties, and disorganized clusters of umbrellas MUST be pushed to the **EXTREME LEFT and RIGHT EDGES** of the frame, and the far distant boundary near the trees.
        - **THE CENTRAL CORE:** Maintain a wide, open corridor from the bottom-center of the image all the way to the Wat Phra Kaew in the background. No stalls allowed in this central viewing lane.
        
        - **PERIPHERAL ONLY:** Any makeshift stalls or umbrellas must be pushed so far to the edges that they are almost **OFF-SCREEN**.

        - **HAPHAZARD CLUSTERING:** Market stalls and umbrellas must be **disorganized and unevenly scattered**. Some should overlap, some should be tilted at odd angles, and they should **NOT** follow a straight line.
        - **MAKESHIFT MATERIALS:** Use weathered materials: **stained canvas tents, worn-out wooden poles, aged bamboo sticks, and faded, multi-colored umbrellas** with visible patches or tears.
        
        **🏃 3. POPULATION & ACTIVITY (MINIMAL KITES):**
        - **VIBRANT CENTER:** Fill the foreground and middle ground with **DOZENS of people scattered throughout**. Focus on activities like riding **vintage bicycles**, sitting in groups on mats, strolling, playing kites, selling things, and socializing.
        - **KITE RESTRICTION:** **VERY FEW TO ZERO KITES.** If any are present, they must be small and distant in the background sky, not dominating the scene.
        - **MOBILE VENDORS:** Include **Mobile Hawkers (Mae-Ka-Hab-Ray)** with shoulder poles walking in the foreground to add life without blocking the view.

        **🏜️ 4. TERRAIN & LIGHTING:**
        - **SURFACE:** Dry dirt and fine dust with green-to-yellow grass. Absolutely **NO ASPHALT, NO CONCRETE, and NO ROADS**.
        - **DYNAMIC LIGHTING:** Strictly follow the lighting and time of day (Day/Night) from [IMAGE 1].

        **⛔ NEGATIVE PROMPT:** stalls in foreground, umbrellas near camera, market structures at the bottom of the image, empty field, ghost town, asphalt, roads, **many kites**, **large kites**.
    """,
    
    "National Museum": """
        **TASK:** Create a **VINTAGE 1960s** view of the National Museum Bangkok.

        **🧱 1. LINEAR FENCE GEOMETRY (THE SINGLE PLANE RULE - CRITICAL):**
        - **SINGLE STRAIGHT LINE:** The entire fence line MUST exist on a **SINGLE FLAT GEOMETRIC PLANE** (180 degrees).
        - **NO RECESS / NO LOOPS:** Absolutely **NO fences wrapping inward**, NO "L-shaped" or "U-shaped" fences, and NO internal loops. The gate area must NOT be recessed.
        - **REPEATING PATTERN:** Follow a strict rhythm: **(One small masonry pillar -> One section of iron bars -> One small masonry pillar)**. Ensure intermediate pillars are visible along the entire line.
        - **VISIBLE MASONRY BASE:** The iron fence must sit on a **SOLID WHITE MASONRY BASE** (Knee-high). Do NOT render it as a flat line.
        - **SURGICAL DELETION:** Erase the side-door structures and the green signage beam from [IMAGE 1] entirely.

        **🚪 2. DOUBLE-SWING GATE & PILLARS:**
        - **DESIGN:** A **DOUBLE-SWING weathered IRON GATE** with vertical bars and a visible center-split line.
        - **THE GAP:** Create a clear **VOID OF AIR** between the standalone gate pillars. No horizontal connections allowed.
        - **PILLAR STYLE:** All pillars must be rectangular blocks with **COMPLETELY FLAT SQUARE TOPS**.
        - **LOW PROFILE:** Keep the structure **SHORT (Waist-high)** to reveal the museum architecture behind.

        **🚧 3. ROAD & ENVIRONMENT:**
        - **SURFACE:** Asphalt road. No traffic markings. Zebra crossings or painted lines.
        - **CLEANUP:** Remove all flags, flagpoles, modern signs, and traffic markings.
        
        ** 4. People & Atmosphere:**
        - **MINIMAL CROWD:** A few people walking on the curb that meets the masonry base directly and also walk in the museum in 1960s attire.
        - **NO VEHICLES:** The road and inside the museum is completely clear of cars and traffic.

        **⛔ NEGATIVE PROMPT:** thin fence base, missing intermediate pillars, side gates, merged pillars, curved entrance, recessed gate, concrete sidewalk, raised curb, pointed pillars, flags.
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
    
    # 1. สร้างฐานคำสั่งกลาง (เพิ่ม Spatial Integrity)
    perspective_instr = f"""
    **MANDATORY PERSPECTIVE INSTRUCTION:**
    - {structure_desc}
    - **GEOMETRY SOURCE:** Use [IMAGE 1] as the ONLY source for composition.
    - **STRICT CONSTRAINT:** No rotation, zooming, or shifting. Perfect overlay required.
    """
    
    if location_key == "Phra Sumen Fort":
        perspective_instr += """
    - **ANGLE MATCHING (CRITICAL):** Check the camera angle of the Input [IMAGE 1]. The Output MUST match it exactly. (e.g., If Input is Left-Oblique, Output MUST be Left-Oblique).
    - **IMMEDIATE DECAPITATION:** The moment you see the roof/pavilion in the input, **TURN IT INTO SKY**. The fort is a headless stump.
    - **REFERENCE DETAILS:** Fill the scene with the *texture and clutter details* seen in [IMAGE 2], but place them according to the perspective of [IMAGE 1].
    - **NO PARK:** Remove all manicured grass/parks.
    - **CLEAN ROAD:** Keep the road surface **smooth and clean**.
        """
    
    # elif location_key == "Giant Swing":
    #     perspective_instr += """
    # - **SPATIAL ENFORCEMENT:** 1. LEFT OF SWING = Temple (No-Build Zone). 2. RIGHT OF SWING = 2-story Shophouses (No Temple Elements).
    # - **ROAD PURGE:** Identify the road surface in the foreground and center. **ERASE** any structures generated on the asphalt. Keep it a clear, empty grey road.
    # - **TEXTURE ISOLATION:** Do not bleed temple textures onto the right-side shophouses.
    # - **MONOLITHIC ROOF:** Flatten the shophouse roofs into one continuous line.
    # - **SKYLINE DELETION:** Replace skyscrapers with sky.
    #     """
        
    elif location_key == "Yaowarat":
        perspective_instr += """
    - **SIGNAGE DENSITY:** Allow a high density of signs. Do NOT leave pillars bare; fill them with vertical hand-painted signs.

    - **CHARACTER BOLDNESS:** Force all distant typography to use **EXTRA BOLD STROKES**.
    - **SYMBOLIC OVERRIDE:** If a distant word is failing to render, replace it with a **single, clear, large Chinese character** in Gold/Red color.

    - **ROAD DETAIL:** Add heavy "surface grime" and tire marks to the asphalt.
    - **CROWD INJECTION:** Populate the scene with a high-density crowd. Ensure they look naturally integrated into the perspective of [IMAGE 1].
    - **INFRASTRUCTURE:** Add vintage utility poles and street-level clutter to fill visual gaps.
        """

    elif location_key == "National Museum":
        perspective_instr += """
    - **PATTERN REPLICATION:** Identify the (Pillar -> Iron Railing -> Pillar) rhythm. You MUST replicate this pattern across the entire fence, especially where side-gates were removed.
    - **BASE ENFORCEMENT:** Ensure the masonry base has a clear, visible height (approx. 40cm). It should look like a solid wall base, not a flat line on the ground.
    - **SIDE GATE DELETION:** Completely DELETE the side entrance structures. Fill the resulting gap with **EMPTY SKY** or the **BACKGROUND BUILDING** to separate the pillars.
    - **LINEAR ALIGNMENT:** Force the fence into a **PERFECTLY STRAIGHT LINE**. Ignore the modern recessed curves from [IMAGE 1].
    - **FLATTEN TOPS:** All pillars must have FLAT SQUARE TOPS.
        """

    elif location_key == "Sanam Luang":
        perspective_instr += """
    - **VASTNESS ENFORCEMENT:** Treat the edges of [IMAGE 1] as "Infinite Borders". 
    - **PERIPHERAL BIAS:** PUSH all market elements (tents, stalls) as far away from the center as possible. 
    - **OFF-SCREEN LOGIC:** It is OKAY if some stalls listed in the prompt are NOT visible in the frame. Priority is a **CLEAR, WIDE OPEN RED DIRT FIELD**.
    - **HORIZON CLEARANCE:** Ensure a direct, unobstructed line of sight to the temples in the background.
        """

    # 3. ประกอบ Global Style (ล็อคอารมณ์ภาพ)
    global_style = f"""
    {perspective_instr}
    
    **GLOBAL STYLE:**
    - Output: Photorealistic color 1960s Kodachrome filter.
    - **RECONSTRUCTION RULE:** Discard any modern architecture from [IMAGE 1] and replace with historical elements from [IMAGE 2] or Prompt.
    - Remove all traffic lights, LED lamps, and digital signage.
    """
    
    # ส่วนการประกอบ Parts และเรียก AI
    parts = [f"{specific_prompt}\n{global_style}\n\n**[IMAGE 1] THE STRUCTURAL BLUEPRINT:**"]
    parts.append(types.Part.from_bytes(data=original_img_bytes, mime_type="image/jpeg"))

    if ref_img_bytes:
        style_instruction = """
        **[IMAGE 2] THE STYLE REFERENCE:**
        - USE ONLY for: Color grading, film grain, and 1960s atmosphere.
        - **DANGER:** Do NOT follow the architecture or camera angle of [IMAGE 2].
        """
        parts.append(style_instruction)
        parts.append(types.Part.from_bytes(data=ref_img_bytes, mime_type="image/jpeg"))

    # Config การเรนเดอร์ (แนะนำ temperature=0.1 เพื่อให้มีความยืดหยุ่นเล็กน้อยแต่ไม่หลุดกรอบ)
    config = types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        temperature=0.1 
    )
    # 3. เรียกโมเดลด้วยค่าความสร้างสรรค์ต่ำที่สุด (Locking the result)
    model_name = "gemini-3-pro-image-preview" 
    max_retries = 5

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

import os
import io
import time
import base64
import datetime
import requests
from PIL import Image

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
        base_prompt = """
        Static tripod camera shot, absolutely NO panning, NO zooming, NO rotation.
        Hyper-realistic 8k video, high fidelity.
        Subtle environmental motion only. Stable structures, no morphing buildings.
        Natural 1960s lighting with very subtle film grain. No visual glitches.
        """

        location_prompts = {
            "Democracy Monument": "Static shot. Cars are parked still on the road. ONLY clouds in the sky move slowly. Subtle heat haze on the asphalt. No car movement at all. **CRITICAL: The monument structure MUST REMAIN PERFECTLY STATIC and RIGID. No morphing, warping, twisting, or glitching of the concrete wings or base throughout the video.**",
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
                    print(f" ...processing ({i+1}/30)")
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


# def generate_video_runway(image_bytes, location_key):
#     # ✅ ลบส่วน "ปิดการใช้งานชั่วคราว" ออกเพื่อให้โค้ดด้านล่างทำงาน
#     runway_key = os.getenv("RUNWAYML_API_KEY")
#     if not runway_key:
#         print("❌ Error: RUNWAYML_API_KEY not found in .env")
#         return None

#     try:
#         print("🎬 Starting Runway Gen-3 Video Generation (Strict Living Photo)...")
        
#         # 1. Prepare Base64
#         base64_str = base64.b64encode(image_bytes).decode('utf-8')

#         # 2. UNIVERSAL PROMPT (Living Photo / Motion Graphic Style)
#         final_prompt = """
#         Style: High-end Motion Graphic / Living Photo. Extreme slow motion (0.25x speed).
#         CAMERA: Smooth, constant, slow horizontal pan. NO ZOOM.
        
#         CRITICAL CONSTRAINTS (ZERO TOLERANCE):
#         - ANIMATE ONLY EXISTING PIXELS: Use only the visual data provided in the source image.
#         - DO NOT ADD ANYTHING: Absolutely NO new people, NO new cars, NO new trees, and NO new leaves.
#         - IF IT'S NOT THERE, DON'T MOVE IT: If the image is empty, keep it empty.

#         MOVEMENT DYNAMICS:
#         - STATIC WORLD: Architecture, text, ground, and background must remain 100% RIGID and FROZEN. No warping or morphing.
#         - MICRO-MOTION: Only IF living beings or vehicles are ALREADY present, apply very subtle breathing or slight shifting movements.
        
#         Atmosphere: Realistic, frozen moment in time, high fidelity.
#         """
        
#         # ตรวจสอบความยาว Prompt
#         if len(final_prompt) > 990:
#             print(f"⚠️ Warning: Prompt length {len(final_prompt)} is close to limit!")

#         print(f"📝 Video Prompt ({len(final_prompt)} chars): {final_prompt.strip()}")

#         # 3. Call Runway API directly
#         url = "https://api.dev.runwayml.com/v1/image_to_video"
#         payload = {
#             "promptImage": f"data:image/png;base64,{base64_str}",
#             "model": "gen3a_turbo", 
#             "promptText": final_prompt.strip(),
#             "duration": 5,
#             "ratio": "1280:768"
#         }
        
#         headers = {
#             "Authorization": f"Bearer {runway_key}",
#             "X-Runway-Version": "2024-11-06",
#             "Content-Type": "application/json"
#         }
        
#         # Send Request
#         response = requests.post(url, json=payload, headers=headers)
        
#         if response.status_code != 200:
#             print(f"❌ Runway API Failed ({response.status_code}): {response.text}")
#             return None
            
#         task_id = response.json().get('id')
#         print(f"⏳ Runway Task ID: {task_id}")
        
#         # Polling Loop (รอให้วิดีโอเจนเสร็จ)
#         for i in range(30):
#             time.sleep(3)
#             status_res = requests.get(f"https://api.dev.runwayml.com/v1/tasks/{task_id}", headers=headers)
#             if status_res.status_code == 200:
#                 data = status_res.json()
#                 if data.get('status') == "SUCCEEDED":
#                     print("✅ Video Generation Complete!")
#                     return data.get('output', [None])[0]
#                 elif data.get('status') == "FAILED":
#                     print(f"❌ Video Generation FAILED: {data.get('failure', 'Unknown error')}")
#                     return None
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
    # ✅ ลบ return jsonify ตัวเก่าออกเพื่อให้โค้ดด้านล่างทำงานจริง
    try:
        print("🚀 [Step 2] Animating Video...")
        data = request.json
        image_data = data.get('image') # Base64 Image
        location_key = data.get('location_key')

        if not image_data: 
            return jsonify({'error': 'No image provided'}), 400
        
        # Clean Base64 header
        if "," in image_data: 
            image_data = image_data.split(",")[1]
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
                except Exception as e: # ✅ เลื่อน except ออกมาให้ตรงกับ try:
                    print(f"⚠️ Read File Error: {e} -> Sending Remote URL instead")
            else:
                print("⚠️ Save failed or File not found -> Sending Remote URL directly")

            # 4. ส่งผลลัพธ์กลับ Frontend
            return jsonify({
                'status': 'success',
                'video': final_video_src
            })
        else:
            return jsonify({'error': 'Video generation failed (Runway returned None)'}), 500

    except Exception as e: # บล็อกนี้คุมทั้ง Route
        print(f"❌ Critical Animate Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/videos/<path:filename>')
def serve_video(filename):
    return send_from_directory(VIDEO_FOLDER, filename)

if __name__ == '__main__':
    app.run(debug=True, port=5000)