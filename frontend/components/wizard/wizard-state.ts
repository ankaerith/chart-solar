// Wizard state shape — mirrors design/solar-decisions/project/app.jsx
// (lines 49–55) and feeds the mock forecast endpoint at
// `/api/forecast`. Once the OpenAPI generator (chart-solar-ajgz) starts
// emitting the real ForecastInputs from backend Pydantic, this file
// becomes a thin adapter that maps the wizard's UI shape onto the
// generated type. Keep field names aligned with the engine's expected
// keys to make that swap mechanical.

export const STEP_KEYS = [
  "address",
  "usage",
  "roof",
  "battery",
  "finance",
] as const;

export type StepKey = (typeof STEP_KEYS)[number];

export const STEPS: ReadonlyArray<{
  key: StepKey;
  n: string;
  label: string;
}> = [
  { key: "address", n: "01", label: "Address" },
  { key: "usage", n: "02", label: "Usage" },
  { key: "roof", n: "03", label: "Roof" },
  { key: "battery", n: "04", label: "Battery" },
  { key: "finance", n: "05", label: "Financing" },
];

export type AddressStep = {
  address: string;
  utility: string;
  tariff: string;
  hold: "5" | "10" | "15" | "25";
};

export type UsageMethod = "greenbutton" | "pdf" | "manual";

export type UsageStep = {
  method: UsageMethod;
  kwh: number;
  bill: number;
  upcoming: ReadonlyArray<string>;
};

export type RoofTilt = "flush" | "15" | "25" | "35";
export type RoofAzimuth = "E" | "SE" | "S" | "SW" | "W";
export type RoofShading = "open" | "light" | "mod" | "heavy";

export type RoofStep = {
  size: number;
  tilt: RoofTilt;
  azimuth: RoofAzimuth;
  shading: RoofShading;
};

export type BatteryDispatchMode = "self" | "tou" | "backup";

export type BatteryStep = {
  include: boolean;
  capacity: number;
  dispatch: BatteryDispatchMode;
  critical: ReadonlyArray<string>;
};

export type FinanceMethod = "cash" | "loan" | "lease" | "ppa";
export type LoanTerm = "10" | "15" | "20" | "25";
export type DealerFee = "no" | "yes" | "zero";
export type Escalator = "0" | "1.9" | "2.9" | "3.9";
export type DiscountRate = "4.5" | "5.5" | "7" | "custom";

export type FinanceStep = {
  method: FinanceMethod;
  term: LoanTerm;
  apr: string;
  dealerFee: DealerFee;
  escalator: Escalator;
  discount: DiscountRate;
};

export type WizardState = {
  address: AddressStep;
  usage: UsageStep;
  roof: RoofStep;
  battery: BatteryStep;
  finance: FinanceStep;
};

export const DEFAULT_WIZARD_STATE: WizardState = {
  address: {
    address: "",
    utility: "",
    tariff: "",
    hold: "10",
  },
  usage: {
    method: "manual",
    kwh: 11000,
    bill: 180,
    upcoming: [],
  },
  roof: {
    size: 8.4,
    tilt: "25",
    azimuth: "S",
    shading: "open",
  },
  battery: {
    include: false,
    capacity: 13.5,
    dispatch: "self",
    critical: [],
  },
  finance: {
    method: "cash",
    term: "20",
    apr: "6.99",
    dealerFee: "no",
    escalator: "2.9",
    discount: "5.5",
  },
};

export const UPCOMING_LOADS = [
  "EV",
  "Heat pump",
  "Pool",
  "New addition",
  "None planned",
] as const;

export const CRITICAL_LOADS = [
  "Fridge",
  "Furnace fan",
  "Well pump",
  "Internet",
  "Medical",
  "Lights only",
] as const;
