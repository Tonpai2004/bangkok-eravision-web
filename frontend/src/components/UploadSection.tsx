'use client';
import { useState, useRef, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import AssessmentModal from './AssessmentModal';

const LOCATIONS_DATA = [
  { id: "อนุสาวรีย์ประชาธิปไตย", th: "อนุสาวรีย์ประชาธิปไตย", en: "Democracy Monument" },
  { id: "ศาลาเฉลิมกรุง", th: "ศาลาเฉลิมกรุง", en: "Sala Chalermkrung" },
  { id: "เสาชิงช้า & วัดสุทัศน์", th: "เสาชิงช้า & วัดสุทัศน์", en: "Giant Swing & Wat Suthat" },
  { id: "เยาวราช", th: "เยาวราช", en: "Yaowarat (Chinatown)" },
  { id: "ถนนข้าวสาร", th: "ถนนข้าวสาร", en: "Khaosan Road" },
  { id: "ป้อมพระสุเมรุ", th: "ป้อมพระสุเมรุ", en: "Phra Sumen Fort" },
  { id: "สนามหลวง", th: "สนามหลวง", en: "Sanam Luang" },
  { id: "พิพิธภัณฑสถานแห่งชาติ", th: "พิพิธภัณฑสถานแห่งชาติ", en: "Bangkok National Museum" }
];

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:5000';

// ฟังก์ชันแปลง Error ภาษาต่างดาว ให้เป็นภาษาคน (ไทย/อังกฤษ)
const getFriendlyErrorMessage = (rawError: string, lang: 'TH' | 'ENG'): string => {
  if (lang === 'ENG') return rawError; // ถ้าโหมดอังกฤษ ให้ส่งค่าเดิมกลับไป

  const err = rawError.toLowerCase();

  // --- 1. Network / Server Connection ---
  if (err.includes("failed to fetch") || err.includes("network error")) {
    return "ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ได้\n(กรุณาเช็คอินเทอร์เน็ต หรือ Server อาจจะปิดอยู่)";
  }
  if (err.includes("timeout") || err.includes("timed out")) {
    return "การเชื่อมต่อหมดเวลา (Server ตอบสนองช้ากว่าปกติ)\nกรุณาลองใหม่อีกครั้ง";
  }

  // --- 2. AI Model Errors (Gemini / Runway) ---
  if (err.includes("503") || err.includes("overloaded") || err.includes("busy") || err.includes("capacity")) {
    return "ขณะนี้ AI กำลังทำงานหนักมาก (Server Busy)\nกรุณารอสักครู่ แล้วกด 'ลองใหม่อีกครั้ง'";
  }
  if (err.includes("429") || err.includes("quota") || err.includes("resource exhausted")) {
    return "โควต้าการใช้งาน AI เต็มชั่วคราว\nกรุณารอประมาณ 1-2 นาที แล้วลองใหม่";
  }
  if (err.includes("safety") || err.includes("blocked") || err.includes("harmful")) {
    return "รูปภาพถูกระงับโดยระบบความปลอดภัยของ AI\n(อาจมีเนื้อหาที่ AI มองว่าไม่เหมาะสม หรือมีความเสี่ยง)";
  }
  if (err.includes("model returned no image") || err.includes("none is not iterable")) {
    return "AI ไม่สามารถสร้างภาพได้ในขณะนี้\n(อาจเกิดจาก Server รวน หรือรูปต้นฉบับซับซ้อนเกินไป)";
  }

  // --- 3. Data / Parsing Errors ---
  if (err.includes("json") || err.includes("unexpected token") || err.includes("syntaxerror")) {
    return "เกิดข้อผิดพลาดในการรับ-ส่งข้อมูล (JSON Error)\nกรุณาลองใหม่อีกครั้ง";
  }
  if (err.includes("no image provided") || err.includes("file")) {
    return "ไม่พบไฟล์รูปภาพ หรือไฟล์เสียหาย";
  }

  // --- 4. Fallback (ถ้าไม่เข้าเคสไหนเลย) ---
  return `เกิดข้อผิดพลาด: ${rawError}`;
};

const UI_TEXT = {
  TH: {
    label_location: "เลือกสถานที่",
    label_upload: "อัปโหลดรูปถ่ายของคุณ",
    dropzone_text: "คลิก หรือ ลากรูปมาวางที่นี่",
    btn_main: "หวนคืนสู่ทศวรรษที่ 1960s",
    btn_try_again: "ลองรูปอื่น",
    btn_retry: "ลองใหม่อีกครั้ง",
    btn_download: "ดาวน์โหลดผลลัพธ์",
    
    status_analyzing: "กำลังวิเคราะห์โครงสร้าง...",
    sub_analyzing: "ตรวจสอบความถูกต้องของรูปภาพ", // เพิ่ม text ที่ขาด
    status_verify_pass: "ผ่านการตรวจสอบ",
    status_verify_fail: "การตรวจสอบไม่ผ่าน",
    status_tech_error: "เกิดข้อผิดพลาดทางเทคนิค",
    
    status_reconstructing: "เตรียมหวนสู่ความวิจิตรในวันวานแห่ง 1960s",
    sub_reconstructing: "กำลังสร้างภาพจำลอง (AI)...",
    
    status_animating: "กำลังทำให้ภาพดูมีชีวิตชีวา",
    sub_animating: "กำลังสร้างภาพเคลื่อนไหว...",
    
    error_desc_prefix: "ระบบขัดข้อง: ",
    warning_title: "ข้อมูลไม่ครบถ้วน",
    warning_msg: "กรุณาเลือกสถานที่\nและอัปโหลดรูปภาพก่อนเริ่มดำเนินการ",
    btn_acknowledge: "รับทราบ"
  },
  ENG: {
    label_location: "Choose a location",
    label_upload: "Upload your Photo",
    dropzone_text: "Click or Drag photo here",
    btn_main: "Transform to 1960s",
    btn_try_again: "Try Another Photo",
    btn_retry: "Retry again",
    btn_download: "Download Result",
    
    status_analyzing: "ANALYZING SCENE",
    sub_analyzing: "Verifying photo compatibility...",
    status_verify_pass: "VERIFICATION PASSED",
    status_verify_fail: "VERIFICATION REJECTED",
    status_tech_error: "TECHNICAL ERROR",
    
    status_reconstructing: "Reconstructing the Past",
    sub_reconstructing: "Generating 1960s Image...",

    status_animating: "Bringing Image to Life",
    sub_animating: "Generating Motion Video...",

    error_desc_prefix: "System Failure: ",
    warning_title: "Missing Information",
    warning_msg: "Please select a location\nand upload an image to proceed.",
    btn_acknowledge: "Okay"
  }
};

type ProcessStatus = 'idle' | 'verifying' | 'verified_pass' | 'verified_fail' | 'generating' | 'animating' | 'finished' | 'error';

interface UploadSectionProps {
  currentLang: 'TH' | 'ENG';
}

export default function UploadSection({ currentLang }: UploadSectionProps) {
  const [selectedLocation, setSelectedLocation] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  
  const [status, setStatus] = useState<ProcessStatus>('idle');
  const [failReason, setFailReason] = useState<string>("");
  const [passDetails, setPassDetails] = useState<{score: number, place: string} | null>(null);

  const [result, setResult] = useState<{image: string, video?: string, desc: string, location_key: string, location: string} | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [showInputWarning, setShowInputWarning] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  const text = UI_TEXT[currentLang];
  const fontClass = currentLang === 'ENG' ? 'font-merri' : 'font-krub';
  const searchParams = useSearchParams();
  const [isDropdownOpen, setIsDropdownOpen] = useState(false); 
  const dropdownRef = useRef<HTMLDivElement>(null); 

  const [showAssessment, setShowAssessment] = useState(false);
  const [hasShownAssessment, setHasShownAssessment] = useState(false);

  const triggerAssessment = () => {
    if (!hasShownAssessment) {
        setShowAssessment(true);
        setHasShownAssessment(true);
    }
  };

  useEffect(() => {
      function handleClickOutside(event: MouseEvent) {
          if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
              setIsDropdownOpen(false);
          }
      }
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    const locationParam = searchParams.get('location');
    if (locationParam) {
       const isValidLocation = LOCATIONS_DATA.some(loc => loc.id === locationParam);
       if (isValidLocation) {
         setSelectedLocation(locationParam);
         const element = document.getElementById('upload-section-start');
         if (element) element.scrollIntoView({ behavior: 'smooth' });
       }
    }
  }, [searchParams]);

  // แสดง Modal แบบประเมินผลหลังจากกระบวนการเสร็จสิ้น + หน่วงเวลา //
  useEffect(() => {
    if (status === 'finished' && result && !hasShownAssessment) {
        
        const delay = result.video ? 8000 : 5000; 
        
        const timer = setTimeout(() => {
            console.log(`⏰ Time's up (${delay/1000}s) - Showing Assessment Modal`);
            triggerAssessment();
        }, delay);

        return () => clearTimeout(timer);
    }
  }, [status, result, hasShownAssessment]);
  
  const processFile = (f: File | undefined) => {
    if (f) {
      if (!f.type.startsWith('image/')) {
        alert(currentLang === 'ENG' ? "Please upload an image file." : "กรุณาอัปโหลดไฟล์รูปภาพเท่านั้น");
        return;
      }
      setFile(f);
      setPreview(URL.createObjectURL(f));
      if (status === 'verified_fail' || status === 'finished') {
        setStatus('idle');
        setResult(null);
      }
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault(); setIsDragging(true);
  };
  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault(); setIsDragging(false);
  };
  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault(); setIsDragging(false);
    const f = e.dataTransfer.files?.[0];
    processFile(f);
  };
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) {
      setFile(f);
      setPreview(URL.createObjectURL(f));
      if (status === 'verified_fail' || status === 'finished') {
        setStatus('idle');
        setResult(null);
      }
    }
  };

  // ------------------------------------------------------------------
  // 🚀 MAIN LOGIC: Chain Requests (Verify -> Image -> Video)
  // ------------------------------------------------------------------
const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!file || !selectedLocation) {
        setShowInputWarning(true);
        return;
    }

    // ✅ รีเซ็ตสถานะแบบประเมินก่อนเริ่มใหม่ทุกครั้ง เพื่อให้ Timer เริ่มนับ 1..8 ใหม่
    setHasShownAssessment(false);
    setShowAssessment(false);

    let currentStep: 'verifying' | 'generating' | 'animating' = 'verifying'; 
    setStatus('verifying'); 
    
    const formData = new FormData();
    formData.append('image', file);
    formData.append('location', selectedLocation);
    formData.append('language', currentLang); 

    try {
      // === STEP 1: Verify ===
      const verifyRes = await fetch(`${API_BASE_URL}/verify`, { method: 'POST', body: formData });
      const verifyData = await verifyRes.json();

      if (!verifyRes.ok || verifyData.status === 'rejected') {
        setFailReason(verifyData.details || verifyData.error || "Unknown Error");
        setStatus('verified_fail'); 
        return; 
      }

      setPassDetails({
        score: verifyData.analysis_report?.score || 0,
        place: verifyData.analysis_report?.detected_place || "Confirmed"
      });
      setStatus('verified_pass');

      await new Promise(r => setTimeout(r, 1500));

      // === STEP 2: Generate Image ===
      currentStep = 'generating';
      setStatus('generating');

      const genFormData = new FormData();
      genFormData.append('image', file);
      genFormData.append('location', selectedLocation);

      const genRes = await fetch(`${API_BASE_URL}/generate`, {
        method: 'POST',
        body: genFormData,
    });

      if (!genRes.ok) {
          const errData = await genRes.json().catch(() => ({}));
          if (genRes.status === 503) throw new Error("503 Service Unavailable (Model Busy)");
          throw new Error(errData.error || `Server Error: ${genRes.status}`);
      }

      const genData = await genRes.json();
      if (!genData.image) throw new Error(genData.error || "Image generation failed");

      // === STEP 3: Animate Video (เรียกใช้อัตโนมัติทันทีหลังจากได้รูป) ===
      currentStep = 'animating';
      setStatus('animating'); 

      let finalVideo = null;
      try {
          const animRes = await fetch(`${API_BASE_URL}/animate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ 
                  image: genData.image, 
                  location_key: genData.location_key 
              }),
          });
          const animData = await animRes.json();
          if (animData.video) {
              finalVideo = animData.video;
          } else {
              // 📢 แจ้งเตือนเบาๆ ว่าวิดีโอขัดข้องแต่ดูรูปได้
              console.warn("Video Credit Exhausted or Error:", animData.error);
          }
      } catch (videoErr) {
          console.warn("Video generation failed, but Image is OK.", videoErr);
      }

      // === FINISH: แสดงผลลัพธ์วิดีโอ (หรือรูปภาพถ้าวิดีโอพัง) ===
      setResult({
        image: genData.image,
        video: finalVideo || undefined,
        desc: genData.description,
        location: genData.location_name,
        location_key: genData.location_key
      });
      setStatus('finished');

    } catch (err: any) {
        console.error("Process Error:", err);
        const friendlyMsg = getFriendlyErrorMessage(err.message || "Unknown Error", currentLang);
        setFailReason(friendlyMsg);
        setStatus(currentStep === 'verifying' ? 'verified_fail' : 'error');
    }
  };


  // const handleGenerate = async (e: React.FormEvent) => {
  //   e.preventDefault();
    
  //   // ตรวจสอบข้อมูลก่อนเริ่ม
  //   if (!file || !selectedLocation) {
  //       setShowInputWarning(true);
  //       return;
  //   }

  //   let currentStep: 'verifying' | 'generating' | 'animating' = 'verifying'; 
  //   setStatus('verifying'); 
    
  //   const formData = new FormData();
  //   formData.append('image', file);
  //   formData.append('location', selectedLocation);
  //   formData.append('language', currentLang); 

  //   try {
  //     // === STEP 1: Verify (ตรวจสอบความถูกต้องของรูปถ่าย) ===
  //     const verifyRes = await fetch('http://127.0.0.1:5000/verify', { method: 'POST', body: formData });
  //     const verifyData = await verifyRes.json();

  //     if (!verifyRes.ok || verifyData.status === 'rejected') {
  //       setFailReason(verifyData.details || verifyData.error || "Unknown Error");
  //       setStatus('verified_fail'); 
  //       return; 
  //     }

  //     // แสดงสถานะเมื่อผ่านการตรวจสอบ
  //     setPassDetails({
  //       score: verifyData.analysis_report?.score || 0,
  //       place: verifyData.analysis_report?.detected_place || "Confirmed"
  //     });
  //     setStatus('verified_pass');

  //     // หน่วงเวลาเล็กน้อยเพื่อให้ User เห็นว่าผ่านแล้ว
  //     await new Promise(r => setTimeout(r, 1500));

  //     // === STEP 2: Generate Image (ส่งไปให้ Gemini/Imagen สร้างภาพ 1960s) ===
  //     currentStep = 'generating';
  //     setStatus('generating');

  //     const genFormData = new FormData();
  //     genFormData.append('image', file);
  //     genFormData.append('location', selectedLocation);

  //     const genRes = await fetch('http://127.0.0.1:5000/generate', {
  //         method: 'POST',
  //         body: genFormData,
  //     });

  //     if (!genRes.ok) {
  //         const errData = await genRes.json().catch(() => ({}));
  //         if (genRes.status === 503) throw new Error("503 Service Unavailable (Model Busy)");
  //         throw new Error(errData.error || `Server Error: ${genRes.status}`);
  //     }

  //     const genData = await genRes.json();

  //     if (!genData.image) throw new Error(genData.error || "Image generation failed");

  //     // === FINISH (STOP AT IMAGE) ===
  //     // เราจะไม่เรียกฟังก์ชัน animate อัตโนมัติที่นี่แล้ว เพื่อประหยัด Credit Runway
  //     // แต่จะเก็บข้อมูลใส่ result เพื่อให้ User เลือกกดปุ่มสร้างวิดีโอเองในหน้า Modal
  //     setResult({
  //       image: genData.image,
  //       video: undefined, // ยังไม่มีวิดีโอในตอนนี้
  //       desc: genData.description,
  //       location: genData.location_name,
  //       location_key: genData.location_key // เก็บ key ไว้ใช้เรียก /animate ทีหลัง
  //     });
  //     setStatus('finished');

  //   } catch (err: any) {
  //       console.error("Process Error:", err);
  //       // แปลงข้อความ Error ให้เป็นภาษาที่อ่านง่าย
  //       const friendlyMsg = getFriendlyErrorMessage(err.message || "Unknown Error", currentLang);
  //       setFailReason(friendlyMsg);
        
  //       if (currentStep === 'verifying') {
  //            setStatus('verified_fail'); 
  //       } else {
  //            setStatus('error'); 
  //       }
  //   }
  // };

  // const handleAnimate = async () => {
  //   if (!result?.image || !result?.location_key) return;

  //   setHasShownAssessment(false); 
  //   setShowAssessment(false);

  //   setStatus('animating');
  //   try {
  //     const animRes = await fetch('http://127.0.0.1:5000/animate', {
  //       method: 'POST',
  //       headers: { 'Content-Type': 'application/json' },
  //       body: JSON.stringify({ 
  //         image: result.image, 
  //         location_key: result.location_key 
  //       }),
  //     });
  //     const animData = await animRes.json();
      
  //     if (animData.video) {
  //       setResult(prev => prev ? { ...prev, video: animData.video } : null);
  //       setStatus('finished');
  //     } else {
  //       throw new Error(animData.error || "Video failed");
  //     }
  //   } catch (err: any) {
  //     setFailReason(getFriendlyErrorMessage(err.message, currentLang));
  //     setStatus('error');
  //   }
  // };

  return (
    <>
      <form id="upload-section-start" onSubmit={handleGenerate} className="w-full mx-auto mt-8">
        
        <div className="dashed-box-container">
            {/* Location Select */}
            <div ref={dropdownRef} 
                className={`flex flex-row md:flex-row md:justify-between md:items-end 
                py-2 font-bold text-xl md:text-2xl border-b-2 border-dark ${fontClass} relative`}>
                <label className="whitespace-nowrap mr-4 cursor-pointer flex-shrink-0" onClick={() => setIsDropdownOpen(!isDropdownOpen)}>{text.label_location}</label>
                <div className="relative flex-1 min-w-0">
                    <div onClick={() => setIsDropdownOpen(!isDropdownOpen)} className="w-full bg-transparent cursor-pointer text-right font-bold pr-12 truncate text-dark select-none">
                        {selectedLocation ? LOCATIONS_DATA.find(l => l.id === selectedLocation)?.[currentLang === 'ENG' ? 'en' : 'th'] : <span className="text-gray-400 opacity-50"></span>}
                        <span className={`absolute right-2 pl-1 bottom-0 transition-transform duration-200 ${isDropdownOpen ? 'rotate-180' : ''}`}>▼</span>
                    </div>
                    {isDropdownOpen && (
                        <div className="absolute top-full left-0 w-full z-50 mt-1 bg-[#FFF8E7] border-2 border-dark shadow-[4px_4px_0px_#2C2C2C] max-h-60 overflow-y-auto">
                            {LOCATIONS_DATA.map(loc => {
                                const isSelected = selectedLocation === loc.id;
                                return (
                                    <div key={loc.id} onClick={() => { setSelectedLocation(loc.id); setIsDropdownOpen(false); }}
                                        className={`cursor-pointer px-4 py-3 text-left sm:text-right transition-colors truncate ${isSelected ? 'bg-dark text-white' : 'text-dark hover:bg-[#F4D03F]'}`}>
                                        {currentLang === 'ENG' ? loc.en : loc.th}
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            </div>
            <div className="h-1"></div>

            {/* File Upload */}
            <div className={`flex justify-between items-end pb-2 font-bold text-xl md:text-2xl mb-3 border-b-2 border-dark relative ${fontClass}`}>
                <label htmlFor="file-upload" className="flex-1">{text.label_upload}</label>
                <button type="button" onClick={() => fileInputRef.current?.click()} className="text-3xl hover:scale-110 transition-transform" title="Click to select image">
                    <img src="/svg/photo-camera.svg" alt="Camera Icon" className="w-8 h-8 md:w-10 md:h-10"/>
                </button>
                <input id="file-upload" type="file" ref={fileInputRef} onChange={handleFileChange} accept="image/*" className="hidden"/>
            </div>

            {/* Drop Zone */}
            <div className={`min-h-[250px] flex justify-center items-center cursor-pointer transition-all duration-200 border-2 p-4 relative overflow-hidden ${isDragging ? 'border-transparent bg-gold/20' : 'border-transparent'}`}
                onClick={() => fileInputRef.current?.click()} onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}>
                {preview ? (
                    <img src={preview} alt="Preview" className="max-h-[300px] w-auto object-contain border-2 border-dark shadow-md z-0" />
                ) : (
                    <div className="flex flex-col items-center text-dark hover:scale-105 transition-transform z-0">
                        <span className="text-6xl mb-1"><img src="/svg/upload-1.svg" alt="Upload Icon" className="w-10 h-10 md:w-20 md:h-20"/></span>
                        <span className={`text-lg text-center ${fontClass}`}>{text.dropzone_text}</span>
                    </div>
                )}
            </div>
        </div>

        {/* Generate Button */}
        <button type="submit" disabled={status !== 'idle' && status !== 'verified_fail' && status !== 'finished'}
            className={`w-full mt-8 bg-dark text-white text-bold py-4 text-2xl md:text-3xl transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed active:translate-y-[2px] active:shadow-[2px_2px_0px_#2C2C2C] hover:scale-105 ${fontClass}`}>
            {text.btn_main}
        </button>
      </form>

      {/* --- WARNING MODAL --- */}
      {showInputWarning && (
        <div className="fixed inset-0 bg-black/80 z-[60] flex justify-center items-center p-4">
            <div className={`border-2 border-gold bg-black p-8 max-w-md w-full text-center shadow-[0_0_30px_rgba(255,255,255,0.2)] animate-fade-in-up ${fontClass} whitespace-pre-line`}>
                <div className="text-5xl mb-4 text-yellow-400">!</div>
                <div className="text-2xl md:text-3xl font-bold mb-4 serif-font text-gold uppercase tracking-wider">{text.warning_title}</div>
                <p className=" text-base md:text-lg text-gold mb-8 leading-relaxed">{text.warning_msg}</p>
                <button onClick={() => setShowInputWarning(false)} className="w-full border border-gold px-6 py-3 bg-transparent text-gold hover:bg-white hover:text-black  tracking-widest transition-colors uppercase">
                    {text.btn_acknowledge}
                </button>
            </div>
        </div>
      )}

      {/* --- PROCESS STATUS MODALS --- */}
      {status !== 'idle' && status !== 'finished' && (
        <div className={`fixed inset-0 bg-black/95 z-50 flex flex-col justify-center items-center text-white px-4 text-center ${fontClass}`}>
            
            {status === 'verifying' && (
                <>
                    <div className="text-4xl md:text-6xl font-bold mb-6 animate-pulse serif-font tracking-widest text-gold">{text.status_analyzing}</div>
                    <p className=" text-sm md:text-base opacity-70 tracking-wider">{text.sub_analyzing}</p>
                </>
            )}

            {status === 'verified_pass' && (
                <>
                    <div className="text-6xl mb-4 text-green-500">✓</div>
                    <div className="text-3xl md:text-5xl font-bold mb-4 serif-font text-green-400">{text.status_verify_pass}</div>
                    <div className=" text-xl mb-2">{passDetails?.place}</div>
                    <div className=" text-sm opacity-70 mb-8">Confidence Score: {passDetails?.score.toFixed(1)}%</div>
                </>
            )}

            {status === 'verified_fail' && (
                <div className="border-2 border-accent p-8 max-w-2xl bg-black">
                    <div className="text-6xl mb-4 text-accent">✕</div>
                    <div className="text-3xl md:text-5xl font-bold mb-6 serif-font text-accent">{text.status_verify_fail}</div>
                    <p className=" text-lg md:text-xl text-white mb-8 leading-relaxed whitespace-pre-line">{failReason}</p>
                    <button onClick={() => setStatus('idle')} className="border border-white px-8 py-3 hover:bg-white hover:text-black  tracking-widest transition-colors uppercase">{text.btn_try_again}</button>
                </div>
            )}

            {status === 'error' && (
                <div className="border-2 border-accent p-8 max-w-2xl bg-black shadow-[0_0_50px_rgba(255,255,255,0.1)]">
                    <div className="text-6xl mb-4 text-red-500">✕</div>
                    <div className="text-3xl md:text-5xl font-bold mb-6 serif-font text-accent">{text.status_tech_error}</div>
                    <p className=" text-lg md:text-xl text-white mb-8 leading-relaxed whitespace-pre-line">{failReason}</p>
                    <button onClick={() => setStatus('idle')} className="border border-white px-8 py-3 hover:bg-white hover:text-black  tracking-widest transition-colors uppercase">{text.btn_retry}</button>
                </div>
            )}

            {status === 'generating' && (
                <>
                    <div className="text-4xl md:text-6xl font-bold mb-6 animate-pulse serif-font tracking-widest text-gold">{text.status_reconstructing}</div>
                    <p className=" text-sm md:text-base opacity-70 tracking-wider">{text.sub_reconstructing}</p>
                </>
            )}

            {/* UI สำหรับสถานะทำวิดีโอ (ANIMATING) */}
            {status === 'animating' && (
                <>
                    <div className="text-4xl md:text-6xl font-bold mb-6 animate-pulse serif-font tracking-widest text-gold">
                        {text.status_animating}
                    </div>
                    <p className=" text-sm md:text-base opacity-70 tracking-wider">
                        {text.sub_animating}
                    </p>
                </>
            )}
        </div>
      )}

      {/* --- RESULT MODAL --- */}
      {result && (
        <div className={`fixed inset-0 bg-black/85 z-50 flex justify-center items-center p-4 ${fontClass}`} onClick={() => setResult(null)}>
            <div className="bg-background p-6 md:p-8 max-w-3xl w-full border-[3px] border-dark shadow-[15px_15px_0px_rgba(0,0,0,0.5)] relative max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
                <button onClick={() => setResult(null)} className="absolute top-4 right-4 text-4xl font-bold leading-none hover:text-accent">&times;</button>
                <h3 className="serif-font text-2xl md:text-4xl font-bold mb-6 mt-2 text-center italic">{result.location}</h3>
                
                <div className="border-[3px] border-dark mb-6 bg-black relative">
                    {result.video ? (
                        <>
                            {/* ✅ เพิ่ม key={result.video} เพื่อบังคับให้วิดีโอเกิดใหม่ทุกครั้งที่เจนใหม่ */}
                            <video 
                                key={result.video} 
                                src={result.video} 
                                className="w-full h-auto block" 
                                controls 
                                autoPlay 
                                loop={false} 
                                onEnded={() => {
                                    console.log("🎬 Video Ended - Triggering Modal...");
                                    triggerAssessment();
                                }} 
                                playsInline 
                            />
                            <div className="absolute top-2 left-2 bg-red-600 text-white text-xs px-2 py-1 font-bold rounded shadow-sm">AI VIDEO</div>
                        </>
                    ) : (
                        <img src={result.image} alt="Generated" className="w-full h-auto block" />
                    )}
                </div>
                
                <button 
                    onClick={() => {
                        const link = document.createElement('a');
                        link.href = result.video || result.image;
                        link.download = `bangkok-1960s-${Date.now()}.${result.video ? 'mp4' : 'png'}`;
                        link.click();
                    }}
                    className="w-full mt-6 border-2 border-dark py-3 font-bold hover:bg-dark hover:text-white transition-colors uppercase tracking-widest"
                >
                    {text.btn_download} {result.video ? "(MP4)" : "(PNG)"}
                </button>
            </div>
        </div>
      )}
    <AssessmentModal 
        isOpen={showAssessment} 
        onClose={() => setShowAssessment(false)} 
        lang={currentLang} 
      />
    </>
  );
}