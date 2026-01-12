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

# --- THE MASTER PROMPT DATABASE (V.10 - FINE-TUNED REALISM & SPECIFIC FIXES) ---
LOCATION_PROMPTS = {
    "Democracy Monument": """
          **TASK:** Create a **HYPER-REALISTIC** photograph of Democracy Monument (Bangkok 1960s).
          **STRUCTURAL LOCK:** Maintain perspective. Concrete wings with concave curves and bas-reliefs. Dark bronze central tray.

          **FINE DETAILS FOR REALISM:**
          - **Weathering:** The cream concrete must show realistic signs of age: subtle rain streaks, slight discoloration in crevices. It is not pristine new paint.
          - **The Base:** The circular concrete steps are **COMPLETELY BARE and CLEAN**. NO grass, NO weeds, NO flowers.
          - **Atmosphere:** Bright tropical sun creating sharp shadows. A slight heat haze in the distance.

          **SURROUNDINGS:**
          - **Buildings:** Aged Terracotta/Brick Orange Ratchadamnoen buildings.
          - **Road & Traffic:** Wide Asphalt. Sparse vintage cars (e.g., Morris Minor, Datsun Bluebird) and public buses.
      """,

    "Sala Chalermkrung": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Sala Chalermkrung Theatre (1967).
        **ABSOLUTE STRUCTURE LOCK:** Keep building shape and "ศาลาเฉลิมกรุง" roof sign identical. Poster: "**บางกอกทวิกาล**".

        **CONTEXT REFINEMENT (WIDE ROAD & REDUCED SURROUNDINGS):**
        - **Street:** The asphalt road in front must appear **VERY WIDE and SPACIOUS**.
        - **Surroundings:** The shophouses on the far left and right should appear **receding and less prominent**, emphasizing the width of the avenue and the theatre itself. They are low-rise 1960s style.
        - **Traffic & Life:** Light vintage traffic, pedestrians on wide sidewalks. No Trams.
    """,

    "Giant Swing": """
        **TASK:** Create a **SHARP, PHOTOREALISTIC COLOR PHOTOGRAPH** of The Giant Swing (1965).
        **STRUCTURAL LOCK:** Red Teak Pillars on White Stone Plinth.

        **SURROUNDING REALISM (LIVED-IN, NOT RUINED):**
        - **Wat Suthat & Shophouses:** The surrounding Sino-Portuguese shophouses and temple walls must look **realistically aged and lived-in**. The stucco paint is faded but intact; roof tiles are weathered. They are **NOT dilapidated or ruined**, just historically accurate for a bustling 1960s district.
        - **Ground:** Clean paved asphalt.
        - **Traffic:** Light vintage traffic driving AROUND the plinth.
    """,

    "Yaowarat": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Yaowarat Road (1968).
        
        **SPECIFIC TEXT & SIGNAGE FIX:**
        - **No Glowing Signs:** All signs are painted wood or metal. **ABSOLUTELY NO NEON GLOW or internal lighting** (it is daytime).
        - **Legible Text:** Signs must have clear, hand-painted Chinese and Thai characters.
        - **Mandatory Sign Examples (Use these styles):** "ห้างทอง ฮั่วเซ่งเฮง (和成興大金行)", "ภัตตาคาร หูฉลาม", "ขายยาจีน".

        **TRAM & ATMOSPHERE:**
        - **The Tram:** A single vintage Yellow & Red wooden tram, looking **weathered and used**, running on rails **hugging the RIGHT-HAND curb** of the road.
        - **Street:** Wide asphalt. Sparse Samlors and trucks. Warm sunlight.
    """,

    "Khaosan Road": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Bang Lamphu / Khaosan Road (1962).
        
        **VIBRANT COMMUNITY LIFE:**
        - **People:** The scene is alive with **local residents** sitting on stools chatting in front of houses, children playing on the street, vendors with carrying poles.
        - **Rice Trade:** **White Hemp Rice Sacks** are visible stacked at only **2 or 3 specific houses**, NOT everywhere.
        
        **VISUALS:**
        - **House Facades:** Wooden row houses. **CRITICAL: NO COMMERCIAL SIGNS or text on the house fronts.** They are residential.
        - **Street:** Wide, clean asphalt road.
    """,

    "Phra Sumen Fort": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Phra Sumen Fort (1960).
        
        **CRITICAL HISTORICAL ACCURACY: COMPLETELY HEADLESS:**
        - **Status:** The main white octagonal fort tower is **SEVERED**. The entire upper wooden roof structure and spire are **COMPLETELY MISSING**. The top is a flat, broken, weathered stump exposing the thick walls.
        - **Condition:** Aged, mold-stained white plaster.
        
        **SURROUNDINGS:**
        - Street level view. Wooden houses nearby. Asphalt/dirt road. Very light traffic.
    """,

    "Sanam Luang": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of Sanam Luang (Weekend Market 1968).
        
        **MARKET REALISM (ORAL HISTORY BASED):**
        - **Ground & Stalls:** The ground is dusty red laterite. Vendors sit on woven mats under simple bamboo-pole canvas parasols (not modern tents). Goods are laid out on the ground.
        - **Atmosphere:** Bustling with ordinary people in 60s clothing walking and browsing.
        - **Kites:** Only **A VERY FEW SCATTERED** traditional Thai kites in the pale sky.
    """,

    "National Museum": """
        **TASK:** Create a **PHOTOREALISTIC COLOR PHOTOGRAPH** of the **FRONT** of National Museum Bangkok (1960).
        
        **FRONT ATMOSPHERE: PEACEFUL & DIGNIFIED:**
        - **Vibe:** Serene, scholarly, and very shady.
        - **Front Grounds:** Focus on the area inside the main gate. It is **well-maintained**. Swept gravel driveways, manicured grass verges (not overgrown), and large mature trees casting deep shade. It looks dignified, not abandoned.
        - **Building:** The traditional Thai facade is aged but clean.
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
    - **GLOBAL NEGATIVE PROMPT:** post-1970 elements, modern cars (sedans post-1970), motorcycles, modern streetlights, LED signs, satellite dishes, air conditioning units, modern clothing (jeans, t-shirts with logos), skyscrapers, concrete barriers.
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