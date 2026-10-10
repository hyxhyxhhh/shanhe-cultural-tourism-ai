"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

export function DialogContent({ className, children, ...props }: DialogPrimitive.DialogContentProps) {
  return <DialogPrimitive.Portal><DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-[#10231e]/45 backdrop-blur-[2px]" /><DialogPrimitive.Content className={cn("fixed left-1/2 top-1/2 z-50 w-[calc(100%-32px)] max-w-xl -translate-x-1/2 -translate-y-1/2 rounded-xl border border-line bg-white p-6 shadow-2xl", className)} {...props}>{children}<DialogPrimitive.Close className="absolute right-4 top-4 rounded p-1 text-moss hover:bg-mist" aria-label="关闭"><X size={16} /></DialogPrimitive.Close></DialogPrimitive.Content></DialogPrimitive.Portal>;
}
export function DialogTitle(props: DialogPrimitive.DialogTitleProps) { return <DialogPrimitive.Title className="text-lg font-semibold text-ink" {...props} />; }
export function DialogDescription(props: DialogPrimitive.DialogDescriptionProps) { return <DialogPrimitive.Description className="mt-1 text-xs leading-5 text-moss" {...props} />; }
