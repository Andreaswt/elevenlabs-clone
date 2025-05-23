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
      let response: Response | null = null;

      if (audioClip.service === "styletts2") {
        response = await fetch(env.STYLETTS2_API_ROUTE + "/generate", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: env.BACKEND_API_KEY,
          },
          body: JSON.stringify({
            text: audioClip.text,
            target_voice: audioClip.voice,
          }),
        });
      } else if (audioClip.service === "seedvc") {
        response = await fetch(env.SEED_VC_API_ROUTE + "/convert", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: env.BACKEND_API_KEY,
          },
          body: JSON.stringify({
            text: audioClip.text,
            voice: audioClip.voice,
          }),
        });
      } else if (audioClip.service === "make-an-audio") {
        response = await fetch(env.MAKE_AN_AUDIO_API_ROUTE + "/generate", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: env.BACKEND_API_KEY,
          },
          body: JSON.stringify({
            prompt: audioClip.text,
          }),
        });
      }

      if (!response) {
        throw new Error("API error: no response");
      }

      if (!response.ok) {
        await db.generatedAudioClip.update({
          where: { id: audioClip.id },
          data: {
            failed: true,
          },
        });

        throw new Error("API error: " + response.statusText);
      }

      return response.json() as Promise<{ audio_url: string; s3_key: string }>;
    });

    const history = await step.run("save-to-history", async () => {
      return await db.generatedAudioClip.update({
        where: { id: audioClip.id },
        data: {
          s3Key: result.s3_key,
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
