import { NextResponse } from "next/server";
import { DEFAULT_WIZARD_STATE } from "@/components/wizard";
import { buildMockResult } from "@/lib/api/forecast";

// Refresh-survival fallback — no server-side store yet, so a refresh
// after submit falls back to DEFAULT_WIZARD_STATE numbers tagged with
// the requested id. The real engine (chart-solar-zyf) replaces this.

export const dynamic = "force-dynamic";

export async function GET(
  _req: Request,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;
  const fallback = buildMockResult(DEFAULT_WIZARD_STATE);
  return NextResponse.json({ ...fallback, id });
}
