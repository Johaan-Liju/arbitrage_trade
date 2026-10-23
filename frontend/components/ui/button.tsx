import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

// Local shadcn/ui component, adapted to the GoldLens theme.
const buttonVariants = cva("inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 shrink-0", {
  variants: { variant: {
    default: "bg-primary text-primary-foreground hover:bg-primary/90",
    outline: "border border-border bg-card hover:bg-accent hover:text-foreground",
    ghost: "hover:bg-accent hover:text-foreground",
  }, size: { default: "h-10 px-4 py-2", sm: "h-8 px-3 text-xs", icon: "size-9" } },
  defaultVariants: { variant: "default", size: "default" },
});
function Button({ className, variant, size, asChild = false, ...props }: React.ComponentProps<"button"> & VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : "button";
  return <Comp data-slot="button" className={cn(buttonVariants({ variant, size, className }))} {...props} />;
}
export { Button, buttonVariants };
