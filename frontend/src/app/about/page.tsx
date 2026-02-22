"use client";

import Navbar from "@/components/Navbar";
import { useState } from "react";
import { useLanguage } from "@/context/LanguageContext";

const PAGE_TEXT = {
  TH: {
    // เปลี่ยนจาก Text เป็น Path รูปภาพแทน
    logo_img: "/images/logo-th.png", 
    section_created_by: "สร้างสรรค์โดย",
    section_advisor: "อาจารย์ที่ปรึกษา",
    
    member1_name: "ณัฐภัทร ชาลี",
    member2_name: "มาดามพงษ์ พฤกษา",
    advisor_name: "อ.ณัฐพงศ์ ประเสริฐสังข์",
    advisor_position: "อาจารย์ประจำภาควิชา\nวิทยาการคอมพิวเตอร์ประยุกต์-มัลติมีเดีย \n มหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรี"
  },
  ENG: {
    // เปลี่ยนจาก Text เป็น Path รูปภาพแทน
    logo_img: "/images/logo-en.png",
    section_created_by: "Created By",
    section_advisor: "Advisor",
    
    member1_name: "Nattapat Chalee",
    member2_name: "Madampong Prueksa",
    advisor_name: "Nuttapong Prasertsang",
    advisor_position: "Lecturer at CMM, KMUTT"
  }
};

export default function AboutPage() {
  const { language } = useLanguage();
  const text = PAGE_TEXT[language];

  const fontClass = language === 'ENG' ? 'font-merri' : 'font-krub';

  return (
    <main className="w-full px-6 pb-20 mx-auto">
      {/* --- Background Texture Layer --- */}
      <div 
        className="fixed inset-0 -z-10 pointer-events-none opacity-[0.2]"
        style={{ 
          backgroundImage: "url('/images/grunge-paper-background3.png')", 
          backgroundSize: 'cover',
          backgroundRepeat: 'no-repeat',
          backgroundPosition: 'center'
        }}
      ></div>

      <Navbar />
      <div className="animate-fade-push-up">
        {/* --- Header Logo Section (Edited) --- */}
        <div className="flex flex-col items-center mb-12 mt-10">
          
          {/* Logo Image Container */}
          <div className="relative w-full flex justify-center px-4 mt-3">
            <img 
              src={text.logo_img} 
              alt="Bangkok EraVision Logo" 
              // Responsive Classes: 
              // w-[80%] สำหรับมือถือ (ไม่ใหญ่เกินไป)
              // sm:w-[60%] สำหรับแท็บเล็ต
              // md:max-w-[500px] สำหรับจอคอม (จำกัดขนาดไม่ให้ใหญ่เบิ้ม)
              // drop-shadow เพิ่มมิติให้ลอยเด่นขึ้นมาจากพื้นหลัง
              className="w-[85%] sm:w-[60%] md:w-[500px] h-auto object-contain drop-shadow-xl transition-all duration-500 ease-in-out hover:scale-105"
            />
          </div>

          {/* Decorative Separator */}
          <div className="flex items-center justify-center w-full mt-8 mb-8">
              <div className="h-[2px] bg-dark w-1/4 md:w-1/3 opacity-70"></div>
              <span className="mx-6 text-2xl md:text-3xl font-serif text-dark">⚜</span>
              <div className="h-[2px] bg-dark w-1/4 md:w-1/3 opacity-70"></div>
          </div>
        </div>

        {/* Created By Section */}
        <section className="mb-16 text-center">
          <h2 className={`text-center text-3xl md:text-4xl font-bold mb-16 italic bg-background inline-block px-4 pr-5 py-3 pt-4 border-[4px] border-dark shadow-[4px_4px_0px_#D4B666] ${fontClass}`}>
            {text.section_created_by}
          </h2>
          <div className="flex flex-wrap justify-center gap-16 px-4 max-w-5xl mx-auto">
            {/* Creator 1 */}
            <div className={`flex flex-col items-center group w-full sm:w-[45%] md:w-[300px] ${fontClass}`}>
              <img
                src="/images/member1.png"
                alt="Nattapat Chalee"
                className="w-full max-w-[280px] aspect-square mb-4 object-cover border-[3px] border-dark shadow-[inset_0_0_0_4px_#FEF9C3,6px_6px_0px_#2C2C2C] group-hover:translate-y-[-5px] transition-transform"
              />
              <p className="font-bold text-xl md:text-2xl mt-2">{text.member1_name}</p>
              <p className={`${fontClass} text-sm md:text-md opacity-70`}>CMM65080500264</p>
            </div>
            
            {/* Creator 2 */}
            <div className={`flex flex-col items-center group w-full sm:w-[45%] md:w-[300px] ${fontClass}`}>
              <img
                src="/images/member2.png"
                alt="Madampong Prueksa"
                className="w-full max-w-[280px] aspect-square mb-4 object-cover border-[3px] border-dark shadow-[inset_0_0_0_4px_#FEF9C3,6px_6px_0px_#2C2C2C] group-hover:translate-y-[-5px] transition-transform"
              />
              <p className="font-bold text-xl md:text-2xl mt-2">{text.member2_name}</p>
              <p className={`${fontClass} text-sm md:text-md opacity-70`}>CMM65080500275</p>
            </div>
          </div>
        </section>

        {/* Advisor Section */}
        <section className="flex flex-col items-center">
          <h2 className={`text-center text-3xl md:text-4xl font-bold mb-10 italic bg-background inline-block px-4 pr-5 py-3 pt-4 border-[4px] border-dark shadow-[4px_4px_0px_#D4B666] ${fontClass}`}>
            {text.section_advisor}
          </h2>
          {/* ปรับขนาด w-full ใน Mobile และจำกัด max-w ใน Desktop */}
          <div className={`flex flex-col items-center group w-full max-w-[300px] ${fontClass}`}>
            <img
              src="/images/advisor.png"
              alt="Nuttapong Prasertsang"
              className="w-full aspect-square mb-4 object-cover border-[3px] border-dark shadow-[inset_0_0_0_4px_#FEF9C3,6px_6px_0px_#2C2C2C] group-hover:translate-y-[-5px] transition-transform"
            />
            <p className="font-bold text-xl md:text-2xl mt-2 text-center">
              {text.advisor_name}
            </p>
            <p className={`${fontClass} text-sm md:text-md text-center whitespace-pre-line opacity-70`}>
              {text.advisor_position}
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}