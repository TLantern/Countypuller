import { NextRequest, NextResponse } from 'next/server';
import prisma from '../../../lib/prisma';
import { normalizeAttomParams } from '@/lib/utils';
import { getServerSession } from "next-auth";
import { authOptions } from "../auth/[...nextauth]/authOptions";

// Helper to detect web search intent
function hasWebSearchIntent(message: string): boolean {
  const triggers = [
    'search online',
    'look up',
    'find on the web',
    'google',
    'search the web',
    'browse the web',
    'search for',
    'look this up',
    'find information about',
  ];
  const lower = message.toLowerCase();
  return triggers.some(trigger => lower.includes(trigger));
}

// Helper to extract postal code from message (simple US ZIP regex)
function extractPostalCode(message: string): string | null {
  const zipMatch = message.match(/\b\d{5}(?:-\d{4})?\b/);
  return zipMatch ? zipMatch[0] : null;
}

// Helper to evaluate if SERP results are sufficient
function areSerpResultsSufficient(webResults: any[], hasWebSearchIntent: boolean): boolean {
  // If user explicitly requested web search, accept any results
  if (hasWebSearchIntent && webResults.length > 0) {
    return true;
  }
  
  // For property-related queries, check if we have enough relevant results
  if (webResults.length >= 3) {
    // Check if results contain property-related terms
    const propertyTerms = ['property', 'real estate', 'home', 'house', 'address', 'zillow', 'realtor', 'mls'];
    const relevantResults = webResults.filter(result => {
      const text = (result.title + ' ' + result.snippet).toLowerCase();
      return propertyTerms.some(term => text.includes(term));
    });
    
    return relevantResults.length >= 2;
  }
  
  return false;
}

export async function POST(req: NextRequest) {
  const { message, chatHistory } = await req.json();

  console.log("Received message:", message);

  // Helper to fetch property data if needed (stub, replace with real logic if available)
  async function fetchPropertyData(params: any) {
    // You can implement a real lookup here if you have a property DB or API
    // For now, just return an empty object
    return {};
  }

  // 1. Normalize user input for potential ATTOM API use later
  const { street, city, state, zip, county } = await normalizeAttomParams(message, fetchPropertyData);
  console.log("Normalized params:", { street, city, state, zip, county });
  const hasAddress = street && city && state && zip;

  // 2. FIRST: Try web search with SERP API
  let webResults = [];
  let serpResultsSufficient = false;
  
  if (process.env.SERPAPI_KEY) {
    let searchQuery = message;
    
    // If we have address info but no explicit web search intent, search by address
    if (!hasWebSearchIntent(message) && hasAddress) {
      searchQuery = [street, city, state, zip].filter(Boolean).join(', ');
    }
    
    console.log('SERP Search Query:', searchQuery);
    
    try {
      const serpRes = await fetch(
        `https://serpapi.com/search.json?q=${encodeURIComponent(searchQuery)}&engine=google&api_key=${process.env.SERPAPI_KEY}`
      );
      const serpData = await serpRes.json();
      webResults = (serpData.organic_results || []).map((item: any) => ({
        title: item.title,
        url: item.link,
        snippet: item.snippet,
      }));
      
      console.log(`SERP returned ${webResults.length} results`);
      serpResultsSufficient = areSerpResultsSufficient(webResults, hasWebSearchIntent(message));
      console.log('SERP results sufficient:', serpResultsSufficient);
    } catch (e) {
      console.error('SERP Fetch Error:', e);
    }
  }

  // Helper to build query string for ATTOM
  function buildAttomParams() {
    return [
      `street=${encodeURIComponent(street)}`,
      city ? `city=${encodeURIComponent(city)}` : '',
      state ? `state=${encodeURIComponent(state)}` : '',
      zip ? `zip=${encodeURIComponent(zip)}` : '',
      county ? `county=${encodeURIComponent(county)}` : 'county=US'
    ].filter(Boolean).join(',');
  }
}