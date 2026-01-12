'use client';
import { useState, useRef, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';

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

// ใช้ข้อความ UI แบบ Processing (เน้นความคลาสสิก/Time Travel)
const UI_TEXT = {
  TH: {
    label_location: "เลือกสถานที่",
    label_upload: "อัปโหลดรูปถ่ายของคุณ",
    dropzone_text: "คลิก หรือ ลากรูปมาวางที่นี่",
    btn_main: "หวนคืนสู่ทศวรรษที่ 1960s",
    btn_try_again: "ลองรูปอื่น",
    btn_retry: "ลองใหม่อีกครั้ง",
    btn_download: "ดาวน์โหลดรูปภาพ",
    
    status_analyzing: "กำลังวิเคราะห์โครงสร้าง...",
    status_verify_pass: "ผ่านการตรวจสอบ",
    status_verify_fail: "การตรวจสอบไม่ผ่าน",
    status_tech_error: "เกิดข้อผิดพลาดทางเทคนิค",
    
    status_reconstructing: "เตรียมหวนสู่ความวิจิตรในวันวานแห่ง 1960s",
    sub_analyzing: "ตรวจสอบความถูกต้องของรูปภาพ",
    sub_reconstructing: "อยู่ระหว่างดำเนินการ...",
    
    error_desc_prefix: "ระบบขัดข้อง: "
  },
  ENG: {
    label_location: "Choose a location",
    label_upload: "Upload your Photo",
    dropzone_text: "Click or Drag photo here",
    btn_main: "Transform to 1960s",
    btn_try_again: "Try Another Photo",
    btn_retry: "Retry again",
    btn_download: "Download Image",
    
    status_analyzing: "ANALYZING SCENE",
    status_verify_pass: "VERIFICATION PASSED",
    status_verify_fail: "VERIFICATION REJECTED",
    status_tech_error: "TECHNICAL ERROR",
    
    status_reconstructing: "Let's Back to 1960s",
    sub_analyzing: "Verifying photo compatibility...",
    sub_reconstructing: "In process...",

    error_desc_prefix: "System Failure: "
  }
};

type ProcessStatus = 'idle' | 'verifying' | 'verified_pass' | 'verified_fail' | 'generating' | 'finished' | 'error';

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

  const [result, setResult] = useState<{image: string, desc: string, location: string} | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const text = UI_TEXT[currentLang];

  const fontClass = currentLang === 'ENG' ? 'font-merri' : 'font-krub';

  // --- Logic Map Integration: รับค่า Location จาก URL ---
  const searchParams = useSearchParams();

  // --- Drop down แบบคัสต้อม ---
  const [isDropdownOpen, setIsDropdownOpen] = useState(false); 
  const dropdownRef = useRef<HTMLDivElement>(null); // สำหรับคลิกข้างนอกแล้วปิด (Optional)

  // เพิ่ม useEffect เพื่อปิด Dropdown เวลาคลิกที่อื่น (Optional แต่ทำให้ UX ดีขึ้น)
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
         // Auto Scroll
         const element = document.getElementById('upload-section-start');
         if (element) element.scrollIntoView({ behavior: 'smooth' });
       }
    }
  }, [searchParams]);
  // ----------------------------------------------------

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

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !selectedLocation) return alert(currentLang === 'ENG' ? "Please select location and image." : "กรุณาเลือกสถานที่และรูปภาพ");

    let currentStep = 'verifying'; 

    setStatus('verifying'); 
    
    const formData = new FormData();
    formData.append('image', file);
    formData.append('location', selectedLocation);
    formData.append('language', currentLang); 

    try {
      // --- STEP 1: Verify (ชี้ไปที่ 127.0.0.1 ตาม Processing Branch) ---
      const verifyRes = await fetch('http://127.0.0.1:5000/verify', {
        method: 'POST',
        body: formData,
      });
      const verifyData = await verifyRes.json();

      if (!verifyRes.ok || verifyData.status === 'rejected') {
        setFailReason(verifyData.details || verifyData.error || "Unknown Error");
        setStatus('verified_fail'); 
        return; 
      }

      // --- STEP 2: Verify Passed ---
      setPassDetails({
        score: verifyData.analysis_report?.score || 0,
        place: verifyData.analysis_report?.detected_place || "Confirmed"
      });
      setStatus('verified_pass');

      await new Promise(r => setTimeout(r, 2000));

      currentStep = 'generating';
      setStatus('generating');

      const genFormData = new FormData();
      genFormData.append('image', file);
      genFormData.append('location', selectedLocation);

      // --- STEP 3: Generate (ชี้ไปที่ 127.0.0.1 ตาม Processing Branch) ---
      const genRes = await fetch('http://127.0.0.1:5000/generate', {
          method: 'POST',
          body: genFormData,
      });
      const genData = await genRes.json();

      if (genData.image) {
          setResult({
            image: genData.image,
            desc: genData.description,
            location: genData.location_name
          });
          setStatus('finished');
      } else {
          throw new Error(genData.error || "Generation process failed");
      }

    } catch (err: any) {
        console.error("Fetch Error Details:", err);
        setFailReason(err.message);
        
        if (currentStep === 'generating') {
            setStatus('error'); 
        } else {
            setStatus('verified_fail'); 
        }
    }
  };

  return (
    <>
      <form id="upload-section-start" onSubmit={handleGenerate} className="w-full mx-auto mt-8">
        
        <div className="dashed-box-container">

            {/* Location Select */}
            <div ref={dropdownRef} 
                className={`flex flex-col md:flex-row md:justify-between md:items-end 
                py-2 font-bold text-xl md:text-2xl border-b-2 border-dark ${fontClass} relative`}>

                <label className="whitespace-nowrap mb-1 md:mb-0 md:mr-4 cursor-pointer w-full md:w-auto" onClick={() => setIsDropdownOpen(!isDropdownOpen)}>
                    {text.label_location}
                </label>
                
                <div className="relative w-full md:flex-1">
                    {/* ส่วนแสดงผลค่าที่เลือก */}
                    <div 
                        onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                        className="w-full bg-transparent cursor-pointer text-right font-bold pr-12 truncate text-dark select-none">
                        
                        {selectedLocation 
                            ? LOCATIONS_DATA.find(l => l.id === selectedLocation)?.[currentLang === 'ENG' ? 'en' : 'th'] 
                            : <span className="text-gray-400 opacity-50"></span>
                        }
                        <span className={`absolute right-2 pl-1 bottom-0 transition-transform duration-200 ${isDropdownOpen ? 'rotate-180' : ''}`}>▼</span>
                    
                    </div>

                    {/* ส่วนรายการตัวเลือก (Dropdown List) */}
                    {isDropdownOpen && (
                        <div className="absolute top-full left-0 w-full z-50 mt-1 bg-[#FFF8E7] border-2 border-dark shadow-[4px_4px_0px_#2C2C2C] max-h-60 overflow-y-auto">
                            {LOCATIONS_DATA.map(loc => {
                                const isSelected = selectedLocation === loc.id;
                                return (
                                    <div
                                        key={loc.id}
                                        onClick={() => {
                                            setSelectedLocation(loc.id);
                                            setIsDropdownOpen(false);
                                        }}
                                        className={`
                                            cursor-pointer px-4 py-3 text-right transition-colors truncate
                                            ${isSelected 
                                                ? 'bg-dark text-white' 
                                                : 'text-dark hover:bg-[#F4D03F]'
                                            }
                                        `}
                                    >
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

                <input 
                    id="file-upload" type="file" ref={fileInputRef} onChange={handleFileChange} 
                    accept="image/*" className="hidden"
                />
            </div>

            {/* Drop Zone */}
            <div 
                className="min-h-[250px] flex justify-center items-center cursor-pointer transition-colors border-2 border-transparent p-4"
                onClick={() => fileInputRef.current?.click()}
            >
                {preview ? (
                    <img src={preview} alt="Preview" className="max-h-[300px] w-auto object-contain border-2 border-dark shadow-md" />
                ) : (
                    <div className="flex flex-col items-center text-dark  hover:scale-105 transition-transform">
                        <span className="text-6xl mb-1">
                            <img src="/svg/upload-1.svg" alt="Upload Icon" className="w-10 h-10 md:w-20 md:h-20"/>
                        </span>
                        <span className={`text-lg text-center ${fontClass}`}>{text.dropzone_text}</span>
                    </div>
                )}
            </div>
        </div>

        {/* Generate Button เครื่องผมมันต้องปรับแบบนี้ ไม่รู้ของคุณมันมีปัญหารึป่าวนะ */}
        <button 
            type="submit" 
            disabled={status !== 'idle' && status !== 'verified_fail' && status !== 'finished'}
            // แก้ไข: เปลี่ยนเป็น transition-all และลบตัวที่ขัดแย้งออก
            className={`w-full mt-8 bg-dark text-white text-bold py-4 text-2xl md:text-3xl transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed active:translate-y-[2px] active:shadow-[2px_2px_0px_#2C2C2C] hover:scale-105 ${fontClass}`}
        >
            {text.btn_main}
        </button>
      </form>

      {/* --- OVERLAY & MODALS --- */}
      {status !== 'idle' && status !== 'finished' && (
        <div className="fixed inset-0 bg-black/95 z-50 flex flex-col justify-center items-center text-white px-4 text-center">
            
            {status === 'verifying' && (
                <>
                    <div className="text-4xl md:text-6xl font-bold mb-6 animate-pulse serif-font tracking-widest text-gold">
                        {text.status_analyzing}
                    </div>
                    <p className="font-mono text-sm md:text-base opacity-70 tracking-wider">
                        {text.sub_analyzing}
                    </p>
                </>
            )}

            {status === 'verified_pass' && (
                <>
                    <div className="text-6xl mb-4 text-green-500">✓</div>
                    <div className="text-3xl md:text-5xl font-bold mb-4 serif-font text-green-400">
                        {text.status_verify_pass}
                    </div>
                    <div className="font-mono text-xl mb-2">
                        {passDetails?.place}
                    </div>
                    <div className="font-mono text-sm opacity-70 mb-8">
                        Confidence Score: {passDetails?.score.toFixed(1)}%
                    </div>
                </>
            )}

            {status === 'verified_fail' && (
                <div className="border-2 border-accent p-8 max-w-2xl bg-black">
                    <div className="text-6xl mb-4 text-accent">✕</div>
                    <div className="text-3xl md:text-5xl font-bold mb-6 serif-font text-accent">
                        {text.status_verify_fail}
                    </div>
                    <p className="font-mono text-lg md:text-xl text-white mb-8 leading-relaxed whitespace-pre-line">
                        {failReason}
                    </p>
                    <button 
                        onClick={() => setStatus('idle')}
                        className="border border-white px-8 py-3 hover:bg-white hover:text-black font-mono tracking-widest transition-colors uppercase"
                    >
                        {text.btn_try_again}
                    </button>
                </div>
            )}

            {status === 'error' && (
                <div className="border-2 border-accent p-8 max-w-2xl bg-black shadow-[0_0_50px_rgba(255,255,255,0.1)]">
                    <div className="text-6xl mb-4 text-red-500">✕</div>
                    <div className="text-3xl md:text-5xl font-bold mb-6 serif-font text-accent">
                        {text.status_tech_error}
                    </div>
                    <p className="font-mono text-lg md:text-xl text-white mb-8 leading-relaxed whitespace-pre-line">
                        {failReason}
                    </p>
                    <button 
                        onClick={() => setStatus('idle')}
                        className="border border-white px-8 py-3 hover:bg-white hover:text-black font-mono tracking-widest transition-colors uppercase"
                    >
                        {text.btn_retry}
                    </button>
                </div>
            )}

            {status === 'generating' && (
                <>
                    <div className="text-4xl md:text-6xl font-bold mb-6 animate-blink serif-font tracking-widest text-gold">
                        {text.status_reconstructing}
                    </div>
                    <p className="font-mono text-sm md:text-base opacity-70 tracking-wider">
                        {text.sub_reconstructing}
                    </p>
                </>
            )}
        </div>
      )}

      {result && (
        <div className="fixed inset-0 bg-black/85 z-50 flex justify-center items-center p-4" onClick={() => setResult(null)}>
            <div className="bg-background p-6 md:p-8 max-w-3xl w-full border-[3px] border-dark shadow-[15px_15px_0px_rgba(0,0,0,0.5)] relative max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
                <button onClick={() => setResult(null)} className="absolute top-4 right-4 text-4xl font-bold leading-none hover:text-accent">&times;</button>
                <h3 className="serif-font text-2xl md:text-4xl font-bold mb-6 mt-2 text-center italic">{result.location}</h3>
                <div className="border-[3px] border-dark mb-6 bg-black">
                    <img src={result.image} alt="Generated" className="w-full h-auto block" />
                </div>
                
                <button 
                    onClick={() => {
                        const link = document.createElement('a');
                        link.href = result.image;
                        link.download = `bangkok-1960s-${Date.now()}.png`;
                        link.click();
                    }}
                    className="w-full mt-6 border-2 border-dark py-3 font-bold hover:bg-dark hover:text-white transition-colors uppercase tracking-widest"
                >
                    {text.btn_download}
                </button>
            </div>
        </div>
      )}
    </>
  );
}