import { PageContainer } from "@/components/layout";
import { SaveForecastContent } from "@/components/modals";
import { Eyebrow, Panel } from "@/components/ui";

export const metadata = { title: "Save forecast · Chart Solar" };

export default function SaveForecastPage() {
  return (
    <PageContainer className="max-w-2xl space-y-8 py-16">
      <header className="space-y-3">
        <Eyebrow>Save forecast</Eyebrow>
        <h1 className="text-4xl">Keep this for later</h1>
        <p className="text-[15px] leading-relaxed text-ink-dim">
          Free account — just an email and a magic link to come back.
        </p>
      </header>
      <Panel>
        <SaveForecastContent />
      </Panel>
    </PageContainer>
  );
}
