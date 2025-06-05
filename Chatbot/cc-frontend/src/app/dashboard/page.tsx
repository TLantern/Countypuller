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

// Custom CSS for the slider
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
`;

const PropertyAddressCell = ({ value }: { value: string }) => {
  const [open, setOpen] = React.useState(false);
  return (
    <>
      <div
        style={{
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          maxWidth: 200,
          cursor: 'pointer',
          borderBottom: '1px dashed #888',
        }}
        title="Click to view full address"
        onClick={() => setOpen(true)}
      >
        {value}
      </div>
      <Dialog open={open} onClose={() => setOpen(false)}>
        <DialogTitle>Full Address</DialogTitle>
        <DialogContent>
          <div style={{ maxWidth: 400, wordBreak: 'break-word' }}>{value}</div>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

// Columns for Lis Pendens (LPH) users
const lphColumns: GridColDef[] = [
  { field: 'case_number', headerName: 'Case Number', minWidth: 110, maxWidth: 130, flex: 0.7 },
  { field: 'case_url', headerName: 'Case URL', minWidth: 70, maxWidth: 90, flex: 0.5, renderCell: (params) => <a href={params.value} target="_blank" rel="noopener noreferrer" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block', width: '100%' }}>Link</a> },
  { field: 'file_date', headerName: 'File Date', minWidth: 90, maxWidth: 110, flex: 0.7 },
  { field: 'property_address', headerName: 'Property Address', minWidth: 120, maxWidth: 180, flex: 1, renderCell: (params) => <PropertyAddressCell value={params.value} /> },
  { field: 'filing_no', headerName: 'Filing No', minWidth: 60, maxWidth: 80, flex: 0.5 },
  { field: 'volume_no', headerName: 'Volume No', minWidth: 60, maxWidth: 80, flex: 0.5 },
  { field: 'page_no', headerName: 'Page No', minWidth: 60, maxWidth: 80, flex: 0.5 },
  { field: 'county', headerName: 'County', minWidth: 70, maxWidth: 90, flex: 0.5 },
  { field: 'created_at', headerName: 'Created At', minWidth: 120, maxWidth: 160, flex: 1, renderCell: (params) => <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block', width: '100%' }}>{params.value}</span> },
  { field: 'is_new', headerName: 'Is New', minWidth: 60, maxWidth: 70, flex: 0.4, type: 'boolean' },
  { field: 'doc_type', headerName: 'Doc Type', minWidth: 60, maxWidth: 80, flex: 0.5 },
];

// Columns for Maryland Case Search users
const mdCaseSearchColumns: GridColDef[] = [
  { field: 'case_number', headerName: 'Case Number', minWidth: 110, maxWidth: 130, flex: 0.7 },
  { field: 'case_url', headerName: 'Case URL', minWidth: 70, maxWidth: 90, flex: 0.5, renderCell: (params) => <a href={params.value} target="_blank" rel="noopener noreferrer" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block', width: '100%' }}>Link</a> },
  { field: 'file_date', headerName: 'File Date', minWidth: 90, maxWidth: 110, flex: 0.7 },
  { field: 'party_name', headerName: 'Party Name', minWidth: 150, maxWidth: 200, flex: 1 },
  { field: 'case_type', headerName: 'Case Type', minWidth: 100, maxWidth: 120, flex: 0.8 },
  { field: 'county', headerName: 'County', minWidth: 70, maxWidth: 90, flex: 0.5 },
  { field: 'property_address', headerName: 'Property Address', minWidth: 120, maxWidth: 180, flex: 1, renderCell: (params) => <PropertyAddressCell value={params.value} /> },
  { field: 'defendant_info', headerName: 'Parties', minWidth: 150, maxWidth: 200, flex: 1, renderCell: (params) => <PropertyAddressCell value={params.value} /> },
  { field: 'created_at', headerName: 'Created At', minWidth: 120, maxWidth: 160, flex: 1, renderCell: (params) => <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block', width: '100%' }}>{params.value}</span> },
  { field: 'is_new', headerName: 'Is New', minWidth: 60, maxWidth: 70, flex: 0.4, type: 'boolean' },
];

// Columns for Hillsborough NH users
const hillsboroughNhColumns: GridColDef[] = [
  { field: 'document_number', headerName: 'Document #', minWidth: 110, maxWidth: 130, flex: 0.7 },
  { field: 'document_url', headerName: 'Doc URL', minWidth: 70, maxWidth: 90, flex: 0.5, renderCell: (params) => params.value ? <a href={params.value} target="_blank" rel="noopener noreferrer" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block', width: '100%' }}>Link</a> : '' },
  { field: 'recorded_date', headerName: 'Recorded Date', minWidth: 110, maxWidth: 130, flex: 0.7 },
  { field: 'instrument_type', headerName: 'Type', minWidth: 80, maxWidth: 100, flex: 0.6 },
  { field: 'grantor', headerName: 'Grantor', minWidth: 120, maxWidth: 160, flex: 1 },
  { field: 'grantee', headerName: 'Grantee', minWidth: 120, maxWidth: 160, flex: 1 },
  { field: 'property_address', headerName: 'Property Address', minWidth: 150, maxWidth: 200, flex: 1.2, renderCell: (params) => <PropertyAddressCell value={params.value} /> },
  { field: 'consideration', headerName: 'Amount', minWidth: 80, maxWidth: 100, flex: 0.6 },
  { field: 'county', headerName: 'County', minWidth: 100, maxWidth: 120, flex: 0.7 },
  { field: 'created_at', headerName: 'Created At', minWidth: 120, maxWidth: 160, flex: 1, renderCell: (params) => <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block', width: '100%' }}>{params.value}</span> },
  { field: 'is_new', headerName: 'Is New', minWidth: 60, maxWidth: 70, flex: 0.4, type: 'boolean' },
];

// Types for different record types
interface LisPendensRecord {
  case_number: string;
  case_url: string;
  file_date: string;
  property_address: string;
  filing_no: string;
  volume_no: string;
  page_no: string;
  county: string;
  created_at: string;
  is_new: boolean;
  doc_type: string;
}

interface MdCaseSearchRecord {
  case_number: string;
  case_url: string;
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

export default function Dashboard() {
  const { data: session, status } = useSession();
  const router = useRouter();
  
  // ALL HOOKS MUST BE CALLED BEFORE ANY CONDITIONAL RETURNS
  const [rows, setRows] = useState<(LisPendensRecord | MdCaseSearchRecord | HillsboroughNhRecord)[]>([]);
  const [paginationModel, setPaginationModel] = useState({ page: 0, pageSize: 10 });
  const [userType, setUserType] = useState<string>('LPH');
  const [county, setCounty] = useState('Harris');
  const counties = ['Harris', 'Fort Bend', 'Montgomery'];
  const [pulling, setPulling] = useState(false);
  const [pullResult, setPullResult] = useState<null | 'success' | 'error'>(null);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string>('');
  const [dateFilter, setDateFilter] = useState<number>(7); // Default to 7 days

  // ALL useEffect hooks must be called before conditional returns
  const fetchData = async () => {
    try {
      const endpoint = userType === 'MD_CASE_SEARCH' ? '/api/md-case-search' : 
                      userType === 'HILLSBOROUGH_NH' ? '/api/hillsborough-nh' : 
                      '/api/lis-pendens';
      const res = await fetch(endpoint);
      const data = await res.json();
      setRows(data);
    } catch (error) {
      console.error('Error fetching data:', error);
    }
  };

  // Fetch user type from session
  const fetchUserType = async () => {
    if (session?.user) {
      try {
        // The user type should be available in the session, but if not, we'll fetch it
        const res = await fetch('/api/auth/user-type');
        if (res.ok) {
          const data = await res.json();
          setUserType(data.userType || 'LPH');
        }
      } catch (error) {
        console.error('Error fetching user type:', error);
        setUserType('LPH'); // Default to LPH
      }
    }
  };

  useEffect(() => {
    if (session) {
      fetchUserType();
    }
  }, [session]);

  useEffect(() => {
    if (userType) {
      fetchData();
    }
  }, [userType]);

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
      const endpoint = userType === 'MD_CASE_SEARCH' 
        ? `/api/pull-md-case-search?job_id=${jobId}`
        : userType === 'HILLSBOROUGH_NH'
        ? `/api/pull-hillsborough-nh?job_id=${jobId}`
        : `/api/pull-lph?job_id=${jobId}`;
      
      const res = await fetch(endpoint);
      const data = await res.json();
      
      if (data.success) {
        setJobStatus(data.status);
        
        if (data.status === 'COMPLETED') {
          setPullResult('success');
          setPulling(false);
          setCurrentJobId(null);
          // Automatically refresh the data after successful completion
          await fetchData();
          return;
        } else if (data.status === 'FAILED') {
          setPullResult('error');
          setPulling(false);
          setCurrentJobId(null);
          return;
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
    setPulling(true);
    setPullResult(null);
    setJobStatus('');
    
    try {
      const endpoint = userType === 'MD_CASE_SEARCH' ? '/api/pull-md-case-search' : 
                      userType === 'HILLSBOROUGH_NH' ? '/api/pull-hillsborough-nh' : 
                      '/api/pull-lph';
      
      // Include the date filter in the request body
      const requestBody = {
        dateFilter: dateFilter // Number of days back to pull records from
      };
      
      const res = await fetch(endpoint, { 
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody)
      });
      const data = await res.json();
      
      if (data.success && data.job_id) {
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
    const recordId = userType === 'HILLSBOROUGH_NH' ? params.row.document_number : params.row.case_number;
    // Only update if is_new is true
    if (!params.row.is_new) return;
    
    // Optimistically update UI
    setRows(prev =>
      prev.map(r => {
        const currentId = userType === 'HILLSBOROUGH_NH' ? (r as HillsboroughNhRecord).document_number : (r as LisPendensRecord | MdCaseSearchRecord).case_number;
        return currentId === recordId ? { ...r, is_new: false } : r;
      })
    );
    
    // Persist to backend
    try {
      let endpoint, body;
      
      if (userType === 'MD_CASE_SEARCH') {
        endpoint = `/api/md-case-search`;
        body = JSON.stringify({ case_number: recordId, is_new: false });
      } else if (userType === 'HILLSBOROUGH_NH') {
        endpoint = `/api/hillsborough-nh`;
        body = JSON.stringify({ document_number: recordId, is_new: false });
      } else {
        endpoint = `/api/lis-pendens/${recordId}`;
        body = JSON.stringify({ is_new: false });
      }
      
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

  // Get the appropriate columns and display info based on user type
  const columns = userType === 'MD_CASE_SEARCH' ? mdCaseSearchColumns : 
                  userType === 'HILLSBOROUGH_NH' ? hillsboroughNhColumns : 
                  lphColumns;
  const displayTitle = userType === 'MD_CASE_SEARCH' ? 'Maryland Case Search' : 
                       userType === 'HILLSBOROUGH_NH' ? 'Hillsborough NH Records' : 
                       `${county} County Records`;
  const loadingMessage = userType === 'MD_CASE_SEARCH' 
    ? 'Scraping records from Maryland Case Search...'
    : userType === 'HILLSBOROUGH_NH'
    ? 'Scraping records from Hillsborough NH Registry...'
    : `Scraping records from ${county} County...`;

  return (
    <SidebarProvider>
      <style dangerouslySetInnerHTML={{ __html: sliderStyles }} />
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-16 shrink-0 items-center gap-2 border-b justify-between pr-6">
          <div className="flex items-center gap-2 px-3">
            <SidebarTrigger />
            <Separator orientation="vertical" className="mr-2 h-4" />
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
          <div className="flex items-center gap-4">
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
              className="bg-blue-600 text-white font-bold py-2 px-6 rounded-lg shadow-lg animate-pulse-grow hover:bg-blue-700 transition-all duration-200 mr-50 cursor-pointer"
              style={{ fontSize: '1.1rem' }}
              onClick={handlePullRecord}
              disabled={pulling}
            >
              Pull Records
            </button>
          </div>
        </header>
        <div className="flex flex-1 flex-col gap-4 p-4">
          <div className="min-h-[100vh] flex-1 rounded-xl bg-white md:min-h-min flex justify-center items-start">
            <div style={{ width: '100%', maxWidth: 1200, margin: '40px auto 0 auto', background: 'white', borderRadius: 8, padding: 16, boxShadow: '0 2px 16px rgba(0,0,0,0.07)', position: 'relative' }}>
              <div className="flex items-center gap-4 mb-4">
                {userType === 'LPH' && (
                  <Select
                    value={county}
                    onChange={e => setCounty(e.target.value)}
                    variant="outlined"
                    sx={{ color: 'black', background: 'white', minWidth: 160, borderColor: '#ccc', '.MuiOutlinedInput-notchedOutline': { borderColor: '#ccc' } }}
                  >
                    {counties.map(c => <MenuItem key={c} value={c} style={{ color: 'black' }}>{c} County</MenuItem>)}
                  </Select>
                )}
                
                <span style={{ color: 'black', fontWeight: 600, fontSize: 24 }}>
                  {displayTitle}
                </span>
              </div>
              <div style={{ position: 'relative', color: 'black' }}>
                <DataGrid
                  rows={rows}
                  columns={columns}
                  getRowId={(row) => userType === 'HILLSBOROUGH_NH' ? (row as HillsboroughNhRecord).document_number : (row as LisPendensRecord | MdCaseSearchRecord).case_number}
                  paginationModel={paginationModel}
                  onPaginationModelChange={setPaginationModel}
                  pageSizeOptions={[10, 25, 50]}
                  checkboxSelection
                  disableRowSelectionOnClick
                  onRowClick={handleRowClick}
                  sx={{ color: 'black', background: 'white', '& .MuiDataGrid-cell': { color: 'black' }, '& .MuiDataGrid-columnHeaders': { color: 'black' } }}
                />
              </div>
              {/* Loader inside content box */}
              {pulling && (
                <div className="absolute inset-0 z-20 flex items-center justify-center bg-white bg-opacity-80 rounded-lg">
                  <div className="flex flex-col items-center justify-center p-8">
                    <div className="flex space-x-2 mt-2">
                      <span className="dot-bounce bg-blue-600"></span>
                      <span className="dot-bounce bg-blue-600" style={{ animationDelay: '0.2s' }}></span>
                      <span className="dot-bounce bg-blue-600" style={{ animationDelay: '0.4s' }}></span>
                    </div>
                    <div className="mt-4 text-blue-700 font-semibold">
                      {jobStatus === 'PENDING' && 'Job queued, waiting to start...'}
                      {jobStatus === 'IN_PROGRESS' && loadingMessage}
                      {!jobStatus && 'Creating scraping job...'}
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
          <div className="fixed bottom-6 left-6 bg-green-600 text-white px-4 py-2 rounded shadow-lg z-50">Records pulled successfully!</div>
        )}
        {pullResult === 'error' && (
          <div className="fixed bottom-6 left-6 bg-red-600 text-white px-4 py-2 rounded shadow-lg z-50">Error pulling records.</div>
        )}
      </SidebarInset>
    </SidebarProvider>
  )
}
