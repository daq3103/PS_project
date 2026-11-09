"use client";
import {useCallback,useEffect,useState} from "react";
import {api} from "@/lib/api-client";
import type {RescueRow} from "@/lib/rescue-types";
export function RescueAudit(){
 const [rows,setRows]=useState<RescueRow[]>([]),[offset,setOffset]=useState(0),[error,setError]=useState("");
 const load=useCallback(()=>api.rescueRequest<RescueRow[]>(`admin/rescue/audit?offset=${offset}`).then(setRows).catch(e=>setError(e.message)),[offset]);
 useEffect(()=>{void load();},[load]);
 return <div className="space-y-5"><h1 className="font-display text-3xl text-forest">Lịch sử thay đổi của trạm</h1><p className="text-sm text-ink-muted">Chỉ chủ tài khoản xem toàn bộ nhật ký. Mỗi thao tác ghi người thực hiện, thời điểm và căn cứ; không sửa lịch sử để thay biên nhận hoặc bàn giao thực tế.</p>{error&&<p role="alert" className="text-danger">{error}</p>}<ol className="space-y-3">{rows.map(r=><li key={r.id} className="space-y-2 rounded-2xl border border-line p-5"><p className="font-semibold">{String(r.action_label)} · {String(r.resource_label)}</p><p className="text-xs text-ink-muted">{String(r.actor_name)} · {new Date(String(r.created_at)).toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'})}</p>{Boolean(r.reason)&&<p className="whitespace-pre-wrap text-sm">{String(r.reason)}</p>}{r.amount!=null&&<p className="text-sm">Số tiền: {Number(r.amount).toLocaleString('vi-VN')}đ</p>}{r.quantity!=null&&<p className="text-sm">Số lượng: {Number(r.quantity)}</p>}</li>)}</ol><div className="flex gap-3"><button disabled={!offset} onClick={()=>setOffset(Math.max(0,offset-100))} className="rounded-full border border-line px-4 py-2 disabled:opacity-40">Trang trước</button><button disabled={rows.length<100} onClick={()=>setOffset(offset+100)} className="rounded-full border border-line px-4 py-2 disabled:opacity-40">Trang sau</button></div></div>;
}
