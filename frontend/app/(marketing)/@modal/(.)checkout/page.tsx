import { CheckoutContent, RouteModal } from "@/components/modals";

export default function CheckoutModalRoute() {
  return (
    <RouteModal
      kicker="Checkout"
      title="Pick a tier"
      subtitle="Stripe handles the payment. We never see card details."
      maxWidth={680}
    >
      <CheckoutContent />
    </RouteModal>
  );
}
