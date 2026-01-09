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
    desc_prefix: "คือนวัตกรรมย้อนเวลาอัจฉริยะ ที่พร้อมพาคุณข้ามศตวรรษกลับไปสัมผัสเสน่ห์แห่ง 'พระนคร' ยุค 2500 อันรุ่งโรจน์ เปิดประสบการณ์ทัศนาจรผ่านมุมมองใหม่ด้วย", 
    desc_highlight: "เทคโนโลยีปัญญาประดิษฐ์จำลองบรรยากาศ", 
    desc_suffix: "ที่จะเนรมิตภาพถ่ายปัจจุบันของคุณ ให้กลายเป็นความทรงจำแสนคลาสสิก เสมือนหลุดยังวันวานแห่งมนต์ขลังของพระนครในอดีต",
    link_dev: "พบกับเจ้าของผลงาน →"
  },
  ENG: {
    brand_name: "Bangkok EraVision",
    title: "WHAT IS BANGKOK ERAVISION?",
    desc_prefix: "is a digital time gateway designed to transport you back to the golden era of 'Phra Nakhon' in the 1960s. Rediscover the vibrant soul of the past through our",
    desc_highlight: "cutting-edge AI retro-simulation technology",
    desc_suffix: "that seamlessly transforms your modern perspective into a vintage masterpiece, capturing the authentic atmosphere of the Venice of the East.",
    link_dev: "The Project's Development Team →"
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
        <h1 className="bg-dark text-white p-3 text-center text-xl md:text-5xl font-bold tracking-[0.2em] mb-8 py-8 font-mono shadow-[6px_6px_0px_#D4B666]">
          {text.title}
        </h1>
        <div className="flex flex-col md:flex-row gap-8 items-stretch mt-10">
          {/* กล่องรูปภาพ */}
          <div className="w-full md:flex-1 md:h-[490px] bg-gold shrink-0 border-[3px] border-dark flex items-center justify-center relative shadow-md">
            <span className="opacity-30 text-5xl font-serif font-bold rotate-[-15deg]">1960s</span>
          </div>

          {/* กล่องข้อความ */}
          <div className="w-full md:flex-1 flex flex-col justify-between">
            <p className="text-base md:text-lg leading-loose mb-6 text-justify">
              <strong className="text-2xl serif-font italic">{text.brand_name}</strong> {text.desc_prefix} "{text.desc_highlight}" {text.desc_suffix}
            </p>
            <Link href="/about" className="self-start font-bold text-xl underline decoration-2 underline-offset-4 hover:opacity-80 transition-colors">
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