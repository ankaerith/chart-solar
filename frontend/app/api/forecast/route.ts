import { NextResponse } from "next/server";
import { buildMockResult } from "@/lib/api/forecast";
import type { WizardState } from "@/components/wizard";

// Mock until chart-solar-bqq wires the real FastAPI engine. The
// 350ms delay below makes the wizard's "Running…" CTA observable in
// dev — skipped in tests so Playwright doesn't pay it on every walk.

export const dynamic = "force-dynamic";

const SUBMIT_DELAY_MS = process.env.NODE_ENV === "test" ? 0 : 350;

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
  if (SUBMIT_DELAY_MS > 0) {
    await new Promise((resolve) => setTimeout(resolve, SUBMIT_DELAY_MS));
  }
  return NextResponse.json(buildMockResult(inputs));
}
