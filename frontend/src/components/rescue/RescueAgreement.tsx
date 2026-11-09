"use client";
import {useEffect,useState} from "react";
import {api} from "@/lib/api-client";
export function RescueAgreement({id}:{id:string}){
 const [review,setReview]=useState<{agreement:string;verified:boolean;handover_at?:string}|null>(null);
 useEffect(()=>{api.rescueRequest<{agreement:string;verified:boolean;handover_at?:string}>(`rescue/applications/${id}/review`).then(setReview).catch(()=>setReview(null));},[id]);
 return review?<div className="space-y-2 rounded-xl bg-moss/10 p-4 text-sm"><p>{review.verified?'Trạm đã ghi nhận xác minh liên hệ.':'Trạm đang chờ xác minh liên hệ.'}</p>{review.agreement&&<><h3 className="font-semibold">Điều kiện và nội dung bàn giao</h3><p className="whitespace-pre-wrap">{review.agreement}</p></>}{review.handover_at&&<p>Đã ghi bàn giao ngày {new Date(review.handover_at).toLocaleDateString('vi-VN')}</p>}</div>:null;
}
