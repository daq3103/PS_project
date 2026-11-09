"use client";

import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { SOCIAL_CHANNELS, SOCIAL_LINKS } from "@/config/social-links";
import { BRAND } from "@/lib/brand";
import { SocialIcon } from "./SocialIcon";

const tabs = [{ id: "contact", label: "Liên hệ" }, { id: "social", label: "Mạng xã hội" }] as const;
type Tab = typeof tabs[number]["id"];

export function ContactWidget() {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("contact");
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const tabButtons = useRef<(HTMLButtonElement | null)[]>([]);

  function close(restoreFocus = false) {
    setOpen(false);
    if (restoreFocus) trigger.current?.focus();
  }

  useEffect(() => {
    if (!open) return;
    root.current?.querySelector<HTMLButtonElement>('[role="tab"][aria-selected="true"]')?.focus();
    function outside(event: PointerEvent) {
      if (event.target instanceof Node && !root.current?.contains(event.target)) setOpen(false);
    }
    function escape(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") { setOpen(false); trigger.current?.focus(); }
    }
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", escape); };
  }, [open]);

  function changeTab(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const next = event.key === "ArrowRight" ? (index + 1) % tabs.length : event.key === "ArrowLeft" ? (index + tabs.length - 1) % tabs.length : event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : -1;
    if (next < 0) return;
    event.preventDefault(); setTab(tabs[next].id); tabButtons.current[next]?.focus();
  }

  return <div ref={root} className="fixed right-4 z-40 flex flex-col items-end gap-3 md:right-6" style={{ bottom: "max(1rem, env(safe-area-inset-bottom))" }}>
    {open && <section id={`${id}-panel`} role="dialog" aria-modal="false" aria-labelledby={`${id}-title`} className="max-h-[calc(100dvh-6.5rem)] w-[calc(100vw-2rem)] max-w-[340px] overflow-y-auto overscroll-contain rounded-3xl border border-line bg-surface shadow-[0_16px_60px_-16px_rgba(18,50,40,0.35)]">
      <div className="relative overflow-hidden bg-forest px-5 pb-5 pt-5 text-white">
        <span aria-hidden="true" className="pointer-events-none absolute -right-5 -top-8 h-28 w-28 rounded-full border-[20px] border-white/5" />
        <div className="relative flex items-start justify-between gap-4">
          <div><p className="text-[11px] font-semibold uppercase tracking-[.18em] text-white/65">Gần nhau hơn một chút</p><h2 id={`${id}-title`} className="mt-2 font-display text-2xl">Kết nối với {BRAND.name}</h2></div>
          <button type="button" aria-label="Đóng bảng liên hệ" onClick={() => close(true)} className="-mr-1 -mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-white/75 hover:bg-white/10 hover:text-white"><CloseIcon /></button>
        </div>
        <p className="relative mt-2 text-sm leading-relaxed text-white/75">Bạn cần hỗ trợ? Chọn kênh phù hợp nhé.</p>
      </div>
      <div className="p-4">
        <div role="tablist" aria-label="Cách kết nối" className="grid grid-cols-2 gap-1 rounded-full bg-paper p-1">
          {tabs.map((item, index) => <button key={item.id} ref={element => { tabButtons.current[index] = element; }} id={`${id}-${item.id}-tab`} role="tab" type="button" aria-selected={tab === item.id} aria-controls={`${id}-${item.id}-content`} tabIndex={tab === item.id ? 0 : -1} onClick={() => setTab(item.id)} onKeyDown={event => changeTab(event, index)} className={`rounded-full px-3 py-2 text-sm font-semibold transition ${tab === item.id ? "bg-surface text-forest shadow-sm" : "text-ink-muted hover:text-forest"}`}>{item.label}</button>)}
        </div>
        {tabs.map(item => <div key={item.id} id={`${id}-${item.id}-content`} role="tabpanel" aria-labelledby={`${id}-${item.id}-tab`} hidden={tab !== item.id} tabIndex={0} className="mt-3 max-h-[min(42dvh,320px)] space-y-2 overflow-y-auto rounded-xl">
          {SOCIAL_CHANNELS.filter(channel => item.id === "contact" ? channel.contact : channel.id !== "zalo").map(channel => <a key={channel.id} href={SOCIAL_LINKS[channel.id]} target="_blank" rel="noopener noreferrer" className="group flex min-h-16 items-center gap-3 rounded-2xl border border-line/70 p-3 transition hover:border-moss/40 hover:bg-paper">
            <SocialIcon channel={channel.id} /><span className="min-w-0 flex-1"><span className="block text-sm font-semibold text-ink">{channel.label}</span><span className="mt-0.5 block text-xs leading-relaxed text-ink-muted">{channel.description}</span></span><span aria-hidden="true" className="pr-1 text-moss transition group-hover:-translate-y-0.5 group-hover:translate-x-0.5">↗</span><span className="sr-only"> (mở trong tab mới)</span>
          </a>)}
        </div>)}
        <p className="mt-4 text-center text-[11px] text-ink-muted">Cùng chăm sóc, cùng sẻ chia.</p>
      </div>
    </section>}
    <button ref={trigger} type="button" aria-label={open ? "Thu gọn liên hệ" : "Liên hệ PetHome"} aria-expanded={open} aria-controls={`${id}-panel`} onClick={() => setOpen(value => !value)} className="flex h-14 min-w-14 items-center justify-center gap-2.5 rounded-full border border-white/25 bg-forest px-4 text-white shadow-[0_6px_24px_rgba(26,69,53,0.28)] transition hover:bg-forest-deep motion-safe:hover:-translate-y-0.5 md:px-5">
      {open ? <CloseIcon /> : <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" className="h-6 w-6"><path strokeLinecap="round" strokeLinejoin="round" d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5h-3L4 22v-6a7.5 7.5 0 0 1 1-12 8.6 8.6 0 0 1 15 7.5Z" /><path strokeLinecap="round" d="M8 10h.01M12 10h.01M16 10h.01" /></svg>}
      <span className="hidden text-sm font-semibold md:inline">{open ? "Thu gọn" : "Liên hệ"}</span>
    </button>
  </div>;
}

function CloseIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5"><path strokeLinecap="round" d="m6 6 12 12M18 6 6 18" /></svg>;
}
