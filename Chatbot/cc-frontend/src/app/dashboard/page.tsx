'use client';
import React, { useEffect, useState } from "react";
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
  const [rows, setRows] = useState<LisPendensRecord[]>([]);
  const [paginationModel, setPaginationModel] = useState({ page: 0, pageSize: 10 });
  const [county, setCounty] = useState('Harris');
  const [docType, setDocType] = useState('L/P');
  const counties = ['Harris', 'Fort Bend', 'Montgomery'];
  const docTypes = ['L/P', 'Deed', 'Mortgage'];
  const [pulling, setPulling] = useState(false);
  const [pullResult, setPullResult] = useState<null | 'success' | 'error'>(null);

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

  const handlePullRecord = async () => {
    setPulling(true);
    setPullResult(null);
    try {
      const res = await fetch('/api/pull-lph', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        setPullResult('success');
        // Automatically refresh the data after successful pull
        await fetchData();
      } else {
        setPullResult('error');
      }
    } catch (e) {
      setPullResult('error');
    } finally {
      setPulling(false);
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
          <button
            className="bg-blue-600 text-white font-bold py-2 px-6 rounded-lg shadow-lg animate-pulse-grow hover:bg-blue-700 transition-all duration-200 mr-50 cursor-pointer"
            style={{ fontSize: '1.1rem' }}
            onClick={handlePullRecord}
            disabled={pulling}
          >
            Pull Records
          </button>
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
                    <div className="mt-4 text-blue-700 font-semibold">Pulling records...</div>
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
