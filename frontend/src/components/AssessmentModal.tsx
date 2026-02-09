'use client';

interface AssessmentModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentLang: 'TH' | 'ENG';
}

export default function AssessmentModal({ isOpen, onClose, currentLang }: AssessmentModalProps) {
  if (!isOpen) return null;

  const fontClass = currentLang === 'ENG' ? 'font-merri' : 'font-krub';

  const content = {
    TH: {
      title: "ความพึงพอใจของคุณคือสิ่งสำคัญ",
      desc: "คำแนะนำของคุณจะเป็นส่วนสำคัญ\nที่จะทำให้วิทยานิพนธ์ฉบับนี้ให้สมบูรณ์ยิ่งขึ้น",
      btn_form: "ไปยังแบบประเมิน",
      btn_close: "ปิดหน้าต่าง"
    },
    ENG: {
      title: "Your Feedback Matters",
      desc: "Your feedback is vital for completing this thesis project.",
      btn_form: "Go to Assessment Form",
      btn_close: "Close"
    }
  };

  const text = content[currentLang];
  // ใส่ลิงก์ Google Form
  const GOOGLE_FORM_URL = "https://forms.gle/heekuytad"; 

  return (
    <>
      {/* 🎨 เพิ่ม CSS Keyframes สำหรับความสมูท */}
      <style jsx>{`
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes scaleUp {
          from { opacity: 0; transform: scale(0.9) translateY(20px); }
          to { opacity: 1; transform: scale(1) translateY(0); }
        }
        .animate-backdrop {
          animation: fadeIn 0.4s ease-out forwards;
        }
        .animate-modal {
          animation: scaleUp 0.5s cubic-bezier(0.165, 0.84, 0.44, 1) forwards;
        }
      `}</style>

      {/* Backdrop: ใช้ animate-backdrop */}
      <div 
        className="fixed inset-0 bg-black/90 z-[70] flex justify-center items-center p-4 animate-backdrop" 
        onClick={onClose}
      >
        {/* Modal Box: ใช้ animate-modal เพื่อให้มีการ "ลอยขึ้น" และ "ขยายออก" */}
        <div 
          className="bg-[#FFF8E7] p-8 max-w-lg w-full border-[4px] border-dark shadow-[10px_10px_0px_#C5A059] relative text-center animate-modal"
          onClick={e => e.stopPropagation()}
        >
          <h2 className={`font-krub text-3xl font-bold mb-4 text-dark italic uppercase tracking-tighter ${fontClass}`}>
              {text.title}
          </h2>
          <p className={`font-krub text-lg mb-8 leading-relaxed text-dark whitespace-pre-line ${fontClass}`}>
              {text.desc}
          </p>

          <a 
            href={GOOGLE_FORM_URL}
            target="_blank"
            rel="noopener noreferrer"
            className={`${fontClass} block w-full bg-gold text-dark py-4 font-bold border-2 border-dark hover:bg-yellow-400 transition-all uppercase tracking-widest mb-4 no-underline text-center`}
          >
            {text.btn_form}
          </a>

          <button 
            onClick={onClose}
            className={`${fontClass} w-full text-dark/60 hover:text-dark transition-colors font-bold uppercase tracking-widest text-sm`}
          >
            {text.btn_close}
          </button>
        </div>
      </div>
    </>
  );
}