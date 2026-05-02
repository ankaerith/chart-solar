import { RouteModal, SaveForecastContent } from "@/components/modals";

export default function SaveForecastModalRoute() {
  return (
    <RouteModal
      kicker="Save forecast"
      title="Keep this for later"
      subtitle="Free account — just an email and a magic link to come back."
      maxWidth={520}
    >
      <SaveForecastContent />
    </RouteModal>
  );
}
