'use client';
import React, { useEffect, useState } from "react";
import { useSession, signOut } from "next-auth/react";
import { useRouter } from "next/navigation";
import { AppSidebar } from "@/components/app-sidebar"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Separator } from "@/components/ui/separator"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { DataGrid, GridColDef } from '@mui/x-data-grid'
import { Dialog, DialogTitle, DialogContent, DialogActions, Button } from '@mui/material';
import ChatBox from '../../components/ChatBox';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import { Box, Typography } from '@mui/material';

import { MessageSquare } from 'lucide-react';
import ThemeToggle from '@/components/ThemeToggle';
import TrialBanner from '@/components/TrialBanner';
// Dynamic imports used in export functions to avoid SSR issues

const SkipTraceButton = ({ address }: { address?: string }) => {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [showResult, setShowResult] = useState(false);
  const [savedToast, setSavedToast] = useState(false);
  const [hasExistingResult, setHasExistingResult] = useState(false);
  const [checkingExisting, setCheckingExisting] = useState(true);

  // Check if address already has skip trace results
  useEffect(() => {
    const checkExistingResult = async () => {
      if (!address || !address.trim()) {
        setCheckingExisting(false);
        return;
      }

      try {
        const response = await fetch(`/api/skip-trace?address=${encodeURIComponent(address)}`);
        const data = await response.json();
        
        if (data.success && data.hasResult) {
          setHasExistingResult(true);
          // Pre-load the result for quick display
          if (data.result) {
            setResult(data.result);
          }
        }
      } catch (error) {
        console.error('Error checking existing skip trace:', error);
      } finally {
        setCheckingExisting(false);
      }
    };

    checkExistingResult();
  }, [address]);

  const handleShowReport = async () => {
    if (hasExistingResult && result) {
      // Show cached result immediately
      setShowResult(true);
    } else {
      // Fetch the full result
      setLoading(true);
      try {
        const response = await fetch('/api/skip-trace', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ address }),
        });

        const data = await response.json();

        if (data.success && data.data) {
          setResult(data.data);
          setShowResult(true);
          setHasExistingResult(true);
        } else {
          alert(`Failed to load report: ${data.error || 'Unknown error'}`);
        }
      } catch (error) {
        console.error('Error loading report:', error);
        alert('Failed to load report: Network error');
      } finally {
        setLoading(false);
      }
    }
  };

  const handleSkipTrace = async () => {
    if (!address || !address.trim()) {
      alert('No address available for skip trace');
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const response = await fetch('/api/skip-trace', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ address }),
      });

      const data = await response.json();

      if (data.success && data.data) {
        setResult(data.data);
        setShowResult(true);
        setHasExistingResult(true);
      } else {
        alert(`Skip trace failed: ${data.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Skip trace error:', error);
      alert('Skip trace failed: Network error');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveReport = () => {
    if (!result) return;
    try {
      const storageKey = 'savedSkipTraces';
      const existing: any[] = JSON.parse(localStorage.getItem(storageKey) || '[]');
      // Avoid duplicates by attomid+address
      const dup = existing.find(r => r.attomid === result.attomid && r.canonical_address === result.canonical_address);
      if (!dup) {
        existing.push(result);
        localStorage.setItem(storageKey, JSON.stringify(existing));
        setSavedToast(true);
        setTimeout(() => setSavedToast(false), 3000);
      } else {
        alert('Report already saved');
      }
    } catch (e) {
      console.error('Save report error', e);
      alert('Could not save report');
    }
  };

  // Show loading state while checking for existing results
  if (checkingExisting) {
    return (
      <button
        disabled
        className="text-sm px-2 py-1 rounded bg-gray-300 text-gray-500 cursor-not-allowed"
      >
        ...
      </button>
    );
  }

  return (
    <>
      <button
        onClick={hasExistingResult ? handleShowReport : handleSkipTrace}
        disabled={loading || !address}
        className={`text-sm px-2 py-1 rounded ${
          loading 
            ? 'bg-gray-400 text-white cursor-not-allowed' 
            : hasExistingResult
              ? 'bg-green-600 hover:bg-green-700 text-white cursor-pointer'
              : 'bg-blue-600 hover:bg-blue-700 text-white cursor-pointer'
        }`}
        title={
          !address 
            ? 'No address available' 
            : hasExistingResult 
              ? `Show existing report for ${address}` 
              : `Skip trace for ${address}`
        }
      >
        {loading 
          ? (hasExistingResult ? 'Loading...' : 'Tracing...') 
          : (hasExistingResult ? 'View' : 'Trace')
        }
      </button>

      {/* Results Modal */}
      {showResult && result && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-10 w-[90vw] max-w-9xl max-h-[90vh] overflow-y-auto relative">
            <div className="flex justify-between items-center mb-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Skip Trace Results</h3>
                {hasExistingResult && (
                  <p className="text-sm text-green-600 mt-1">✓ Saved report from database</p>
                )}
              </div>
              <button
                onClick={() => setShowResult(false)}
                className="text-gray-400 hover:text-gray-600 text-xl"
              >
                ×
              </button>
            </div>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-gray-800">
              <div className="bg-gray-50 p-4 rounded shadow">
                <div className="text-gray-600 mb-2">Address:</div>
                <div className="font-medium text-xl">{result.raw_address}</div>
              </div>
              
              {result.owner_name && (
                <div className="bg-purple-50 p-4 rounded shadow">
                  <div className="text-gray-600 mb-2">Owner Name:</div>
                  <div className="text-purple-800 font-semibold text-2xl">{result.owner_name}</div>
                </div>
              )}
              
              {result.market_value && (
                <div className="bg-indigo-50 p-4 rounded shadow">
                  <div className="text-gray-600 mb-2">Market Value:</div>
                  <div className="text-indigo-800 font-semibold text-xl">
                    ${result.market_value.toLocaleString()}
                  </div>
                </div>
              )}
              
              {result.est_balance && (
                <div className="bg-green-50 p-4 rounded shadow">
                  <div className="text-gray-600 mb-2">Estimated Loan Balance:</div>
                  <div className="text-green-800 font-semibold text-xl">
                    ${result.est_balance.toLocaleString()}
                  </div>
                </div>
              )}
              
              {result.available_equity && (
                <div className="bg-blue-50 p-4 rounded shadow">
                  <div className="text-gray-600 mb-2">Available Equity:</div>
                  <div className="text-blue-800 font-semibold text-xl">
                    ${result.available_equity.toLocaleString()}
                  </div>
                </div>
              )}
              
              {result.ltv && (
                <div className="bg-yellow-50 p-4 rounded shadow">
                  <div className="text-gray-600 mb-2">Loan-to-Value (LTV):</div>
                  <div className="text-yellow-800 font-semibold text-xl">
                    {result.ltv.toFixed(1)}%
                  </div>
                </div>
              )}
              
              {result.loans_count > 0 && (
                <div className="bg-gray-50 p-4 rounded shadow">
                  <div className="text-gray-600 mb-2">Number of Loans:</div>
                  <div className="font-medium text-xl">{result.loans_count}</div>
                </div>
              )}
              
              <div className="bg-gray-50 p-4 rounded shadow">
                <div className="text-gray-600 mb-2">Processed at:</div>
                <div className="text-base">{new Date(result.processed_at).toLocaleString()}</div>
              </div>
              
              {/* Coming Soon Cards */}
              <div className="bg-orange-50 p-4 rounded shadow border-2 border-orange-200">
                <div className="text-gray-600 mb-2">Email Address:</div>
                <div className="text-orange-600 font-medium italic text-xl">Coming Soon</div>
              </div>
              
              <div className="bg-orange-50 p-4 rounded shadow border-2 border-orange-200">
                <div className="text-gray-600 mb-2">Phone Number:</div>
                <div className="text-orange-600 font-medium italic text-xl">Coming Soon</div>
              </div>
            </div>
            
            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={handleSaveReport}
                className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded shadow"
              >
                Save Report
              </button>
              <button
                onClick={() => setShowResult(false)}
                className="bg-gray-500 hover:bg-gray-600 text-white px-4 py-2 rounded"
              >
                Close
              </button>
            </div>
            {/* Saved toast at end of modal */}
            {savedToast && (
              <div className="fixed bottom-6 right-6 bg-yellow-500 text-white px-4 py-2 rounded shadow-lg z-50">
                Report saved
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
};

const Hot20Button = ({ data, userType }: { data: any[], userType: string }) => {
  const [processing, setProcessing] = useState(false);
  const [results, setResults] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [showResults, setShowResults] = useState(false);

  const handleHot20Click = async () => {
    setProcessing(true);
    setResults([]);
    setSummary(null);
    
    try {
      console.log('Starting Hot 20 analysis for', data.length, 'current dashboard records');
      
      // Extract addresses from current dashboard data
      const currentProperties = data
        .filter(record => {
          // Only Harris County records now
          const address = record.property_address;
          return address && address.trim() !== '';
        })
        .map(record => ({
          id: record.case_number || record.id,
          address: record.property_address || '',
          original_record: record
        }));

      if (currentProperties.length === 0) {
        alert('No properties with addresses found in current dashboard data');
        return;
      }

      console.log(`Found ${currentProperties.length} properties with addresses to analyze`);
      
      const response = await fetch('/api/hot-20', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          userType,
          properties: currentProperties
        }),
      });

      const responseData = await response.json();

      if (responseData.success) {
        setResults(responseData.data);
        setSummary(responseData.summary);
        setShowResults(true);
        console.log('Hot 20 analysis complete:', responseData);
      } else {
        alert(`Hot 20 analysis failed: ${responseData.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Hot 20 error:', error);
      alert('Hot 20 analysis failed: Network error');
    } finally {
      setProcessing(false);
    }
  };

  return (
    <>
      <button
        onClick={handleHot20Click}
        disabled={processing || data.length === 0}
        className={`
          hot-gradient text-white font-bold py-2 px-4 rounded-lg shadow-lg 
          transition-all duration-200 flex items-center gap-2 transform
          ${processing || data.length === 0 
            ? 'opacity-50 cursor-not-allowed' 
            : 'hover:shadow-2xl hover:scale-105 active:scale-95 active:shadow-md cursor-pointer'
          }
        `}
        title={data.length === 0 ? 'No data available' : 'Analyze top 20 hottest prospects by equity and LTV'}
      >
        <span className="text-lg">🔥</span>
        <span className="font-semibold">
          {processing ? 'Analyzing...' : 'Hot 20'}
        </span>
      </button>

      {/* Hot 20 Results Modal */}
      {showResults && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-6xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                <span className="text-2xl">🔥</span>
                Hot 20 Analysis Results
              </h2>
              <button
                onClick={() => setShowResults(false)}
                className="text-gray-400 hover:text-gray-600 text-2xl font-bold"
              >
                ×
              </button>
            </div>
            
            {/* Summary Statistics */}
            {summary && (
              <div className="bg-gradient-to-r from-red-50 to-green-50 p-4 rounded-lg mb-6">
                <h3 className="text-lg font-semibold text-gray-800 mb-3">Analysis Summary</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div className="bg-white p-3 rounded shadow">
                    <div className="text-gray-600">Total Properties</div>
                    <div className="text-xl font-bold text-blue-600">{summary.total_properties_analyzed}</div>
                  </div>
                  <div className="bg-white p-3 rounded shadow">
                    <div className="text-gray-600">With Equity Data</div>
                    <div className="text-xl font-bold text-green-600">{summary.properties_with_equity}</div>
                  </div>
                  <div className="bg-white p-3 rounded shadow">
                    <div className="text-gray-600">Avg Equity</div>
                    <div className="text-xl font-bold text-green-700">
                      ${Math.round(summary.avg_equity).toLocaleString()}
                    </div>
                  </div>
                  <div className="bg-white p-3 rounded shadow">
                    <div className="text-gray-600">Avg LTV</div>
                    <div className="text-xl font-bold text-red-600">
                      {(summary.avg_ltv * 100).toFixed(1)}%
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Results Table */}
            {results.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-100"> 
                      <th className="text-left p-3 font-semibold text-black">#</th>
                      <th className="text-left p-3 font-semibold text-black">Property Address</th>
                      <th className="text-left p-3 font-semibold text-black">Available Equity</th>
                      <th className="text-left p-3 font-semibold text-black">LTV Ratio</th>
                      <th className="text-left p-3 font-semibold text-black">Loan Balance</th>
                      <th className="text-left p-3 font-semibold text-black">Market Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((property, index) => (
                      <tr key={`${property.id}-${index}`} className={index % 2 === 0 ? 'bg-gray-50' : 'bg-white'}>
                        <td className="p-3 font-bold text-gray-600">#{index + 1}</td>
                        <td className="p-3">
                          <div className="font-medium text-gray-900">{property.property_address}</div>
                          {property.canonical_address !== property.property_address && (
                            <div className="text-xs text-gray-500">{property.canonical_address}</div>
                          )}
                        </td>
                        <td className="p-3">
                          <span className="font-bold text-green-700 text-lg">
                            ${property.available_equity?.toLocaleString() || 'N/A'}
                          </span>
                        </td>
                        <td className="p-3">
                          <span className={`font-bold text-lg ${
                            (property.ltv || 0) < 0.8 ? 'text-green-600' : 
                            (property.ltv || 0) < 0.9 ? 'text-yellow-600' : 'text-red-600'
                          }`}>
                            {property.ltv ? `${(property.ltv * 100).toFixed(1)}%` : 'N/A'}
                          </span>
                        </td>
                        <td className="p-3 text-gray-700">
                          ${property.est_balance?.toLocaleString() || 'N/A'}
                        </td>
                        <td className="p-3 text-gray-700">
                          ${property.market_value?.toLocaleString() || 'N/A'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <div className="text-4xl mb-4">🔍</div>
                <div className="text-lg font-medium">No properties found with equity data</div>
                <div className="text-sm">Try running data collection first or check your ATTOM API configuration</div>
              </div>
            )}
            
            <div className="mt-6 flex justify-end gap-3">
              {results.length > 0 && (
                <button
                  onClick={() => {
                    // Export functionality could be added here
                    const csvContent = [
                      ['Rank', 'Property Address', 'Available Equity', 'LTV Ratio', 'Loan Balance', 'Market Value'],
                      ...results.map((p, i) => [
                        i + 1,
                        p.property_address,
                        p.available_equity || '',
                        p.ltv ? (p.ltv * 100).toFixed(2) + '%' : '',
                        p.est_balance || '',
                        p.market_value || ''
                      ])
                    ].map(row => row.map(cell => `"${cell}"`).join(',')).join('\n');
                    
                    const blob = new Blob([csvContent], { type: 'text/csv' });
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `hot20_${userType}_${new Date().toISOString().split('T')[0]}.csv`;
                    a.click();
                    window.URL.revokeObjectURL(url);
                  }}
                  className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded font-medium"
                >
                  Export CSV
                </button>
              )}
              <button
                onClick={() => setShowResults(false)}
                className="bg-gray-500 hover:bg-gray-600 text-white px-4 py-2 rounded font-medium"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

// Custom CSS for the slider and Hot 20 button
const sliderStyles = `
  .slider::-webkit-slider-thumb {
    appearance: none;
    height: 16px;
    width: 16px;
    border-radius: 50%;
    background: #ffffff;
    cursor: pointer;
    border: 2px solid #1e40af;
    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
  }
  .slider::-moz-range-thumb {
    height: 16px;
    width: 16px;
    border-radius: 50%;
    background: #ffffff;
    cursor: pointer;
    border: 2px solid #1e40af;
    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
  }
  .hot-gradient {
    background: linear-gradient(45deg, #dc2626, #16a34a, #dc2626, #16a34a);
    background-size: 400% 400%;
    animation: hotGradientShift 3s ease-in-out infinite;
  }
  @keyframes hotGradientShift {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
  }
`;

const PropertyAddressCell = ({ value, row }: { value?: string; row: any }) => {
  // Prefer explicit value, otherwise fallback to row.address / row.property_address
  const text = (value && value.trim()) ? value : (row.address || row.property_address || '—');
  return (
    <span style={{ whiteSpace: 'normal', wordBreak: 'break-word' }}>{text}</span>
  );
};





// Columns for Hillsborough NH users
const hillsboroughNhColumns: GridColDef[] = [
  { field: 'document_number', headerName: 'Document #', minWidth: 110, maxWidth: 130, flex: 0.7 },
  { field: 'document_url', headerName: 'Doc URL', minWidth: 70, maxWidth: 90, flex: 0.5, renderCell: (params) => params.value ? <a href={params.value} target="_blank" rel="noopener noreferrer" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block', width: '100%' }}>Link</a> : '' },
  { field: 'recorded_date', headerName: 'Recorded Date', minWidth: 110, maxWidth: 130, flex: 0.7 },
  { field: 'instrument_type', headerName: 'Type', minWidth: 80, maxWidth: 100, flex: 0.6 },
  { field: 'grantor', headerName: 'Grantor', minWidth: 120, maxWidth: 160, flex: 1 },
  { field: 'grantee', headerName: 'Grantee', minWidth: 120, maxWidth: 160, flex: 1 },
  { field: 'property_address', headerName: 'Property Address', minWidth: 150, flex: 1.2, renderCell: (params) => <PropertyAddressCell value={params.value} row={params.row} /> },
  { field: 'consideration', headerName: 'Amount', minWidth: 80, maxWidth: 100, flex: 0.6 },
  { field: 'county', headerName: 'County', minWidth: 100, maxWidth: 120, flex: 0.7 },
  { field: 'created_at', headerName: 'Created At', minWidth: 120, maxWidth: 160, flex: 1, renderCell: (params) => <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block', width: '100%' }}>{params.value}</span> },
  { field: 'is_new', headerName: 'Is New', minWidth: 60, maxWidth: 70, flex: 0.4, type: 'boolean' },
  // TEMPORARILY HIDDEN - Skip trace button commented out for user onboarding
  // { field: 'skip_trace', headerName: 'Skip Trace', minWidth: 80, maxWidth: 100, flex: 0.6, renderCell: (params) => (
  //   <SkipTraceButton address={params.row.property_address} />
  // ) },
];

// Columns for Brevard FL users
const brevardFlColumns: GridColDef[] = [
  { field: 'case_number', headerName: 'Case #', minWidth: 120, maxWidth: 140, flex: 0.8 },
  { field: 'document_url', headerName: 'Doc URL', minWidth: 70, maxWidth: 90, flex: 0.5, renderCell: (params) => params.value ? <a href={params.value} target="_blank" rel="noopener noreferrer" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block', width: '100%' }}>Link</a> : '' },
  { field: 'file_date', headerName: 'Record Date', minWidth: 110, maxWidth: 130, flex: 0.7 },
  { field: 'case_type', headerName: 'Doc Type', minWidth: 100, maxWidth: 120, flex: 0.8 },
  { field: 'party_name', headerName: 'Party Name', minWidth: 150, maxWidth: 200, flex: 1.2 },
  { field: 'property_address', headerName: 'Property Address', minWidth: 150, flex: 1.2, renderCell: (params) => <PropertyAddressCell value={params.value} row={params.row} /> },
  { field: 'county', headerName: 'County', minWidth: 80, maxWidth: 100, flex: 0.6 },
  { field: 'created_at', headerName: 'Created At', minWidth: 120, maxWidth: 160, flex: 1, renderCell: (params) => <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block', width: '100%' }}>{params.value}</span> },
  { field: 'is_new', headerName: 'Is New', minWidth: 60, maxWidth: 70, flex: 0.4, type: 'boolean' },
  // TEMPORARILY HIDDEN - Skip trace button commented out for user onboarding
  // { field: 'skip_trace', headerName: 'Skip Trace', minWidth: 80, maxWidth: 100, flex: 0.6, renderCell: (params) => (
  //   <SkipTraceButton address={params.row.property_address} />
  // ) },
];

// Columns for Fulton GA users
const fultonGaColumns: GridColDef[] = [
  { field: 'case_number', headerName: 'Case #', minWidth: 120, maxWidth: 140, flex: 0.8 },
  { field: 'document_link', headerName: 'Doc Link', minWidth: 70, maxWidth: 90, flex: 0.5, renderCell: (params) => params.value ? <a href={params.value} target="_blank" rel="noopener noreferrer" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block', width: '100%' }}>Link</a> : '' },
  { field: 'filing_date', headerName: 'Filing Date', minWidth: 110, maxWidth: 130, flex: 0.7 },
  { field: 'document_type', headerName: 'Doc Type', minWidth: 100, maxWidth: 120, flex: 0.8 },
  { field: 'debtor_name', headerName: 'Debtor', minWidth: 150, maxWidth: 200, flex: 1.2 },
  { field: 'claimant_name', headerName: 'Claimant', minWidth: 150, maxWidth: 200, flex: 1.2 },
  { field: 'book_page', headerName: 'Book/Page', minWidth: 100, maxWidth: 120, flex: 0.7 },
  { field: 'county', headerName: 'County', minWidth: 80, maxWidth: 100, flex: 0.6 },
  { field: 'created_at', headerName: 'Created At', minWidth: 120, maxWidth: 160, flex: 1, renderCell: (params) => <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block', width: '100%' }}>{params.value}</span> },
  { field: 'is_new', headerName: 'Is New', minWidth: 60, maxWidth: 70, flex: 0.4, type: 'boolean' },
  // TEMPORARILY HIDDEN - Skip trace button commented out for user onboarding
  // { field: 'skip_trace', headerName: 'Skip Trace', minWidth: 80, maxWidth: 100, flex: 0.6, renderCell: (params) => (
  //   <SkipTraceButton address={params.row.property_address} />
  // ) },
];

// Columns for Cobb GA users
const cobbGaColumns: GridColDef[] = [
  { field: 'case_number', headerName: 'Case #', minWidth: 120, maxWidth: 140, flex: 0.8 },
  { field: 'document_link', headerName: 'Doc Link', minWidth: 70, maxWidth: 90, flex: 0.5, renderCell: (params) => params.value ? <a href={params.value} target="_blank" rel="noopener noreferrer" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block', width: '100%' }}>Link</a> : '' },
  { field: 'filing_date', headerName: 'Filing Date', minWidth: 110, maxWidth: 130, flex: 0.7 },
  { field: 'document_type', headerName: 'Doc Type', minWidth: 100, maxWidth: 120, flex: 0.8 },
  { field: 'debtor_name', headerName: 'Debtor', minWidth: 150, maxWidth: 200, flex: 1.2 },
  { field: 'claimant_name', headerName: 'Claimant', minWidth: 150, maxWidth: 200, flex: 1.2 },
  { field: 'book_page', headerName: 'Book/Page', minWidth: 100, maxWidth: 120, flex: 0.7 },
  { field: 'county', headerName: 'County', minWidth: 80, maxWidth: 100, flex: 0.6 },
  { field: 'created_at', headerName: 'Created At', minWidth: 120, maxWidth: 160, flex: 1, renderCell: (params) => <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block', width: '100%' }}>{params.value}</span> },
  { field: 'is_new', headerName: 'Is New', minWidth: 60, maxWidth: 70, flex: 0.4, type: 'boolean' },
  // TEMPORARILY HIDDEN - Skip trace button commented out for user onboarding
  // { field: 'skip_trace', headerName: 'Skip Trace', minWidth: 80, maxWidth: 100, flex: 0.6, renderCell: (params) => (
  //   <SkipTraceButton address={params.row.property_address} />
  // ) },
];

// Types for different record types
interface LisPendensRecord {
  case_number: string;
  file_date: string;
  property_address: string;
  filing_no: string;
  volume_no: string;
  page_no: string;
  county: string;
  created_at: string;
  is_new: boolean;
  doc_type: string;
  ai_summary?: string;
}

interface MdCaseSearchRecord {
  case_number: string;
  file_date: string;
  party_name: string;
  case_type: string;
  county: string;
  property_address: string;
  defendant_info: string;
  created_at: string;
  is_new: boolean;
  doc_type: string;
}

interface HillsboroughNhRecord {
  document_number: string;
  document_url: string;
  recorded_date: string;
  instrument_type: string;
  grantor: string;
  grantee: string;
  property_address: string;
  book_page: string;
  consideration: string;
  legal_description: string;
  county: string;
  state: string;
  filing_date: string;
  amount: string;
  parties: string;
  location: string;
  status: string;
  created_at: string;
  is_new: boolean;
  doc_type: string;
}

interface BrevardFlRecord {
  case_number: string;
  document_url: string;
  file_date: string;
  case_type: string;
  party_name: string;
  property_address: string;
  county: string;
  created_at: string;
  is_new: boolean;
}

interface FultonGaRecord {
  case_number: string;
  document_type: string;
  filing_date: string;
  debtor_name: string;
  claimant_name: string;
  county: string;
  book_page: string;
  document_link: string;
  state: string;
  created_at: string;
  is_new: boolean;
}

interface CobbGaRecord {
  case_number: string;
  document_type: string;
  filing_date: string;
  debtor_name: string;
  claimant_name: string;
  county: string;
  book_page: string;
  document_link: string;
  state: string;
  created_at: string;
  is_new: boolean;
}

// Add a union type covering every possible record shape used by the grid
type AnyRecord =
  | LisPendensRecord
  | MdCaseSearchRecord
  | HillsboroughNhRecord
  | BrevardFlRecord
  | FultonGaRecord
  | CobbGaRecord;

// Export Button Component
interface ExportButtonProps {
  data: any[];
  userType: string;
  displayTitle: string;
}

const ExportButton: React.FC<ExportButtonProps> = ({ data, userType, displayTitle }) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = React.useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  React.useEffect(() => {
    try {
      const handleClickOutside = (event: MouseEvent) => {
        if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
          setIsOpen(false);
        }
      };

      document.addEventListener('mousedown', handleClickOutside);
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    } catch (error) {
      console.error('Event listener setup error:', error);
    }
  }, []);

  const exportToCSV = async () => {
    try {
      if (data.length === 0) {
        alert('No data to export');
        return;
      }
      const fileSaver = await import('file-saver');
      const saveAs = fileSaver.saveAs || fileSaver.default;
      const csvContent = convertToCSV(data);
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      saveAs(blob, `${displayTitle.replace(/\s+/g, '_')}_${new Date().toISOString().split('T')[0]}.csv`);
      setIsOpen(false);
    } catch (error) {
      console.error('CSV Export Error:', error);
      alert('Failed to export CSV file');
      setIsOpen(false);
    }
  };

  const exportToExcel = async () => {
    try {
      if (data.length === 0) {
        alert('No data to export');
        return;
      }
      const XLSX = (await import('xlsx')).default;
      const worksheet = (XLSX.utils as any).json_to_sheet(data);
      const workbook = (XLSX.utils as any).book_new();
      (XLSX.utils as any).book_append_sheet(workbook, worksheet, displayTitle);
      XLSX.writeFile(workbook, `${displayTitle.replace(/\s+/g, '_')}_${new Date().toISOString().split('T')[0]}.xlsx`);
      setIsOpen(false);
    } catch (error) {
      console.error('Excel Export Error:', error);
      alert('Failed to export Excel file');
      setIsOpen(false);
    }
  };

  const exportToPDF = async () => {
    try {
      if (data.length === 0) {
        alert('No data to export');
        return;
      }
      const jsPDF = (await import('jspdf')).default;
      await import('jspdf-autotable' as any);
      const doc = new jsPDF();
      
      // PDF Header
      doc.setFontSize(16);
      doc.text(displayTitle, 20, 20);
      doc.setFontSize(12);
      doc.text(`Export Date: ${new Date().toLocaleDateString()}`, 20, 30);
      
      let yPosition = 50;
      
      data.forEach((record, index) => {
        // Check if we need a new page
        if (yPosition > 250) {
          doc.addPage();
          yPosition = 20;
        }
        
        // Lead header
        doc.setFontSize(14);
        doc.text(`Lead ${index + 1}`, 20, yPosition);
        yPosition += 10;
        
        // Lead details
        doc.setFontSize(10);
        Object.entries(record).forEach(([key, value]) => {
          if (value && key !== 'id') {
            const displayKey = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            const displayValue = String(value).substring(0, 100); // Truncate long values
            doc.text(`${displayKey}: ${displayValue}`, 20, yPosition);
            yPosition += 5;
          }
        });
        
        yPosition += 10; // Space between leads
      });
      
      doc.save(`${displayTitle.replace(/\s+/g, '_')}_${new Date().toISOString().split('T')[0]}.pdf`);
      setIsOpen(false);
    } catch (error) {
      console.error('PDF Export Error:', error);
      alert('Failed to export PDF file');
      setIsOpen(false);
    }
  };

  const convertToCSV = (data: any[]) => {
    if (data.length === 0) return '';
    
    const headers = Object.keys(data[0]);
    const csvRows = [];
    
    // Add headers
    csvRows.push(headers.join(','));
    
    // Add data rows
    data.forEach(row => {
      const values = headers.map(header => {
        const value = row[header];
        // Escape quotes and wrap in quotes if contains comma
        const stringValue = String(value || '');
        return stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\n') 
          ? `"${stringValue.replace(/"/g, '""')}"` 
          : stringValue;
      });
      csvRows.push(values.join(','));
    });
    
    return csvRows.join('\n');
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="bg-blue-800 hover:bg-blue-900 active:bg-blue-950 text-white font-semibold py-2 px-4 rounded-lg shadow-lg hover:shadow-xl active:shadow-md transform hover:scale-105 active:scale-95 transition-all duration-200 flex items-center gap-2"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a4 4 0 01-4-4V5a4 4 0 014-4h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a4 4 0 01-4 4z" />
        </svg>
        Export
        <svg className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      
      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-48 bg-white rounded-lg shadow-xl border border-gray-200 z-50">
          <div className="py-2">
            <button
              onClick={exportToCSV}
              className="w-full text-left px-4 py-2 text-gray-700 hover:bg-gray-100 active:bg-gray-200 transform active:scale-95 transition-all duration-150 flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Export as CSV
            </button>
            <button
              onClick={exportToExcel}
              className="w-full text-left px-4 py-2 text-gray-700 hover:bg-gray-100 active:bg-gray-200 transform active:scale-95 transition-all duration-150 flex items-center gap-2"
            >
              <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Export as Excel
            </button>
            <button
              onClick={exportToPDF}
              className="w-full text-left px-4 py-2 text-gray-700 hover:bg-gray-100 active:bg-gray-200 transform active:scale-95 transition-all duration-150 flex items-center gap-2"
            >
              <svg className="w-4 h-4 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707L14.586 4.586A1 1 0 0014 4.293V2a1 1 0 00-1-1H7a2 2 0 00-2 2v16a2 2 0 002 2z" />
              </svg>
              Export as PDF (One-pager per lead)
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

interface ProgressBarProps {
  jobStatus: string;
  pulling: boolean;
}

const ProgressBar: React.FC<ProgressBarProps> = ({ jobStatus, pulling }) => {
  const [progress, setProgress] = React.useState(0);
  const [startTime, setStartTime] = React.useState<number | null>(null);
  
  React.useEffect(() => {
    if (pulling && jobStatus === 'IN_PROGRESS') {
      // Set start time when pulling begins
      if (!startTime) {
        setStartTime(Date.now());
      }
      
      const interval = setInterval(() => {
        const now = Date.now();
        const elapsed = now - (startTime || now);
        const threeMinutes = 3 * 60 * 1000; // 3 minutes in milliseconds
        
        // Calculate progress as percentage of 3 minutes, max 98%
        const calculatedProgress = Math.min(98, (elapsed / threeMinutes) * 100);
        setProgress(calculatedProgress);
      }, 100); // Update every 100ms for smooth animation
      
      return () => clearInterval(interval);
    } else if (!pulling) {
      // Reset when not pulling
      setProgress(0);
      setStartTime(null);
    }
  }, [pulling, jobStatus, startTime]);
  
  React.useEffect(() => {
    if (jobStatus === 'COMPLETED') {
      setProgress(100);
    }
  }, [jobStatus]);
  
  return (
    <div style={{ width: '100%', maxWidth: 400, margin: '0 auto 16px auto' }}>
      <div style={{ height: 12, background: '#e5e7eb', borderRadius: 6, overflow: 'hidden', marginBottom: 8 }}>
        <div style={{ width: `${progress}%`, height: '100%', background: '#1e40af', transition: 'width 0.1s ease-out' }} />
      </div>
      <div style={{ textAlign: 'center', color: '#1e40af', fontWeight: 600, fontSize: 14 }}>{Math.round(progress)}%</div>
    </div>
  );
};

export default function Dashboard() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [selectedCounty, setSelectedCounty] = useState<string | null>(null);
  const onboardingCounties = ["Harris (Recommended)", "Dallas", "Tarrant", "Bexar", "Travis"];
  // ALL HOOKS MUST BE CALLED BEFORE ANY CONDITIONAL RETURNS
  const [rows, setRows] = useState<(LisPendensRecord | MdCaseSearchRecord | HillsboroughNhRecord | BrevardFlRecord | FultonGaRecord | CobbGaRecord)[]>([]);
  const [paginationModel, setPaginationModel] = useState({ page: 0, pageSize: 10 });
  const [userType, setUserType] = useState<string>('LPH');
  const [county, setCounty] = useState('Harris');
  const counties = ['Harris', 'Fort Bend', 'Montgomery'];
  const [pulling, setPulling] = useState(false);
  const [pullResult, setPullResult] = useState<null | 'success' | 'error'>(null);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string>('');
  const [dateFilter, setDateFilter] = useState<number>(7); // Default to 7 days
  // State for focused cell display
  const [focusedCellContent, setFocusedCellContent] = useState<string>('');
  const [focusedCellField, setFocusedCellField] = useState<string>('');
  const [onboardingStep, setOnboardingStep] = useState(1);
  const [selectedDocTypes, setSelectedDocTypes] = useState<string[]>([]);
  const docTypes = [
    "Tax Delinquency"
  ];
  
  // Summary modal state
  const [summaryModalOpen, setSummaryModalOpen] = useState(false);
  const [selectedSummary, setSelectedSummary] = useState<{
    caseNumber: string;
    summary: string;
  } | null>(null);



  // Handle summary modal
  const handleSummaryClick = (data: { caseNumber: string; summary: string }) => {
    setSelectedSummary(data);
    setSummaryModalOpen(true);
  };

  const handleCloseSummaryModal = () => {
    setSummaryModalOpen(false);
    setSelectedSummary(null);
  };

  // Summary Button Component
  const SummaryButton = ({ row }: { row: any }) => {
    const summary = row.ai_summary || row.summary || '';
    const caseNumber = row.case_number || '';
    
    if (!summary || !summary.trim()) {
      return (
        <span className="text-gray-400 text-sm">No summary</span>
      );
    }
    
    return (
      <button
        onClick={() => handleSummaryClick({ caseNumber, summary })}
        className="bg-blue-500 hover:bg-blue-600 text-white text-sm px-3 py-1 rounded font-medium transition-colors"
        title="View AI Summary"
      >
        Summary
      </button>
    );
  };





  // Column definitions (moved inside component to access SummaryButton)
  const lphColumns: GridColDef[] = [
    { field: 'case_number', headerName: 'Case Number', minWidth: 110, maxWidth: 130, flex: 0.7 },
    { field: 'property_address', headerName: 'Property Address', minWidth: 250, flex: 2, renderCell: (params) => <PropertyAddressCell value={params.value} row={params.row} /> },
    { field: 'ai_summary', headerName: 'Summary', minWidth: 90, maxWidth: 110, flex: 0.6, renderCell: (params) => <SummaryButton row={params.row} /> },
    { field: 'county', headerName: 'County', minWidth: 70, maxWidth: 90, flex: 0.5 },
    { field: 'created_at', headerName: 'Created At', minWidth: 120, maxWidth: 160, flex: 1, renderCell: (params) => <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block', width: '100%' }}>{params.value}</span> },
    { field: 'is_new', headerName: 'Is New', minWidth: 60, maxWidth: 70, flex: 0.4, type: 'boolean' },
    { field: 'doc_type', headerName: 'Doc Type', minWidth: 60, maxWidth: 80, flex: 0.5 },
  ];

  // Columns for Maryland Case Search users
  const mdCaseSearchColumns: GridColDef[] = [
    { field: 'case_number', headerName: 'Case Number', minWidth: 110, maxWidth: 130, flex: 0.7 },
    { field: 'file_date', headerName: 'File Date', minWidth: 90, maxWidth: 110, flex: 0.7 },
    { field: 'party_name', headerName: 'Party Name', minWidth: 150, maxWidth: 200, flex: 1 },
    { field: 'case_type', headerName: 'Case Type', minWidth: 100, maxWidth: 120, flex: 0.8 },
    { field: 'county', headerName: 'County', minWidth: 70, maxWidth: 90, flex: 0.5 },
    { field: 'property_address', headerName: 'Property Address', minWidth: 150, flex: 1.2, renderCell: (params) => <PropertyAddressCell value={params.value} row={params.row} /> },
    { field: 'defendant_info', headerName: 'Parties', minWidth: 150, maxWidth: 200, flex: 1, renderCell: (params) => <PropertyAddressCell value={params.value} row={params.row} /> },
    { field: 'created_at', headerName: 'Created At', minWidth: 120, maxWidth: 160, flex: 1, renderCell: (params) => <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block', width: '100%' }}>{params.value}</span> },
    { field: 'is_new', headerName: 'Is New', minWidth: 60, maxWidth: 70, flex: 0.4, type: 'boolean' },
  ];

  // ALL useEffect hooks must be called before conditional returns
  const fetchData = async () => {
    try {
      // Only Harris County is supported now
      const endpoint = '/api/harris-county';
      
      console.log('🔍 Fetching data from endpoint:', endpoint);
      console.log('👤 Current user ID:', (session?.user as any)?.id);
      console.log('🏷️ User type:', userType);
      
      const res = await fetch(endpoint);
      const data = await res.json();
      
      console.log('📊 Fetched data response:', data);
      console.log('📈 Number of records returned:', Array.isArray(data) ? data.length : 'Not an array');
      
      if (Array.isArray(data)) {
        console.log('✅ Setting rows with', data.length, 'records');
        setRows(data);
      } else {
        console.error('❌ Response is not an array:', data);
        if (data.error) {
          console.error('🚨 API Error:', data.error);
        }
        setRows([]);
      }
    } catch (error) {
      console.error('💥 Error fetching data:', error);
      setRows([]);
    }
  };

  // Fetch user type from session
  const fetchUserType = async () => {
    if (session?.user) {
      try {
        // Default to LPH (Harris County) as it's the only supported type now
        const res = await fetch('/api/auth/user-type');
        if (res.ok) {
          const data = await res.json();
          setUserType(data.userType || 'LPH');
        }
      } catch (error) {
        console.error('Error fetching user type:', error);
        setUserType('LPH'); // Default to LPH (Harris County only)
      }
    }
  };

  useEffect(() => {
    if (session) {
      fetchUserType();
    }
  }, [session]);

  useEffect(() => {
    if (userType && session) {
      console.log('🔄 useEffect triggered - fetching data for userType:', userType);
      fetchData();
    }
  }, [userType, session]);

  // Redirect if not authenticated
  useEffect(() => {
    console.log('Dashboard useEffect - status:', status, 'session:', session);
    if (status === "loading") return; // Still loading
    if (!session) {
      console.log('No session found, redirecting to login');
      router.push("/login");
      return;
    }
    console.log('Session found, staying on dashboard');
  }, [session, status, router]);

  // Check onboarding status from database
  useEffect(() => {
    const checkOnboardingStatus = async () => {
      if (session?.user?.id) {
        try {
          const response = await fetch('/api/auth/onboarding');
          if (response.ok) {
            const data = await response.json();
            if (!data.hasCompletedOnboarding) {
              setShowOnboarding(true);
            }
          }
        } catch (error) {
          console.error('Error checking onboarding status:', error);
          // Fallback to sessionStorage for error cases
          if (typeof window !== 'undefined') {
            const onboarded = sessionStorage.getItem('onboarded');
            if (!onboarded) {
              setShowOnboarding(true);
            }
          }
        }
      }
    };

    checkOnboardingStatus();
  }, [session]);

  const handleCountySelect = (county: string) => {
    setSelectedCounty(county);
    setOnboardingStep(2);
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('selectedCounty', county);
    }
    setCounty(county);
  };

  const handleDocTypeToggle = (docType: string) => {
    setSelectedDocTypes((prev) =>
      prev.includes(docType)
        ? prev.filter((d) => d !== docType)
        : [...prev, docType]
    );
  };

  const handleOnboardingFinish = async () => {
    try {
      // Mark onboarding as completed in database
      const response = await fetch('/api/auth/onboarding', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          county: selectedCounty,
          docTypes: selectedDocTypes
        })
      });

      if (response.ok) {
        setShowOnboarding(false);
        // Keep sessionStorage as backup/cache
        if (typeof window !== 'undefined') {
          sessionStorage.setItem('onboarded', '1');
          sessionStorage.setItem('selectedDocTypes', JSON.stringify(selectedDocTypes));
        }
      } else {
        console.error('Failed to save onboarding completion');
        // Still hide onboarding on frontend error
        setShowOnboarding(false);
      }
    } catch (error) {
      console.error('Error completing onboarding:', error);
      // Still hide onboarding on error
      setShowOnboarding(false);
    }
  };

  // Automatically clear success/error toast after 5 seconds
  useEffect(() => {
    if (pullResult) {
      const timer = setTimeout(() => setPullResult(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [pullResult]);

  // NOW we can do conditional rendering AFTER all hooks are called
  if (status === "loading") {
    console.log('Status is loading...');
    return <div>Loading...</div>;
  }

  if (!session) {
    console.log('No session, returning null');
    return null;
  }

  const pollJobStatus = async (jobId: string) => {
    try {
      // Only Harris County agent scraper is supported now
      const endpoint = `/api/scrape?job_id=${jobId}`;
      
      const res = await fetch(endpoint);
      const data = await res.json();
      
      if (data.success) {
        setJobStatus(data.status);
        
        if (data.status === 'COMPLETED') {
          console.log('🎉 Job completed successfully! Refreshing data...');
          setPullResult('success');
          setPulling(false);
          setCurrentJobId(null);
          
          // Multiple refresh attempts to ensure data appears
          const refreshData = async (attempt = 1) => {
            console.log(`🔄 Attempt ${attempt}: Fetching fresh data after job completion...`);
            await fetchData();
            
            // If this is the first attempt, try again after a longer delay
            if (attempt === 1) {
              setTimeout(() => refreshData(2), 2000);
            }
            // Third attempt after even longer delay for edge cases
            if (attempt === 2) {
              setTimeout(() => refreshData(3), 5000);
            }
          };
          
          // First immediate refresh
          setTimeout(() => refreshData(1), 500);
          return;
        } else if (data.status === 'FAILED') {
          setPullResult('error');
          setPulling(false);
          setCurrentJobId(null);
        }
        
        // Continue polling if job is still pending or in progress
        if (data.status === 'PENDING' || data.status === 'IN_PROGRESS') {
          setTimeout(() => pollJobStatus(jobId), 2000); // Poll every 2 seconds
        }
      } else {
        setPullResult('error');
        setPulling(false);
        setCurrentJobId(null);
      }
    } catch (error) {
      console.error('Error polling job status:', error);
      setPullResult('error');
      setPulling(false);
      setCurrentJobId(null);
    }
  };

  const handlePullRecord = async () => {
    setPullResult(null);
    setJobStatus('');
    try {
      // Only Harris County agent scraper is supported now
      const endpoint = '/api/scrape';
      
      // Agent scraper expects county and filters
      const fromDate = new Date();
      fromDate.setDate(fromDate.getDate() - dateFilter);
      const toDate = new Date();
      
      const requestBody = {
        county: county.toLowerCase(), // 'harris', 'dallas', etc.
        filters: {
          documentType: 'LisPendens',
          dateFrom: fromDate.toISOString().split('T')[0], // YYYY-MM-DD format
          dateTo: toDate.toISOString().split('T')[0], // YYYY-MM-DD format
          pageSize: 50
        }
      };
      
      const res = await fetch(endpoint, { 
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody)
      });
      const data = await res.json();
      
      // Handle agent scraper job polling
      if (data.success && data.job_id) {
        setPulling(true);
        setCurrentJobId(data.job_id);
        setJobStatus(data.status);
        // Start polling for job status
        pollJobStatus(data.job_id);
      } else {
        setPullResult('error');
        setPulling(false);
      }
    } catch (e) {
      setPullResult('error');
      setPulling(false);
    }
  };

  // Add this handler to mark is_new as false and persist
  const handleRowClick = async (params: any) => {
    // Only Harris County records now
    const recordId = params.row.case_number;
    
    // Only update if is_new is true and we have a valid recordId
    if (!params.row.is_new || !recordId) return;
    
    // Optimistically update UI
    setRows(prev =>
      prev.map(r => {
        const currentId = (r as LisPendensRecord).case_number;
        return currentId === recordId ? { ...r, is_new: false } : r;
      })
    );
    
    // Persist to backend - Harris County uses the /api/harris-county endpoint
    try {
      const endpoint = `/api/harris-county`;
      const body = JSON.stringify({ case_number: recordId, is_new: false });
      
      await fetch(endpoint, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body,
      });
    } catch (e) {
      // Optionally: revert UI or show error
      console.error('Failed to update is_new:', e);
    }
  };

  // Get the appropriate columns and display info - only Harris County supported now
  const columns = lphColumns as GridColDef[];
  const displayTitle = `${county} County Records`;
  const loadingMessage = `Scraping Records from ${county} County Est. wait time 2-3 mins`;

  // Handle cell focus to show content in the wide box
  const handleCellFocus = (params: any) => {
    const cellValue = params.value || '';
    const fieldName = params.field || '';
    
    // Only show the box if there's meaningful content
    if (cellValue && cellValue.toString().trim().length > 0) {
      setFocusedCellContent(cellValue.toString());
      setFocusedCellField(fieldName);
    }
  };

  // Handle cell blur to hide the wide box
  const handleCellBlur = () => {
    setFocusedCellContent('');
    setFocusedCellField('');
  };

  return (
    <>
      {/* Onboarding Flex Panel */}
      {showOnboarding && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100vw',
          height: '100vh',
          zIndex: 1000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'rgba(20, 20, 40, 0.85)',
        }}>
          <div style={{
            background: 'linear-gradient(135deg, #1e2a78 0%, #3a3d9f 100%)',
            borderRadius: 24,
            boxShadow: '0 8px 48px 0 rgba(30,42,120,0.25)',
            padding: '2.5rem 2rem',
            minWidth: 340,
            maxWidth: '90vw',
            color: '#fff',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '2rem',
          }}>
            {onboardingStep === 1 && (
              <>
                <h2 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: 8, textAlign: 'center', letterSpacing: 1 }}>Welcome!<br/>Choose Your County</h2>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem', width: '100%' }}>
                  {onboardingCounties.map((county) => (
                    <button
                      key={county}
                      onClick={() => handleCountySelect(county)}
                      style={{
                        background: '#fff',
                        color: '#1e2a78',
                        fontWeight: 700,
                        fontSize: '1.2rem',
                        borderRadius: 12,
                        padding: '1rem 0',
                        border: 'none',
                        cursor: 'pointer',
                        boxShadow: '0 2px 12px 0 rgba(30,42,120,0.10)',
                        transition: 'background 0.2s, color 0.2s',
                      }}
                      onMouseEnter={e => {
                        e.currentTarget.style.background = '#3a3d9f';
                        e.currentTarget.style.color = '#fff';
                      }}
                      onMouseLeave={e => {
                        e.currentTarget.style.background = '#fff';
                        e.currentTarget.style.color = '#1e2a78';
                      }}
                    >
                      {county}
                    </button>
                  ))}
                </div>
              </>
            )}
            {onboardingStep === 2 && (
              <>
                <h2 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: 8, textAlign: 'center', letterSpacing: 1 }}>Select Document Types</h2>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem', width: '100%' }}>
                  {docTypes.map((docType) => (
                    <label key={docType} style={{
                      display: 'flex',
                      alignItems: 'center',
                      background: selectedDocTypes.includes(docType) ? '#3a3d9f' : '#fff',
                      color: selectedDocTypes.includes(docType) ? '#fff' : '#1e2a78',
                      fontWeight: 600,
                      fontSize: '1.1rem',
                      borderRadius: 10,
                      padding: '0.8rem 1rem',
                      cursor: 'pointer',
                      boxShadow: '0 1px 6px 0 rgba(30,42,120,0.08)',
                      transition: 'background 0.2s, color 0.2s',
                    }}>
                      <input
                        type="checkbox"
                        checked={selectedDocTypes.includes(docType)}
                        onChange={() => handleDocTypeToggle(docType)}
                        style={{ marginRight: 12, accentColor: '#3a3d9f', width: 18, height: 18 }}
                      />
                      {docType}
                    </label>
                  ))}
                </div>
                <button
                  onClick={handleOnboardingFinish}
                  disabled={selectedDocTypes.length === 0}
                  style={{
                    marginTop: 24,
                    background: selectedDocTypes.length === 0 ? '#aaa' : '#fff',
                    color: selectedDocTypes.length === 0 ? '#fff' : '#1e2a78',
                    fontWeight: 700,
                    fontSize: '1.2rem',
                    borderRadius: 12,
                    padding: '1rem 0',
                    border: 'none',
                    cursor: selectedDocTypes.length === 0 ? 'not-allowed' : 'pointer',
                    boxShadow: '0 2px 12px 0 rgba(30,42,120,0.10)',
                    transition: 'background 0.2s, color 0.2s',
                    width: '100%'
                  }}
                >
                  Continue
                </button>
              </>
            )}
          </div>
        </div>
      )}
      {/* Dashboard content, visually dimmed/blurred if onboarding is open */}
      <div style={showOnboarding ? { filter: 'blur(2px)', pointerEvents: 'none', userSelect: 'none', opacity: 0.5 } : {}}>
        <SidebarProvider>
          <style dangerouslySetInnerHTML={{ __html: sliderStyles }} />
          <AppSidebar />
          <SidebarInset>
            <header className="flex h-16 shrink-0 items-center border-b px-6">
              {/* Left section with navigation */}
              <div className="flex items-center gap-3 flex-shrink-0">
                <SidebarTrigger />
                <Separator orientation="vertical" className="h-4" />
                <Breadcrumb>
                  <BreadcrumbList>
                    <BreadcrumbItem className="hidden md:block">
                      <BreadcrumbLink href="#">
                        Clerk Crawler
                      </BreadcrumbLink>
                    </BreadcrumbItem>
                    <BreadcrumbSeparator className="hidden md:block" />
                    <BreadcrumbItem>
                      <BreadcrumbPage>Dashboard</BreadcrumbPage>
                    </BreadcrumbItem>
                  </BreadcrumbList>
                </Breadcrumb>
              </div>

              {/* Center spacer */}
              <div className="flex-1"></div>

              {/* Right section with controls - evenly spaced */}
              <div className="flex items-center gap-6 flex-shrink-0">
                <button
                  className="bg-blue-500 text-white p-2 rounded-lg shadow-lg hover:bg-blue-600 transition-all duration-200 cursor-pointer"
                  onClick={() => router.push('/live-support')}
                  title="Get Live Support"
                >
                  <MessageSquare className="w-5 h-5" />
                </button>
                
                <button
                  className="bg-gray-500 text-white font-bold py-2 px-4 rounded-lg shadow-lg hover:bg-gray-600 transition-all duration-200 cursor-pointer"
                  onClick={() => signOut({ callbackUrl: '/' })}
                >
                  Sign Out
                </button>
                
                {/* Date Filter Slider */}
                <div className="flex items-center gap-3 bg-blue-600 text-white px-4 py-2 rounded-lg shadow-lg">
                  <span className="text-sm font-medium whitespace-nowrap">Pull from last:</span>
                  <input
                    type="range"
                    min="1"
                    max="90"
                    value={dateFilter}
                    onChange={(e) => setDateFilter(Number(e.target.value))}
                    className="w-24 h-2 bg-blue-400 rounded-lg appearance-none cursor-pointer slider"
                    style={{
                      background: `linear-gradient(to right, #93c5fd 0%, #93c5fd ${((dateFilter - 1) / 89) * 100}%, #1e40af ${((dateFilter - 1) / 89) * 100}%, #1e40af 100%)`
                    }}
                  />
                  <input
                    type="number"
                    min="1"
                    max="90"
                    value={dateFilter}
                    onChange={(e) => {
                      const value = Math.min(90, Math.max(1, Number(e.target.value) || 1));
                      setDateFilter(value);
                    }}
                    className="w-12 h-8 text-center text-blue-900 bg-white rounded border-0 focus:ring-2 focus:ring-blue-300"
                    style={{ fontSize: '20px' }}
                  />
                  <span className="text-sm font-medium whitespace-nowrap">
                    day{dateFilter !== 1 ? 's' : ''}
                  </span>
                </div>
                
                <button
                  className="bg-blue-600 text-white font-bold py-2 px-6 rounded-lg shadow-lg animate-pulse-grow hover:bg-blue-700 transition-all duration-200 cursor-pointer"
                  style={{ fontSize: '1.1rem' }}
                  onClick={handlePullRecord}
                  disabled={pulling}
                >
                  Pull Records
                </button>
                
                <ThemeToggle inHeader={true} />
              </div>
            </header>
            
            {/* Trial Banner */}
            <div className="px-6 pt-4">
              <TrialBanner />
            </div>
            
            <div className="flex flex-1 flex-col gap-4 p-4">
              <div className="min-h-[100vh] flex-1 rounded-xl bg-white md:min-h-min flex justify-center items-start">
                <div style={{ width: '100%', maxWidth: 1200, margin: '40px auto 0 auto', background: 'white', borderRadius: 8, padding: 16, boxShadow: '0 2px 16px rgba(0,0,0,0.07)', position: 'relative' }}>
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-4">
                      {/* Remove the dropdown, only show the county name */}
                      <span style={{ color: 'black', fontWeight: 600, fontSize: 24, padding: 10, marginLeft: 30 }}>
                        {displayTitle}
                      </span>
                      {/* Record count display */}
                      <span style={{ 
                        color: '#059669', 
                        fontWeight: 600, 
                        fontSize: 20, 
                        marginLeft: 16,
                        backgroundColor: '#ecfdf5',
                        padding: '4px 12px',
                        borderRadius: '8px',
                        border: '1px solid #10b981'
                      }}>
                        {rows.length} records
                      </span>
                    </div>
                    
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => {
                          console.log('🔄 Manual refresh triggered by user');
                          fetchData();
                        }}
                        className="bg-green-600 hover:bg-green-700 active:bg-green-800 text-white font-semibold py-2 px-4 rounded-lg shadow-lg hover:shadow-xl active:shadow-md transform hover:scale-105 active:scale-95 transition-all duration-200 flex items-center gap-2"
                        title="Refresh data manually"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        Refresh
                      </button>
                      
                      <Hot20Button 
                        data={rows} 
                        userType={userType} 
                      />
                      <ExportButton 
                        data={rows} 
                        userType={userType} 
                        displayTitle={displayTitle}
                      />
                    </div>
                  </div>
                  <div style={{ position: 'relative', color: 'black' }}>
                    <DataGrid
                      rows={rows}
                      columns={columns as any}
                      getRowId={(row) => {
                        let id;
                        if (userType === 'HILLSBOROUGH_NH') {
                          id = (row as HillsboroughNhRecord).document_number;
                        } else if (userType === 'BREVARD_FL') {
                          id = (row as BrevardFlRecord).case_number;
                        } else if (userType === 'FULTON_GA') {
                          id = (row as FultonGaRecord).case_number;
                        } else if (userType === 'COBB_GA') {
                          id = (row as CobbGaRecord).case_number;
                        } else {
                          id = (row as LisPendensRecord | MdCaseSearchRecord).case_number;
                        }
                        
                        // Ensure we always return a valid string ID
                        if (!id || typeof id !== 'string' || id.trim() === '') {
                          // Fallback: create a unique ID using other available fields
                          const fallbackId = `${row.county || 'unknown'}-${row.created_at || Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
                          console.warn('Row missing valid ID, using fallback:', fallbackId, 'Row:', row);
                          return fallbackId;
                        }
                        
                        return id;
                      }}
                      paginationModel={paginationModel}
                      onPaginationModelChange={setPaginationModel}
                      pageSizeOptions={[10, 25, 50]}
                      checkboxSelection
                      disableRowSelectionOnClick
                      onRowClick={handleRowClick}
                      onCellClick={handleCellFocus}
                      sx={{ 
                        color: 'black', 
                        background: 'white', 
                        '& .MuiDataGrid-cell': { 
                          color: 'black',
                          cursor: 'pointer'
                        }, 
                        '& .MuiDataGrid-columnHeaders': { color: 'black' } 
                      }}
                    />
                  </div>
                  
                  {/* Wide Text Display Box for Focused Cell */}
                  {focusedCellContent && (
                    <div className="mt-4 p-4 bg-gray-50 border border-gray-200 rounded-lg shadow-sm">
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="text-sm font-semibold text-gray-700 capitalize">
                          {focusedCellField.replace(/_/g, ' ')} Content:
                        </h3>
                        <button 
                          onClick={handleCellBlur}
                          className="text-gray-400 hover:text-gray-600 text-xl leading-none"
                          title="Close"
                        >
                          ×
                        </button>
                      </div>
                      <div className="bg-white p-3 rounded border border-gray-100 max-h-40 overflow-y-auto">
                        <p className="text-gray-800 whitespace-pre-wrap text-sm leading-relaxed">
                          {focusedCellContent}
                        </p>
                      </div>
                    </div>
                  )}
                  
                  {/* Loader inside content box */}
                  {pulling && jobStatus === 'IN_PROGRESS' && (
                    <div className="absolute inset-0 z-20 flex items-center justify-center bg-white bg-opacity-80 rounded-lg">
                      <div className="flex flex-col items-center justify-center p-8 w-full">
                        {/* Progress Bar */}
                        <ProgressBar jobStatus={jobStatus} pulling={pulling} />
                        <div className="flex space-x-2 mt-2">
                          <span className="dot-bounce bg-blue-600"></span>
                          <span className="dot-bounce bg-blue-600" style={{ animationDelay: '0.2s' }}></span>
                          <span className="dot-bounce bg-blue-600" style={{ animationDelay: '0.4s' }}></span>
                        </div>
                        <div className="mt-4 text-blue-700 font-semibold">
                          {jobStatus === 'IN_PROGRESS' && loadingMessage}
                        </div>
                        {currentJobId && (
                          <div className="mt-2 text-gray-600 text-sm">
                            Job ID: {currentJobId}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                  {/* Show only a simple message when job is queued */}
                  {pulling && jobStatus === 'PENDING' && (
                    <div className="absolute inset-0 z-20 flex items-center justify-center bg-white bg-opacity-80 rounded-lg">
                      <div className="flex flex-col items-center justify-center p-8 w-full">
                        <div className="flex space-x-2 mt-2">
                          <span className="dot-bounce bg-blue-600"></span>
                          <span className="dot-bounce bg-blue-600" style={{ animationDelay: '0.2s' }}></span>
                          <span className="dot-bounce bg-blue-600" style={{ animationDelay: '0.4s' }}></span>
                        </div>
                        <div className="mt-4 text-blue-700 font-semibold">
                          Job queued, waiting to start...
                        </div>
                        {currentJobId && (
                          <div className="mt-2 text-gray-600 text-sm">
                            Job ID: {currentJobId}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
            {/* Toast for result */}
            {pullResult === 'success' && (
              <div className="fixed bottom-6 left-6 bg-green-600 text-white px-6 py-3 rounded-lg shadow-lg z-50 flex items-center gap-2">
                <span className="text-lg">✅</span>
                <div>
                  <div className="font-semibold">Fresh records pulled successfully!</div>
                  <div className="text-sm opacity-90">
                    Data refreshed at {new Date().toLocaleTimeString()} • Duplicates automatically skipped
                  </div>
                </div>
              </div>
            )}
            {pullResult === 'error' && (
              <div className="fixed bottom-6 left-6 bg-red-600 text-white px-6 py-3 rounded-lg shadow-lg z-50 flex items-center gap-2">
                <span className="text-lg">❌</span>
                <span className="font-semibold">Error pulling records. Please try again.</span>
              </div>
            )}
          </SidebarInset>
          

        </SidebarProvider>
        
        {/* Summary Modal */}
        <Dialog 
          open={summaryModalOpen} 
          onClose={handleCloseSummaryModal}
          maxWidth="md"
          fullWidth
        >
          <DialogTitle>
            AI Summary - Case {selectedSummary?.caseNumber}
          </DialogTitle>
          <DialogContent>
            <div style={{ marginTop: '16px' }}>
              <Typography variant="body1" style={{ lineHeight: 1.6 }}>
                {selectedSummary?.summary}
              </Typography>
            </div>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleCloseSummaryModal} color="primary">
              Close
            </Button>
          </DialogActions>
        </Dialog>
      </div>
    </>
  )
}
