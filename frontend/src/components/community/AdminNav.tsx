import Link from "next/link";
export function CommunityAdminNav() {
  return <nav aria-label="Quản lý cứu hộ" className="mb-5 flex flex-wrap gap-3 text-sm text-forest">
    <Link href="/admin/community" className="underline">Tin cứu hộ</Link>
    <Link href="/admin/community/new" className="underline">Đăng nhận nuôi</Link>
    <Link href="/admin/community/adoptions" className="underline">Hồ sơ nhận nuôi</Link>
    <Link href="/admin/community/reports" className="underline">Báo cáo vi phạm</Link>
    <Link href="/admin/community/metrics" className="underline">Theo dõi vận hành</Link>
  </nav>;
}
