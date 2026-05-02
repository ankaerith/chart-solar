import { PageContainer } from "@/components/layout";
import { MagicSentContent } from "@/components/modals";
import { Eyebrow, Panel } from "@/components/ui";

export const metadata = { title: "Magic link sent · Chart Solar" };

export default function MagicSentPage() {
  return (
    <PageContainer className="max-w-2xl space-y-8 py-16">
      <header className="space-y-3">
        <Eyebrow>Magic link sent</Eyebrow>
        <h1 className="text-4xl">Check your inbox</h1>
        <p className="text-[15px] leading-relaxed text-ink-dim">
          Open the link on this device to come back to where you left off.
        </p>
      </header>
      <Panel>
        <MagicSentContent />
      </Panel>
    </PageContainer>
  );
}
