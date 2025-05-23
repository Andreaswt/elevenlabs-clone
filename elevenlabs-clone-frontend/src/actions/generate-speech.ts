"use server";

import { revalidatePath } from "next/cache";
import { inngest } from "~/inngest/client";
// import { getPresignedUrl, getUploadUrl } from "~/lib/s3"; // Removed
import { auth } from "~/server/auth";
import { db } from "~/server/db";
import { ServiceType } from "~/types/services"; // Keep for now, may be simplified later
import { env } from "~/env"; // Added for SEED_VC_API_ROUTE

// Obsolete function generateTextToSpeech (for styletts2) has been removed.

export async function generateTextToSpeechFromService(
  text: string,
  voice: string,
) {
  const session = await auth();
  if (!session?.user.id) {
    throw new Error("User not authenticated");
  }

  const audioClipJob = await db.generatedAudioClip.create({
    data: {
      text: text,
      voice: voice,
      user: {
        connect: {
          id: session.user.id,
        },
      },
      service: "seedvc",
    },
  });

  await inngest.send({
    name: "generate.request",
    data: {
      audioClipId: audioClipJob.id,
      userId: session.user.id,
    },
  });

  return {
    audioId: audioClipJob.id,
    shouldShowThrottleAlert: await shouldShowThrottleAlert(session.user.id),
  };
}

// Obsolete function generateSoundEffect (for make-an-audio) has been removed.

const shouldShowThrottleAlert = async (userId: string) => {
  const oneMinuteAgo = new Date();
  oneMinuteAgo.setMinutes(oneMinuteAgo.getMinutes() - 1);

  const count = await db.generatedAudioClip.count({
    where: {
      userId: userId,
      createdAt: {
        gte: oneMinuteAgo,
      },
    },
  });

  return count > 3;
};

export async function generationStatus(
  audioId: string,
): Promise<{ success: boolean; audioUrl: string | null }> {
  const session = await auth();

  const audioClip = await db.generatedAudioClip.findFirstOrThrow({
    where: { id: audioId, userId: session?.user.id },
    select: {
      id: true,
      failed: true,
      s3Key: true,
      service: true,
    },
  });

  if (audioClip.failed) {
    revalidateBasedOnService(audioClip.service as ServiceType);
    return { success: false, audioUrl: null };
  }

  if (audioClip.s3Key) {
    revalidateBasedOnService(audioClip.service as ServiceType); // Keep this
    // Ensure no double slashes if s3Key starts with '/' and SEED_VC_API_ROUTE doesn't end with '/'
    const baseUrl = env.SEED_VC_API_ROUTE.endsWith('/') ? env.SEED_VC_API_ROUTE.slice(0, -1) : env.SEED_VC_API_ROUTE;
    const audioPath = audioClip.s3Key.startsWith('/') ? audioClip.s3Key : '/' + audioClip.s3Key;
    return {
      success: true,
      audioUrl: baseUrl + audioPath,
    };
  }

  return {
    success: true,
    audioUrl: null,
  };
}

const revalidateBasedOnService = async (service: ServiceType) => {
  // Only "seedvc" is expected now.
  // The path might be updated in a subsequent step when UI routes are changed.
  if (service === "seedvc") {
    revalidatePath("/app/speech-synthesis/main"); 
  }
  // Removed cases for "styletts2" and "make-an-audio"
};

// Obsolete function generateUploadUrl has been removed.
