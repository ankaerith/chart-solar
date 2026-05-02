import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

// max-w 1360 with 40px horizontal padding — matches the Hero / MathRow /
// ModesStrip framing in the design ref. All marketing-route content
// frames itself inside this container.
export function PageContainer({
  children,
  className,
  ...rest
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("mx-auto w-full max-w-[1360px] px-10", className)}
      {...rest}
    >
      {children}
    </div>
  );
}
