// Isolated fixtures for the Excel regression suite. Never connects to a real database.
import http from "node:http";
const states = new Map();
const variant = (id, qty) => ({ id, sku: id, title: id, price: 89000, cached_available_qty: qty, is_active: true });
const product = { id: "product1", slug: "vong-co-nylon-m", name: "Vòng cổ nylon size M", pet_type: "both", status: "active", variants: [variant("M", 47), variant("L", 43)] };
const address = { id: "address1", recipient_name: "Người nhận QA", recipient_phone: "0901234567", province_id: 20, province_name: "Hà Nội", district_id: 21, district_name: "Cầu Giấy", ward_code: "22", ward_name: "Dịch Vọng", street_address: "12 Đường QA", is_default: true };
const post = { id: "post1", title: "Tin kiểm thử", author_name: "QA", post_type: "lost_pet", moderation_status: "pending", lifecycle_status: "open", version: 1, images: [] };
const options = { breeds: { dog: [], cat: [], other: [] }, colors: {}, patterns: {}, coat_lengths: {}, sexes: {}, sizes: {} };
http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://localhost");
  const cookie = req.headers.cookie ?? "";
  const key = cookie.match(/qa_session=([^;]+)/)?.[1] ?? "default";
  if (!states.has(key)) states.set(key, { qty: 3, addresses: [{ ...address }], posts: [{ ...post }], lots: [{id:"lot1",variant_id:"M",lot_no:"SEED-001",qty_on_hand:10,qty_reserved:0,available:10,status:"active",expiry_date:null}] });
  const state = states.get(key);
  const role = cookie.match(/qa_role=([^;]+)/)?.[1];
  let input = ""; for await (const chunk of req) input += chunk;
  const body = input ? JSON.parse(input) : {};
  let result = {};
  const path = url.pathname.replace(/^\/api\/v1/, "");
  let status = 200;
  if (path === "/auth/me") result = { user: role ? { id: "user1", role: role === "staff" ? "owner" : "customer", full_name: "QA", totp_enabled: true, staff_permissions: [] } : null, admin_verified: true };
  else if (path === "/auth/google/config") result = { client_id: "", nonce: "" };
  else if (path === "/auth/password-reset/config") result = { available: true };
  else if (path === "/admin/catalog/products") result = url.searchParams.get("q") ? [] : [product];
  else if (path === "/admin/catalog/categories") result = [{id:"cat1",name:"Phụ kiện",slug:"phu-kien",sort_order:2,is_active:true}];
  else if (path === "/admin/lots") result = state.lots;
  else if (path === "/admin/stock-alerts") result = [{id:"N",product_name:"Chưa nhập lô",title:"N",sku:"LOW-STOCK",quantity:0,threshold:5}];
  else if (path === "/admin/stock-movements") result = [];
  else if (path === "/admin/stock/adjust") { state.lots[0].qty_on_hand += body.qty_delta; state.lots[0].available=state.lots[0].qty_on_hand; result={status:"ok"}; }
  else if (path === "/admin/promotions") result = [];
  else if (path === "/admin/reports/drift") result = {lots:[],drift_count:0,lot_count:0};
  else if (path === "/admin/reports/sales") result = {date_from:"2026-11-01",date_to:"2026-11-04",orders:3,cancelled_orders:1,ordered_value:40000,delivered_value:30000,paid_order_value:0,discount:0,statuses:[],daily:[]};
  else if (path === "/orders/me") result = [];
  else if (path === "/support/tickets" || path === "/me/support") result = [];
  else if (path === "/rescue/config") result = {};
  else if (path === "/rescue/me/reports") result = [];
  else if (path === "/community/config") result = { enabled: true };
  else if (path === "/analytics/config") result = { enabled: false };
  else if (path === "/community/pet-options") result = options;
  else if (path === "/community/locations") result = { provinces: [] };
  else if (path === "/community/posts") result = { items: [], next_cursor: null };
  else if (path === "/community/posts/test-adoption") result = { ...post, expires_at:"2027-12-31T00:00:00Z", slug:"test-adoption", title:"Bé nhận nuôi QA", post_type:"adoption", pet_type:"cat", province_name:"Hà Nội", location_detail:null, ward_name:null, district_name:null, adoption_meta:{size:"unknown",age_months:null}, pet_details:{colors:[],pattern:"unknown",coat_length:"unknown",sex:"unknown",size:"unknown"},created_at:"2026-11-04T00:00:00Z" };
  else if (path === "/community/me/posts") { status = 401; result = { detail: "Vui lòng đăng nhập" }; }
  else if (path.startsWith("/cart")) {
    if (req.method === "PATCH") {
      await new Promise(resolve => setTimeout(resolve, 150));
      if (body.qty > 47) { status = 409; result = { detail: "Chỉ còn 47 sản phẩm trong kho" }; }
      else state.qty = body.qty;
    }
    if (req.method === "DELETE") state.qty = 0;
    if (status === 200) result = { id: "cart1", item_count: state.qty, subtotal: 89000 * state.qty, items: state.qty ? [{ id: "item1", variant_id: "M", product_name: product.name, product_slug: product.slug, title: "M", qty: state.qty, unit_price: 89000, is_available: true, cached_available_qty: 47 }] : [] };
  }
  else if (path === "/products") result = [product];
  else if (path === "/categories") result = [];
  else if (path === "/me/addresses") result = state.addresses;
  else if (path.startsWith("/me/addresses/")) {
    if (req.method === "PATCH") Object.assign(state.addresses[0], body);
    result = state.addresses[0];
  }
  else if (path === "/admin/community/posts") result = url.searchParams.get("q") === "zzzznomatch" ? [] : state.posts.filter(p => !url.searchParams.get("moderation_status") || p.moderation_status === url.searchParams.get("moderation_status"));
  else if (path.endsWith("/moderate")) { Object.assign(state.posts[0], { moderation_status: "rejected", version: 2 }); result = state.posts[0]; }
  else if (path.endsWith("/audit")) result = [];
  res.writeHead(status, { "Content-Type": "application/json" }); res.end(JSON.stringify(result));
}).listen(18000, "127.0.0.1");
