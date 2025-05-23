import { db } from "~/server/db";
import { inngest } from "./client";
import { env } from "~/env";

export const aiGenerationFunction = inngest.createFunction(
  {
    id: "genrate-audio-clip",
    retries: 2,
    throttle: {
      limit: 3,
      period: "1m",
      key: "event.data.userId",
    },
  },
  { event: "generate.request" },
  async ({ event, step }) => {
    const { audioClipId } = event.data;

    const audioClip = await step.run("get-clip", async () => {
      return await db.generatedAudioClip.findUniqueOrThrow({
        where: { id: audioClipId },
        select: {
          id: true,
          text: true,
          voice: true,
          userId: true,
          service: true,
          originalVoiceS3Key: true,
        },
      });
    });

    const result = await step.run("call-api", async () => {
      // Only SeedVC service is supported now.
      // Consider adding a check here if audioClip.service is not 'seedvc' and throw an error,
      // though subsequent steps will remove other services from being selected.
      if (audioClip.service !== "seedvc") {
        // This case should ideally not be reached if frontend only allows 'seedvc'
        await db.generatedAudioClip.update({
          where: { id: audioClip.id },
          data: { failed: true, failureReason: "Invalid service selected" },
        });
        throw new Error(
          `Unsupported service: ${audioClip.service}. Only 'seedvc' is allowed.`,
        );
      }

      const response = await fetch(env.SEED_VC_API_ROUTE + "/convert", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: env.BACKEND_API_KEY,
        },
        body: JSON.stringify({
          text: audioClip.text,
          voice: audioClip.voice,
          user_id: audioClip.userId, // Added user_id
        }),
      });

      if (!response.ok) {
        const errorBody = await response.text();
        await db.generatedAudioClip.update({
          where: { id: audioClip.id },
          data: {
            failed: true,
            failureReason: `API error: ${response.status} ${response.statusText} - ${errorBody}`,
          },
        });
        throw new Error(
          `API error: ${response.status} ${response.statusText} - ${errorBody}`,
        );
      }
      // Updated response type
      return response.json() as Promise<{
        audio_url: string;
        local_path: string;
      }>;
    });

    const history = await step.run("save-to-history", async () => {
      return await db.generatedAudioClip.update({
        where: { id: audioClip.id },
        data: {
          s3Key: result.audio_url, // Changed from result.s3_key to result.audio_url
          // Optional: could also store result.local_path if needed for debugging or other backend processes
        },
      });
    });

    const deductCredits = await step.run("deduct-credits", async () => {
      return await db.user.update({
        where: { id: audioClip.userId },
        data: {
          credits: {
            decrement: 50,
          },
        },
      });
    });

    return { success: true };
  },
);
