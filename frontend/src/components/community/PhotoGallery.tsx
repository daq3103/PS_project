"use client";

import Image from "next/image";
import { useRef, useState } from "react";
import type { CommunityImageOut } from "@/lib/api-client";

export function PhotoGallery({ images, title }: { images: CommunityImageOut[]; title: string }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [index, setIndex] = useState(0);
  const [zoom, setZoom] = useState(false);
  const move = (offset: number) => { setIndex(old => (old + offset + images.length) % images.length); setZoom(false); };
  if (!images.length) return null;
  return <div className="mt-6">
    <p className="mb-2 text-sm text-ink-muted">Chạm vào ảnh để xem rõ hơn.</p>
    <div className="grid gap-3 sm:grid-cols-2">{images.map((image, position) => <button type="button" key={image.upload_id} aria-label={`Xem ảnh ${position + 1} của ${title}`} onClick={() => {
      setIndex(position); setZoom(false); dialog.current?.showModal();
    }} className="relative aspect-[4/3] overflow-hidden rounded-lg bg-forest/5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forest">
      <Image unoptimized src={image.url} alt={title} fill className="object-contain" sizes="(max-width: 768px) 100vw, 50vw" />
    </button>)}</div>
    <dialog ref={dialog} aria-label={`Ảnh của ${title}`} onClick={event => { if (event.target === event.currentTarget) dialog.current?.close(); }} onKeyDown={event => {
      if (event.key === "ArrowRight") { event.preventDefault(); move(1); }
      if (event.key === "ArrowLeft") { event.preventDefault(); move(-1); }
    }} className="m-auto h-[90dvh] max-h-[90dvh] w-[calc(100%_-_1rem)] max-w-5xl rounded-xl border-0 bg-paper p-3 text-ink backdrop:bg-black/80 sm:p-4">
      <div className="flex h-full min-h-0 flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-sm" aria-live="polite">Ảnh {index + 1} / {images.length}</span>
          <div className="flex gap-2"><button type="button" aria-pressed={zoom} onClick={() => setZoom(old => !old)} className="rounded-full border border-line px-3 py-2 text-sm">{zoom ? "Thu nhỏ" : "Phóng to"}</button>
            <button type="button" onClick={() => dialog.current?.close()} className="rounded-full bg-forest px-4 py-2 text-sm text-white">Đóng ảnh</button></div>
        </div>
        <div className="min-h-0 flex-1 overflow-auto rounded-lg bg-forest/5" key={`${index}-${zoom}`}>
          {/* Native image retains its full dimensions when zoomed and can be panned by scrolling. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={images[index].url} alt={`${title}, ảnh ${index + 1}`} draggable={false} className={zoom ? "mx-auto block h-auto w-[180%] max-w-none" : "h-full w-full object-contain"} />
        </div>
        {images.length > 1 && <div className="flex justify-between gap-3"><button type="button" onClick={() => move(-1)} className="rounded-full border border-line px-4 py-2 text-sm">← Ảnh trước</button><button type="button" onClick={() => move(1)} className="rounded-full border border-line px-4 py-2 text-sm">Ảnh tiếp →</button></div>}
      </div>
    </dialog>
  </div>;
}
