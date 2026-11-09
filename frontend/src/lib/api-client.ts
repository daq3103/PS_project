import { readCookie } from "./format";
import type { SystemReport, TrafficReport } from "./analytics";

const SERVER_API =
  process.env.INTERNAL_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Browser calls same-origin /api/proxy → Next.js forwards to FastAPI with cookies. */
function apiBase(): string {
  if (typeof window === "undefined") return SERVER_API;
  return "/api/proxy";
}

export type VariantDto = {
  id: string;
  sku: string;
  title: string;
  options: Record<string, string>;
  price: number;
  weight_grams: number;
  length_cm: number;
  width_cm: number;
  height_cm: number;
  cached_available_qty: number;
  nearest_expiry_date: string | null;
  is_active: boolean;
};

export type ProductImageOut = {
  id: string;
  product_id: string;
  variant_id: string | null;
  r2_url: string;
  alt_text: string | null;
  sort_order: number;
  created_at: string;
};

export type ProductDto = {
  seo_title?: string | null;
  seo_description?: string | null;
  id: string;
  category_id: string;
  name: string;
  slug: string;
  brand: string | null;
  pet_type: string;
  life_stage?: string | null;
  short_description: string | null;
  description: string | null;
  status: string;
  has_expiry: boolean;
  variants: VariantDto[];
  images?: ProductImageOut[];
};

export type CategoryDto = {
  id: string;
  name: string;
  slug: string;
  sort_order: number;
  is_active: boolean;
  show_in_nav: boolean;
};

export type ShopNavItem = { key: string; label: string; href: string; visible: boolean };

export type CartItemDto = {
  id: string;
  variant_id: string;
  qty: number;
  sku: string | null;
  title: string | null;
  product_name: string | null;
  product_slug: string | null;
  image_url: string | null;
  unit_price: number | null;
  cached_available_qty: number | null;
  is_available: boolean;
  unavailable_label: string | null;
};

export type CartDto = {
  id: string;
  items: CartItemDto[];
  item_count: number;
  subtotal: number;
};

export type UserDto = {
  username?: string | null;
  google_linked?: boolean;
  email_verified?: boolean;
  id: string;
  email: string | null;
  phone: string | null;
  full_name: string;
  role: string;
  totp_enabled?: boolean;
  staff_permissions: string[];
};

export type StaffUserDto = UserDto & {
  is_active: boolean;
  created_at: string;
};

export type StaffRoleChangeDto = {
  target_user_id: string;
  target_name: string;
  actor_name: string;
  old_role: string;
  new_role: string;
  old_permissions: string[];
  new_permissions: string[];
  created_at: string;
};

let sessionRefresh: Promise<boolean> | null = null;

export function refreshSession(): Promise<boolean> {
  if (sessionRefresh) return sessionRefresh;
  const renew = async () => {
    // Another tab may have renewed the shared cookies while this tab waited.
    const me = await fetch("/api/proxy/api/v1/auth/me", { credentials: "include", cache: "no-store" });
    if (me.ok && (await me.json()).user) return true;
    const csrf = readCookie("csrf_token");
    const response = await fetch("/api/proxy/api/v1/auth/refresh", {
      method: "POST", credentials: "include", cache: "no-store",
      headers: csrf ? { "X-CSRF-Token": csrf } : {},
    });
    return response.ok;
  };
  sessionRefresh = (async () => typeof navigator !== "undefined" && navigator.locks
    ? await navigator.locks.request("pethome-session-refresh", renew) : await renew())()
    .catch(() => false).finally(() => { sessionRefresh = null; });
  return sessionRefresh;
}

function readableApiError(detail: unknown, fallback: string): string {
  if (Array.isArray(detail)) {
    const labels: Record<string, string> = {
      recipient_name: "Người nhận", recipient_phone: "SĐT người nhận", province_name: "Tỉnh / TP",
      district_name: "Quận / Huyện", ward_name: "Phường / Xã", street_address: "Địa chỉ",
      customer_phone: "Số điện thoại", phone: "Số điện thoại", contact_phone: "Điện thoại",
      customer_name: "Họ tên", full_name: "Họ tên", full_address: "Địa chỉ",
      location_detail: "Địa điểm công khai", title: "Tiêu đề", event_at: "Thời gian",
    };
    const fields = detail.flatMap(issue => {
      const field = Array.isArray(issue?.loc) ? issue.loc.at(-1) : undefined;
      return typeof field === "string" && labels[field] ? [labels[field]] : [];
    });
    if (fields.length) return `Vui lòng kiểm tra thông tin: ${[...new Set(fields)].join(", ")}.`;
    return fallback;
  }
  if (detail && typeof detail === "object" && "message" in detail) detail = (detail as {message: unknown}).message;
  if (typeof detail !== "string") return fallback;
  const message = detail.trim();
  if (!message || /https?:\/\/|\[[^\]]+\]\(/i.test(message)) return fallback;
  // Older API versions may still return English or internal identifiers.
  if (!/[À-ỹ]/u.test(message) && /[A-Za-z]/.test(message)) return fallback;
  if (/\b(?:token|refresh|slug|category_id|variant_id|stock_movements|webhook)\b/i.test(message)) return fallback;
  return message;
}

async function apiFetch<T>(
  path: string,
  init?: RequestInit & { nextTags?: string[] },
  retried = false,
): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!headers.has("Content-Type") && init?.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const method = (init?.method ?? "GET").toUpperCase();
  if (typeof window !== "undefined" && !["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrf = readCookie("csrf_token");
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }

  const res = await fetch(`${apiBase()}${path}`, {
    ...init,
    headers,
    credentials: "include",
    cache: init?.cache,
    next: init?.nextTags
      ? { revalidate: 60, tags: init.nextTags }
      : init?.cache === "no-store"
        ? undefined
        : { revalidate: 60 },
  });

  if (!retried && typeof window !== "undefined" && readCookie("session_present") &&
      !["/api/v1/auth/login", "/api/v1/auth/logout", "/api/v1/auth/register", "/api/v1/auth/refresh"].includes(path) &&
      (res.status === 401 || (path === "/api/v1/auth/me" && res.ok && !(await res.clone().json()).user))) {
    if (await refreshSession()) return apiFetch<T>(path, init, true);
  }

  if (!res.ok) {
    let detail = res.status === 401 ? "Vui lòng đăng nhập lại để tiếp tục."
      : res.status === 403 ? "Bạn chưa có quyền thực hiện thao tác này."
      : res.status === 404 ? "Không tìm thấy thông tin bạn yêu cầu."
      : res.status === 429 ? "Bạn thao tác quá nhanh. Vui lòng thử lại sau ít phút."
      : res.status >= 500 ? "Hệ thống đang bận. Vui lòng thử lại sau."
      : "Không thực hiện được yêu cầu. Vui lòng kiểm tra thông tin và thử lại.";
    try {
      const body = await res.json();
      if (body?.detail) detail = readableApiError(body.detail, detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json() as T;
  if (typeof window !== "undefined" && path.startsWith("/api/v1/cart") &&
      data && typeof data === "object" && "item_count" in data) {
    window.dispatchEvent(new CustomEvent("petshop:cart", { detail: data }));
  }
  return data;
}

const rescuePendingKeys = new Map<string,string>();
async function rescueRequest<T>(path:string,body?:unknown,method="POST"):Promise<T>{
  if(body===undefined)return apiFetch<T>(`/api/v1/${path}`,{cache:"no-store"});
  const payload=JSON.stringify(body),scope=`${method}:${path}:${payload}`;
  const key=rescuePendingKeys.get(scope)??crypto.randomUUID();rescuePendingKeys.set(scope,key);
  const result=await apiFetch<T>(`/api/v1/${path}`,{method,body:payload,cache:"no-store",headers:{"Idempotency-Key":key}});
  rescuePendingKeys.delete(scope);return result;
}

export const api = {
  stockAlerts: () => apiFetch<{id:string; product_name:string; title:string; sku:string; quantity:number; threshold:number}[]>("/api/v1/admin/stock-alerts", { cache: "no-store" }),
  salesReport: (from = "", to = "") => apiFetch<SalesReport>(`/api/v1/admin/reports/sales?${new URLSearchParams({ ...(from ? {date_from: from} : {}), ...(to ? {date_to: to} : {}) })}`, { cache: "no-store" }),
  shopOverview: () => apiFetch<ShopOverview>("/api/v1/admin/reports/overview", { cache: "no-store" }),
  shopExpenses: () => apiFetch<ShopExpense[]>("/api/v1/admin/shop-expenses", { cache: "no-store" }),
  createShopExpense: (body: ShopExpenseInput) => apiFetch<ShopExpense>("/api/v1/admin/shop-expenses", { method: "POST", body: JSON.stringify(body), cache: "no-store" }),
  addShopExpenseReceipt: (id: string, body: FormData) => apiFetch<{id: string}>(`/api/v1/admin/shop-expenses/${id}/receipts`, { method: "POST", body, cache: "no-store" }),
  voidShopExpense: (id: string, reason: string) => apiFetch<ShopExpense>(`/api/v1/admin/shop-expenses/${id}/void`, { method: "POST", body: JSON.stringify({ reason }), cache: "no-store" }),
  removeAdminRecord: (kind: string, id: string) => apiFetch<void>(`/api/v1/admin/records/${kind}/${id}`, { method: "DELETE", cache: "no-store" }),
  rescueRequest,
  analyticsTraffic: (days: number, section: string) => apiFetch<TrafficReport>(`/api/v1/admin/analytics/traffic?days=${days}&section=${encodeURIComponent(section)}`, { cache: "no-store" }),
  analyticsSystem: () => apiFetch<SystemReport>("/api/v1/admin/analytics/system", { cache: "no-store" }),
  listCategories: (activeOnly = true) =>
    apiFetch<CategoryDto[]>(`/api/v1/categories?active_only=${activeOnly}`, {
      nextTags: ["catalog"],
    }),
  adminListCategories: () =>
    apiFetch<CategoryDto[]>("/api/v1/admin/catalog/categories?active_only=false", { cache: "no-store" }),
  shopNavigation: () => apiFetch<ShopNavItem[]>("/api/v1/shop/navigation", { cache: "no-store" }),
  adminShopNavigation: () => apiFetch<ShopNavItem[]>("/api/v1/admin/shop/navigation", { cache: "no-store" }),
  saveShopNavigation: (items: ShopNavItem[]) => apiFetch<ShopNavItem[]>("/api/v1/admin/shop/navigation", {
    method: "PUT", body: JSON.stringify({ items }), cache: "no-store",
  }),
  createCategory: (body: { name: string; slug: string; parent_id?: string | null; sort_order?: number; is_active?: boolean }) =>
    apiFetch<CategoryDto>("/api/v1/categories", {
      method: "POST", body: JSON.stringify(body), cache: "no-store",
    }),
  updateCategory: (id: string, body: { name?: string; sort_order?: number; is_active?: boolean; show_in_nav?: boolean }) =>
    apiFetch<CategoryDto>(`/api/v1/categories/${id}`, {
      method: "PATCH", body: JSON.stringify(body), cache: "no-store",
    }),
  adminListProducts: (qs: string) =>
    apiFetch<ProductDto[]>(`/api/v1/admin/catalog/products?${qs}`, { cache: "no-store" }),
  listProducts: (qs: string) =>
    apiFetch<ProductDto[]>(`/api/v1/products?${qs}`, { nextTags: ["catalog"] }),
  getProductBySlug: (slug: string) =>
    apiFetch<ProductDto>(`/api/v1/products/by-slug/${slug}`, {
      cache: "no-store",
    }),
  getStock: (productId: string) =>
    apiFetch<{ variants: Array<{
      variant_id: string;
      title: string;
      unit: string;
      cached_available_qty: number;
      nearest_expiry_date: string | null;
      price: number;
      is_active: boolean;
    }> }>(`/api/v1/products/${productId}/stock`, { cache: "no-store" }),
  getCategoryBySlug: (slug: string) =>
    apiFetch<CategoryDto>(`/api/v1/categories/by-slug/${slug}`, {
      nextTags: ["catalog"],
    }),
  me: () => apiFetch<{ user: UserDto | null; csrf_token: string | null; admin_verified?: boolean }>("/api/v1/auth/me", {
    cache: "no-store",
  }),
  register: (body: {
    username: string;
    full_name: string;
    password: string;
    email?: string;
    phone?: string;
  }) =>
    apiFetch<UserDto>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  login: (body: { password: string; username?: string; email?: string; phone?: string; totp_code?: string }) =>
    apiFetch<UserDto | { requires_totp: true }>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  passwordResetConfig: () =>
    apiFetch<{ available: boolean }>("/api/v1/auth/password-reset/config", { cache: "no-store" }),
  googleConfig: () => apiFetch<{ client_id: string; nonce: string }>("/api/v1/auth/google/config", { cache: "no-store" }),
  requestRecoveryEmail: (email: string) => apiFetch("/api/v1/auth/me/email/request", { method: "POST", body: JSON.stringify({ email }) }),
  verifyRecoveryEmail: (email: string, code: string) => apiFetch<void>("/api/v1/auth/me/email/verify", { method: "POST", body: JSON.stringify({ email, code }) }),
  googleLogin: (id_token: string, link = false, totp_code?: string) => apiFetch<UserDto | { requires_totp: true }>("/api/v1/auth/google", {
    method: "POST", body: JSON.stringify({ id_token, link, totp_code }), cache: "no-store",
  }),
  requestPasswordReset: (email: string) =>
    apiFetch<{ message: string }>("/api/v1/auth/password-reset/request", {
      method: "POST", body: JSON.stringify({ email }), cache: "no-store",
    }),
  confirmPasswordReset: (token: string, password: string) =>
    apiFetch<void>("/api/v1/auth/password-reset/confirm", {
      method: "POST", body: JSON.stringify({ token, password }), cache: "no-store",
    }),
  verifyPasswordResetCode: (email: string, code: string) =>
    apiFetch<{ token: string }>("/api/v1/auth/password-reset/verify-code", {
      method: "POST", body: JSON.stringify({ email, code }), cache: "no-store",
    }),
  logout: () => apiFetch<void>("/api/v1/auth/logout", { method: "POST" }),

  listMyOrders: (params?: { status?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.limit != null) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return apiFetch<OrderOut[]>(`/api/v1/orders/me${q ? `?${q}` : ""}`, { cache: "no-store" });
  },

  listAddresses: () =>
    apiFetch<AddressOut[]>("/api/v1/me/addresses", { cache: "no-store" }),
  createAddress: (body: AddressCreate) =>
    apiFetch<AddressOut>("/api/v1/me/addresses", {
      method: "POST",
      body: JSON.stringify(body),
      cache: "no-store",
    }),
  updateAddress: (id: string, body: Partial<AddressCreate>) =>
    apiFetch<AddressOut>(`/api/v1/me/addresses/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
      cache: "no-store",
    }),
  deleteAddress: (id: string) =>
    apiFetch<void>(`/api/v1/me/addresses/${id}`, { method: "DELETE", cache: "no-store" }),

  createProduct: (body: ProductCreateIn) =>
    apiFetch<ProductDto>("/api/v1/products", {
      method: "POST",
      body: JSON.stringify(body),
      cache: "no-store",
    }),
  updateProduct: (id: string, body: ProductUpdateIn) =>
    apiFetch<ProductDto>(`/api/v1/products/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
      cache: "no-store",
    }),
  createVariant: (productId: string, body: VariantCreateIn) =>
    apiFetch<VariantDto>(`/api/v1/products/${productId}/variants`, {
      method: "POST",
      body: JSON.stringify(body),
      cache: "no-store",
    }),
  updateVariant: (variantId: string, body: Partial<VariantCreateIn>) =>
    apiFetch<VariantDto>(`/api/v1/variants/${variantId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
      cache: "no-store",
    }),

  getCart: () => apiFetch<CartDto>("/api/v1/cart", { cache: "no-store" }),
  addToCart: (variant_id: string, qty = 1) =>
    apiFetch<CartDto>("/api/v1/cart/items", {
      method: "POST",
      body: JSON.stringify({ variant_id, qty }),
    }),
  updateCartItem: (itemId: string, qty: number) =>
    apiFetch<CartDto>(`/api/v1/cart/items/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify({ qty }),
    }),
  removeCartItem: (itemId: string) =>
    apiFetch<CartDto>(`/api/v1/cart/items/${itemId}`, { method: "DELETE" }),

  checkout: (body: CheckoutRequest) =>
    apiFetch<CheckoutResponse>("/api/v1/checkout", {
      method: "POST",
      body: JSON.stringify(body),
      cache: "no-store",
    }),

  checkoutMethods: () => apiFetch<{methods: {id: string; label: string; available: boolean}[]}>("/api/v1/checkout/methods", {cache: "no-store"}),
  recoverCheckout: (key: string) => apiFetch<CheckoutResponse>(`/api/v1/checkout/recover?idempotency_key=${encodeURIComponent(key)}`, {cache: "no-store"}),
  quoteCheckout: (body: CheckoutRequest) => apiFetch<CheckoutQuote>("/api/v1/checkout/quote", {method: "POST", body: JSON.stringify(body), cache: "no-store"}),
  lookupOrder: (token: string) => apiFetch<TrackedOrderOut>("/api/v1/orders/lookup", {method: "POST", body: JSON.stringify({token}), cache: "no-store"}),
  requestTrackingLink: (order_code: string, email: string) => apiFetch<{message: string}>("/api/v1/orders/tracking-link", {method: "POST", body: JSON.stringify({order_code, email})}),
  getOrderPayment: (orderId: string) => apiFetch<{status: string; checkout_url?: string | null}>(`/api/v1/orders/${orderId}/payment`, {cache: "no-store"}),
  manualShipment: (orderId: string, body: {carrier_code: string; tracking_code: string; total_weight_grams: number; package_count: number}) => apiFetch(`/api/v1/admin/orders/${orderId}/manual-shipment`, {method: "POST", body: JSON.stringify(body)}),
  confirmManualDelivery: (orderId: string, note: string, codReceived = false, codNote = "") => apiFetch<OrderOut>(`/api/v1/admin/orders/${orderId}/delivered`, {method: "POST", body: JSON.stringify({ note, cod_received: codReceived, cod_note: codNote }), cache: "no-store"}),
  recordCodReceipt: (orderId: string, note: string) => apiFetch<OrderOut>(`/api/v1/admin/orders/${orderId}/cod-receipt`, {method: "POST", body: JSON.stringify({ note }), cache: "no-store"}),
  listSupport: (admin = false, offset = 0) => apiFetch<SupportTicket[]>(`/api/v1/${admin ? "admin/" : ""}support/tickets?offset=${offset}`, {cache: "no-store"}),
  createSupport: (body: {subject: string; content: string; topic: string; order_id?: string}) => apiFetch<SupportTicket>("/api/v1/support/tickets", {method: "POST", body: JSON.stringify(body)}),
  supportDetail: (id: string) => apiFetch<SupportTicket>(`/api/v1/support/tickets/${id}`, {cache: "no-store"}),
  replySupport: (id: string, content: string) => apiFetch(`/api/v1/support/tickets/${id}/messages`, {method: "POST", body: JSON.stringify({content})}),
  supportStatus: (id: string, status: string) => apiFetch(`/api/v1/admin/support/tickets/${id}`, {method: "PATCH", body: JSON.stringify({status})}),
  operations: () => apiFetch<OperationsReport>("/api/v1/admin/operations", {cache: "no-store"}),
  retryOperation: (id: string) => apiFetch(`/api/v1/admin/operations/jobs/${id}/retry`, {method: "POST"}),
  resolveOperation: (id: string, reference: string, note: string) => apiFetch(`/api/v1/admin/operations/cases/${id}/resolve`, {method: "POST", body: JSON.stringify({reference, note})}),

  trackOrder: (orderCode: string, phone: string) =>
    apiFetch<TrackedOrderOut>(
      `/api/v1/orders/track?${new URLSearchParams({ order_code: orderCode, phone }).toString()}`,
      { cache: "no-store" },
    ),

  getOrder: (orderId: string) =>
    apiFetch<OrderOut>(`/api/v1/orders/${orderId}`, { cache: "no-store" }),

  adminListOrders: (params?: {
    view?: "active" | "closed" | "all";
    status?: string;
    report_metric?: string;
    q?: string;
    payment_method?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.view) qs.set("view", params.view);
    if (params?.status) qs.set("status", params.status);
    if (params?.report_metric) qs.set("report_metric", params.report_metric);
    if (params?.q?.trim()) qs.set("q", params.q.trim());
    if (params?.payment_method) qs.set("payment_method", params.payment_method);
    if (params?.date_from) qs.set("date_from", params.date_from);
    if (params?.date_to) qs.set("date_to", params.date_to);
    if (params?.limit != null) qs.set("limit", String(params.limit));
    if (params?.offset != null) qs.set("offset", String(params.offset));
    const q = qs.toString();
    return apiFetch<OrderOut[]>(`/api/v1/admin/orders${q ? `?${q}` : ""}`, {
      cache: "no-store",
    });
  },

  adminGetOrderDetail: (orderId: string) =>
    apiFetch<OrderDetailOut>(`/api/v1/admin/orders/${orderId}`, {
      cache: "no-store",
    }),

  adminConfirmOrder: (orderId: string) =>
    apiFetch<OrderOut>(`/api/v1/orders/${orderId}/confirm`, {
      method: "POST",
      cache: "no-store",
    }),

  adminPackOrder: (orderId: string) =>
    apiFetch<OrderOut>(`/api/v1/admin/orders/${orderId}/pack`, {
      method: "POST",
      cache: "no-store",
    }),

  adminShipOrder: (orderId: string) =>
    apiFetch<OrderOut>(`/api/v1/admin/orders/${orderId}/ship`, {
      method: "POST",
      cache: "no-store",
    }),

  cancelOrder: (orderId: string, reason?: string) =>
    apiFetch<OrderOut>(`/api/v1/orders/${orderId}/cancel`, {
      method: "POST",
      body: JSON.stringify({ reason: reason ?? "" }),
      cache: "no-store",
    }),

  adminCreateShipment: (
    orderId: string,
    body?: { package_count?: number; total_weight_grams?: number; carrier_code?: string },
  ) =>
    apiFetch<{ status: string; order_id: string }>(`/api/v1/admin/orders/${orderId}/shipments`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
      cache: "no-store",
    }),

  adminListInventoryLots: (variantId?: string) => {
    const qs = variantId ? `?variant_id=${encodeURIComponent(variantId)}` : "";
    return apiFetch<InventoryLotOut[]>(`/api/v1/admin/lots${qs}`, {
      cache: "no-store",
    });
  },

  adminCreateInventoryLot: (body: InventoryLotCreate) =>
    apiFetch<{ id: string; lot_no: string }>("/api/v1/admin/lots", {
      method: "POST",
      body: JSON.stringify(body),
      cache: "no-store",
    }),

  adminAdjustStock: (body: StockAdjustIn) =>
    apiFetch<{ status: string; lot_id: string }>("/api/v1/admin/stock/adjust", {
      method: "POST",
      body: JSON.stringify(body),
      cache: "no-store",
    }),

  adminListPromotions: () =>
    apiFetch<PromotionOut[]>("/api/v1/admin/promotions", { cache: "no-store" }),

  adminCreatePromotion: (body: PromotionCreate) =>
    apiFetch<{ id: string; code: string }>("/api/v1/admin/promotions", {
      method: "POST",
      body: JSON.stringify(body),
      cache: "no-store",
    }),

  adminListReviews: (params?: { pending_only?: boolean }) => {
    const qs = new URLSearchParams();
    if (params?.pending_only) qs.set("pending_only", "true");
    const q = qs.toString();
    return apiFetch<ReviewOut[]>(`/api/v1/admin/reviews${q ? `?${q}` : ""}`, {
      cache: "no-store",
    });
  },

  adminApproveReview: (reviewId: string, approve = true) =>
    apiFetch<{ id: string; is_approved: boolean }>(`/api/v1/admin/reviews/${reviewId}/approve`, {
      method: "POST",
      body: JSON.stringify({ approve }),
      cache: "no-store",
    }),

  adminDriftReport: () =>
    apiFetch<DriftReportOut>("/api/v1/admin/reports/drift", { cache: "no-store" }),

  adminListStockMovements: (params?: {
    lot_id?: string;
    variant_id?: string;
    reason?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.lot_id) qs.set("lot_id", params.lot_id);
    if (params?.variant_id) qs.set("variant_id", params.variant_id);
    if (params?.reason) qs.set("reason", params.reason);
    if (params?.date_from) qs.set("date_from", params.date_from);
    if (params?.date_to) qs.set("date_to", params.date_to);
    if (params?.limit != null) qs.set("limit", String(params.limit));
    if (params?.offset != null) qs.set("offset", String(params.offset));
    const q = qs.toString();
    return apiFetch<StockMovementOut[]>(
      `/api/v1/admin/stock-movements${q ? `?${q}` : ""}`,
      { cache: "no-store" },
    );
  },

  adminUpdatePromotion: (
    promotionId: string,
    body: Partial<{
      is_active: boolean;
      usage_limit: number | null;
      starts_at: string;
      expires_at: string;
    }>,
  ) =>
    apiFetch<{ id: string; code: string; is_active: boolean }>(
      `/api/v1/admin/promotions/${promotionId}`,
      {
        method: "PATCH",
        body: JSON.stringify(body),
        cache: "no-store",
      },
    ),

  getProductImages: (productId: string) =>
    apiFetch<ProductImageOut[]>(`/api/v1/products/${productId}/images`, {
      cache: "no-store",
    }),

  adminUpdateProductImages: (productId: string, body: ProductImageUpdateIn[]) =>
    apiFetch<ProductImageOut[]>(`/api/v1/admin/products/${productId}/images`, {
      method: "PUT",
      body: JSON.stringify(body),
      cache: "no-store",
    }),

  adminDashboard: () =>
    apiFetch<DashboardOut>("/api/v1/admin/dashboard", { cache: "no-store" }),

  adminStaffUsers: (q = "") =>
    apiFetch<StaffUserDto[]>(`/api/v1/admin/staff/users${q ? `?q=${encodeURIComponent(q)}` : ""}`, { cache: "no-store" }),

  adminStaffChanges: () =>
    apiFetch<StaffRoleChangeDto[]>("/api/v1/admin/staff/changes", { cache: "no-store" }),

  adminSetStaffPermissions: (userId: string, permissions: string[]) =>
    apiFetch<StaffUserDto>(`/api/v1/admin/staff/users/${userId}/permissions`, {
      method: "PATCH",
      body: JSON.stringify({ permissions }),
      cache: "no-store",
    }),

  adminTotpEnroll: () =>
    apiFetch<{ secret: string; provisioning_uri: string; message: string }>(
      "/api/v1/admin/totp/enroll",
      { method: "POST", cache: "no-store" },
    ),

  adminTotpVerify: (code: string) =>
    apiFetch<{ totp_enabled: boolean }>("/api/v1/admin/totp/verify", {
      method: "POST",
      body: JSON.stringify({ code }),
      cache: "no-store",
    }),

  updateProfile: (body: { full_name?: string; phone?: string }) =>
    apiFetch<UserDto>("/api/v1/auth/me", {
      method: "PATCH",
      body: JSON.stringify(body),
      cache: "no-store",
    }),

  // Community rescue
  communityPetOptions: () => apiFetch<PetOptions>("/api/v1/community/pet-options", { cache: "no-store" }),
  listCommunityPosts: (params?: {
    post_type?: "lost_pet" | "found_pet" | "adoption";
    province_id?: number;
    pet_type?: "dog" | "cat" | "other";
    lifecycle_status?: string;
    cursor?: string;
    limit?: number;
    q?: string;
    breed?: string;
    colors?: string;
    coat_length?: string;
    pattern?: string;
    sex?: string;
    size?: string;
    date_from?: string;
    date_to?: string;
  }) => {
    const qs = new URLSearchParams();
    if (params?.post_type) qs.set("post_type", params.post_type);
    if (params?.province_id != null) qs.set("province_id", String(params.province_id));
    if (params?.pet_type) qs.set("pet_type", params.pet_type);
    if (params?.lifecycle_status) qs.set("lifecycle_status", params.lifecycle_status);
    if (params?.cursor) qs.set("cursor", params.cursor);
    if (params?.limit != null) qs.set("limit", String(params.limit));
    for (const key of ["q", "breed", "colors", "coat_length", "pattern", "sex", "size", "date_from", "date_to"] as const) {
      if (params?.[key]) qs.set(key, params[key]);
    }
    const q = qs.toString();
    return apiFetch<{ items: CommunityPostPublicOut[]; next_cursor: string | null }>(`/api/v1/community/posts${q ? `?${q}` : ""}`, {
      cache: "no-store",
    });
  },

  getCommunityPost: (slug: string) =>
    apiFetch<CommunityPostPublicOut>(`/api/v1/community/posts/${encodeURIComponent(slug)}`, {
      cache: "no-store",
    }),

  revealCommunityContact: (slug: string) =>
    apiFetch<ContactRevealOut>(
      `/api/v1/community/posts/${encodeURIComponent(slug)}/contact-reveal`,
      { method: "POST", cache: "no-store" },
    ),

  createCommunityPost: (body: CommunityPostCreateIn) =>
    apiFetch<CommunityPostOwnerOut>("/api/v1/community/posts", {
      method: "POST",
      headers: { "Idempotency-Key": body.idempotency_key },
      body: JSON.stringify({ ...body, idempotency_key: undefined }),
      cache: "no-store",
    }),

  listMyCommunityPosts: () =>
    apiFetch<CommunityPostOwnerOut[]>("/api/v1/community/me/posts", { cache: "no-store" }),

  updateCommunityPost: (id: string, body: CommunityPostUpdateIn) =>
    apiFetch<CommunityPostOwnerOut>(`/api/v1/community/posts/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
      cache: "no-store",
    }),

  transitionCommunityPost: (id: string, body: LifecycleActionIn) =>
    apiFetch<CommunityPostOwnerOut>(`/api/v1/community/posts/${id}/lifecycle`, {
      method: "POST",
      body: JSON.stringify(body),
      cache: "no-store",
    }),

  reportCommunityPost: (id: string, reason: string) =>
    apiFetch<ReportOut>(`/api/v1/community/posts/${id}/reports`, {
      method: "POST",
      body: JSON.stringify({ reason }),
      cache: "no-store",
    }),

  uploadRescueFile: (body: FormData) => apiFetch<{id:string}>("/api/v1/rescue/files", {method:"POST", body, cache:"no-store"}),

  uploadCommunityImage: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiFetch<{ upload_id: string; object_key: string; url: string }>(
      "/api/v1/community/uploads",
      {
        method: "POST",
        body: formData,
        cache: "no-store",
      },
    );
  },

  adminListCommunityPosts: (params?: {
    q?: string;
    post_type?: "lost_pet" | "found_pet" | "adoption";
    moderation_status?: "pending" | "approved" | "rejected" | "hidden";
    lifecycle_status?: "open" | "resolved" | "closed" | "expired";
    limit?: number;
    offset?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.q) qs.set("q", params.q);
    if (params?.post_type) qs.set("post_type", params.post_type);
    if (params?.moderation_status) qs.set("moderation_status", params.moderation_status);
    if (params?.lifecycle_status) qs.set("lifecycle_status", params.lifecycle_status);
    if (params?.limit != null) qs.set("limit", String(params.limit));
    if (params?.offset != null) qs.set("offset", String(params.offset));
    const q = qs.toString();
    return apiFetch<CommunityPostAdminOut[]>(`/api/v1/admin/community/posts${q ? `?${q}` : ""}`, {
      cache: "no-store",
    });
  },

  adminModerateCommunityPost: (id: string, body: ModerationActionIn) =>
    apiFetch<CommunityPostAdminOut>(`/api/v1/admin/community/posts/${id}/moderate`, {
      method: "POST",
      body: JSON.stringify(body),
      cache: "no-store",
    }),

  adminCreateAdoptionPost: (body: CommunityPostCreateIn) =>
    apiFetch<CommunityPostAdminOut>("/api/v1/admin/community/posts", {
      method: "POST",
      headers: { "Idempotency-Key": body.idempotency_key },
      body: JSON.stringify({ ...body, idempotency_key: undefined }),
      cache: "no-store",
    }),

  adminListCommunityReports: (status?: "pending" | "resolved" | "dismissed", offset = 0) => {
    const qs = `?offset=${offset}${status ? `&status=${status}` : ""}`;
    return apiFetch<ReportOut[]>(`/api/v1/admin/community/reports${qs}`, { cache: "no-store" });
  },

  adminHandleCommunityReport: (id: string, action: "resolved" | "dismissed", reason?: string) =>
    apiFetch<ReportOut>(`/api/v1/admin/community/reports/${id}/handle`, {
      method: "POST",
      body: JSON.stringify({ action, reason: reason ?? "" }),
      cache: "no-store",
    }),

  communityConfig: () => apiFetch<{ enabled: boolean; turnstile_site_key: string }>("/api/v1/community/config", { cache: "no-store" }),
  communityLocations: () => apiFetch<{ version: string; provinces: { id: number; name: string }[] }>("/api/v1/community/locations", { cache: "no-store" }),
  getMyCommunityPost: (id: string) => apiFetch<CommunityPostOwnerOut>(`/api/v1/community/me/posts/${id}`, { cache: "no-store" }),
  applyForAdoption: (id: string, body: AdoptionInput, key: string) => apiFetch<AdoptionRequestOut>(`/api/v1/community/posts/${id}/adoption-requests`, {
    method: "POST", headers: { "Idempotency-Key": key }, body: JSON.stringify(body), cache: "no-store",
  }),
  myAdoptionRequests: () => apiFetch<AdoptionRequestOut[]>("/api/v1/community/me/adoption-requests", { cache: "no-store" }),
  withdrawAdoption: (id: string) => apiFetch<AdoptionRequestOut>(`/api/v1/community/adoption-requests/${id}/withdraw`, { method: "POST", cache: "no-store" }),
  adminAdoptionRequests: (status = "", offset = 0) => apiFetch<AdoptionRequestAdminOut[]>(`/api/v1/admin/community/adoption-requests?offset=${offset}${status ? `&status=${status}` : ""}`, { cache: "no-store" }),
  adminAdoptionAction: (id: string, action: "contact" | "approve" | "reject" | "complete", reason?: string, admin_note?: string) => apiFetch<AdoptionRequestAdminOut>(`/api/v1/admin/community/adoption-requests/${id}/action`, { method: "POST", body: JSON.stringify({ action, reason, admin_note }), cache: "no-store" }),
  adminCommunityPost: (id: string) => apiFetch<CommunityPostAdminOut>(`/api/v1/admin/community/posts/${id}`, { cache: "no-store" }),
  adminUpdateCommunityPost: (id: string, body: CommunityPostUpdateIn) => apiFetch<CommunityPostAdminOut>(`/api/v1/admin/community/posts/${id}`, { method: "PATCH", body: JSON.stringify(body), cache: "no-store" }),
  adminCommunityLifecycle: (id: string, body: LifecycleActionIn) => apiFetch<CommunityPostAdminOut>(`/api/v1/admin/community/posts/${id}/lifecycle`, { method: "POST", body: JSON.stringify(body), cache: "no-store" }),
  adminCommunityAudit: (id: string) => apiFetch<CommunityAuditOut[]>(`/api/v1/admin/community/posts/${id}/audit`, { cache: "no-store" }),
  adminCommunityMetrics: () => apiFetch<{ pending_posts: number; pending_reports: number; active_applications: number; completed_adoptions: number; resolved_posts: number; pending_jobs: number; failed_jobs: number; oldest_pending_at: string | null }>("/api/v1/admin/community/metrics", { cache: "no-store" }),
  communityNotifications: () => apiFetch<CommunityNotificationOut[]>("/api/v1/community/me/notifications", { cache: "no-store" }),
  readCommunityNotification: (id: string) => apiFetch<void>(`/api/v1/community/me/notifications/${id}/read`, { method: "POST", cache: "no-store" }),
};

export type SalesReport = {date_from: string; date_to: string; orders: number; cancelled_orders: number; ordered_value: number; delivered_value: number; paid_order_value: number; discount: number; statuses: {status: string; orders: number; amount: number}[]; daily: {day: string; orders: number; delivered_value: number; delivered_orders: number; closed_orders: number; processing_orders: number; cod_pending_orders: number; handled: boolean; status_breakdown: {status: string; orders: number}[]}[]};
export type ShopOverview = { date_from: string; date_to: string; daily: {day: string; orders: number; delivered_orders: number; revenue: number; product_cost: number; carrier_shipping_cost: number; other_expenses: number; missing_product_cost_orders: number; missing_shipping_cost_orders: number; estimated_profit: number}[]; orders_by_progress: {completed: number; pending: number; cancelled_or_returned: number}; basis: string };
export type ShopExpenseInput = { spent_on: string; category: "shipping" | "supplies" | "other"; amount: number; note: string; reference?: string | null };
export type ShopExpense = ShopExpenseInput & { id: string; actor_user_id: string; actor_name?: string; voided_by_name?: string | null; created_at: string; voided_at: string | null; void_reason: string | null; receipts: {id: string; created_at: string}[] };

export type ShippingAddressInput = {
  full_address?: string;
  province?: string;
  district?: string;
  ward?: string;
  street?: string;
};

export type CheckoutRequest = {
  quote_id?: string;
  idempotency_key: string;
  customer_name: string;
  customer_phone: string;
  customer_email?: string;
  shipping_address: ShippingAddressInput;
  payment_method: "cod" | "vietqr";
  customer_note?: string;
  promo_code?: string;
};

export type CheckoutResponse = {
  tracking_token?: string;
  id: string;
  order_code: string;
  status: string;
  payment_method: string;
  payment_status: string;
  total_amount: number;
  qr_code_url?: string | null;
  reservation_expires_at?: string | null;
};

export type CheckoutQuote = {quote_id: string; expires_at: string; subtotal_amount: number; discount_amount: number; shipping_fee: number; shipping_discount: number; total_amount: number};
export type SupportTicket = {id: string; order_id?: string | null; subject: string; topic: string; status: string; created_at: string; updated_at: string; messages?: {id: string; author_type: string; content: string; created_at: string}[]};
export type OperationsReport = {jobs: {id: string; task: string; status: string; attempts: number; last_error?: string; created_at: string}[]; cases: {id: string; order_code: string; kind: string; amount: number; status: string; created_at: string}[]};

export type TrackedOrderOut = {
  order_code: string;
  status: string;
  payment_status: string;
  customer_name: string;
  customer_phone_masked: string;
  shipping_address: Record<string, string | undefined>;
  total_amount: number;
  created_at: string;
  items: Array<{
    product_name_snapshot: string;
    variant_title_snapshot: string;
    qty: number;
    line_total: number;
  }>;
};

export type OrderOut = {
  id: string;
  order_code: string;
  status: string;
  payment_method: string;
  payment_status: string;
  customer_name: string;
  customer_phone: string;
  customer_email?: string | null;
  shipping_address?: ShippingAddressInput & {
    street_address?: string;
    ward_name?: string;
    district_name?: string;
    province_name?: string;
  };
  subtotal_amount?: number;
  discount_amount?: number;
  shipping_fee?: number;
  total_amount: number;
  created_at: string;
  updated_at?: string;
  tracking_code?: string | null;
  label_print_url?: string | null;
  package_count?: number | null;
  total_weight_grams?: number | null;
};

export type OrderStatusHistoryOut = {
  id: string;
  from_status: string | null;
  to_status: string;
  actor_type: string;
  actor_user_id: string | null;
  note: string | null;
  created_at: string;
};

export type OrderFulfillmentOut = {
  carrier_code: string;
  tracking_code: string | null;
  label_print_url: string | null;
  package_count: number;
  total_weight_grams: number;
  internal_status: string;
  cod_reconciled: boolean;
};

export type OrderDetailOut = OrderOut & {
  items: Array<{
    id: string;
    variant_id: string;
    product_name_snapshot: string;
    variant_title_snapshot: string;
    sku_snapshot: string;
    qty: number;
    unit_price: number;
    line_total: number;
  }>;
  status_history: OrderStatusHistoryOut[];
  fulfillment: OrderFulfillmentOut | null;
};

export type InventoryLotOut = {
  id: string;
  variant_id: string;
  lot_no: string;
  expiry_date: string | null;
  qty_on_hand: number;
  qty_reserved: number;
  available?: number;
  status: string;
};

export type InventoryLotCreate = {
  variant_id: string;
  lot_no: string;
  qty: number;
  unit_cost: number;
  expiry_date?: string | null;
  manufactured_date?: string | null;
  note?: string;
};

export type StockAdjustIn = {
  lot_id: string;
  qty_delta: number;
  reason: "stocktake_adjust" | "damaged_adjust" | "manual_correct";
  note?: string;
};

export type PromotionOut = {
  id: string;
  code: string;
  description: string | null;
  discount_type: string;
  discount_value?: number;
  usage_limit: number | null;
  used_count: number;
  is_active: boolean;
  starts_at?: string;
  expires_at?: string;
};

export type CommunityImageOut = {
  upload_id: string;
  object_key: string;
  sort_order: number;
  url: string;
};

export type AdoptionMeta = {
  age_months: number | null;
  size: "small" | "medium" | "large" | "unknown";
  vaccinated: boolean | null;
  neutered: boolean | null;
  health: string | null;
  requirements: string | null;
};
export type AdoptionInput = { consent?: boolean; applicant_name: string; applicant_phone: string; applicant_address: string; living_condition: string };
export type AdoptionRequestOut = AdoptionInput & {
  id: string; post_id: string; post_title: string; post_slug: string;
  status: "pending" | "contacted" | "approved" | "completed" | "rejected" | "withdrawn";
  outcome_reason: string | null; created_at: string; updated_at: string;
  completed_at: string | null; anonymized_at: string | null;
};
export type AdoptionRequestAdminOut = AdoptionRequestOut & { user_id: string; admin_note: string | null; handled_by: string | null };
export type CommunityAuditOut = { id: string; action: string; old_status: string | null; new_status: string | null; reason: string | null; created_at: string };
export type CommunityNotificationOut = { id: string; message: string; href: string; read_at: string | null; created_at: string };

export type PetOptions = {
  breeds: Record<string, string[]>;
  colors: Record<string, string>;
  patterns: Record<string, string>;
  coat_lengths: Record<string, string>;
  sexes: Record<string, string>;
  sizes: Record<string, string>;
};
export type PetDetails = {
  colors: string[];
  coat_length: "short" | "medium" | "long" | "hairless" | "unknown";
  pattern: "solid" | "tabby" | "spotted" | "bicolor" | "tricolor" | "tortoiseshell" | "unknown";
  sex: "male" | "female" | "unknown";
  size: "small" | "medium" | "large" | "unknown";
  age_months: number | null;
  weight_kg: number | null;
  markings: string | null;
};

export type CommunityPostPublicOut = {
  id: string;
  slug: string;
  post_type: "lost_pet" | "found_pet" | "adoption";
  title: string;
  description: string | null;
  pet_type: "dog" | "cat" | "other";
  breed: string | null;
  color: string | null;
  pet_details: PetDetails;
  location_detail: string | null;
  province_name: string;
  district_name: string | null;
  ward_name: string | null;
  event_at: string | null;
  created_at: string;
  images: CommunityImageOut[];
  province_id: number;
  district_id: number | null;
  last_seen_at: string | null;
  found_at: string | null;
  expires_at: string;
  lifecycle_status: "open" | "resolved" | "closed" | "expired";
  adoption_meta: AdoptionMeta;
  resolution_note: string | null;
};

export type CommunityPostOwnerOut = CommunityPostPublicOut & {
  moderation_status: "pending" | "approved" | "rejected" | "hidden";
  lifecycle_status: "open" | "resolved" | "closed" | "expired";
  contact_phone: string;
  contact_zalo: string | null;
  contact_facebook: string | null;
  expires_at: string;
  version: number;
  moderation_reason: string | null;
};

export type CommunityPostAdminOut = CommunityPostOwnerOut & {
  author_user_id: string;
  author_name: string;
  author_contact: string | null;
  moderation_reason: string | null;
  moderated_at: string | null;
};

export type CommunityPostCreateIn = {
  idempotency_key: string;
  turnstile_token?: string;
  adoption_meta?: AdoptionMeta;
  post_type: "lost_pet" | "found_pet" | "adoption";
  title: string;
  description?: string | null;
  pet_type: "dog" | "cat" | "other";
  breed?: string | null;
  color?: string | null;
  pet_details?: PetDetails;
  location_detail?: string | null;
  province_id: number;
  province_name: string;
  district_id?: number | null;
  district_name?: string | null;
  ward_code?: string | null;
  ward_name?: string | null;
  last_seen_at?: string | null;
  found_at?: string | null;
  contact_phone: string;
  contact_zalo?: string | null;
  contact_facebook?: string | null;
  image_upload_ids?: string[];
};

export type CommunityPostUpdateIn = Partial<
  Omit<CommunityPostCreateIn, "post_type" | "image_upload_ids" | "idempotency_key" | "turnstile_token">
> & {
  version: number;
  image_upload_ids?: string[];
};

export type LifecycleActionIn = {
  version?: number;
  action: "close" | "resolve" | "renew";
  reason?: string | null;
};

export type ModerationActionIn = {
  version?: number;
  action: "approve" | "reject" | "hide";
  reason?: string | null;
};

export type ContactRevealOut = {
  contact_phone: string;
  contact_zalo: string | null;
  contact_facebook: string | null;
};

export type ReportOut = {
  id: string;
  reporter_user_id: string;
  post_id: string;
  reason: string;
  status: "pending" | "resolved" | "dismissed";
  created_at: string;
};

export type DashboardOut = {
  orders_today: number;
  revenue_today: number;
  pending_orders: number;
  pending_reviews: number;
  drift_count: number;
  out_of_stock_variants: number;
  low_stock_variants: number;
  lots_expiring_30d: number;
  recent_orders: OrderOut[];
};

export type StockMovementOut = {
  id: string;
  lot_id: string;
  variant_id: string;
  lot_no: string;
  qty_delta: number;
  reason: string;
  ref_type: string | null;
  ref_id: string | null;
  actor_user_id: string | null;
  note: string | null;
  created_at: string;
};

export type PromotionCreate = {
  code: string;
  description?: string;
  discount_type: "percentage" | "fixed_amount" | "free_shipping";
  discount_value: number;
  min_order_subtotal?: number;
  usage_limit?: number | null;
  starts_at: string;
  expires_at: string;
};

export type ReviewOut = {
  id: string;
  product_id: string;
  product_name: string | null;
  reviewer_name: string;
  rating: number;
  content: string | null;
  is_approved: boolean;
  created_at: string;
};

export type DriftLotRow = {
  lot_id: string;
  lot_no: string;
  variant_id: string;
  qty_on_hand: number;
  movements_sum: number;
  drift: number;
};

export type DriftReportOut = {
  checked_at: string;
  lot_count: number;
  drift_count: number;
  lots: DriftLotRow[];
};

export type AddressOut = {
  id: string;
  recipient_name: string;
  recipient_phone: string;
  province_id: number;
  province_name: string;
  district_id: number;
  district_name: string;
  ward_code: string;
  ward_name: string;
  street_address: string;
  full_address: string | null;
  is_default: boolean;
  created_at: string;
};

export type AddressCreate = {
  recipient_name: string;
  recipient_phone: string;
  full_address: string;
  is_default?: boolean;
};

export type VariantCreateIn = {
  sku: string;
  title: string;
  price: number;
  weight_grams: number;
  compare_at_price?: number | null;
  options?: Record<string, string>;
  is_active?: boolean;
};

export type ProductImageUpdateIn = {
  r2_url: string;
  alt_text?: string | null;
  variant_id?: string | null;
  sort_order?: number;
};

export type ProductCreateIn = {
  category_id: string;
  name: string;
  slug: string;
  brand?: string | null;
  pet_type: "dog" | "cat" | "both";
  life_stage?: "baby" | "adult" | "senior" | "all" | null;
  has_expiry?: boolean;
  short_description?: string | null;
  description?: string | null;
  status?: "draft" | "active" | "hidden";
  variants?: VariantCreateIn[];
};

export type ProductUpdateIn = Partial<Omit<ProductCreateIn, "variants">>;
