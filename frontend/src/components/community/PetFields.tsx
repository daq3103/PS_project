"use client";

import { useState } from "react";
import type { CommunityPostOwnerOut, PetOptions } from "@/lib/api-client";

const input = "mt-1 w-full rounded-sm border border-line bg-paper px-3 py-2 text-sm";

export function PetFields({ post, options }: { post: CommunityPostOwnerOut | null; options: PetOptions }) {
  const [species, setSpecies] = useState(post?.pet_type ?? "dog");
  const [breed, setBreed] = useState(post?.breed ?? "");
  const details = post?.pet_details;
  const traits = [
    ["coat_length", "Độ dài lông", options.coat_lengths],
    ["pattern", "Hoa văn lông", options.patterns],
    ["sex", "Giới tính", options.sexes],
    ["size", "Vóc dáng", options.sizes],
  ] as const;
  return <fieldset className="space-y-4 rounded-xl border border-line p-4">
    <legend className="px-2 font-medium">Đặc điểm của bé</legend>
    <p className="text-sm text-ink-muted">Điền những đặc điểm bạn biết để mọi người dễ nhận ra bé hơn.</p>
    <div className="grid gap-4 sm:grid-cols-2">
      <label>Loài<select aria-label="Loài" name="pet_type" value={species} onChange={event => {
        setSpecies(event.target.value as typeof species); setBreed("");
      }} className={input}><option value="dog">Chó</option><option value="cat">Mèo</option><option value="other">Khác</option></select></label>
      <label>Giống<input name="breed" list="pet-breed-options" maxLength={100} value={breed} onChange={event => setBreed(event.target.value)} placeholder="Chọn gợi ý hoặc nhập nếu biết" className={input} />
        <datalist id="pet-breed-options">{(options.breeds[species] ?? []).map(name => <option key={name} value={name} />)}</datalist>
      </label>
    </div>
    <fieldset><legend className="mb-2">Màu lông <span className="text-sm text-ink-muted">(có thể chọn nhiều màu)</span></legend>
      <div className="flex flex-wrap gap-2">{Object.entries(options.colors).map(([value, label]) => <label key={value} className="flex cursor-pointer items-center gap-2 rounded-full border border-line px-3 py-2 text-sm has-checked:border-forest has-checked:bg-forest/10">
        <input type="checkbox" name="colors" value={value} defaultChecked={details?.colors?.includes(value)} className="accent-forest" />{label}
      </label>)}</div>
    </fieldset>
    <label className="block">Mô tả thêm về màu lông<input name="color" maxLength={100} defaultValue={post?.color ?? ""} placeholder="Ví dụ: trắng ở ngực và bốn chân" className={input} /></label>
    <div className="grid gap-4 sm:grid-cols-2">{traits.map(([name, label, items]) => <label key={name}>{label}<select aria-label={label} name={name} defaultValue={details?.[name] && details[name] !== "unknown" ? details[name] : name === "size" ? post?.adoption_meta.size ?? "unknown" : "unknown"} className={input}>
      <option value="unknown">Chưa rõ</option>{Object.entries(items).map(([value, text]) => <option key={value} value={value}>{text}</option>)}
    </select></label>)}
      <label>Tuổi ước tính (tháng)<input type="number" min={0} max={480} name="age_months" defaultValue={details?.age_months ?? post?.adoption_meta.age_months ?? ""} className={input} /></label>
      <label>Cân nặng ước tính (kg)<input type="number" min={0.01} max={500} step="0.01" name="weight_kg" defaultValue={details?.weight_kg ?? ""} className={input} /></label>
    </div>
    <label className="block">Dấu hiệu nhận dạng<textarea aria-label="Dấu hiệu nhận dạng" name="markings" rows={2} maxLength={500} defaultValue={details?.markings ?? ""} placeholder="Ví dụ: đuôi cụt, tai trái khuyết, đeo vòng cổ đỏ…" className={input} /></label>
  </fieldset>;
}
