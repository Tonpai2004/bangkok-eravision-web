"use client";

import Navbar from "@/components/Navbar";
import { useLanguage } from "@/context/LanguageContext";
import { useState, useRef } from "react";

import { TransformWrapper, TransformComponent, useControls, useTransformContext, ReactZoomPanPinchRef } from "react-zoom-pan-pinch";
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

const Controls = () => {
  const { zoomIn, zoomOut, centerView } = useControls();
  
  return (
    <div className={`absolute bottom-4 right-4 flex flex-col gap-2 z-10 font-krub`}>
      <button onClick={() => zoomIn()} className="w-12 h-12 bg-white/80 text-dark font-bold text-xl shadow-md hover:scale-105 transition-transform">+</button>
      <button onClick={() => zoomOut()} className="w-12 h-12 bg-white/80 text-dark font-bold text-xl shadow-md hover:scale-105 transition-transform">-</button>
      <button 
        onClick={() => centerView(0.45)} 
        className="w-12 h-12 bg-white/80 text-dark border-2 border-dark font-bold text-xs shadow-md hover:scale-105 transition-transform"
      >
        RESET
      </button>
    </div>
  );
};

const MapPin = ({ loc, activePin, setActivePin, language, onClick }: any) => {
  const { transformState } = useTransformContext();
  const scale = transformState.scale;
  const counterScale = 1 / Math.min(scale, 2.5); 

  return (
    <div 
        className="absolute group cursor-pointer origin-bottom"
        style={{ 
            top: loc.top, 
            left: loc.left, 
            transform: 'translate(-50%, -100%)' 
        }}
        onMouseEnter={() => setActivePin(loc.id)}
        onMouseLeave={() => setActivePin(null)}
        onMouseDown={(e) => e.stopPropagation()} 
        onTouchStart={(e) => e.stopPropagation()}
        onClick={(e) => {
            e.stopPropagation();
            onClick(loc);
        }}
    >
        <div 
            className="text-4xl md:text-5xl drop-shadow-md text-red-600 hover:scale-125 transition-transform animate-bounce"
            style={{ 
                transform: `scale(${counterScale})`, 
                transformOrigin: 'bottom center' 
            }}
        >
            <img src="/svg/pin-gold.svg" alt="Pin" className="w-16 h-16"/>
        </div>

        <div 
            className={`
                absolute bottom-full left-1/2 -translate-x-1/2 mb-1 w-max px-3 py-1 
                bg-black/90 text-white text-xs md:text-sm tracking-wide border border-gold
                transition-opacity duration-200 pointer-events-none z-50 rounded shadow-lg
                ${activePin === loc.id ? 'opacity-100' : 'opacity-0'} ${language === 'TH' ? 'font-krub' : 'font-merri'}
            `}
            style={{
                transform: `scale(${counterScale})`,
                transformOrigin: 'bottom center',
                marginBottom: `${10 * counterScale}px` 
            }}
        >
            {language === 'TH' ? loc.th : loc.en}
        </div>
    </div>
  );
};

const VideoModal = ({ location, onClose, language }: any) => {
    const router = useRouter(); 

    if (!location) return null;

    const handleNavigateToUpload = () => {
        router.push(`/?location=${encodeURIComponent(location.th)}`);
    };

    return (
        <div className="fixed inset-0 z-[100] bg-black/90 flex justify-center items-center p-4 backdrop-blur-sm" onClick={onClose}>
            <div 
                className={`bg-background rounded-3xl w-full max-w-4xl relative flex flex-col ${language === 'TH' ? 'font-krub' : 'font-merri'}`}
                onClick={e => e.stopPropagation()} 
            >
              <div className="bg-[#F4EDDB] px-8 rounded-3xl overflow-hidden flex flex-col">
                <div className="text-dark py-6 flex justify-between items-center">
                    <h3 className="serif-font font-bold text-xl md:text-3xl tracking-wide">
                        {language === 'TH' ? location.th : location.en}
                    </h3>
                    <button onClick={onClose} className="text-2xl text-white bg-dark hover:bg-accent px-3 py-1 transition-colors font-bold">&times;</button>
                </div>

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

                <div className="py-6 flex flex-col md:flex-row justify-between items-center gap-4 border-t-2 border-dark">
                   <span className="text-sm opacity-70">
                       {language === 'TH' ? "*วิดีโอจำลองบรรยากาศช่วงทศวรรษที่ 1960" : "*1960s Atmosphere Simulation Video"}
                   </span>
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

export default function MapPage() {
  const { language } = useLanguage();
  const [activePin, setActivePin] = useState<number | null>(null);

  const [selectedLocation, setSelectedLocation] = useState<any>(null);

  const transformRef = useRef<ReactZoomPanPinchRef | null>(null);

  const fontClass = language === 'ENG' ? 'font-merri' : 'font-krub';

  return (
    <main className="w-full px-4 md:px-6 pb-20 mx-auto">
      {/* --- Background Texture Layer --- */}
      <div 
        className="fixed inset-0 -z-10 pointer-events-none opacity-[0.4]"
        style={{ 
          backgroundImage: "url('/images/grunge-paper-background.jpg')", 
          backgroundSize: 'cover',
          backgroundRepeat: 'no-repeat',
          backgroundPosition: 'center'
        }}
      ></div>
      
      <Navbar />
      
      {selectedLocation && (
          <VideoModal 
            location={selectedLocation} 
            onClose={() => setSelectedLocation(null)} 
            language={language}
          />
      )}

      <h1 className="bg-dark text-white font-prachachon p-3 mt-10 mb-10 pt-6 pb-4 text-center text-4xl sm:text-6xl md:text-8xl whitespace-pre-line tracking-[0.1em]">
          {language === 'TH' ? "แผนที่สถานที่" : "Location Map"}
      </h1>

      <div className="w-full mx-auto border-[4px] border-dark bg-background p-2"> 
        
        <div className="w-full h-[500px] md:h-[650px] relative overflow-hidden bg-dark cursor-grab active:cursor-grabbing">
             
             <TransformWrapper
                ref={transformRef}
                initialScale={0.45}
                minScale={0.45}
                maxScale={8}
                centerOnInit={true}
                wheel={{ step: 0.1 }}
                limitToBounds={false}
             >
                <Controls />
                
                <TransformComponent wrapperClass="!w-full !h-full" contentClass="!w-full flex items-center justify-center">
                    
                    <div className="relative w-auto h-auto inline-block">
                        <img 
                            src="/images/map.png" 
                            alt="Phra Nakhon Map"
                            className="block max-w-none h-auto object-contain"
                            draggable={false}
                            onLoad={() => {
                                if (transformRef.current) {
                                    transformRef.current.centerView(0.45);
                                }
                            }}
                        />
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

             <div className={`absolute bottom-4 left-4 bg-white/80 backdrop-blur-sm p-2 border border-dark text-xs pointer-events-none z-10 ${fontClass}`}>
                {language === 'TH' ? "🖱️ เลื่อนเมาส์เพื่อซูม / คลิกแล้วลากเพื่อขยับ" : "🖱️ Scroll to Zoom / Drag to Pan"}
             </div>
        </div>
      </div>
    </main>
  );
}