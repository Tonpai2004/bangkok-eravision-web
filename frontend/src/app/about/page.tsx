"use client";

import Navbar from "@/components/Navbar";
import { useState } from "react";
import { useLanguage } from "@/context/LanguageContext";

// 2. สร้างชุดคำแปล
const PAGE_TEXT = {
  TH: {
    header_title: "บางกอก", // ชื่อแบรนด์ทับศัพท์ หรือจะใช้ภาษาไทยก็ได้ครับ
    header_subtitle: "ทวิกาล",
    section_created_by: "สร้างสรรค์โดย",
    section_advisor: "อาจารย์ที่ปรึกษา",
    
    // ข้อมูลสมาชิก (แก้ไขชื่อไทยได้ตามจริงเลยนะครับ)
    member1_name: "ณัฐภัทร ชาลี",
    member2_name: "มาดามพงษ์ พฤกษา",
    advisor_name: "อ.ณัฐพงศ์ ประเสริฐสังข์",
    advisor_position: "อาจารย์ประจำภาควิชา\nวิทยาการคอมพิวเตอร์ประยุกต์-มัลติมีเดีย \n มหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรี" // Lecturer in CMM KMUTT
  },
  ENG: {
    header_title: "Bangkok",
    header_subtitle: "EraVision",
    section_created_by: "Created By",
    section_advisor: "Advisor",
    
    member1_name: "Nattapat Chalee",
    member2_name: "Madampong Prueksa",
    advisor_name: "Nuttapong Prasertsang",
    advisor_position: "Lecturer in CMM KMUTT"
  }
};

export default function AboutPage() {
  // 3. ดึงค่าภาษาจาก Context
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

      <div className="text-center mb-12 mt-10">
        <h1 className="text-5xl md:text-7xl serif-font font-bold mb-6 italic tracking-tight text-dark">
          {text.header_title}<br/><span className="text-accent">{text.header_subtitle}</span>
        </h1>
        <div className="flex items-center justify-center my-8">
            <div className="h-[2px] bg-dark w-1/3"></div>
            <span className="mx-6 text-3xl font-serif">⚜</span>
            <div className="h-[2px] bg-dark w-1/3"></div>
        </div>
      </div>

      {/* Created By Section */}
      <section className="mb-16 text-center">
        <h2 className="text-center text-3xl md:text-4xl serif-font font-bold mb-16 italic bg-background inline-block px-4 pr-5 py-2 border-[4px] border-dark shadow-[4px_4px_0px_#D4B666]">
          {text.section_created_by}
        </h2>
        <div className="flex flex-wrap justify-center gap-16 px-4 max-w-5xl mx-auto">
          {/* Creator 1 */}
          <div className="flex flex-col items-center group w-full sm:w-[45%] md:w-[300px]">
            <img
              src="/images/member1.png"
              alt="Nattapat Chalee"
              className="w-full max-w-[280px] aspect-square mb-4 object-cover border-[3px] border-dark shadow-[inset_0_0_0_4px_#FEF9C3,6px_6px_0px_#2C2C2C] group-hover:translate-y-[-5px] transition-transform"
            />
            <p className="font-bold text-xl md:text-2xl mt-2">{text.member1_name}</p>
            <p className="text-sm md:text-md font-mono opacity-70">CMM65080500264</p>
          </div>
          
          {/* Creator 2 */}
          <div className="flex flex-col items-center group w-full sm:w-[45%] md:w-[300px]">
            <img
              src="/images/member2.png"
              alt="Madampong Prueksa"
              className="w-full max-w-[280px] aspect-square mb-4 object-cover border-[3px] border-dark shadow-[inset_0_0_0_4px_#FEF9C3,6px_6px_0px_#2C2C2C] group-hover:translate-y-[-5px] transition-transform"
            />
            <p className="font-bold text-xl md:text-2xl mt-2">{text.member2_name}</p>
            <p className="text-sm md:text-md font-mono opacity-70">CMM65080500275</p>
          </div>
        </div>
      </section>

      {/* Advisor Section */}
      <section className="flex flex-col items-center">
        <h2 className="text-center text-3xl md:text-4xl serif-font font-bold mb-10 italic bg-background inline-block px-4 pr-5 py-2 border-[4px] border-dark shadow-[4px_4px_0px_#D4B666]">
          {text.section_advisor}
        </h2>
        {/* ปรับขนาด w-full ใน Mobile และจำกัด max-w ใน Desktop */}
        <div className="flex flex-col items-center w-full max-w-[320px] group">
          <img
            src="/images/advisor.png"
            alt="Nuttapong Prasertsang"
            className="w-full aspect-square mb-4 object-cover border-[3px] border-dark shadow-[inset_0_0_0_4px_#FEF9C3,6px_6px_0px_#2C2C2C] group-hover:translate-y-[-5px] transition-transform"
          />
          <p className="font-bold text-xl md:text-2xl mt-2 text-center">
            {text.advisor_name}
          </p>
          <p className="text-sm md:text-md text-center font-mono whitespace-pre-line opacity-70">
            {text.advisor_position}
          </p>
        </div>
      </section>
    </main>
  );
}