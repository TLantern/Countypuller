"use client";
import { usePathname } from "next/navigation";
import { useFeedback } from "@/context/FeedbackContext";
import ThemeToggle from "@/components/ThemeToggle";
import ChatbotWidget from "@/components/ChatbotWidget";

export default function ClientOnlyToggles() {
  const pathname = usePathname();
  const { isFeedbackPanelOpen } = useFeedback();
  
  if (!pathname.startsWith("/dashboard")) return null;
  return (
    <>
      {/* ThemeToggle is now shown directly in dashboard header, so hide it here */}
      <ChatbotWidget isHidden={isFeedbackPanelOpen} />
    </>
  );
} 