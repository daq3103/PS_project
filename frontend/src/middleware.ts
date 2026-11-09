import { NextResponse } from "next/server";

export function middleware() {
  // The server admin layout validates the API session and redirects on the
  // current origin. A cookie-only redirect here cannot validate that session.
  const response = NextResponse.next();
  response.headers.set("Cache-Control", "no-store, no-cache, must-revalidate");
  response.headers.set("X-Robots-Tag", "noindex, nofollow");
  return response;
}

export const config = {
  matcher: ["/admin/:path*", "/account/:path*", "/cart", "/checkout", "/login", "/register", "/track-order", "/forgot-password", "/reset-password", "/search"],
};
