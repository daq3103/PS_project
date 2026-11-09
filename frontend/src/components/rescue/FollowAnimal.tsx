"use client";
import {useState} from "react";
import {api} from "@/lib/api-client";
export function FollowAnimal({id}:{id:string}){
 const [message,setMessage]=useState(""),[busy,setBusy]=useState(false);
 async function follow(updates:boolean){setBusy(true);try{await api.rescueRequest(`rescue/animals/${id}/follow`,{purpose:"updates",allowed:updates});setMessage(updates?"Đã lưu và bật thông báo cập nhật trong tài khoản.":"Đã lưu bé. Chưa bật thông báo cập nhật.");}catch(e){setMessage(e instanceof Error?e.message:"Vui lòng đăng nhập để lưu bé.");}finally{setBusy(false);}}
 return <div className="space-y-2 text-sm"><div className="flex flex-wrap gap-2"><button disabled={busy} onClick={()=>void follow(false)} className="rounded-full border border-line px-4 py-2 text-forest">Lưu bé quan tâm</button><button disabled={busy} onClick={()=>void follow(true)} className="rounded-full border border-line px-4 py-2 text-forest">Đăng ký nhận cập nhật</button><button onClick={()=>{navigator.clipboard.writeText(location.href).then(()=>setMessage("Đã sao chép đường dẫn.")).catch(()=>setMessage("Bạn có thể sao chép đường dẫn trên thanh địa chỉ."));}} className="rounded-full border border-line px-4 py-2 text-forest">Chia sẻ</button></div>{message&&<p role="status">{message}</p>}</div>;
}
