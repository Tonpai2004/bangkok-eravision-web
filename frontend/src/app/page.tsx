"use client";

import Navbar from "@/components/Navbar";
import UploadSection from "@/components/UploadSection";
import Link from "next/link";
import { useLanguage } from "@/context/LanguageContext";

// คงเนื้อหา Marketing/คำสวยหรู ของ Processing ไว้ตามคำขอ
const PAGE_TEXT = {
  TH: {
    brand_name: "บางกอกทวิกาล",
    title: "บางกอกทวิกาล คืออะไร?",
    desc_prefix: "คือนวัตกรรมทางเทคโนโลยีถ่ายที่เชื่อมโยงคุณเข้ากับความงามสง่าของ \"พระนคร\" ในช่วงคริสต์ทศวรรษที่ 1960s อีกครั้ง เชิญสัมผัสประสบการณ์ย้อนเวลาด้วย",
    desc_highlight: "เทคโนโลยีปัญญาประดิษฐ์ผสานศาสตร์ศิลป์และประวัติศาสตร์",
    desc_suffix: "ที่จะเนรมิตภาพถ่ายปัจจุบันของคุณ ให้กลายเป็นภาพบันทึกความทรงจำแสนคลาสสิก เปี่ยมด้วยเสน่ห์และกลิ่นอายที่แท้จริงของยุคสมัย ที่แม้จะย้อนกลับไปไม่ได้ แต่ก็ได้สัมผัสประสบการณ์แห่งกาลเวลาจากเทคโนโลยีของเรา",
    link_dev: "คณะผู้รังสรรค์ผลงาน →"
  },
  ENG: {
    brand_name: "Bangkok EraVision",
    title: "WHAT IS BANGKOK ERAVISION?",
    desc_prefix: "is an innovative imaging platform reconnecting you with the elegance of 1960s 'Phra Nakhon'. Experience a journey through time via",
    desc_highlight: "AI technology infused with artistry and history",
    desc_suffix: "that transforms your modern photos into classic mementos, capturing the era's authentic charm. Though the past cannot be reclaimed, our technology allows you to touch its very essence once more.",
    link_dev: "The Project Creators →"
  }
};

export default function Home() {
  const { language } = useLanguage();
  const text = PAGE_TEXT[language];

  return (
    <main className="w-full px-6 pb-20 mx-auto">
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

      {/* Hero Section */}
      <section className="mt-0 mb-0 md:mt-10 md:mb-7">
        <h1 className="bg-dark text-white font-prachachon p-3 mb-8 pt-6 pb-4 text-center text-4xl sm:text-6xl md:text-8xl whitespace-pre-line tracking-[0.1em]">
          {text.title}
        </h1>
        <div className="flex flex-col md:flex-row gap-8 items-stretch mt-10">
          
          {/* --- [แก้ไข] กล่องรูปภาพ --- */}
          <div className="w-full md:flex-1 md:h-[490px] bg-gold shrink-0 border-[3px] border-dark relative overflow-hidden group"> {/* shadow-[6px_6px_0px_rgba(0,0,0,0.2)] เผื่อใส่เงากลับ */}
            
            {/* ใส่ Path รูปภาพของคุณตรงนี้ เช่น /images/hero-bangkok.jpg */}
            <img 
              src="/images/placeholder-hero.png"  
              alt="Vintage Bangkok Atmosphere"
              className="w-full h-full object-cover sepia-[20%] contrast-110 transition-transform duration-700 group-hover:scale-105"
            />

            {/* Overlay จางๆ สีเข้มทับภาพเพื่อให้ดูขรึมขึ้น */}
            <div className="absolute inset-0 bg-dark/20 pointer-events-none"></div>
          </div>
          {/* --------------------------- */}


          {/* กล่องข้อความ */}
          <div className="w-full md:flex-1 flex flex-col justify-between">
            <p className="font-pimdeed text-3xl md:text-4xl whitespace-pre-line leading-normal mb-6 text-justify">
              <strong className="text-3xl md:text-4xl font-pimdeed italic">{text.brand_name}</strong> {text.desc_prefix} "{text.desc_highlight}" {text.desc_suffix}
            </p>
            <Link href="/about" className="self-start font-pimdeed font-bold text-3xl md:text-4xl underline decoration-2 underline-offset-4 hover:opacity-80 transition-colors mb-6 md:mb-0">
              {text.link_dev}
            </Link>
          </div>
        </div>
      </section>

      {/* Ornament Divider */}
      <div className="flex items-center justify-center mb-12">
        <div className="h-[2px] bg-dark flex-1"></div>
        <span className="mx-6 text-3xl font-serif">⚜</span>
        <div className="h-[2px] bg-dark flex-1"></div>
      </div>

      {/* Upload Section */}
      <UploadSection currentLang={language} />
    </main>
  );
}