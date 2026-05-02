import { RouteModal, SignInContent } from "@/components/modals";

export default function SigninModalRoute() {
  return (
    <RouteModal
      kicker="Sign in"
      title="Continue with magic link"
      subtitle="One-tap link to your inbox — no password to forget."
      maxWidth={520}
    >
      <SignInContent />
    </RouteModal>
  );
}
