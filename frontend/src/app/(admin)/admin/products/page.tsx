"use client";
import { DeleteRecordButton } from "@/components/admin/DeleteRecordButton";
import { ValidatedForm } from "@/components/ValidatedForm";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  api,
  type CategoryDto,
  type ProductDto,
  type ProductImageOut,
  type ProductImageUpdateIn,
  type ProductUpdateIn,
  type VariantCreateIn,
  type VariantDto,
  type VariantCreateIn as VariantCreateInType,
} from "@/lib/api-client";
import { formatVnd } from "@/lib/format";
import { DataTable, type Column } from "@/components/admin/DataTable";
import { Drawer } from "@/components/admin/Drawer";
import { FilterBar, FilterField } from "@/components/admin/FilterBar";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { CategoryCreateForm } from "@/components/admin/CategoryCreateForm";
import { slugify } from "@/lib/slugify";

const PET_OPTIONS = [
  { value: "both", label: "Chó & mèo" },
  { value: "dog", label: "Chó" },
  { value: "cat", label: "Mèo" },
];

export default function AdminProductsPage() {
  const [products, setProducts] = useState<ProductDto[]>([]);
  const [categories, setCategories] = useState<CategoryDto[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [selected, setSelected] = useState<ProductDto | null>(null);
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const qs = new URLSearchParams();
      qs.set("limit", "200");
      if (statusFilter) qs.set("status", statusFilter);
      if (categoryFilter) qs.set("category_id", categoryFilter);
      if (q.trim()) qs.set("q", q.trim());
      const [prods, cats] = await Promise.all([
        api.adminListProducts(qs.toString()),
        api.adminListCategories(),
      ]);
      setProducts(prods);
      setCategories(cats);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không tải được sản phẩm");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, categoryFilter, q]);

  useEffect(() => {
    void load();
  }, [load]);

  const categoryMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const c of categories) map.set(c.id, c.name);
    return map;
  }, [categories]);

  async function setProductStatus(id: string, next: "active" | "hidden" | "draft") {
    try {
      await api.updateProduct(id, { status: next });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Cập nhật thất bại");
    }
  }

  const columns: Column<ProductDto>[] = [
    { key: "delete", header: "", cell: (p) => <DeleteRecordButton kind="products" id={p.id} onDeleted={load} /> },
    {
      key: "image",
      header: "",
      width: "w-16",
      cell: (p) => {
        const src = p.images?.[0]?.r2_url;
        return src ? (
          <img src={src} alt="" className="h-12 w-12 rounded-sm object-cover" />
        ) : (
          <div className="flex h-12 w-12 items-center justify-center rounded-sm bg-line text-xs text-ink-muted">
            —
          </div>
        );
      },
    },
    {
      key: "name",
      header: "Sản phẩm",
      cell: (p) => (
        <div>
          <p className="font-medium">{p.name}</p>

        </div>
      ),
    },
    {
      key: "category",
      header: "Danh mục",
      cell: (p) => categoryMap.get(p.category_id) ?? "—",
    },
    {
      key: "price",
      header: "Giá",
      cell: (p) => {
        const prices = p.variants.filter((v) => v.is_active).map((v) => v.price);
        if (!prices.length) return "—";
        const min = Math.min(...prices);
        const max = Math.max(...prices);
        return min === max ? formatVnd(min) : `${formatVnd(min)} - ${formatVnd(max)}`;
      },
    },
    {
      key: "stock",
      header: "Tồn",
      align: "right",
      cell: (p) => p.variants.reduce((sum, v) => sum + (v.cached_available_qty ?? 0), 0),
    },
    {
      key: "status",
      header: "Trạng thái",
      cell: (p) => <StatusBadge status={p.status} />,
    },
    {
      key: "actions",
      header: "",
      cell: (p) => (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setSelected(p)}
            className="rounded-full border border-forest px-3 py-1 text-xs text-forest hover:bg-forest/8"
          >
            Sửa
          </button>
          {p.status !== "active" ? (
            <button
              type="button"
              onClick={() => void setProductStatus(p.id, "active")}
              className="rounded-full border border-forest px-3 py-1 text-xs text-forest hover:bg-forest/8"
            >
              Hiện
            </button>
          ) : (
            <button
              type="button"
              onClick={() => void setProductStatus(p.id, "hidden")}
              className="rounded-full border border-line px-3 py-1 text-xs text-ink-muted hover:border-honey hover:text-honey"
            >
              Ẩn
            </button>
          )}
          <Link
            href={`/p/${p.slug}`}
            target="_blank"
            className="rounded-full px-3 py-1 text-xs text-moss hover:underline"
          >
            Xem
          </Link>
        </div>
      ),
    },
  ];

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl text-forest">Sản phẩm</h1>
          <p className="mt-1 text-sm text-ink-muted">Tạo danh mục, thêm sản phẩm, rồi hoàn thiện hình ảnh và tồn kho.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/admin/categories" className="rounded-full border border-forest px-4 py-2 text-sm font-medium text-forest hover:bg-forest/5">Quản lý danh mục</Link>
          <button type="button" onClick={() => setCreating(true)} className="rounded-full bg-forest px-4 py-2 text-sm font-medium text-white hover:bg-forest-deep">+ Thêm sản phẩm</button>
        </div>
      </div>

      <FilterBar>
        <FilterField label="Tìm kiếm">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onBlur={() => void load()}
            onKeyDown={(e) => e.key === "Enter" && void load()}
            placeholder="Tên, tên trong đường dẫn hoặc mã hàng"
            className="w-56 rounded-sm border border-line bg-paper px-2 py-1.5"
          />
        </FilterField>
        <FilterField label="Danh mục">
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="rounded-sm border border-line bg-paper px-2 py-1.5"
          >
            <option value="">Tất cả</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </FilterField>
        <FilterField label="Trạng thái">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-sm border border-line bg-paper px-2 py-1.5"
          >
            <option value="">Tất cả</option>
            <option value="active">Hiện</option>
            <option value="hidden">Ẩn</option>
            <option value="draft">Nháp</option>
          </select>
        </FilterField>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-full border border-forest px-4 py-1.5 text-sm text-forest hover:bg-forest/8"
        >
          Làm mới
        </button>
      </FilterBar>

      {error && <p className="mt-4 text-sm text-danger">{error}</p>}

      <div className="mt-4"><DataTable columns={columns} rows={products} keyExtractor={(p) => p.id} onRowClick={setSelected} rowAriaLabel={(p) => `Mở chi tiết sản phẩm ${p.name}`} loading={loading} empty={q || statusFilter || categoryFilter ? "Không có sản phẩm phù hợp với bộ lọc." : categories.length ? "Chưa có sản phẩm. Bấm Thêm sản phẩm để tạo mới." : "Hãy tạo danh mục trước, rồi thêm sản phẩm."} /></div>

      {creating && <Drawer open onClose={() => setCreating(false)} title="Thêm sản phẩm" width="max-w-2xl">
        <CreateProductForm categories={categories} onCategoryCreated={load} onCreated={(product) => { setCreating(false); setSelected(product); void load(); }} />
      </Drawer>}

      {selected && (
        <ProductEditDrawer
          product={selected}
          categories={categories}
          onClose={() => setSelected(null)}
          onSaved={load}
        />
      )}
    </div>
  );
}

function CreateProductForm({
  categories,
  onCategoryCreated,
  onCreated,
}: {
  categories: CategoryDto[];
  onCategoryCreated: () => Promise<void>;
  onCreated: (product: ProductDto) => void;
}) {
  const [categoryId, setCategoryId] = useState("");
  const [showCategoryForm, setShowCategoryForm] = useState(false);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);
  const [brand, setBrand] = useState("");
  const [petType, setPetType] = useState<"dog" | "cat" | "both">("both");
  const [status, setStatus] = useState<"draft" | "active" | "hidden">("draft");
  const [shortDesc, setShortDesc] = useState("");
  const [sku, setSku] = useState("");
  const [variantTitle, setVariantTitle] = useState("Mặc định");
  const [unit, setUnit] = useState("cái");
  const [price, setPrice] = useState("");
  const [weight, setWeight] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const activeCategories = categories;
  const selectedCategoryId = activeCategories.some((category) => category.id === categoryId)
    ? categoryId : activeCategories[0]?.id ?? "";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      if (!selectedCategoryId) throw new Error("Hãy tạo danh mục trước khi thêm sản phẩm.");
      if (!slug.trim() && !slugify(name)) throw new Error("Tên sản phẩm cần có chữ hoặc số.");
      if (!unit.trim()) throw new Error("Hãy nhập đơn vị bán và nhập kho.");
      if (Number(price) < 0 || Number(weight) <= 0) throw new Error("Kiểm tra lại giá và cân nặng.");
      const product = await api.createProduct({
        category_id: selectedCategoryId,
        name: name.trim(),
        slug: slug.trim() || slugify(name),
        brand: brand.trim() || null,
        pet_type: petType,
        status,
        short_description: shortDesc.trim() || null,
        has_expiry: false,
        variants: [
          {
            sku: sku.trim() || `SKU-${Date.now()}`,
            title: variantTitle.trim() || "Mặc định",
            options: { unit: unit.trim() },
            price: Number(price),
            weight_grams: Number(weight),
            is_active: true,
          },
        ],
      });
      setName("");
      setSlug("");
      setBrand("");
      setShortDesc("");
      setSku("");
      setUnit("cái");
      setPrice("");
      setWeight("");
      onCreated(product);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tạo sản phẩm thất bại");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <p className="text-sm text-ink-muted">Sản phẩm mới lưu ở bản nháp. Sau khi tạo, thêm ảnh và kiểm tra tồn kho trước khi cho hiển thị.</p>
      <button type="button" onClick={() => setShowCategoryForm(value => !value)} className="mt-3 text-left text-sm font-medium text-forest underline underline-offset-2">{showCategoryForm ? "Đóng tạo danh mục" : "+ Tạo danh mục mới"}</button>
      {showCategoryForm && <div className="mt-3 rounded-lg border border-line bg-paper p-3"><CategoryCreateForm sortOrder={Math.max(-1, ...categories.map(c => c.sort_order)) + 1} onCreated={async category => { await onCategoryCreated(); setCategoryId(category.id); setShowCategoryForm(false); }} /></div>}
      <ValidatedForm onSubmit={submit}>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="text-sm sm:col-span-2">
          <span className="text-ink-muted">Danh mục</span>
          <select
            value={selectedCategoryId}
            onChange={(e) => setCategoryId(e.target.value)}
            required
            className="mt-1 block w-full rounded-sm border border-line bg-paper px-2 py-1.5"
          >
            {!activeCategories.length && <option value="">Chưa có danh mục</option>}
            {activeCategories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <Field
          label="Tên sản phẩm"
          value={name}
          onChange={(v) => {
            setName(v);
            if (!slugEdited) setSlug(slugify(v));
          }}
          required
        />
        <Field label="Tên trong đường dẫn" value={slug} onChange={value => { setSlug(value); setSlugEdited(Boolean(value)); }} />
        <Field label="Thương hiệu" value={brand} onChange={setBrand} />
        <label className="text-sm">
          <span className="text-ink-muted">Loại thú</span>
          <select
            value={petType}
            onChange={(e) => setPetType(e.target.value as typeof petType)}
            className="mt-1 block w-full rounded-sm border border-line bg-paper px-2 py-1.5"
          >
            {PET_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="text-ink-muted">Trạng thái</span>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as typeof status)}
            className="mt-1 block w-full rounded-sm border border-line bg-paper px-2 py-1.5"
          >
            <option value="draft">Nháp</option>
            <option value="active">Hiện</option>
            <option value="hidden">Ẩn</option>
          </select>
        </label>
        <div className="sm:col-span-2"><Field label="Mô tả ngắn" value={shortDesc} onChange={setShortDesc} /></div>
        <Field label="Mã hàng" value={sku} onChange={setSku} />
        <Field label="Tên biến thể" value={variantTitle} onChange={setVariantTitle} />
        <UnitField value={unit} onChange={setUnit} />
        <Field label="Giá (đ)" value={price} onChange={setPrice} type="number" required />
        <Field label="Cân nặng (g)" value={weight} onChange={setWeight} type="number" required />
      </div>
      {error && <p className="mt-3 text-sm text-danger">{error}</p>}
      <button
        type="submit"
        disabled={saving || !selectedCategoryId}
        className="mt-4 w-full rounded-full bg-forest px-4 py-2 text-sm font-medium text-white hover:bg-forest-deep disabled:opacity-50"
      >
        {saving ? "Đang lưu…" : "Tạo sản phẩm"}
      </button>
      </ValidatedForm>
    </div>
  );
}

function ProductEditDrawer({
  product,
  categories,
  onClose,
  onSaved,
}: {
  product: ProductDto;
  categories: CategoryDto[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [tab, setTab] = useState<"info" | "variants" | "images">("info");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // info fields
  const [name, setName] = useState(product.name);
  const [slug, setSlug] = useState(product.slug);
  const [brand, setBrand] = useState(product.brand ?? "");
  const [petType, setPetType] = useState<"dog" | "cat" | "both">(
    product.pet_type as "dog" | "cat" | "both",
  );
  const [status, setStatus] = useState<"draft" | "active" | "hidden">(
    product.status as "draft" | "active" | "hidden",
  );
  const [categoryId, setCategoryId] = useState(product.category_id);
  const [shortDesc, setShortDesc] = useState(product.short_description ?? "");
  const [description, setDescription] = useState(product.description ?? "");

  async function saveInfo(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    const body: ProductUpdateIn = {
      name: name.trim(),
      slug: slug.trim(),
      brand: brand.trim() || null,
      pet_type: petType,
      status,
      category_id: categoryId,
      short_description: shortDesc.trim() || null,
      description: description.trim() || null,
    };
    try {
      await api.updateProduct(product.id, body);
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lưu thất bại");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Drawer open onClose={onClose} title={product.name} width="max-w-3xl">
      <div className="mb-4 border-b border-line">
        <div className="flex gap-4 text-sm">
          {[
            { key: "info", label: "Thông tin" },
            { key: "variants", label: "Biến thể" },
            { key: "images", label: "Hình ảnh" },
          ].map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key as typeof tab)}
              className={`border-b-2 px-1 py-2 transition ${
                tab === t.key
                  ? "border-forest font-medium text-forest"
                  : "border-transparent text-ink-muted hover:text-forest"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="mb-4 text-sm text-danger">{error}</p>}

      {tab === "info" && (
        <ValidatedForm onSubmit={saveInfo} className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm sm:col-span-2">
            <span className="text-ink-muted">Danh mục</span>
            <select
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
              className="mt-1 block w-full rounded-sm border border-line bg-paper px-2 py-1.5"
            >
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <Field label="Tên" value={name} onChange={setName} required />
          <Field label="Tên trong đường dẫn" value={slug} onChange={setSlug} required />
          <Field label="Thương hiệu" value={brand} onChange={setBrand} />
          <label className="text-sm">
            <span className="text-ink-muted">Loại thú</span>
            <select
              value={petType}
              onChange={(e) => setPetType(e.target.value as typeof petType)}
              className="mt-1 block w-full rounded-sm border border-line bg-paper px-2 py-1.5"
            >
              {PET_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            <span className="text-ink-muted">Trạng thái</span>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as typeof status)}
              className="mt-1 block w-full rounded-sm border border-line bg-paper px-2 py-1.5"
            >
              <option value="active">Hiện</option>
              <option value="draft">Nháp</option>
              <option value="hidden">Ẩn</option>
            </select>
          </label>
          <div className="sm:col-span-2">
            <Field label="Mô tả ngắn" value={shortDesc} onChange={setShortDesc} />
          </div>
          <div className="sm:col-span-2">
            <label className="block text-sm">
              <span className="text-ink-muted">Mô tả chi tiết</span>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={5}
                className="mt-1 block w-full rounded-sm border border-line bg-paper px-2 py-1.5"
              />
            </label>
          </div>
          <div className="sm:col-span-2">
            <button
              type="submit"
              disabled={saving}
              className="rounded-full bg-forest px-5 py-2 text-sm font-medium text-white hover:bg-forest-deep disabled:opacity-50"
            >
              {saving ? "Đang lưu…" : "Lưu thông tin"}
            </button>
          </div>
        </ValidatedForm>
      )}

      {tab === "variants" && (
        <VariantsPanel product={product} onSaved={onSaved} />
      )}

      {tab === "images" && <ImagesPanel product={product} onSaved={onSaved} />}
    </Drawer>
  );
}

function VariantsPanel({ product, onSaved }: { product: ProductDto; onSaved: () => void }) {
  const [variants, setVariants] = useState<VariantDto[]>(product.variants);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [newVariant, setNewVariant] = useState<Partial<VariantCreateInType>>({
    sku: "",
    title: "",
    options: { unit: "cái" },
    price: 0,
    weight_grams: 500,
    is_active: true,
  });

  async function updateVariant(v: VariantDto) {
    setSaving(true);
    setError("");
    try {
      const saved = await api.updateVariant(v.id, {
        sku: v.sku,
        title: v.title,
        options: { ...v.options, unit: v.options?.unit?.trim() || "cái" },
        price: v.price,
        weight_grams: v.weight_grams,
        is_active: v.is_active,
      });
      setVariants(current => current.map(item => item.id === saved.id ? saved : item));
      setEditingId(null);
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cập nhật thất bại");
    } finally {
      setSaving(false);
    }
  }

  async function createVariant(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const created = await api.createVariant(product.id, {
        sku: newVariant.sku ?? `SKU-${Date.now()}`,
        title: newVariant.title ?? "Mới",
        options: { ...newVariant.options, unit: newVariant.options?.unit?.trim() || "cái" },
        price: Number(newVariant.price) || 0,
        weight_grams: Number(newVariant.weight_grams) || 500,
        is_active: true,
      });
      setVariants(current => [...current, created]);
      setNewVariant({ sku: "", title: "", options: { unit: "cái" }, price: 0, weight_grams: 500, is_active: true });
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tạo thất bại");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      {error && <p className="text-sm text-danger">{error}</p>}
      <div className="overflow-hidden rounded-sm border border-line bg-surface">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-line bg-forest/5">
            <tr>
              <th className="px-3 py-2 text-ink-muted">Mã hàng</th>
              <th className="px-3 py-2 text-ink-muted">Tên</th>
              <th className="px-3 py-2 text-ink-muted">Đơn vị</th>
              <th className="px-3 py-2 text-ink-muted">Giá</th>
              <th className="px-3 py-2 text-ink-muted">Tồn</th>
              <th className="px-3 py-2 text-ink-muted">Active</th>
              <th className="px-3 py-2 text-ink-muted"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {variants.map((v) =>
              editingId === v.id ? (
                <VariantEditRow
                  key={v.id}
                  value={v}
                  onSave={(updated) => void updateVariant(updated)}
                  onCancel={() => setEditingId(null)}
                  saving={saving}
                />
              ) : (
                <tr key={v.id}>
                  <td className="px-3 py-2 font-mono">{v.sku}</td>
                  <td className="px-3 py-2">{v.title}</td>
                  <td className="px-3 py-2">{v.options?.unit || "cái"}</td>
                  <td className="px-3 py-2">{formatVnd(v.price)}</td>
                  <td className="px-3 py-2">{v.cached_available_qty} {v.options?.unit || "cái"}</td>
                  <td className="px-3 py-2">
                    <StatusBadge status={v.is_active ? "active" : "hidden"} />
                  </td>
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      onClick={() => setEditingId(v.id)}
                      className="text-xs text-forest hover:underline"
                    >
                      Sửa
                    </button>
                  </td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      </div>

      <ValidatedForm onSubmit={createVariant} className="rounded-sm border border-line bg-surface p-4">
        <h3 className="font-medium">Thêm biến thể</h3>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <Field
            label="Mã hàng"
            value={newVariant.sku ?? ""}
            onChange={(s) => setNewVariant((v) => ({ ...v, sku: s }))}
            required
          />
          <Field
            label="Tên"
            value={newVariant.title ?? ""}
            onChange={(s) => setNewVariant((v) => ({ ...v, title: s }))}
            required
          />
          <UnitField value={newVariant.options?.unit ?? "cái"} onChange={(unit) => setNewVariant((v) => ({ ...v, options: { ...v.options, unit } }))} />
          <Field
            label="Giá"
            value={String(newVariant.price ?? 0)}
            onChange={(s) => setNewVariant((v) => ({ ...v, price: Number(s) }))}
            type="number"
            required
          />
          <Field
            label="Cân nặng (g)"
            value={String(newVariant.weight_grams ?? 500)}
            onChange={(s) => setNewVariant((v) => ({ ...v, weight_grams: Number(s) }))}
            type="number"
            required
          />
        </div>
        <button
          type="submit"
          disabled={saving}
          className="mt-3 rounded-full bg-forest px-4 py-2 text-sm font-medium text-white hover:bg-forest-deep disabled:opacity-50"
        >
          {saving ? "Đang lưu…" : "Thêm biến thể"}
        </button>
      </ValidatedForm>
    </div>
  );
}

function VariantEditRow({
  value,
  onSave,
  onCancel,
  saving,
}: {
  value: VariantDto;
  onSave: (v: VariantDto) => void;
  onCancel: () => void;
  saving: boolean;
}) {
  const [v, setV] = useState(value);
  return (
    <tr>
      <td className="px-3 py-2">
        <input
          value={v.sku}
          onChange={(e) => setV({ ...v, sku: e.target.value })}
          className="w-full rounded-sm border border-line bg-paper px-2 py-1"
        />
      </td>
      <td className="px-3 py-2">
        <input
          value={v.title}
          onChange={(e) => setV({ ...v, title: e.target.value })}
          className="w-full rounded-sm border border-line bg-paper px-2 py-1"
        />
      </td>
      <td className="px-3 py-2"><input value={v.options?.unit ?? "cái"} onChange={(e) => setV({ ...v, options: { ...v.options, unit: e.target.value } })} className="w-20 rounded-sm border border-line bg-paper px-2 py-1" aria-label="Đơn vị" /></td>
      <td className="px-3 py-2">
        <input
          type="number"
          value={v.price}
          onChange={(e) => setV({ ...v, price: Number(e.target.value) })}
          className="w-24 rounded-sm border border-line bg-paper px-2 py-1"
        />
      </td>
      <td className="px-3 py-2 text-ink-muted">{v.cached_available_qty} {v.options?.unit || "cái"}</td>
      <td className="px-3 py-2">
        <input
          type="checkbox"
          checked={v.is_active}
          onChange={(e) => setV({ ...v, is_active: e.target.checked })}
        />
      </td>
      <td className="px-3 py-2">
        <div className="flex gap-2">
          <button
            type="button"
            disabled={saving}
            onClick={() => onSave(v)}
            className="text-xs text-forest hover:underline disabled:opacity-50"
          >
            Lưu
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="text-xs text-ink-muted hover:underline"
          >
            Huỷ
          </button>
        </div>
      </td>
    </tr>
  );
}

function ImagesPanel({ product, onSaved }: { product: ProductDto; onSaved: () => void }) {
  const [images, setImages] = useState<ProductImageUpdateIn[]>(
    (product.images ?? []).map((img, idx) => ({
      r2_url: img.r2_url,
      alt_text: img.alt_text,
      variant_id: img.variant_id,
      sort_order: img.sort_order ?? idx,
    })),
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await api.adminUpdateProductImages(
        product.id,
        images
          .map((img, idx) => ({
            ...img,
            sort_order: img.sort_order ?? idx,
          }))
          .filter((img) => img.r2_url.trim()),
      );
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lưu hình thất bại");
    } finally {
      setSaving(false);
    }
  }

  function addImage() {
    setImages([...images, { r2_url: "", alt_text: "", sort_order: images.length }]);
  }

  function updateImage(idx: number, patch: Partial<ProductImageUpdateIn>) {
    const next = [...images];
    next[idx] = { ...next[idx], ...patch };
    setImages(next);
  }

  function removeImage(idx: number) {
    setImages(images.filter((_, i) => i !== idx));
  }

  return (
    <ValidatedForm onSubmit={save} className="space-y-4">
      <p className="text-sm text-ink-muted">
        Dán liên kết đến hình ảnh để thêm ảnh cho sản phẩm.
      </p>
      {error && <p className="text-sm text-danger">{error}</p>}
      <div className="space-y-3">
        {images.map((img, idx) => (
          <div
            key={idx}
            className="flex items-start gap-3 rounded-sm border border-line bg-surface p-3"
          >
            {img.r2_url && (
              <img src={img.r2_url} alt="" className="h-16 w-16 rounded-sm object-cover" />
            )}
            <div className="grid flex-1 gap-2 sm:grid-cols-2">
              <input
                value={img.r2_url}
                onChange={(e) => updateImage(idx, { r2_url: e.target.value })}
                placeholder="https://..."
                className="rounded-sm border border-line bg-paper px-2 py-1.5 text-sm"
              />
              <input
                value={img.alt_text ?? ""}
                onChange={(e) => updateImage(idx, { alt_text: e.target.value })}
                placeholder="Alt text"
                className="rounded-sm border border-line bg-paper px-2 py-1.5 text-sm"
              />
              <input
                type="number"
                value={img.sort_order ?? idx}
                onChange={(e) =>
                  updateImage(idx, { sort_order: Number(e.target.value) })
                }
                placeholder="Thứ tự"
                className="rounded-sm border border-line bg-paper px-2 py-1.5 text-sm"
              />
            </div>
            <button
              type="button"
              onClick={() => removeImage(idx)}
              className="text-sm text-danger hover:underline"
            >
              Xoá
            </button>
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={addImage}
          className="rounded-full border border-forest px-4 py-1.5 text-sm text-forest hover:bg-forest/8"
        >
          + Thêm hình
        </button>
        <button
          type="submit"
          disabled={saving}
          className="rounded-full bg-forest px-4 py-1.5 text-sm font-medium text-white hover:bg-forest-deep disabled:opacity-50"
        >
          {saving ? "Đang lưu…" : "Lưu hình ảnh"}
        </button>
      </div>
    </ValidatedForm>
  );
}

function UnitField({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return <label className="block text-sm">
    <span className="text-ink-muted">Đơn vị bán / nhập kho</span>
    <input value={value} onChange={event => onChange(event.target.value)} list="product-units" required maxLength={30} placeholder="cái, chiếc, túi, tải, kg…" className="mt-1 block w-full rounded-sm border border-line bg-paper px-2 py-1.5 outline-none focus:border-moss" />
    <datalist id="product-units">{["cái", "chiếc", "túi", "tải", "kg", "g", "hộp", "chai", "gói", "bộ"].map(unit => <option key={unit} value={unit} />)}</datalist>
  </label>;
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  required,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  required?: boolean;
}) {
  return (
    <label className="block text-sm">
      <span className="text-ink-muted">{label}</span>
      <input
        type={type}
        value={value}
        required={required}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 block w-full rounded-sm border border-line bg-paper px-2 py-1.5 outline-none focus:border-moss"
      />
    </label>
  );
}
