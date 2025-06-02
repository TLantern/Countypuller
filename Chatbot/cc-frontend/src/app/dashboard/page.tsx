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

const columns: GridColDef[] = [
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

// Add type for rows
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

export default function Dashboard() {
  const { data: session, status } = useSession();
  const router = useRouter();
  
  // ALL HOOKS MUST BE CALLED BEFORE ANY CONDITIONAL RETURNS
  const [rows, setRows] = useState<LisPendensRecord[]>([]);
  const [paginationModel, setPaginationModel] = useState({ page: 0, pageSize: 10 });
  const [county, setCounty] = useState('Harris');
  const [docType, setDocType] = useState('L/P');
  const counties = ['Harris', 'Fort Bend', 'Montgomery'];
  const docTypes = ['L/P', 'Deed', 'Mortgage'];
  const [pulling, setPulling] = useState(false);
  const [pullResult, setPullResult] = useState<null | 'success' | 'error'>(null);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string>('');

  // ALL useEffect hooks must be called before conditional returns
  const fetchData = async () => {
    try {
      const res = await fetch('/api/lis-pendens');
      const data = await res.json();
      setRows(data);
    } catch (error) {
      console.error('Error fetching data:', error);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

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
      const res = await fetch(`/api/pull-lph?job_id=${jobId}`);
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
      const res = await fetch('/api/pull-lph', { method: 'POST' });
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
    const case_number = params.row.case_number;
    // Only update if is_new is true
    if (!params.row.is_new) return;
    // Optimistically update UI
    setRows(prev =>
      prev.map(r =>
        r.case_number === case_number ? { ...r, is_new: false } : r
      )
    );
    // Persist to backend
    try {
      await fetch(`/api/lis-pendens/${case_number}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_new: false }),
      });
    } catch (e) {
      // Optionally: revert UI or show error
      console.error('Failed to update is_new:', e);
    }
  };

  return (
    <SidebarProvider>
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
                <Select
                  value={county}
                  onChange={e => setCounty(e.target.value)}
                  variant="outlined"
                  sx={{ color: 'black', background: 'white', minWidth: 160, borderColor: '#ccc', '.MuiOutlinedInput-notchedOutline': { borderColor: '#ccc' } }}
                >
                  {counties.map(c => <MenuItem key={c} value={c} style={{ color: 'black' }}>{c}</MenuItem>)}
                </Select>
                <Select
                  value={docType}
                  onChange={e => setDocType(e.target.value)}
                  variant="outlined"
                  sx={{ color: 'black', background: 'white', minWidth: 160, borderColor: '#ccc', '.MuiOutlinedInput-notchedOutline': { borderColor: '#ccc' } }}
                >
                  {docTypes.map(dt => <MenuItem key={dt} value={dt} style={{ color: 'black' }}>{dt}</MenuItem>)}
                </Select>
                <span style={{ color: 'black', fontWeight: 600, fontSize: 24 }}>
                  {county} County / {docType}
                </span>
              </div>
              <div style={{ position: 'relative', color: 'black' }}>
                <DataGrid
                  rows={rows}
                  columns={columns}
                  getRowId={(row) => row.case_number}
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
                      {jobStatus === 'IN_PROGRESS' && 'Scraping records from Harris County...'}
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
