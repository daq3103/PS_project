"use client";
import {useState} from "react";
import {api} from "@/lib/api-client";
export function TransparencyHistory({fundId}:{fundId:string}){
 const [rows,setRows]=useState<{version:number;published_at:string;report:{as_of:string;confirmed:number;spent:number}}[]>([]),[error,setError]=useState("");
 return <div className="space-y-3 text-sm"><button onClick={()=>void api.rescueRequest<typeof rows>(`rescue/transparency/${fundId}/history`).then(setRows).catch(e=>setError(e.message))} className="text-forest underline">Xem các lần chốt đã công bố</button>{error&&<p role="alert">{error}</p>}{rows.map(r=><p key={r.version} className="rounded-xl border border-line p-3">Bản {r.version} · Chốt {new Date(r.report.as_of).toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'})} · Thu xác nhận {r.report.confirmed.toLocaleString('vi-VN')}đ · Đã chi {r.report.spent.toLocaleString('vi-VN')}đ</p>)}</div>;
}
