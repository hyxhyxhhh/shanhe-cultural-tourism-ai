import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva("inline-flex items-center justify-center gap-2 rounded-md text-xs font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-moss disabled:pointer-events-none disabled:opacity-45 active:scale-[.98]", {
  variants: {
    variant: { default: "bg-forest text-white hover:bg-pine", outline: "border border-line bg-white text-ink hover:border-moss hover:bg-mist", ghost: "text-ink hover:bg-mist", gold: "bg-gold text-white hover:bg-[#b99859]" },
    size: { default: "h-9 px-4", sm: "h-8 px-3", icon: "h-9 w-9" }
  },
  defaultVariants: { variant: "default", size: "default" }
});

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {}
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, ...props }, ref) => <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />);
Button.displayName = "Button";
