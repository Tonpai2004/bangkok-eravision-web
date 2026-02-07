/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export', // 👈 บรรทัดนี้สำคัญมาก!
  images: { unoptimized: true }, // (แนะนำ: ป้องกันรูปไม่ขึ้น)
};
export default nextConfig;