"use client";

import Link from "next/link";
import { useState } from "react";
import type { PetOptions } from "@/lib/api-client";

const input = "mt-1 block w-full min-w-0 rounded-lg border border-line bg-paper px-3 py-2 text-sm";
type Params = Record<string, string | undefined>;

export function FeedFilters({ params, options, provinces }: {
  params: Params; options: PetOptions; provinces: { id: number; name: string }[];
}) {
  const [species, setSpecies] = useState(params.pet_type ?? "");
  const [breed, setBreed] = useState(params.breed ?? "");
  const [colors, setColors] = useState((params.colors ?? "").split(",").filter(Boolean));
  const advanced = ["breed", "coat_length", "pattern", "sex", "size", "date_from", "date_to", "lifecycle_status"]
    .some(key => !!params[key] && params[key] !== "open");
  const reset = params.post_type ? `/tram-cuu-ho?post_type=${encodeURIComponent(params.post_type)}` : "/tram-cuu-ho";
  return <form action="/tram-cuu-ho" className="space-y-4 rounded-xl border border-line bg-surface p-4 md:p-5">
    <input type="hidden" name="post_type" value={params.post_type ?? ""} />
    <input type="hidden" name="colors" value={colors.join(",")} />
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <label className="min-w-0 text-sm sm:col-span-2">Tìm theo từ khóa<input type="search" name="q" maxLength={100} defaultValue={params.q ?? ""} placeholder="Ví dụ: mèo xám, ALN, vòng cổ đỏ…" className={input} /></label>
      <label className="min-w-0 text-sm">Loài<select aria-label="Loài" name="pet_type" value={species} onChange={event => { setSpecies(event.target.value); setBreed(""); }} className={input}><option value="">Tất cả</option><option value="dog">Chó</option><option value="cat">Mèo</option><option value="other">Khác</option></select></label>
      <label className="min-w-0 text-sm">Khu vực<select aria-label="Khu vực" name="province_id" defaultValue={params.province_id ?? ""} className={input}><option value="">Tất cả khu vực</option>{provinces.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
    </div>
    <fieldset><legend className="mb-2 text-sm">Màu lông</legend><div className="flex flex-wrap gap-2">{Object.entries(options.colors).map(([value, label]) => <label key={value} className="flex cursor-pointer items-center gap-2 rounded-full border border-line px-3 py-2 text-sm has-checked:border-forest has-checked:bg-forest/10">
      <input type="checkbox" checked={colors.includes(value)} onChange={event => setColors(old => event.target.checked ? [...old, value] : old.filter(c => c !== value))} className="accent-forest" />{label}
    </label>)}</div><p className="mt-2 text-xs text-ink-muted">Chọn nhiều màu để tìm bé có đủ các màu đó. Bỏ trống nếu chưa rõ.</p></fieldset>
    <details open={advanced || undefined} className="rounded-lg border border-line px-3 py-2">
      <summary className="cursor-pointer py-1 text-sm font-medium text-forest">Lọc thêm</summary>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <label className="min-w-0 text-sm">Giống<input name="breed" list="filter-breeds" value={breed} onChange={event => setBreed(event.target.value)} maxLength={100} placeholder="Chọn gợi ý hoặc nhập giống" className={input} />
          <datalist id="filter-breeds">{(species ? options.breeds[species] ?? [] : [...new Set(Object.values(options.breeds).flat())]).map(name => <option key={name} value={name} />)}</datalist>
        </label>
        {([
          ["coat_length", "Độ dài lông", options.coat_lengths], ["pattern", "Hoa văn lông", options.patterns],
          ["sex", "Giới tính", options.sexes], ["size", "Vóc dáng", options.sizes],
        ] as const).map(([key, label, entries]) => <label key={key} className="min-w-0 text-sm">{label}<select aria-label={label} name={key} defaultValue={params[key] ?? ""} className={input}><option value="">Tất cả</option>{Object.entries(entries).map(([value, text]) => <option key={value} value={value}>{text}</option>)}<option value="unknown">Chưa rõ</option></select></label>)}
        <label className="min-w-0 text-sm">Trạng thái<select aria-label="Trạng thái" name="lifecycle_status" defaultValue={params.lifecycle_status ?? "open"} className={input}><option value="open">Đang tìm / chờ nhận nuôi</option><option value="resolved">Đã đoàn tụ / nhận nuôi</option><option value="closed">Đã đóng</option><option value="expired">Hết hạn</option></select></label>
        <label className="min-w-0 text-sm">Từ ngày<input type="date" name="date_from" min="1900-01-01" max="2100-12-31" defaultValue={params.date_from ?? ""} className={input} /></label>
        <label className="min-w-0 text-sm">Đến ngày<input type="date" name="date_to" min="1900-01-01" max="2100-12-31" defaultValue={params.date_to ?? ""} className={input} /></label>
      </div>
      <p className="mt-3 text-xs text-ink-muted">Khoảng ngày áp dụng cho lần thấy cuối hoặc ngày nhặt được; tin nhận nuôi dùng ngày đăng. Tin chưa có ngày tương ứng sẽ không xuất hiện khi lọc.</p>
    </details>
    <div className="flex flex-wrap items-center gap-3"><button className="rounded-full bg-forest px-5 py-2 text-sm text-white">Tìm tin</button><Link href={reset} className="px-2 py-2 text-sm underline">Xóa bộ lọc</Link></div>
  </form>;
}
