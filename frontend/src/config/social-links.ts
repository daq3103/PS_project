// Thay các URL mẫu bằng kênh chính thức của PetHome tại đây.
// Zalo: https://zalo.me/84xxxxxxxxx
// Facebook: https://www.facebook.com/ten-trang hoặc https://m.me/ten-trang
// TikTok: https://www.tiktok.com/@ten-tai-khoan
export const SOCIAL_LINKS = {
  zalo: "https://zalo.me/",
  facebook: "https://www.facebook.com/",
  tiktok: "https://www.tiktok.com/",
} as const;

export type SocialChannel = keyof typeof SOCIAL_LINKS;

export const SOCIAL_CHANNELS: { id: SocialChannel; label: string; description: string; contact: boolean }[] = [
  { id: "zalo", label: "Zalo", description: "Trao đổi và nhận hỗ trợ", contact: true },
  { id: "facebook", label: "Facebook", description: "Kết nối và gửi lời nhắn", contact: true },
  { id: "tiktok", label: "TikTok", description: "Khám phá những câu chuyện thú cưng", contact: false },
];
