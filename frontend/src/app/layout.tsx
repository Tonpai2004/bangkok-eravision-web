import type { Metadata } from "next";
// 1. Import จาก Google
import { Merriweather, Krub } from "next/font/google";
// 2. Import สำหรับฟอนต์ในเครื่อง (Local)
import localFont from 'next/font/local';
import "./globals.css"; 

import { LanguageProvider } from "@/context/LanguageContext";

// --- Setup Google Fonts ---
const merriweather = Merriweather({ 
  weight: ['300', '400', '700', '900'], 
  subsets: ["latin"],
  variable: '--font-merriweather',
  display: 'swap',
});

const krub = Krub({ 
  weight: ['300', '400', '500', '600', '700'], 
  subsets: ["thai", "latin"],
  variable: '--font-krub',
  display: 'swap',
});

// --- Setup Local Fonts ---
// หมายเหตุ: ตรวจสอบ path ไฟล์ให้ตรงกับที่คุณวางไว้ใน public/fonts/
const prachachon = localFont({
  src: '../../public/fonts/TS-Prachachon-NP.ttf',
  variable: '--font-prachachon',
  display: 'swap',
});

const pimdeed = localFont({
  src: '../../public/fonts/PSPimpdeedIINew.ttf', // แก้ชื่อไฟล์ให้ตรงกับที่มี
  variable: '--font-pimdeed',
  display: 'swap',
});

export const metadata: Metadata = {
  title: "Bangkok EraVision",
  description: "Experience 1960s Phra Nakhon through AI simulation.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      {/* 3. ใส่ Variable ทั้งหมดลงใน body */}
      <body className={`
        ${merriweather.variable} 
        ${krub.variable} 
        ${prachachon.variable} 
        ${pimdeed.variable}
        min-h-screen flex flex-col items-center antialiased overflow-x-hidden relative
      `}>
        
        {/* --- Global Background Texture (กระดาษเก่า) --- */}
        <div 
          className="fixed inset-0 -z-10 pointer-events-none opacity-20"></div>

        {/* Container หลัก */}
        <div className="w-full max-w-[1440px] flex flex-col items-center relative z-0">
          <LanguageProvider>
            {children}
          </LanguageProvider>
        </div>
      </body>
    </html>
  );
}