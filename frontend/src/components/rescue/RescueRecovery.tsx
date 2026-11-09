"use client";
import {useCallback,useEffect,useState} from "react";
import {api} from "@/lib/api-client";
type Review={gift_order_exceptions:{pledge_id:string;order_code:string;action:string}[];unassigned_open_episodes:number;pending_transfer_exceptions:number;as_of:string};
export function RescueRecovery(){
 const [data,setData]=useState<Review|null>(null),[error,setError]=useState("");
 const load=useCallback(()=>api.rescueRequest<Review>('admin/rescue/recovery-review').then(setData).catch(e=>setError(e.message)),[]);
 useEffect(()=>{void load();},[load]);
 return <section className="space-y-4 rounded-2xl border border-line p-5"><h2 className="font-display text-2xl text-forest">Việc cần đối chiếu và phương án dự phòng</h2><p className="text-sm leading-7 text-ink-muted">Sau phục hồi dữ liệu, đối chiếu bé đã bàn giao, nơi chăm sóc, tiền ngân hàng và hiện vật đã nhận trước khi chạy lại công việc. Danh sách này phát hiện một số tình huống cần kiểm tra, không thay việc đối soát thực tế.</p>{error&&<p role="alert" className="text-danger">{error}</p>}{data&&<><p className="text-sm">Đợt đang mở có người phụ trách bị khóa/không còn quyền: <strong>{data.unassigned_open_episodes}</strong></p><p className="text-sm">Thông báo tiền còn cần xử lý: <strong>{data.pending_transfer_exceptions}</strong></p>{data.gift_order_exceptions.map(r=><div key={r.pledge_id} className="rounded-xl bg-honey/10 p-3 text-sm"><p className="font-semibold">Đơn Shop {r.order_code} thay đổi sau khi trạm nhận quà</p><p className="mt-1">{r.action}</p></div>)}<p className="text-xs text-ink-muted">Kiểm tra lúc {new Date(data.as_of).toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'})}</p></>}<button onClick={()=>void load()} className="text-sm text-forest underline">Kiểm tra lại</button></section>;
}
