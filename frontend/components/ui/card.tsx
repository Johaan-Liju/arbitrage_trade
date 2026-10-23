import * as React from "react";
import { cn } from "@/lib/utils";
function Card({ className, ...props }: React.ComponentProps<"div">) { return <div data-slot="card" className={cn("rounded-xl border border-border bg-card text-card-foreground", className)} {...props} />; }
function CardHeader({ className, ...props }: React.ComponentProps<"div">) { return <div data-slot="card-header" className={cn("flex items-start justify-between gap-4 p-5", className)} {...props} />; }
function CardTitle({ className, ...props }: React.ComponentProps<"h2">) { return <h2 data-slot="card-title" className={cn("text-sm font-semibold", className)} {...props} />; }
function CardContent({ className, ...props }: React.ComponentProps<"div">) { return <div data-slot="card-content" className={cn("px-5 pb-5", className)} {...props} />; }
export { Card, CardHeader, CardTitle, CardContent };
