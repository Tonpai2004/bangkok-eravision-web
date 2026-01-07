from flask import Flask, request, jsonify
import os
import base64
import time
import random
import pickle
import numpy as np
from scipy.spatial.distance import cdist
from sentence_transformers import SentenceTransformer
from PIL import Image
import io
from dotenv import load_dotenv
from google import genai
from google.genai import types
from flask_cors import CORS

# --- 1. Setup ---
load_dotenv()
app = Flask(__name__)
CORS(app)

# ==========================================
# 🧠 AI MEMORY LOADING (Smart Match System)
# ==========================================
print("⏳ Initializing System...")
SEARCH_MODEL = None
IMAGE_DB = None

try:
    print("🧠 Loading AI Memory (bangkok_vectors.pkl)...")
    with open('bangkok_vectors.pkl', 'rb') as f:
        IMAGE_DB = pickle.load(f)
    
    print("👁️  Loading CLIP Vision Model...")
    SEARCH_MODEL = SentenceTransformer('clip-ViT-B-32')
    print("✅ AI System Ready: Smart Match Enabled!")
    
except Exception as e:
    print(f"⚠️ Warning: Smart Match System Failed to load. ({e})")
    print("   -> System will fall back to random reference selection.")
    IMAGE_DB = None
    SEARCH_MODEL = None

# ==========================================
# 📍 MAPPINGS & CONFIGURATION
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

# 1. Mapping ชื่อไทย -> ชื่อโฟลเดอร์จริงใน backend/reference_images
LOCATION_FOLDER_MAP = {
    "อนุสาวรีย์ประชาธิปไตย": "Democracy Monument",
    "ศาลาเฉลิมกรุง": "Sala Chalermkrung Royal Theatre",
    "เสาชิงช้า & วัดสุทัศน์": "Giant Swing – Wat Suthat",
    "เยาวราช": "Yaowarat (Chinatown)",
    # "ถนนข้าวสาร": ไม่มีโฟลเดอร์ (ใช้ Prompt ล้วน)
    "ป้อมพระสุเมรุ": "Phra Sumen Fort – Santichaiprakarn Park",
    "สนามหลวง": "Sanam Luang (Royal Field)",
    "พิพิธภัณฑสถานแห่งชาติ": "Phra Nakhon National Museum"
}

# 2. Mapping ชื่อไทย -> Key ในไฟล์ bangkok_vectors.pkl
LOCATION_DB_KEYS = LOCATION_FOLDER_MAP.copy() 

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

# --- THE MASTER PROMPT DATABASE (High-Fidelity Historical Accuracy) ---
# Prompt ชุดนี้รวมความละเอียดที่คุณต้องการ + ข้อมูลประวัติศาสตร์จริง + คำสั่ง ML
LOCATION_PROMPTS = {
    "Democracy Monument": """
          **TASK:** Photorealistic Reconstruction of 1960s Democracy Monument.
          **STRUCTURAL LOCK:** Maintain the original perspective and monument geometry 100%.

          **VISUAL ELEMENTS (HISTORICAL ACCURACY):**
          - **Main Concrete Structure:** The four wing structures and the central turret column are **Matte Cement / Off-White Cream color**. **DO NOT** make the concrete wings look black, smoked, or dirty.
          - **The Pedestal Tray (Phan):** **ONLY** the central tray carrying the constitution at the very top is **Dark Black Oxidized Metal / Bronze**.
          - **The Doors:** The specific doors at the base of the central turret are **Red Ochre / Deep Red**.
          - **Sculptures:** The bas-relief sculptures at the base of the wings are **Cement Color** (same as the wings).
          - **Surroundings:** Flanking buildings along Ratchadamnoen Avenue are **Terracotta Brick Orange / Burnt Orange**.
          - **Street:** Wide asphalt, coarse texture. **NO traffic lines**. 
          - **Vehicles:** **White 'Nai Lert' Buses** (Rounded body). Vintage cars.
          - **Atmosphere:** Bright daylight, clear visibility, historical film grain.
      """,

    "Sala Chalermkrung": """
        **TASK:** Create a photorealistic color photograph of Sala Chalermkrung Theatre in Bangkok, circa 1967.
        
        **STRUCTURE LOCK (EXTREME PRIORITY):** - **THE ROOF SIGN:** The wire-frame metal structure reading "ศาลาเฉลิมกรุง" MUST remain 100% IDENTICAL to the input. DO NOT change, warp, or translate the text.
        - **THEATER SHAPE:** Keep the original architectural form of the theater (Art Deco style).

        **ISOLATION INSTRUCTION (CRITICAL):**
        - **REMOVE SIDE BUILDINGS:** Any buildings visible to the immediate left or right of the theater must be removed, lowered significantly, or blurred out. The theater must be the undisputed dominant structure.
        - **CLEAR SKY:** Remove all utility poles, electrical wires, and cables crossing the sky.
        - **NO TALL NEIGHBORS:** Do not allow any modern skyscrapers or tall structures to peek from behind.

        **THE MOVIE POSTER INJECTION (MANDATORY):**
        - **Action:** Overlay a massive, hand-painted oil cut-out billboard on the front facade (covering the entrance area).
        - **Poster Content:** A Thai movie titled "**บางกอกทวิกาล**" (Bangkok EraVision).
        - **Visuals on Poster:**
            1. Actor 1: A **MUSCULAR, bulky man** in a suit wearing **GLASSES** (M.R. Mod-Or-Por style).
            2. Actor 2: A **SLIM, handsome man** in a suit with **Middle-part hair** (Nattapat style).
            3. Director credit: "Tor-Tum".
        - **Style:** 1960s Thai Cinema Art, vivid colors, dramatic brush strokes.

        **1960s STREET LEVEL:**
        - **Building Surface:** Weathered Creamy White concrete walls with rain stains.
        - **Traffic:** Asphalt road. **NO TRAMS. NO TRAM TRACKS.** Only a few Vintage Taxis (Fiat/Austin) parked or slowly driving.
        - **Crowd:** Teenagers in 60s fashion (Elvis hair, high buns) walking on the pavement.
        
        **NEGATIVE PROMPT:** LED displays, Modern glass doors, BTS, Modern cars, **Tram, Tram tracks, electrical wires, utility poles, dense trees, tall prominent surrounding buildings**.
    """,

    "Giant Swing": """
        **TASK:** Photorealistic Reconstruction of The Giant Swing (1965).
        **STRUCTURAL LOCK:** Keep the exact perspective.

        **VISUAL ELEMENTS (HISTORICAL ACCURACY):**
        - **The Swing Structure:** - **Vibrant Red Teak Logs**. 
            - **CRITICAL:** The swing sits on a **Raised Stone Plinth/Base**. 
            - **CRITICAL:** **NO VEHICLES driving underneath the swing**. Traffic goes AROUND the base.
        - **Traffic:** - **REMOVE TRAMS**. No trams visible in this scene. 
            - Few vintage cars driving around the perimeter.
        - **Context:** - Wat Suthat in the background must look **aged, weathered, and historically accurate** (not pristine/renovated).
            - Surrounding area is residential wooden houses, unpaved or rough asphalt roads.
        - **Community:** The surrounding shop houses must be strictly **1960s Bangkok Style** (Sino-Portuguese shophouses mixed with wooden row houses). 
    """,

    "Yaowarat": """
        **TASK:** Photorealistic Reconstruction of Yaowarat Road (1968).
        **CONTEXT:** Chinatown.

        **VISUAL ELEMENTS (HISTORICAL ACCURACY):**
        - **TRAM SYSTEM:** - **Position:** The Tram MUST run **CLOSE TO THE SIDEWALK/CURB**, NOT in the middle of the road.
            - **Type:** Open-sided 1960s Bangkok Tram (Yellow/Red).
        
        **SIGNAGE & ATMOSPHERE (STRICT):**
        - **Sign Style:** **Hand-painted wooden or metal signs**. Cloth banners hanging vertically.
        - **Lighting:** **NO NEON GLOW.** NO LED. Muted colors (Red, Gold, Black).
        - **Density:** Signs should not be overly dense or cluttered like modern times.
        - **TEXT RULE:** All visible text must be **THAI SCRIPT** (ภาษาไทย) or Chinese characters. NO English.
        
        **ARCHITECTURE:**
        - Old Sino-Thai shophouses. 2-3 stories high. 
        - Weathered concrete.
        - **Traffic:** Vintage trucks, rickshaws.
    """,

    "Khaosan Road": """
        **TASK:** Photorealistic Reconstruction of Bang Lamphu / Khaosan Road (1962).
        **CONTEXT:** A quiet **Rice Trading Residential Community**. NOT a tourist street.
        **NEGATIVE PROMPT:** Tourist, Backpacker, Bar, Club, Beer, English Sign, Neon, Party.

        **VISUAL ELEMENTS (HISTORICAL ACCURACY):**
        - **Architecture:** **Wooden Row Houses** (2 stories) mixed with concrete shophouses.
        - **Storefronts:** **"Baan Fiam"** (Accordion wooden plank doors).
        - **Props:** Piles of **Hemp Rice Sacks** stacked in front. White rice dust on the ground. Large glass jars with biscuits.
        - **Signage:** Simple wooden signs in **THAI LANGUAGE** (e.g., "หจก. ข้าวสาร"). NO English bars/hostel signs.
        - **Activity:** Children playing with bicycle tires. Quiet, domestic vibe. Old men sitting.
    """,

    "Phra Sumen Fort": """
        **TASK:** Photorealistic Reconstruction of Phra Sumen Fort (1960).
        **CRITICAL:** **NO MODERN PARK. NO LAWN.**

        **THE FORT CONDITION:**
        - **Texture:** The white plaster must look **aged, stained with black mold, and green moss**.
        - **Structure:** The top battlements may look slightly crumbled or imperfect (not pristine renovation).

        **SURROUNDINGS (CRITICAL REPLACEMENT):**
        - **IF GRASS IS DETECTED:** Replace all green manicured lawns/parks with **DIRT GROUND** or **CANAL WATER**.
        - **Road side:** Rough asphalt/dirt road.
        - **Community:** Ramshackle wooden houses and community dwellings are built TIGHTLY against the fort walls. Lived-in but not completely slum-like.
        - **River side:** Muddy banks, traditional boats.
    """,

    "Sanam Luang": """
        **TASK:** Photorealistic Reconstruction of Sanam Luang (Weekend Market 1968).

        **VISUAL ELEMENTS (HISTORICAL ACCURACY):**
        - **Market Layout:** Stalls are **spaced out**, not jammed together. 
        - **Stall Type:** Simple canvas parasols (Red/White/Blue) and wooden tables.
        - **Merchandise:** Old books, amulets, sugarcane juice, traditional food.
        - **The Sky:** A **FEW** Thai Kites (Snake, Chula, Pakpao) flying (do not fill the whole sky).
        - **Backdrop (Grand Palace):** The walls must look aged (Off-white/Yellowish), gold spires slightly dulled by time. **NO SCAFFOLDING.**
        - **Ground:** **Red Dirt (Sanarm Chai)** mixed with dry patchy grass. Uneven surface.
    """,

    "National Museum": """
        **TASK:** Photorealistic Reconstruction of National Museum Bangkok (1960).

        **VISUAL ELEMENTS (HISTORICAL ACCURACY):**
        - **Viewpoint:** Focus on the **Front Facade** and the immediate courtyard.
        - **Building Condition:** Dignified but aged. 
            - Walls: Off-white with natural weathering/rain stains (not dirty, just old).
            - Roof: Darkened tiles.
        - **Context:** Large trees providing shade (Temple in forest vibe).
        - **Ground:** Gravel paths, well-swept but unpaved.
        - **Fence:** Black iron spearhead fence (slightly rusted).
        - **Atmosphere:** Quiet, scholarly, ancient.
    """
}

# ==========================================
# 🛠️ HELPER FUNCTIONS
# ==========================================

def get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: raise ValueError("GEMINI_API_KEY not found")
    return genai.Client(api_key=api_key)

# --- ฟังก์ชัน ML: หาภาพที่เหมือนที่สุด (Smart Match) ---
def get_best_match_reference(location_th, user_img_bytes):
    # กรณี: ถนนข้าวสาร (ไม่มีโฟลเดอร์) -> คืนค่า None ทันที
    if location_th == "ถนนข้าวสาร":
        print(f"🌾 Khaosan Road selected: Using Prompt Only (No reference image).")
        return None

    folder_name = LOCATION_FOLDER_MAP.get(location_th)
    if not folder_name: return None # กันเหนียว

    # 1. ถ้าโหลด AI ไม่สำเร็จ ให้ใช้วิธีสุ่ม (Fallback)
    if not IMAGE_DB or not SEARCH_MODEL:
        print("⚠️ AI Memory not ready. Using Random Selection.")
        return get_random_reference(folder_name)

    # 2. เช็คว่ามี Key สถานที่นี้ใน Database ไหม
    db_key = LOCATION_DB_KEYS.get(location_th)
    if not db_key or db_key not in IMAGE_DB:
        print(f"⚠️ No AI data for {location_th}. Using Random Selection.")
        return get_random_reference(folder_name)
    
    # 3. เริ่มกระบวนการ ML Matching
    try:
        data = IMAGE_DB[db_key] # ข้อมูล vectors ของสถานที่นั้น
        
        # แปลงรูป User เป็น Vector
        user_img = Image.open(io.BytesIO(user_img_bytes))
        user_vector = SEARCH_MODEL.encode(user_img)
        
        # คำนวณความเหมือน (Cosine Distance) กับทุกรูปในโฟลเดอร์
        distances = cdist([user_vector], data['vectors'], metric='cosine')[0]
        
        # เลือกรูปที่ระยะห่างน้อยที่สุด (เหมือนสุด)
        best_idx = np.argmin(distances)
        best_filename = data['filenames'][best_idx]
        
        print(f"🎯 Smart Match! User Image matches with -> {best_filename}")
        
        # อ่านไฟล์รูปนั้น
        file_path = os.path.join(os.path.dirname(__file__), "reference_images", folder_name, best_filename)
        with open(file_path, "rb") as f:
            return f.read()
            
    except Exception as e:
        print(f"❌ Smart Match Error: {e}. Fallback to random.")
        return get_random_reference(folder_name)

# ฟังก์ชันสุ่ม (ใช้กรณี ML พัง หรือยังไม่ได้ทำ Index)
def get_random_reference(folder_name):
    base_path = os.path.join(os.path.dirname(__file__), "reference_images", folder_name)
    if not os.path.exists(base_path): return None
    
    images = []
    for ext in ['*.jpg', '*.jpeg', '*.png']:
        import glob
        images.extend(glob.glob(os.path.join(base_path, ext)))
        
    if not images: return None
    selected = random.choice(images)
    print(f"🎲 Random Reference selected: {os.path.basename(selected)}")
    with open(selected, "rb") as f:
        return f.read()

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
    
    style_instruction = ""
    parts = []
    
    # ถ้ามีรูป Ref (จาก ML หรือสุ่ม)
    if ref_img_bytes:
        style_instruction = """
        **STYLE TRANSFER INSTRUCTION (IP-ADAPTER MODE):**
        - The second image provided is the **STYLE REFERENCE** (Ground Truth from 1960s).
        - **COPY the color palette, film grain, lighting, and mood** from the Reference Image and apply it to the Input Image.
        - **CRITICAL:** Use the Reference Image mainly for COLOR and ATMOSPHERE. Use the Prompt for STRUCTURAL details (e.g. posters, signs).
        """
        parts = [
            f"{specific_prompt}\n{style_instruction}\n**GEOMETRY CONSTRAINT:**\nReference Analysis: {structure_desc}",
            types.Part.from_bytes(data=original_img_bytes, mime_type="image/jpeg"),
            types.Part.from_bytes(data=ref_img_bytes, mime_type="image/jpeg") # รูป Ref ส่งไปให้ Gemini ดู
        ]
    else:
        # ถ้าไม่มี (เช่น ข้าวสาร)
        parts = [
            f"{specific_prompt}\n**GEOMETRY CONSTRAINT:**\nReference Analysis: {structure_desc}",
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

@app.route('/generate', methods=['POST'])
def generate_image_route():
    try:
        print("🚀 Starting Generation Process...")
        file = request.files['image']
        location_th = request.form['location']
        img_bytes = file.read()
        
        # 1. หา Best Reference ด้วย ML
        print(f"🔍 Searching for best reference for: {location_th}")
        ref_bytes = get_best_match_reference(location_th, img_bytes)
        
        client = get_client()
        
        # 2. Analyze
        print(f"📸 1. Analyzing Structure...")
        structure = step1_analyze(client, img_bytes)
        
        # 3. Generate
        print(f"🎨 2. Generating Image...")
        prompt_key = LOCATION_INFO.get(location_th, {}).get('prompt_key', "Democracy Monument")
        result_bytes = step2_generate(client, structure, prompt_key, img_bytes, ref_bytes)
        
        if result_bytes:
            print("🎉 Success!")
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

@app.route('/verify', methods=['POST'])
def verify_image_route():
    # Bypass Logic (100% Pass)
    try:
        location_th = request.form['location']
        print(f"🚧 Verify Bypass: {location_th}")
        return jsonify({
            'status': 'success',
            'analysis_report': {
                "status": "success",
                "detected_place": LOCATION_MAPPING_TH_TO_EN.get(location_th, "Debug Place"),
                "score": 99.9,
                "is_valid": True
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/')
def home():
    return "✅ Bangkok EraVision Backend (Smart Match Enabled) is Running!"

if __name__ == '__main__':
    app.run(debug=True, port=5000)