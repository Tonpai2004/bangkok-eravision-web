'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

type Language = 'TH' | 'ENG';

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>('ENG');

  // 1. โหลดภาษาเดิมจากความจำเครื่อง (ถ้ามี)
  useEffect(() => {
    const saved = localStorage.getItem('app-language');
    if (saved === 'TH' || saved === 'ENG') {
      setLanguage(saved);
    }
  }, []);

  // 2. ฟังก์ชันเปลี่ยนภาษาพร้อมบันทึก
  const handleSetLanguage = (lang: Language) => {
    setLanguage(lang);
    localStorage.setItem('app-language', lang);
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage: handleSetLanguage }}>
      {children}
    </LanguageContext.Provider>
  );
}

// Hook สำหรับเรียกใช้ในหน้าอื่นๆ
export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
}