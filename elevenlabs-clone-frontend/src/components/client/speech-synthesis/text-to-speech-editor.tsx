"use client";

import { useEffect, useState } from "react";
import {
  IoBookOutline,
  IoFilmOutline,
  IoGameControllerOutline,
  IoHappyOutline,
  IoLanguageOutline,
  IoLeafOutline,
  IoMegaphoneOutline,
  IoMicOutline,
} from "react-icons/io5";
import { ServiceType } from "~/types/services";
import { GenerateButton } from "../generate-button";
import {
  generateTextToSpeech,
  generateTextToSpeechFromService, // Import the new action
  generationStatus,
} from "~/actions/generate-speech";
import { useVoiceStore } from "~/stores/voice-store";
import { useAudioStore } from "~/stores/audio-store";
import toast from "react-hot-toast";

export function TextToSpeechEditor({
  service,
  credits,
}: {
  service: ServiceType;
  credits: number;
}) {
  const [textContent, setTextContent] = useState("");
  const [activePlaceholder, setActivePlaceholder] = useState(
    "Start typing here or paste any text you want to turn into lifelike speech...",
  );
  const [loading, setLoading] = useState(false);
  const [currentAudioId, setCurrentAudioId] = useState<string | null>(null);

  const getSelectedVoice = useVoiceStore((state) => state.getSelectedVoice);

  const { playAudio } = useAudioStore();

  useEffect(() => {
    if (!currentAudioId || !loading) return;

    const pollInterval = setInterval(async () => {
      try {
        const status = await generationStatus(currentAudioId);

        const selectedVoice = getSelectedVoice(service); // Use service prop
        if (status.success && status.audioUrl && selectedVoice) {
          clearInterval(pollInterval);
          setLoading(false);

          const newAudio = {
            id: currentAudioId,
            title:
              textContent.substring(0, 50) +
              (textContent.length > 50 ? "..." : ""),
            audioUrl: status.audioUrl,
            voice: selectedVoice.id,
            duration: "0:30",
            progress: 0,
            service: service,
            createdAt: new Date().toLocaleDateString(),
          };

          playAudio(newAudio);
          setCurrentAudioId(null);
        } else if (!status.success) {
          clearInterval(pollInterval);
          setLoading(false);
          setCurrentAudioId(null);
          console.error("Text to speech failed");
        }
      } catch (error) {
        console.error("Error polling for audio status: " + error);
        clearInterval(pollInterval);
        setLoading(false);
        setCurrentAudioId(null);
      }
    }, 500);

    return () => {
      clearInterval(pollInterval);
    };
  }, [
    currentAudioId,
    loading,
    getSelectedVoice,
    playAudio,
    textContent,
    service,
  ]);

  const templateTexts = {
    "Narrate a story":
      "Once upon a time in a forest shrouded in mist, a young adventurer discovered an ancient doorway hidden beneath twisted roots. As they reached out to touch the weathered stone, the forest fell silent. What secrets would be revealed beyond this mysterious threshold?",
    "Tell a silly joke":
      "Why don't scientists trust atoms? Because they make up everything! Speaking of making things up, I once convinced my friend that the moon was just the back of the sun. He believed me until nighttime when both were visible in the sky.",
    "Record an advertisement":
      "Introducing TranquilSleep, the revolutionary mattress designed with cutting-edge comfort technology. Experience the perfect balance of support and softness that adapts to your body. Wake up refreshed and energized every morning! Order now and get 30% off your first purchase.",
    "Speak in different languages":
      "Hello! Hola! Bonjour! Ciao! Konnichiwa! Guten Tag! I can help you communicate your message in multiple languages. Perfect for reaching a global audience or adding an international flair to your content.",
    "Direct a dramatic movie scene":
      "The rain beats against the windows as Sarah stares at the faded photograph. 'I never thought it would end this way,' she whispers, her voice barely audible above the storm. Behind her, the door slowly opens. 'It doesn't have to,' says a familiar voice she never expected to hear again.",
    "Hear from a video game character":
      "Greetings, adventurer! I am Captain Varrick of the Starship Horizon. Our mission to explore the outer reaches of the Andromeda galaxy has led us to this mysterious planet. The energy readings are off the charts, and we need your help to investigate the ancient ruins ahead.",
    "Introduce your podcast":
      "Welcome to 'Unexplained Phenomena,' the podcast where we explore the mysteries that science has yet to solve. I'm your host, Alex Morgan, and today we're diving into the fascinating world of synchronicity – those meaningful coincidences that seem to defy the laws of probability.",
    "Guide a meditation class":
      "Settle into a comfortable position and gently close your eyes. Take a deep breath in through your nose, filling your lungs completely. Hold for a moment, and then exhale slowly through your mouth, releasing any tension you've been carrying. Feel your body becoming heavier with each breath, melting into the surface beneath you.",
  };

  const handleButtonHover = (text: string) => {
    setActivePlaceholder(templateTexts[text as keyof typeof templateTexts]);
  };

  const handleButtonClick = (text: string) => {
    setTextContent(templateTexts[text as keyof typeof templateTexts]);
  };

  const handleGenerateSpeech = async () => {
    const selectedVoice = getSelectedVoice(service); // Use service prop

    if (textContent.trim().length === 0 || !selectedVoice) return;

    try {
      setLoading(true);
      let audioId: string;
      let shouldShowThrottleAlert: boolean;

      if (service === "styletts2") {
        const result = await generateTextToSpeech(
          textContent,
          selectedVoice.id,
        );
        audioId = result.audioId;
        shouldShowThrottleAlert = result.shouldShowThrottleAlert;
      } else if (service === "seedvc") {
        const result = await generateTextToSpeechFromService(
          textContent,
          selectedVoice.id,
        );
        audioId = result.audioId;
        shouldShowThrottleAlert = result.shouldShowThrottleAlert;
      } else {
        // Optional: handle other services or throw an error
        console.error("Unsupported service type in TextToSpeechEditor:", service);
        setLoading(false);
        return;
      }

      if (shouldShowThrottleAlert) {
        toast("Exceeding 3 requests per minute will queue your requests.", {
          icon: "⏳",
        });
      }

      setCurrentAudioId(audioId);
    } catch (error) {
      console.error("Error generating speech: ", error);
      setLoading(false);
    }
  };

  return (
    <>
      <textarea
        value={textContent}
        onChange={(e) => setTextContent(e.target.value)}
        placeholder={activePlaceholder}
        disabled={loading}
        className="w-full flex-grow resize-none rounded-lg bg-white p-4 placeholder:font-light placeholder:text-gray-500 focus:border-none focus:outline-none focus:ring-0"
      />

      <div className="mt-4 px-0 md:px-4">
        {textContent.length === 0 ? (
          <div className="mt-auto">
            <p className="mb-2 text-sm text-gray-500">Get started with</p>

            <div className="flex flex-wrap gap-2">
              {[
                { text: "Narrate a story", icon: <IoBookOutline /> },
                { text: "Tell a silly joke", icon: <IoHappyOutline /> },
                {
                  text: "Record an advertisement",
                  icon: <IoMegaphoneOutline />,
                },
                {
                  text: "Speak in different languages",
                  icon: <IoLanguageOutline />,
                },
                {
                  text: "Direct a dramatic movie scene",
                  icon: <IoFilmOutline />,
                },
                {
                  text: "Hear from a video game character",
                  icon: <IoGameControllerOutline />,
                },
                {
                  text: "Introduce your podcast",
                  icon: <IoMicOutline />,
                },
                {
                  text: "Guide a meditation class",
                  icon: <IoLeafOutline />,
                },
              ].map(({ text, icon }) => (
                <button
                  key={text}
                  className="flex items-center rounded-lg border border-gray-200 bg-white p-2 text-xs hover:bg-gray-50"
                  onMouseEnter={() => handleButtonHover(text)}
                  onMouseLeave={() =>
                    setActivePlaceholder(
                      "Start typing here or paste any text you want to turn into lifelike speech...",
                    )
                  }
                  onClick={() => handleButtonClick(text)}
                >
                  <span className="mr-2 text-gray-500">{icon}</span>
                  {text}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <GenerateButton
            onGenerate={handleGenerateSpeech}
            isDisabled={
              textContent.length > 5000 ||
              textContent.trim().length === 0 ||
              loading
            }
            isLoading={loading}
            showDownload={true}
            creditsRemaining={credits}
            showCredits={true}
            characterCount={textContent.length}
            characterLimit={5000}
          />
        )}
      </div>
    </>
  );
}
