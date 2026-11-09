"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type CommunityPostCreateIn, type CommunityPostOwnerOut, type PetDetails, type PetOptions } from "@/lib/api-client";
import { Turnstile } from "./Turnstile";
import { canManagePlatform } from "@/lib/admin-navigation";
import { PetFields } from "./PetFields";

const input = "mt-1 w-full rounded-sm border border-line bg-paper px-3 py-2 text-sm";
type Upload = { upload_id: string; url: string };

export function PostForm({ editId, adoption = false, admin = false }: { editId?: string; adoption?: boolean; admin?: boolean }) {
  const router = useRouter();
  const [post, setPost] = useState<CommunityPostOwnerOut | null>(null);
  const [petOptions, setPetOptions] = useState<PetOptions | null>(null);
  const [locations, setLocations] = useState<{ id: number; name: string }[]>([]);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [kind, setKind] = useState("lost_pet");
  const [siteKey, setSiteKey] = useState("");
  const [token, setToken] = useState("");
  const [resetKey, setResetKey] = useState(0);
  const [requestKey, setRequestKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const [me, catalog, config, pets] = await Promise.all([api.me(), api.communityLocations(), api.communityConfig(), api.communityPetOptions()]);
        if (!me.user) { router.replace(`/login?next=${encodeURIComponent(window.location.pathname)}`); return; }
        if (!config.enabled) throw new Error("Trạm cứu hộ đang tạm ngưng");
        if (adoption && !canManagePlatform(me.user) && !me.user.staff_permissions?.includes("rescue_manage")) throw new Error("Bạn không có quyền đăng tin nhận nuôi");
        const item = editId ? (admin ? await api.adminCommunityPost(editId) : await api.getMyCommunityPost(editId)) : null;
        if (!active) return;
        setPost(item); setPetOptions(pets); setKind(item?.post_type ?? (adoption ? "adoption" : "lost_pet"));
        setUploads(item?.images ?? []); setLocations(catalog.provinces); setSiteKey(config.turnstile_site_key);
        setRequestKey(crypto.randomUUID()); setLoaded(true);
      } catch (e) { if (active) setError(e instanceof Error ? e.message : "Không tải được biểu mẫu"); }
    })();
    return () => { active = false; };
  }, [editId, adoption, admin, router]);

  async function upload(files: FileList | null) {
    if (!files) return;
    if (uploads.length + files.length > 5) { setError("Tối đa 5 ảnh"); return; }
    setUploading(true); setError("");
    try {
      for (const file of Array.from(files)) {
        if (file.size > 5 * 1024 * 1024) throw new Error("Mỗi ảnh tối đa 5 MB");
        const result = await api.uploadCommunityImage(file);
        setUploads(old => [...old, result]);
      }
    } catch (e) { setError(e instanceof Error ? e.message : "Không tải được ảnh"); }
    finally { setUploading(false); }
  }

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); if (busy || uploading) return;
    setBusy(true); setError("");
    const form = new FormData(e.currentTarget);
    const text = (name: string) => String(form.get(name) ?? "").trim();
    const nullable = (name: string) => text(name) || null;
    const province = locations.find(p => p.id === Number(text("province_id")));
    const event = text("event_at");
    const yesNo = (name: string) => text(name) === "" ? null : text(name) === "yes";
    const data: CommunityPostCreateIn = {
      idempotency_key: requestKey, post_type: kind as CommunityPostCreateIn["post_type"],
      title: text("title"), description: nullable("description"), pet_type: text("pet_type") as "dog" | "cat" | "other",
      breed: nullable("breed"), color: nullable("color"), province_id: province?.id ?? 0, province_name: province?.name ?? "",
      pet_details: {
        colors: form.getAll("colors").map(String),
        coat_length: text("coat_length") as PetDetails["coat_length"],
        pattern: text("pattern") as PetDetails["pattern"], sex: text("sex") as PetDetails["sex"],
        size: text("size") as PetDetails["size"],
        age_months: text("age_months") ? Number(text("age_months")) : null,
        weight_kg: text("weight_kg") ? Number(text("weight_kg")) : null, markings: nullable("markings"),
      },
      district_name: nullable("district_name"), ward_name: nullable("ward_name"), location_detail: nullable("location_detail"),
      contact_phone: text("contact_phone"), contact_zalo: nullable("contact_zalo"), contact_facebook: nullable("contact_facebook"),
      last_seen_at: kind === "lost_pet" && event ? new Date(event).toISOString() : null,
      found_at: kind === "found_pet" && event ? new Date(event).toISOString() : null,
      image_upload_ids: uploads.map(u => u.upload_id), turnstile_token: token || undefined,
      adoption_meta: kind === "adoption" ? { age_months: text("age_months") ? Number(text("age_months")) : null,
        size: text("size") as "small" | "medium" | "large" | "unknown", vaccinated: yesNo("vaccinated"), neutered: yesNo("neutered"),
        health: nullable("health"), requirements: nullable("requirements") } : undefined,
    };
    try {
      if (post) {
        const { idempotency_key: _key, turnstile_token: _token, post_type: _type, ...values } = data;
        if (admin) await api.adminUpdateCommunityPost(post.id, { ...values, version: post.version });
        else await api.updateCommunityPost(post.id, { ...values, version: post.version });
      } else if (adoption) await api.adminCreateAdoptionPost(data);
      else await api.createCommunityPost(data);
      if (adoption || admin) { router.push("/admin/community"); router.refresh(); }
      else window.location.assign(`/account/community?${post ? "updated" : "created"}=1`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không lưu được tin"); setToken(""); setResetKey(v => v + 1);
      // Preserve key for an identical network retry. A changed form gets a new key through onChange below.
    } finally { setBusy(false); }
  }
  if (!loaded) return <div className="p-6"><p role="status">{error || "Đang tải…"}</p><Link href="/login" className="text-forest underline">Đăng nhập</Link></div>;
  return <form onSubmit={submit} onChange={() => setRequestKey(crypto.randomUUID())} className="mx-auto max-w-2xl space-y-5">
    <h1 className="font-display text-3xl text-forest">{post ? "Sửa tin cứu hộ" : adoption ? "Đăng tin nhận nuôi" : "Đăng tin cứu hộ"}</h1>
    <p className="text-sm text-ink-muted">{adoption ? "Mỗi tin dành cho một bé. Hồ sơ nhận nuôi được quản lý riêng." : "Tin sẽ hiển thị sau khi được duyệt. Sửa nội dung sẽ cần duyệt lại."}</p>
    {error && <p role="alert" className="text-danger">{error}</p>}
    {!adoption && !post && <label className="block">Loại tin<select className={input} value={kind} onChange={e => setKind(e.target.value)}><option value="lost_pet">Tìm thú cưng thất lạc</option><option value="found_pet">Tìm chủ cho bé nhặt được</option></select></label>}
    <label className="block">Tiêu đề<input name="title" required minLength={5} maxLength={255} defaultValue={post?.title} className={input} /></label>
    <label className="block">Mô tả<textarea name="description" rows={4} maxLength={3000} defaultValue={post?.description ?? ""} className={input} /></label>
    {petOptions && <PetFields post={post} options={petOptions} />}
    <label className="block">Khu vực<select name="province_id" required defaultValue={post?.province_id ?? ""} className={input}><option value="">Chọn khu vực</option>{locations.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
    <div className="grid gap-4 sm:grid-cols-2"><label>Khu vực chi tiết<input name="district_name" maxLength={100} defaultValue={post?.district_name ?? ""} className={input} /></label><label>Phường / xã<input name="ward_name" maxLength={100} defaultValue={post?.ward_name ?? ""} className={input} /></label></div>
    <label className="block">Địa điểm công khai<input name="location_detail" maxLength={500} defaultValue={post?.location_detail ?? ""} className={input} /><span className="text-xs text-ink-muted">Chỉ nhập địa điểm bạn muốn công khai trên bài.</span></label>
    {kind !== "adoption" && <label className="block">{kind === "lost_pet" ? "Lần thấy cuối" : "Thời điểm nhặt được"}<input type="datetime-local" name="event_at" className={input} defaultValue={localDate(post?.last_seen_at ?? post?.found_at)} /></label>}
    {kind === "adoption" && <fieldset className="space-y-4 rounded-sm border border-line p-4"><legend>Thông tin nhận nuôi</legend>
      {(["vaccinated", "neutered"] as const).map(name => <label key={name} className="block">{name === "vaccinated" ? "Tiêm phòng" : "Triệt sản"}<select name={name} defaultValue={post?.adoption_meta[name] == null ? "" : post.adoption_meta[name] ? "yes" : "no"} className={input}><option value="">Chưa biết</option><option value="yes">Đã thực hiện</option><option value="no">Chưa thực hiện</option></select></label>)}
      <label className="block">Sức khỏe<textarea name="health" maxLength={1000} defaultValue={post?.adoption_meta.health ?? ""} className={input} /></label>
      <label className="block">Điều kiện nhận nuôi<textarea name="requirements" maxLength={1000} defaultValue={post?.adoption_meta.requirements ?? ""} className={input} /></label>
    </fieldset>}
    <label className="block">Điện thoại<input name="contact_phone" type="tel" required pattern="\+?[0-9]{9,15}" defaultValue={post?.contact_phone} className={input} /></label>
    <label className="block">Zalo<input name="contact_zalo" type="tel" maxLength={20} defaultValue={post?.contact_zalo ?? ""} className={input} /></label>
    <label className="block">Facebook<input name="contact_facebook" type="url" maxLength={255} placeholder="https://www.facebook.com/..." defaultValue={post?.contact_facebook ?? ""} className={input} /></label>
    <label className="block">Ảnh ({uploads.length}/5)<input type="file" accept="image/jpeg,image/png,image/webp" multiple disabled={uploading || busy || uploads.length >= 5} onChange={e => void upload(e.target.files)} className={input} /></label>
    <p className="text-sm text-ink-muted">Nên có ảnh rõ mặt, toàn thân và dấu hiệu đặc biệt. Ảnh đầu tiên sẽ làm ảnh đại diện.</p>
    <div className="flex flex-wrap gap-3">{uploads.map((u, index) => <div key={u.upload_id} className="w-28 space-y-1"><img src={u.url} alt={`Ảnh đính kèm ${index + 1}`} className="h-24 w-28 rounded-sm object-cover" />
      {index === 0 ? <span className="block text-xs text-forest">Ảnh đại diện</span> : <button type="button" disabled={busy || uploading} onClick={() => { setUploads(old => [u, ...old.filter(i => i.upload_id !== u.upload_id)]); setRequestKey(crypto.randomUUID()); }} className="block text-xs text-forest underline">Làm ảnh đại diện</button>}
      <button type="button" disabled={busy || uploading} onClick={() => { setUploads(old => old.filter(i => i.upload_id !== u.upload_id)); setRequestKey(crypto.randomUUID()); }} className="text-sm text-danger">Xóa ảnh</button></div>)}</div>
    {!post && !adoption && <Turnstile siteKey={siteKey} onToken={setToken} resetKey={resetKey} />}
    <button disabled={busy || uploading || (!post && !adoption && !!siteKey && !token)} className="rounded-full bg-forest px-6 py-3 text-white disabled:opacity-50">{uploading ? "Đang tải ảnh…" : busy ? "Đang lưu…" : "Lưu tin"}</button>
  </form>;
}

function localDate(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}
