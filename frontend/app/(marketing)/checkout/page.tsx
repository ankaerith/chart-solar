import { PageContainer } from "@/components/layout";
import { CheckoutContent } from "@/components/modals";
import { Eyebrow, Panel } from "@/components/ui";

export const metadata = { title: "Checkout · Chart Solar" };

export default function CheckoutPage() {
  return (
    <PageContainer className="max-w-3xl space-y-8 py-16">
      <header className="space-y-3">
        <Eyebrow>Checkout</Eyebrow>
        <h1 className="text-4xl">Pick a tier</h1>
        <p className="text-[15px] leading-relaxed text-ink-dim">
          Stripe handles the payment. We never see card details.
        </p>
      </header>
      <Panel>
        <CheckoutContent />
      </Panel>
    </PageContainer>
  );
}
