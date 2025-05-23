import { PageLayout } from "~/components/client/page-layout";
import { TextToSpeechEditor } from "~/components/client/speech-synthesis/text-to-speech-editor";
// import { VoiceChanger } from "~/components/client/speech-synthesis/voice-changer"; // No longer needed
import { getHistoryItems } from "~/lib/history";
import { auth } from "~/server/auth";
import { db } from "~/server/db";

export default async function SpeechToSpeechPage() {
  const session = await auth();
  const userId = session?.user.id;

  let credits = 0;

  if (userId) {
    const user = await db.user.findUnique({
      where: { id: userId },
      select: {
        credits: true,
      },
    });
    credits = user?.credits ?? 0;
  }

  const service = "seedvc";

  const historyItems = await getHistoryItems(service);

  return (
    <PageLayout
      title={"Text-to-Speech (SeedVC)"}
      service={service}
      showSidebar={true}
      historyItems={historyItems}
    >
      <TextToSpeechEditor credits={credits} service={service} />
    </PageLayout>
  );
}
