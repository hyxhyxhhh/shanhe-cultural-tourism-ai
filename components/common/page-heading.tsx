"use client";

import { Download, Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";

export function PageHeading({ title, description }: { title: string; description: string }) {
  const [open, setOpen] = useState(false);
  return <>
    <div className="mb-5 flex items-end justify-between gap-4 max-sm:items-start">
      <div><div className="eyebrow">SHANHE TOURISM DECISION INTELLIGENCE</div><h1 className="mt-3 text-[28px] font-semibold leading-none tracking-[-.03em] text-ink max-sm:text-2xl">{title}</h1><p className="mt-3 text-[11px] text-[#788983]">{description}</p></div>
      <div className="flex shrink-0 gap-2 max-lg:hidden"><Button variant="outline" size="sm" onClick={()=>toast.success("决策简报已进入导出队列")}><Download size={12}/>导出决策简报</Button><Button size="sm" onClick={()=>setOpen(true)}><Plus size={12}/>发起专业任务</Button></div>
    </div>
    <Dialog open={open} onOpenChange={setOpen}><DialogContent><DialogTitle>发起专业任务</DialogTitle><DialogDescription>任务将创建在当前客户空间，可稍后接入真实 FastAPI 服务。</DialogDescription><div className="mt-5 space-y-3"><label className="block text-xs font-medium">任务名称<input className="mt-1.5 w-full rounded-md border border-line bg-[#f8f9f7] px-3 py-2.5 outline-none focus:border-moss" placeholder="请输入任务名称"/></label><label className="block text-xs font-medium">任务说明<textarea className="mt-1.5 min-h-24 w-full resize-none rounded-md border border-line bg-[#f8f9f7] px-3 py-2.5 outline-none focus:border-moss" placeholder="描述目标、范围与交付要求"/></label><div className="flex justify-end gap-2 pt-2"><Button variant="outline" onClick={()=>setOpen(false)}>取消</Button><Button onClick={()=>{setOpen(false);toast.success("专业任务已创建")}}>创建任务</Button></div></div></DialogContent></Dialog>
  </>;
}
