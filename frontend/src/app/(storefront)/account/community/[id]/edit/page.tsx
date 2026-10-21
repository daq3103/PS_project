import { PostForm } from "@/components/community/PostForm";
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <div className="px-4 py-8"><PostForm editId={id} /></div>;
}
