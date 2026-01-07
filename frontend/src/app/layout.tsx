import type { Metadata } from "next";
// Import Google Fonts
import { Courier_Prime, Playfair_Display } from "next/font/google";
// *** บรรทัดนี้สำคัญที่สุด! ห้ามลืม ***
import "./globals.css"; 

// เพิ่ม Provider จาก Classifier
import { LanguageProvider } from "@/context/LanguageContext";

// Setup Fonts
const courier = Courier_Prime({ 
  weight: ['400', '700'], 
  subsets: ["latin"],
  variable: '--font-courier',
  display: 'swap',
});

const playfair = Playfair_Display({ 
  weight: ['400', '700', '900'], 
  subsets: ["latin"],
  variable: '--font-playfair',
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
    <html lang="en" className={`${courier.variable} ${playfair.variable}`}>
      <body className="min-h-screen flex flex-col items-center antialiased overflow-x-hidden">
        {/* Container หลักเพื่อคุมความกว้างให้เหมือน Design */}
        <div className="w-full max-w-[1440px] flex flex-col items-center">
          {/* ครอบด้วย LanguageProvider */}
          <LanguageProvider>
            {children}
          </LanguageProvider>
        </div>
      </body>
    </html>
  );
}