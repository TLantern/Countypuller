"use client";

import React, { createContext, useContext, useState, ReactNode } from 'react';

interface FeedbackContextType {
  isFeedbackPanelOpen: boolean;
  setIsFeedbackPanelOpen: (open: boolean) => void;
}

const FeedbackContext = createContext<FeedbackContextType | undefined>(undefined);

export function FeedbackProvider({ children }: { children: ReactNode }) {
  const [isFeedbackPanelOpen, setIsFeedbackPanelOpen] = useState(false);

  return (
    <FeedbackContext.Provider value={{ isFeedbackPanelOpen, setIsFeedbackPanelOpen }}>
      {children}
    </FeedbackContext.Provider>
  );
}

export function useFeedback() {
  const context = useContext(FeedbackContext);
  if (!context) {
    throw new Error('useFeedback must be used within a FeedbackProvider');
  }
  return context;
} 