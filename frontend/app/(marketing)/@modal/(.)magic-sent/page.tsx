import { MagicSentContent, RouteModal } from "@/components/modals";

export default function MagicSentModalRoute() {
  return (
    <RouteModal
      kicker="Magic link sent"
      title="Check your inbox"
      subtitle="Open the link on this device to come back to where you left off."
      maxWidth={480}
    >
      <MagicSentContent />
    </RouteModal>
  );
}
