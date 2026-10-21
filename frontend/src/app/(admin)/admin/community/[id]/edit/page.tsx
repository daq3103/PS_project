import { PostForm } from "@/components/community/PostForm";
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <PostForm editId={id} admin />;
}
