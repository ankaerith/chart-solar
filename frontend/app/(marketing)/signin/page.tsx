import { PageContainer } from "@/components/layout";
import { SignInContent } from "@/components/modals";
import { Eyebrow, Panel } from "@/components/ui";

// Full-page fallback for direct nav / refresh / shared link. The
// intercepted modal version lives at @modal/(.)signin/page.tsx.

export const metadata = { title: "Sign in · Chart Solar" };

export default function SigninPage() {
  return (
    <PageContainer className="max-w-2xl space-y-8 py-16">
      <header className="space-y-3">
        <Eyebrow>Sign in</Eyebrow>
        <h1 className="text-4xl">Continue with magic link</h1>
        <p className="text-[15px] leading-relaxed text-ink-dim">
          One-tap link to your inbox — no password to forget, no support
          burden.
        </p>
      </header>
      <Panel>
        <SignInContent />
      </Panel>
    </PageContainer>
  );
}
