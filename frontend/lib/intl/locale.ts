"use client";

import { createContext, useContext } from "react";

// Locale boundary. UK launch is Phase 3b; baking the boundary in now is
// order-of-magnitude cheaper than retrofitting after the wizard ships in $.
//
// At v1 the locale is fixed by Provider prop (defaults to en-US). Later
// beads will derive it from the user's address country and let them
// override it in /settings — without changing any of the call sites.

export type Locale = "en-US" | "en-GB";

export type Currency = "USD" | "GBP";

export const CURRENCY_FOR_LOCALE: Record<Locale, Currency> = {
  "en-US": "USD",
  "en-GB": "GBP",
};

const LocaleContext = createContext<Locale>("en-US");

export const LocaleProvider = LocaleContext.Provider;

export function useLocale(): Locale {
  return useContext(LocaleContext);
}

export function useCurrency(): Currency {
  return CURRENCY_FOR_LOCALE[useLocale()];
}
