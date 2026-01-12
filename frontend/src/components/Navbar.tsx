'use client';
import Link from 'next/link';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import { useState } from 'react';
import { useLanguage } from '@/context/LanguageContext';

const NAV_TEXT = {
  TH: { home: "หน้าหลัก", map: "แผนที่", about: "เกี่ยวกับเรา" },
  ENG: { home: "Home", map: "Map", about: "About Us" }
};

export default function Navbar() {
  const pathname = usePathname();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isLangDropdownOpen, setIsLangDropdownOpen] = useState(false);
  
  // เรียกใช้ Context
  const { language, setLanguage } = useLanguage();
  const text = NAV_TEXT[language];

  const fontClass = language === 'ENG' ? 'font-merri' : 'font-krub';

  const isActive = (path: string) => 
    pathname === path ? "underline decoration-2 underline-offset-4" : "";

  const Logo = () => (
    <div className="logo select-none cursor-pointer">
       <Image 
         src="/images/headlogo.png" alt="Bangkok EraVision Logo" width={80} height={80} className="object-contain"
       />
    </div>
  );

  const handleSelectLang = (lang: 'TH' | 'ENG') => {
    setLanguage(lang);
    setIsLangDropdownOpen(false);
    setIsMobileMenuOpen(false);
  };

  return (
    <nav className="w-full text-dark font-serif md:mb-7 relative z-50">
      
      
      <div className={`hidden md:flex flex-col items-center w-full ${fontClass}`}>
        <div className="py-8"><Logo /></div>
        <div className="w-full border-y-[2px] border-dark flex justify-between items-center px-3 py-3 relative">
          <div className="flex gap-12 font-bold italic text-xl tracking-wide">
            <Link href="/" className={`${isActive('/')} hover:opacity-70 transition-opacity`}>
              {text.home}
            </Link>
            <Link href="/map" className={`${isActive('/map')} hover:opacity-70 transition-opacity`}>
              {text.map}
            </Link>
            <Link href="/about" className={`${isActive('/about')} hover:opacity-70 transition-opacity`}>
              {text.about}
            </Link>
          </div>

          <div className="relative">
            <button 
              onClick={() => setIsLangDropdownOpen(!isLangDropdownOpen)}
              className={`font-bold italic text-lg cursor-pointer hover:text-gray-600 select-none min-w-[60px] text-right flex items-center gap-2 ${fontClass}`}
            >
              {language} <span className={`text-sm ${fontClass}`}>▼</span>
            </button>

            {isLangDropdownOpen && (
              <div className={`absolute right-0 top-full mt-2 w-24 bg-background border-[2px] border-dark shadow-[4px_4px_0px_rgba(0,0,0,1)] flex flex-col z-50 ${fontClass}`}>
                <button onClick={() => handleSelectLang('TH')} className={`py-2 px-4 text-left hover:bg-gold hover:text-white transition-colors font-bold ${language === 'TH' ? 'bg-gray-200' : ''}`}>TH</button>
                <button onClick={() => handleSelectLang('ENG')} className={`py-2 px-4 text-left hover:bg-gold hover:text-white transition-colors font-bold ${language === 'ENG' ? 'bg-gray-200' : ''}`}>ENG</button>
                
              </div>
            )}
          </div>
        </div>
      </div>

      {/* --- Mobile Menu --- */}
      <div className="md:hidden">
        {/* Header: คลีนๆ ไม่มีเงา */}
        <div className="flex justify-between items-center py-5 border-b-2 border-dark relative z-20 bg-transparent">
          <Logo />
          <button title='hamburger menu' onClick={() => setIsMobileMenuOpen(true)} className="p-2 focus:outline-none hover:opacity-60 transition-opacity">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-dark" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
          </button>
        </div>

        {/* Overlay */}
        <div 
          className={`fixed inset-0 bg-black/60 backdrop-blur-sm z-40 transition-opacity duration-300 ${isMobileMenuOpen ? 'opacity-100 visible' : 'opacity-0 invisible'}`}
          onClick={() => setIsMobileMenuOpen(false)}
        ></div>

        {/* Sidebar Panel */}
        <div 
          className={`
            fixed top-0 right-0 h-full w-[75%] max-w-[300px] z-50 
            flex flex-col bg-[#FFF8E7]
            transition-transform duration-500 ease-in-out
            ${isMobileMenuOpen ? 'translate-x-0 shadow-[-10px_0px_30px_rgba(0,0,0,0.2)]' : 'translate-x-full shadow-none'}
          `}>

          <div 
              className="absolute inset-0 opacity-40 pointer-events-none z-0 mix-blend-multiply"
              style={{ 
                backgroundImage: "url('/images/grunge-paper-background.jpg')", 
                backgroundSize: 'cover',
                backgroundPosition: 'center'
            }}></div>

          {/* --- Contents --- */}
          <div className="relative z-10 w-full h-full flex flex-col">
              {/* ปุ่มปิด (X) */}
              <div className="flex justify-end p-5">
                <button title='x button' onClick={() => setIsMobileMenuOpen(false)} className="text-dark hover:rotate-90 transition-transform duration-300">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {/* รายการเมนู */}
              <div className="flex flex-col items-center gap-8 mt-4">
                <Link href="/" onClick={() => setIsMobileMenuOpen(false)} className={`${isActive('/')} text-2xl font-bold italic text-dark`}>
                  {text.home}
                </Link>
                <Link href="/map" onClick={() => setIsMobileMenuOpen(false)} className={`${isActive('/map')} text-2xl font-bold italic text-dark`}>
                  {text.map}
                </Link>
                <Link href="/about" onClick={() => setIsMobileMenuOpen(false)} className={`${isActive('/about')} text-2xl font-bold italic text-dark`}>
                  {text.about}
                </Link>

                <div className="w-1/2 h-[2px] bg-dark opacity-30"></div>
                
                <div className="flex gap-6">
                    <button onClick={() => handleSelectLang('TH')} className={`font-bold text-xl text-dark ${language === 'TH' ? 'underline decoration-gold decoration-4' : 'opacity-50'}`}>TH</button>
                    <span className="text-dark/50 text-xl">|</span>
                    <button onClick={() => handleSelectLang('ENG')} className={`font-bold text-xl text-dark ${language === 'ENG' ? 'underline decoration-gold decoration-4' : 'opacity-50'}`}>ENG</button>
                </div>
              </div>
          </div>
        </div>
      </div>
    </nav>
  );
}