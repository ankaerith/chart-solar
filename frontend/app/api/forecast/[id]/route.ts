import { NextResponse } from "next/server";
import { DEFAULT_WIZARD_STATE } from "@/components/wizard";
import { buildMockResult } from "@/lib/api/forecast";

// GET /api/forecast/[id] — placeholder lookup that returns a default
// mock result so the result page survives a hard refresh. The real
// engine (chart-solar-zyf / -bqq) reads the persisted job + inputs.
//
// In the mock world there's no server-side store, so we return a
// fixture derived from DEFAULT_WIZARD_STATE and tag it with the
// requested id. Practical effect: whoever first runs the wizard sees
// their numbers (sessionStorage on the client); a refresh later falls
// back to the defaults rather than 404'ing.

export const dynamic = "force-dynamic";

export async function GET(
  _req: Request,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;
  const fallback = buildMockResult(DEFAULT_WIZARD_STATE);
  return NextResponse.json({ ...fallback, id });
}
