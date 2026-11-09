import { ResetPasswordForm } from "./reset-password-form";

export const dynamic = "force-dynamic";
export const metadata = { title: "Đặt mật khẩu mới" };

export default async function ResetPasswordPage({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  const { token } = await searchParams;
  return <ResetPasswordForm token={token ?? ""} />;
}
