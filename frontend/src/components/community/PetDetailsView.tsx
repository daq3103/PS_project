import type { CommunityPostPublicOut, PetOptions } from "@/lib/api-client";

export function PetDetailsView({ post, options }: { post: CommunityPostPublicOut; options: PetOptions }) {
  const pet = post.pet_details;
  const fields = [
    ["Giống", post.breed],
    ["Màu lông", pet?.colors?.map(color => options.colors[color]).filter(Boolean).join(", ")],
    ["Hoa văn lông", options.patterns[pet?.pattern]],
    ["Độ dài lông", options.coat_lengths[pet?.coat_length]],
    ["Giới tính", options.sexes[pet?.sex]],
    ["Vóc dáng", options.sizes[pet?.size] ?? options.sizes[post.adoption_meta.size]],
    ["Tuổi ước tính", (pet?.age_months ?? post.adoption_meta.age_months) == null ? null : `${pet?.age_months ?? post.adoption_meta.age_months} tháng`],
    ["Cân nặng ước tính", pet?.weight_kg == null ? null : `${pet.weight_kg.toLocaleString("vi-VN")} kg`],
  ];
  return <section className="mt-6 rounded-xl border border-line p-4">
    <h2 className="font-medium text-forest">Đặc điểm nhận dạng</h2>
    <dl className="mt-3 grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">{fields.map(([label, value]) => <div key={label}><dt className="text-ink-muted">{label}</dt><dd className="mt-1 break-words text-ink">{value || "Chưa rõ"}</dd></div>)}</dl>
    {post.color && <p className="mt-4 whitespace-pre-wrap break-words text-sm">Mô tả màu lông: {post.color}</p>}
    {pet?.markings && <p className="mt-3 whitespace-pre-wrap break-words text-sm"><span className="font-medium">Dấu hiệu đặc biệt: </span>{pet.markings}</p>}
  </section>;
}
