'use client';
import Link from 'next/link';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import { useState } from 'react';
// Import Context
import { useLanguage } from '@/context/LanguageContext';

const NAV_TEXT = {
  TH: { home: "หน้าหลัก", map: "แผนที่", about: "เกี่ยวกับเรา" },
  ENG: { home: "Home", map: "Map", about: "About Us" }
};

// ลบ Interface Props เดิมออก
// interface NavbarProps { ... } 

export default function Navbar() {
  const pathname = usePathname();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isLangDropdownOpen, setIsLangDropdownOpen] = useState(false);
  
  // เรียกใช้ Context แทน Props
  const { language, setLanguage } = useLanguage();
  const text = NAV_TEXT[language];

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
    setLanguage(lang); // ใช้ setLanguage จาก Context
    setIsLangDropdownOpen(false);
    setIsMobileMenuOpen(false);
  };

  return (
    <nav className="w-full text-dark font-serif md:mb-7 relative z-50">
      
      {/* --- DESKTOP --- */}
      <div className="hidden md:flex flex-col items-center w-full">
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

          {/* Language Dropdown (Desktop) */}
          <div className="relative">
            <button 
              onClick={() => setIsLangDropdownOpen(!isLangDropdownOpen)}
              className="font-bold italic text-lg cursor-pointer hover:text-gray-600 select-none min-w-[60px] text-right flex items-center gap-2"
            >
              {language} <span className="text-sm">▼</span>
            </button>

            {isLangDropdownOpen && (
              <div className="absolute right-0 top-full mt-2 w-24 bg-background border-[2px] border-dark shadow-[4px_4px_0px_rgba(0,0,0,1)] flex flex-col z-50">
                <button 
                  onClick={() => handleSelectLang('ENG')}
                  className={`py-2 px-4 text-left hover:bg-gold hover:text-white transition-colors font-bold ${language === 'ENG' ? 'bg-gray-200' : ''}`}
                >
                  ENG
                </button>
                <button 
                  onClick={() => handleSelectLang('TH')}
                  className={`py-2 px-4 text-left hover:bg-gold hover:text-white transition-colors font-bold ${language === 'TH' ? 'bg-gray-200' : ''}`}
                >
                  TH
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* --- MOBILE --- */}
      <div className="md:hidden">
        <div className="flex justify-between items-center py-5 border-b-[2px] border-dark relative z-20 bg-background">
          <Logo />
          <button title='btn' onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)} className="p-2 focus:outline-none">
             <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-dark" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={isMobileMenuOpen ? "M6 18L18 6M6 6l12 12" : "M4 6h16M4 12h16M4 18h16"} />
              </svg>
          </button>
        </div>

        {/* Mobile Menu Dropdown */}
        <div className={`flex flex-col items-center gap-6 py-6 border-b-[2px] border-dark bg-background absolute w-full transition-all duration-300 ease-in-out origin-top z-10 ${isMobileMenuOpen ? 'opacity-100 top-full' : 'opacity-0 -top-[500px] pointer-events-none'}`}>
            <Link href="/" onClick={() => setIsMobileMenuOpen(false)} className={`${isActive('/')} text-xl font-bold italic`}>
              {text.home}
            </Link>
            <Link href="/map" onClick={() => setIsMobileMenuOpen(false)} className={`${isActive('/map')} text-xl font-bold italic`}>
              {text.map}
            </Link>
            <Link href="/about" onClick={() => setIsMobileMenuOpen(false)} className={`${isActive('/about')} text-xl font-bold italic`}>
              {text.about}
            </Link>
            
            <div className="pt-4 border-t border-gray-300 w-1/2 flex justify-center gap-6">
                <button 
                  onClick={() => handleSelectLang('ENG')}
                  className={`font-bold text-lg ${language === 'ENG' ? 'underline decoration-gold decoration-4' : 'opacity-50'}`}
                >
                  ENG
                </button>
                <span className="text-gray-400">|</span>
                <button 
                   onClick={() => handleSelectLang('TH')}
                   className={`font-bold text-lg ${language === 'TH' ? 'underline decoration-gold decoration-4' : 'opacity-50'}`}
                >
                  TH
                </button>
            </div>
        </div>
      </div>
    </nav>
  );
}