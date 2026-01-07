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
# 📍 MAPPINGS
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

# --- THE MASTER PROMPT DATABASE (ULTIMATE FIX VERSION) ---
LOCATION_PROMPTS = {
    # 1. อนุสาวรีย์ฯ: แก้สีพานดำ, เพิ่มรายละเอียดตึกและรถ
    "Democracy Monument": """
          **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of the 1960s Democracy Monument.
          **STRUCTURAL LOCK:** Maintain original perspective and geometry 100%. Aspect Ratio must match input.

          **COLOR & MATERIAL SPECIFICATION (STRICT):**
          - **The Phan (Constitution Tray at the very top):** MUST be **DARK BLACK / BRONZE METAL**. This is the ONLY black element on the monument.
          - **Main Wings & Central Turret:** **Matte, weathered concrete (Off-white/Cream/Light Grey)** with rain stains. NOT BLACK.
          - **Doors:** **Deep Red Ochre**.

          **SURROUNDING CONTEXT (1960s):**
          - **Flanking Buildings:** The Ratchadamnoen Avenue buildings must be visible, colored in **Terracotta/Burnt Orange**, with 1960s shop signs (Thai script).
          - **Street:** Wide asphalt, **NO traffic lines**.
          - **Vehicles:** **White 'Nai Lert' Buses** (rounded body), vintage cars (Austin, Fiat), samlors.
          - **Atmosphere:** Bright daylight, natural color film grain (Kodachrome).
      """,

    # 2. ศาลาเฉลิมกรุง: เติมตึกข้างๆ คืนมาแบบย้อนยุค, ไม่ให้โล่ง
    "Sala Chalermkrung": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Sala Chalermkrung Theatre, 1967.
        **STRUCTURE LOCK:** - **ROOF SIGN:** The "ศาลาเฉลิมกรุง" wire-frame sign MUST remain 100% IDENTICAL.
        - **THEATER SHAPE:** Keep the Art Deco architecture.

        **SURROUNDING RECONSTRUCTION (CRITICAL):**
        - **DO NOT** make the surroundings empty space.
        - **RESTORE ADJACENT BUILDINGS:** To the immediate left and right, reconstruct **1960s-style shophouses** (2-3 stories, weathered concrete, wooden shutters) that physically connect to or flank the theater. They should look lived-in, not like modern voids.
        - **CLEAR SKY:** Remove modern utility poles/wires, but keep the vintage buildings.

        **THE MOVIE POSTER INJECTION:**
        - **Action:** Overlay a massive, hand-painted oil cut-out billboard titled "**บางกอกทวิกาล**".
        - **Visuals:** Muscular man in suit with glasses + Slim man with middle-part hair.
        
        **STREET LEVEL:**
        - **Road:** Asphalt. **NO TRAMS/TRACKS.** Vintage Taxis, 60s pedestrians.
    """,

    # 3. เสาชิงช้า: เน้นภาพคมชัด, วัดสุทัศน์สมจริง
    "Giant Swing": """
        **TASK:** Create a **SHARP, PHOTOREALISTIC COLOR PHOTOGRAPH** of The Giant Swing (1965).
        **STRUCTURAL LOCK:** Keep exact perspective. Ensure sharp focus on the swing and Wat Suthat.

        **VISUAL ELEMENTS:**
        - **Swing:** Vibrant Red Teak Logs on a **Raised Stone Plinth**.
        - **Traffic Rule:** Traffic goes AROUND the plinth. **NO vehicles under the swing.** NO TRAMS.
        - **Wat Suthat (Background):** Must look sharp, aged, and historically accurate with weathered roofs and walls.
        **SURROUNDING COMMUNITY:**
        - **Architecture:** 1960s Bangkok Style shophouses (Sino-Portuguese/wooden). Weathered, lived-in.
        - **Road:** Rough asphalt/paved stone, dusty.
    """,

    # 4. เยาวราช: ลดความรกของป้าย, เน้นบรรยากาศโปร่ง
    "Yaowarat": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Yaowarat Road (1968).
        
        **ATMOSPHERE & SIGNAGE (CRITICAL REDUCTION):**
        - **REDUCE SIGN DENSITY:** The street should look **less cluttered** than modern times. There are fewer signs, making the street feel wider and more open.
        - **Sign Style:** **Hand-painted wooden/metal signs** and vertical cloth banners. **NO NEON GLOW.** NO LED.
        - **Text:** THAI SCRIPT or Chinese characters only.

        **VISUAL ELEMENTS:**
        - **TRAM SYSTEM:** Open-sided Tram running **CLOSE TO THE SIDEWALK**, NOT in the middle.
        - **ARCHITECTURE:** Old Sino-Thai shophouses. Weathered concrete.
        - **Traffic:** Vintage trucks, rickshaws.
        - **Color Grade:** Warm, golden hour light, rich film colors.
    """,

    # 5. ข้าวสาร: ยืนยันความเงียบสงบ (Prompt เดิมดีอยู่แล้ว)
    "Khaosan Road": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Bang Lamphu / Khaosan Road (1962).
        **CONTEXT:** A quiet **Rice Trading Residential Community**. NOT a tourist street.
        **NEGATIVE PROMPT:** Tourist, Backpacker, Bar, Club, Beer, English Sign, Neon, Party.

        **VISUAL ELEMENTS:**
        - **Architecture:** **Wooden Row Houses** (2 stories) with "Baan Fiam" doors. 
        - **Trade:** Piles of **Hemp Rice Sacks** stacked in front. White rice dust on the ground. 
        - **Signs:** Simple wooden signs in **THAI LANGUAGE** (e.g., "หจก. ข้าวสาร").
        - **Activity:** Children playing. Quiet, domestic vibe. Old men sitting.
    """,

    # 6. ป้อมพระสุเมรุ: บ้านเรือนไม่ติดป้อมเกินไป, หัวป้อมทรุดโทรม
    "Phra Sumen Fort": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Phra Sumen Fort (1960).
        **CRITICAL:** **NO MODERN PARK. NO LAWN.**

        **THE FORT CONDITION:**
        - **Texture:** Aged white plaster, heavily stained with black mold and green moss.
        - **Top Structure:** The battlements and the roof spire must look **slightly crumbled, weathered, or imperfect**, showing age and lack of modern restoration.

        **SURROUNDINGS (SETBACK & REPLACEMENT):**
        - **IF GRASS IS DETECTED:** Replace with **DIRT GROUND** or **CANAL WATER**.
        - **Community Setback:** Ramshackle wooden houses are present but maintain a **small dirt path or gap** from the fort wall, not physically fused to it.
        - **River side:** Muddy banks, traditional boats.
    """,

    # 7. สนามหลวง: เน้นสีสันตลาด, ว่าวน้อย (Prompt เดิมดี)
    "Sanam Luang": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Sanam Luang (Weekend Market 1968).
        **VISUAL ELEMENTS:**
        - **Market Layout:** Stalls are **spaced out**. Colorful canvas parasols (Red/White/Blue).
        - **The Sky:** A **FEW** Thai Kites flying.
        - **Backdrop (Grand Palace):** Aged walls, dulled gold spires. **NO SCAFFOLDING.**
        - **Ground:** Red dirt (Sanarm Chai) mixed with dry grass.
    """,

    # 8. พิพิธภัณฑ์: เน้นความสมจริงของอาคารเก่า (Prompt เดิมดี)
    "National Museum": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of National Museum Bangkok (1960).
        **VISUAL ELEMENTS:**
        - **Viewpoint:** Focus on the **Front Facade**.
        - **Building Condition:** Dignified but aged. Off-white walls with natural weathering/rain stains. Darkened tiles.
        - **Context:** Large trees providing shade.
        - **Ground:** Gravel paths, well-swept but unpaved.
        - **Fence:** Black iron spearhead fence (slightly rusted).
    """
}

# ==========================================
# 🛠️ HELPER FUNCTIONS
# ==========================================

def get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: raise ValueError("GEMINI_API_KEY not found")
    return genai.Client(api_key=api_key)

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
    
    # เพิ่มคำสั่งบังคับสีและสไตล์รวมในทุก request
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
                # บังคับให้ API พยายามรักษา aspect ratio ของภาพต้นฉบับ (แม้จะคุมไม่ได้ 100% แต่ช่วยได้)
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
    return "✅ Bangkok EraVision Backend (Ultimate Fix Version) is Running!"

if __name__ == '__main__':
    app.run(debug=True, port=5000)