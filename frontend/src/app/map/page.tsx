"use client";

import Navbar from "@/components/Navbar";
import { useLanguage } from "@/context/LanguageContext";
import { useState } from "react";

import { TransformWrapper, TransformComponent, useControls, useTransformContext } from "react-zoom-pan-pinch";
import { useRouter } from "next/navigation";

const MAP_LOCATIONS = [
  { id: 1, th: "อนุสาวรีย์ประชาธิปไตย", en: "Democracy Monument", top: "28.5%", left: "41%", videoUrl: "/videos/demo1.mp4" },
  { id: 2, th: "ศาลาเฉลิมกรุง", en: "Sala Chalermkrung", top: "62.5%", left: "44.5%", videoUrl: "/videos/demo2.mp4" },
  { id: 3, th: "เสาชิงช้า & วัดสุทัศน์", en: "Giant Swing & Wat Suthat", top: "45%", left: "43.5%", videoUrl: "/videos/demo3.mp4" },
  { id: 4, th: "ถนนข้าวสาร", en: "Khaosan Road", top: "26%", left: "28%", videoUrl: "/videos/demo4.mp4" },
  { id: 5, th: "ป้อมพระสุเมรุ", en: "Phra Sumen Fort", top: "10.8%", left: "20%", videoUrl: "/videos/demo5.mp4" },
  { id: 6, th: "พิพิธภัณฑสถานแห่งชาติ", en: "National Museum", top: "34.5%", left: "17.25%", videoUrl: "/videos/demo6.mp4" },
  { id: 7, th: "ถนนเยาวราช", en: "Yaowarat (Chinatown)", top: "72.5%", left: "70%", videoUrl: "/videos/demo7.mp4" },
  { id: 8, th: "สนามหลวง", en: "Sanam Luang", top: "45%", left: "21%", videoUrl: "/videos/demo8.mp4" },
];

// --- Component ย่อย 1: ปุ่มควบคุมการซูม ---
const Controls = () => {
  const { zoomIn, zoomOut, centerView } = useControls();
  
  return (
    <div className="absolute bottom-4 right-4 flex flex-col gap-2 z-10">
      <button onClick={() => zoomIn()} className="w-10 h-10 bg-white/80 text-dark font-bold text-xl shadow-md hover:scale-105 transition-transform">+</button>
      <button onClick={() => zoomOut()} className="w-10 h-10 bg-white/80 text-dark font-bold text-xl shadow-md hover:scale-105 transition-transform">-</button>
      <button 
        onClick={() => centerView(0.45)} 
        className="w-10 h-10 bg-white/80 text-dark border-2 border-dark font-bold text-xs shadow-md hover:scale-105 transition-transform"
      >
        RESET
      </button>
    </div>
  );
};

// --- Component ย่อย 2: หมุดแผนที่ (จัดการเรื่องขนาดคงที่) ---
const MapPin = ({ loc, activePin, setActivePin, language, onClick }: any) => {
  // ดึงค่า scale ปัจจุบันจาก Library
  const { transformState } = useTransformContext();
  const scale = transformState.scale;

  // สูตรคำนวณ: ยิ่งแมพเล็ก (scale น้อย) -> หมุดต้องยิ่งขยาย (counterScale มาก)
  // Math.max(1, ...) เพื่อกันไม่ให้หมุดเล็กกว่าปกติเวลาซูมเข้าลึกๆ
  const counterScale = 1 / Math.min(scale, 2.5); 

  return (
    <div 
        className="absolute group cursor-pointer origin-bottom"
        style={{ 
            top: loc.top, 
            left: loc.left, 
            transform: 'translate(-50%, -100%)' // จุดอ้างอิงอยู่ตรงปลายแหลมหมุด
        }}
        onMouseEnter={() => setActivePin(loc.id)}
        onMouseLeave={() => setActivePin(null)}
        onMouseDown={(e) => e.stopPropagation()} 
        onTouchStart={(e) => e.stopPropagation()}

        onClick={(e) => {
            e.stopPropagation(); // ป้องกันไม่ให้ทะลุไปกด map
            onClick(loc);
        }}
    >
        {/* ส่วนรูปภาพหมุด */}
        <div 
            className="text-4xl md:text-5xl drop-shadow-md text-red-600 hover:scale-125 transition-transform animate-bounce"
            style={{ 
                transform: `scale(${counterScale})`, // ขยายสวนทางกับแผนที่
                transformOrigin: 'bottom center' 
            }}
        >
            <img src="/svg/pin-gold.svg" alt="Pin" className="w-16 h-16"/>
        </div>

        {/* ส่วนข้อความ Tooltip */}
        <div 
            className={`
                absolute bottom-full left-1/2 -translate-x-1/2 mb-1 w-max px-3 py-1 
                bg-black/90 text-white text-xs md:text-sm font-mono tracking-wide border border-gold
                transition-opacity duration-200 pointer-events-none z-50 rounded shadow-lg
                ${activePin === loc.id ? 'opacity-100' : 'opacity-0'}
            `}
            style={{
                transform: `scale(${counterScale})`, // ขยายข้อความด้วย
                transformOrigin: 'bottom center',
                marginBottom: `${10 * counterScale}px` // ดันข้อความหนีหมุดขึ้นไปตามสัดส่วน
            }}
        >
            {language === 'TH' ? loc.th : loc.en}
        </div>
    </div>
  );
};

// --- Component ย่อย 3: Video Modal (Pop-up) ---
const VideoModal = ({ location, onClose, language }: any) => {
    const router = useRouter(); // 2. เรียกใช้ Router

    if (!location) return null;

    // ฟังก์ชันกดปุ่มแล้วย้ายหน้า
    const handleNavigateToUpload = () => {
        // ส่งชื่อภาษาไทย (location.th) ไป เพราะใน UploadSection เราใช้ชื่อไทยเป็น ID
        // ใช้ encodeURIComponent เผื่อภาษาไทยมีปัญหาใน URL
        router.push(`/?location=${encodeURIComponent(location.th)}`);
    };

    return (
        <div className="fixed inset-0 z-[100] bg-black/90 flex justify-center items-center p-4 backdrop-blur-sm" onClick={onClose}>
            <div 
                className="bg-background rounded-3xl w-full max-w-4xl relative flex flex-col"
                onClick={e => e.stopPropagation()} 
            >
              <div className="bg-[#F4EDDB] px-8 rounded-3xl overflow-hidden flex flex-col">
                {/* Header */}
                <div className="text-dark py-6 flex justify-between items-center">
                    <h3 className="serif-font font-bold text-xl md:text-3xl tracking-wide">
                        {language === 'TH' ? location.th : location.en}
                    </h3>
                    <button onClick={onClose} className="text-2xl text-white bg-dark hover:bg-accent px-3 py-1 transition-colors font-bold">&times;</button>
                </div>

                {/* Video Player */}
                <div className="w-full aspect-video bg-black relative">
                    <video 
                        src={location.videoUrl} 
                        className="w-full h-full object-contain"
                        controls 
                        autoPlay
                    >
                        Your browser does not support the video tag.
                    </video>
                </div>

                {/* Footer with Action Button */}
                <div className="py-6 flex flex-col md:flex-row justify-between items-center gap-4 border-t-2 border-dark">
                   <span className="font-mono text-sm opacity-70">
                       {language === 'TH' ? "*วิดีโอจำลองบรรยากาศช่วงทศวรรษที่ 1960" : "*1960s Atmosphere Simulation Video"}
                   </span>

                   {/* 3. ✅ ปุ่ม CTA ใหม่ */}
                   <button 
                        onClick={handleNavigateToUpload}
                        className="bg-gold text-dark transition-colors px-6 py-2 font-bold tracking-widest flex items-center gap-2"
                   >
                      {language === 'TH' ? "ลองสร้างวิดีโอของคุณ" : "Generate Your Own"}
                   </button>
                </div>
              </div>
                
            </div>
        </div>
    );
};

// --- Main Page Component ---
export default function MapPage() {
  const { language } = useLanguage();
  const [activePin, setActivePin] = useState<number | null>(null);

  const [selectedLocation, setSelectedLocation] = useState<any>(null);

  return (
    <main className="w-full px-4 md:px-6 pb-20 mx-auto">
      <Navbar />
      
      {selectedLocation && (
          <VideoModal 
            location={selectedLocation} 
            onClose={() => setSelectedLocation(null)} 
            language={language}
          />
      )}

      <h1 className="bg-dark text-white p-3 text-center text-xl md:text-5xl font-bold tracking-[0.2em] mt-10 mb-8 py-8 font-mono shadow-[6px_6px_0px_#D4B666]">
          {language === 'TH' ? "แผนที่ประวัติศาสตร์" : "Historical Map"}
      </h1>

      <div className="w-full mx-auto border-[4px] border-dark p-2"> 
        
        <div className="w-full h-[500px] md:h-[650px] relative overflow-hidden bg-dark cursor-grab active:cursor-grabbing">
             
             <TransformWrapper
                initialScale={0.45}
                minScale={0.45}
                maxScale={8}
                centerOnInit={true}
                wheel={{ step: 0.1 }}
                limitToBounds={false}
             >
                {/* Controls และ MapPin ต้องอยู่ภายใน TransformWrapper ถึงจะใช้ Context ได้ */}
                <Controls />
                
                <TransformComponent wrapperClass="!w-full !h-full" contentClass="!w-full flex items-center justify-center">
                    
                    <div className="relative w-auto h-auto inline-block">
                        {/* รูปภาพแผนที่ */}
                        <img 
                            src="/images/map.png" 
                            alt="Phra Nakhon Map"
                            className="block max-w-none h-auto object-contain"
                            draggable={false}
                        />

                        {/* เรียกใช้ Component หมุดที่เราสร้างไว้ */}
                        {MAP_LOCATIONS.map((loc) => (
                            <MapPin 
                                key={loc.id}
                                loc={loc}
                                activePin={activePin}
                                setActivePin={setActivePin}
                                language={language}
                                onClick={(location: any) => setSelectedLocation(location)}
                            />
                        ))}
                    </div>
                </TransformComponent>
             </TransformWrapper>

             {/* คำอธิบายวิธีใช้ */}
             <div className="absolute bottom-4 left-4 bg-white/80 backdrop-blur-sm p-2 border border-dark text-xs font-mono pointer-events-none z-10">
                {language === 'TH' ? "🖱️ เลื่อนเมาส์เพื่อซูม / คลิกแล้วลากเพื่อขยับ" : "🖱️ Scroll to Zoom / Drag to Pan"}
             </div>
        </div>
      </div>
    </main>
  );
}