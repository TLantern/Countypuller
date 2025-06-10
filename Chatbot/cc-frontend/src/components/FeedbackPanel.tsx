'use client';

import React, { useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { X, Info, Star } from 'lucide-react';

interface FeedbackPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

const FeedbackPanel: React.FC<FeedbackPanelProps> = ({ isOpen, onClose }) => {
  const [rating, setRating] = useState(0);
  const [hoverRating, setHoverRating] = useState(0);
  const [feedback, setFeedback] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [isFocused, setIsFocused] = useState(false);

  const handleSubmit = async () => {
    if (!feedback.trim()) {
      setHasError(true);
      return;
    }

    setIsSubmitting(true);
    setHasError(false);

    try {
      // Here you would typically send the feedback to your API
      console.log('Feedback submitted:', { rating, feedback });
      
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Reset form and close panel
      setRating(0);
      setFeedback('');
      onClose();
    } catch (error) {
      setHasError(true);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRatingClick = (selectedRating: number) => {
    setRating(selectedRating);
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setFeedback(e.target.value);
    if (hasError && e.target.value.trim()) {
      setHasError(false);
    }
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Overlay - dims the background */}
      <div 
        className={`fixed inset-0 bg-black transition-all duration-300 z-40 ${
          isOpen ? 'bg-opacity-30' : 'bg-opacity-0 pointer-events-none'
        }`}
        onClick={onClose}
      />
      
      {/* Panel - slides in from right */}
      <div className={`fixed right-0 top-0 h-full w-96 bg-white shadow-xl transform transition-all duration-300 ease-out z-50 ${
        isOpen ? 'translate-x-0' : 'translate-x-full'
      }`}>
        <Card className="h-full rounded-none border-0 shadow-none bg-white">
          <div className="p-6 h-full flex flex-col border-l border-gray-200">
            {/* Header */}
            <div className="flex items-center justify-between mb-6 pb-4 border-b border-gray-100">
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-semibold text-gray-900">Your Feedback</h2>
                <Info className="w-4 h-4 text-blue-500" />
              </div>
              <button
                onClick={onClose}
                className="p-2 rounded-full hover:bg-gray-100 transition-colors"
              >
                <X className="w-5 h-5 text-gray-400 hover:text-gray-600" />
              </button>
            </div>

            {/* Star Rating */}
            <div className="mb-6">
              <Label className="text-sm font-medium text-gray-700 mb-3 block">
                How would you rate your experience?
              </Label>
              <div className="flex gap-1">
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    type="button"
                    className="p-1 rounded-md hover:bg-gray-50 transition-colors"
                    onClick={() => handleRatingClick(star)}
                    onMouseEnter={() => setHoverRating(star)}
                    onMouseLeave={() => setHoverRating(0)}
                  >
                    <Star
                      className={`w-6 h-6 transition-colors ${
                        star <= (hoverRating || rating)
                          ? 'fill-yellow-400 text-yellow-400'
                          : 'text-gray-300'
                      }`}
                    />
                  </button>
                ))}
              </div>
            </div>

            {/* Feedback Text Area */}
            <div className="flex-1 mb-6">
              <Label className="text-sm font-medium text-gray-700 mb-2 block">
                What can we improve?
              </Label>
              <div className="relative">
                <textarea
                  value={feedback}
                  onChange={handleTextareaChange}
                  onFocus={() => setIsFocused(true)}
                  onBlur={() => setIsFocused(false)}
                  placeholder="Share your thoughts, suggestions, or report any issues..."
                  className={`w-full h-32 p-3 border-2 rounded-lg resize-none transition-all duration-200 text-black ${
                    hasError
                      ? 'border-red-500 focus:border-red-500 focus:ring-2 focus:ring-red-200'
                      : isFocused
                      ? 'border-blue-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-200'
                      : 'border-gray-300 hover:border-gray-400'
                  } focus:outline-none placeholder-gray-400`}
                />
              </div>
              {hasError && (
                <p className="text-red-500 text-sm mt-2">
                  Please provide your feedback before submitting.
                </p>
              )}
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3 pt-6 border-t border-gray-100">
              <Button
                onClick={handleSubmit}
                disabled={isSubmitting}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-6 rounded-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm hover:shadow-md"
              >
                {isSubmitting ? 'Submitting...' : 'Submit Feedback'}
              </Button>
              <button
                onClick={onClose}
                className="px-4 py-3 text-gray-600 hover:text-gray-800 font-medium transition-colors hover:bg-gray-50 rounded-lg"
              >
                Dismiss
              </button>
            </div>
          </div>
        </Card>
      </div>
    </>
  );
};

export default FeedbackPanel; 