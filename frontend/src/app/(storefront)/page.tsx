import HomePageContent from "@/components/HomePageContent";
import { pageMetadata } from "@/lib/seo";
import { BRAND } from "@/lib/brand";
export function generateMetadata() { return pageMetadata("PetHome — Chăm sóc và kết nối thú cưng", BRAND.description, "/"); }
export default function HomePage() { return <HomePageContent />; }
