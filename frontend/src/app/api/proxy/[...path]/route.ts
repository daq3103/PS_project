import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const UPSTREAM = process.env.INTERNAL_API_URL ?? "http://fastapi-api:8000";

async function forward(req: NextRequest, pathParts: string[]) {
  const path = pathParts.join("/");
  const url = new URL(req.url);
  const target = `${UPSTREAM}/${path}${url.search}`;

  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((c) => `${c.name}=${c.value}`)
    .join("; ");

  const headers = new Headers();
  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  const csrf = req.headers.get("x-csrf-token");
  if (csrf) headers.set("x-csrf-token", csrf);
  const totp = req.headers.get("x-totp-code");
  if (totp) headers.set("x-totp-code", totp);
  if (cookieHeader) headers.set("cookie", cookieHeader);
  const idempotency = req.headers.get("idempotency-key");
  if (idempotency) headers.set("idempotency-key", idempotency);
  for (const name of ["dnt", "sec-gpc"]) {
    const value = req.headers.get(name);
    if (value) headers.set(name, value);
  }
  // Enabled only behind Nginx, which replaces client supplied XFF at ingress.
  if (process.env.TRUST_PROXY_HEADERS === "true") {
    const forwarded = req.headers.get("x-forwarded-for");
    if (forwarded) headers.set("x-forwarded-for", forwarded);
  }

  const method = req.method.toUpperCase();
  const upstream = await fetch(target, {
    method,
    headers,
    cache: "no-store",
    body: method === "GET" || method === "HEAD" ? undefined : await req.arrayBuffer(),
  });
  // 204 No Content and similar status codes must not carry a body in the Edge Response.
  const body = upstream.status === 204 || upstream.status === 304 ? null : await upstream.arrayBuffer();
  const res = new NextResponse(body, { status: upstream.status });

  const passHeaders = ["content-type", "cache-control"];
  for (const h of passHeaders) {
    const v = upstream.headers.get(h);
    if (v) res.headers.set(h, v);
  }

  // Relay Set-Cookie so browser stores auth on the Next.js origin
  const setCookies =
    typeof upstream.headers.getSetCookie === "function"
      ? upstream.headers.getSetCookie()
      : [];
  for (const c of setCookies) {
    res.headers.append("set-cookie", c);
  }

  return res;
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return forward(req, path);
}
export async function POST(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return forward(req, path);
}
export async function PATCH(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return forward(req, path);
}
export async function PUT(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return forward(req, path);
}
export async function DELETE(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return forward(req, path);
}
