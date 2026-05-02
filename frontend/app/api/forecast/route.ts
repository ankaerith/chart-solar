import { NextResponse } from "next/server";
import { buildMockResult } from "@/lib/api/forecast";
import type { WizardState } from "@/components/wizard";

// Mock forecast endpoint — accepts the wizard's WizardState and
// returns a deterministic ForecastResultMock. Lets the wizard ship
// before the real engine endpoint (chart-solar-bqq) is wired.
//
// Production swaps this for POST /api/forecast on the FastAPI side
// (chart-solar-zyf) which enqueues an RQ job and polls for status.
// Same client path; different transport. The mock keeps the contract
// thin enough that the swap is mechanical.

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  let inputs: WizardState;
  try {
    inputs = (await req.json()) as WizardState;
  } catch {
    return NextResponse.json(
      { error: "Invalid JSON body" },
      { status: 400 },
    );
  }
  // Tiny artificial delay so the wizard's "Running…" CTA is observable
  // during local development without slowing down tests meaningfully.
  await new Promise((resolve) => setTimeout(resolve, 350));
  return NextResponse.json(buildMockResult(inputs));
}
