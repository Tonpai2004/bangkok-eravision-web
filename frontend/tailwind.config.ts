import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    // แบบมี src (เผื่อคุณใช้)
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    
    // --- เพิ่มส่วนนี้เข้าไปครับ (แบบไม่มี src) ---
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    
    // เผื่อไฟล์วางอยู่หน้าบ้านสุด
    "./*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        // 1. ฟอนต์พาดหัวข่าว (TS-Prachachon)
        prachachon: ["var(--font-prachachon)", "serif"],
        
        // 2. ฟอนต์พิมพ์ดีด (PS Pimdeed)
        pimdeed: ["var(--font-pimdeed)", "monospace"],
        
        // 3. ฟอนต์อังกฤษ (Merriweather)
        merri: ["var(--font-merriweather)", "serif"],
        
        // 4. ฟอนต์ไทย (Krub)
        krub: ["var(--font-krub)", "sans-serif"],
      },
      colors: {
        background: "#F0EAD6",
        dark: "#2C2C2C",
        accent: "#D84335",
        gold: "#E3C565",
      },
    },
  },
  plugins: [],
};
export default config;