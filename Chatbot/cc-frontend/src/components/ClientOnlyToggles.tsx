"use client";
import { usePathname } from "next/navigation";
import ThemeToggle from "@/components/ThemeToggle";
import ChatbotWidget from "@/components/ChatbotWidget";

export default function ClientOnlyToggles() {
  const pathname = usePathname();
  
  if (!pathname.startsWith("/dashboard")) return null;
  return (
    <>
      {/* ThemeToggle is now shown directly in dashboard header, so hide it here */}
      <ChatbotWidget />
    </>
  );
} 