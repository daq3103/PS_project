import type { SocialChannel } from "@/config/social-links";

const backgrounds = { zalo: "bg-[#eaf3ff] text-[#0068ff]", facebook: "bg-[#edf3ff] text-[#1877f2]", tiktok: "bg-ink text-white" };

export function SocialIcon({ channel, compact = false }: { channel: SocialChannel; compact?: boolean }) {
  return <span aria-hidden="true" className={`inline-flex shrink-0 items-center justify-center rounded-xl ${compact ? "h-9 w-9" : "h-11 w-11"} ${backgrounds[channel]}`}>
    {channel === "zalo" ? <svg viewBox="0 0 32 32" className="h-8 w-8" fill="none">
      <path d="M6 8.5A3.5 3.5 0 0 1 9.5 5h13A3.5 3.5 0 0 1 26 8.5v11a3.5 3.5 0 0 1-3.5 3.5H13l-5.5 4v-5A3.5 3.5 0 0 1 6 19.5z" fill="currentColor" />
      <text x="16" y="17.2" fill="white" fontSize="8.5" fontWeight="700" fontFamily="Arial, sans-serif" textAnchor="middle">Zalo</text>
    </svg> : channel === "facebook" ? <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor"><path d="M14.2 22v-9.1h3.1l.5-3.6h-3.6V7c0-1 .3-1.7 1.8-1.7h1.9V2.1a25 25 0 0 0-2.8-.1c-2.8 0-4.7 1.7-4.7 4.8v2.5H7.2v3.6h3.2V22z" /></svg>
      : <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor"><path d="M16.7 2c.2 2.2 1.4 3.5 3.6 3.7v3.1a8.5 8.5 0 0 1-3.6-1.1v7.1a6 6 0 1 1-5.2-5.9v3.2a2.8 2.8 0 1 0 2 2.7V2z" /></svg>}
  </span>;
}
