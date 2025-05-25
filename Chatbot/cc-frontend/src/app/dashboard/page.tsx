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

  useEffect(() => {
    fetch('/api/lis-pendens')
      .then(res => res.json())
      .then(data => setRows(data));
  }, []);

  // Handle row click to set is_new to false (X)
  const handleRowClick = async (params: { row: LisPendensRecord }) => {
    setRows((prevRows) =>
      prevRows.map((row) =>
        row.case_number === params.row.case_number
          ? { ...row, is_new: false }
          : row
      )
    );
    // Persist to backend
    try {
      const res = await fetch(`/api/lis-pendens/${params.row.case_number}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_new: false }),
      });
      if (!res.ok) {
        throw new Error('Failed to update record');
      }
    } catch (err) {
      alert('Failed to update record in the database.');
    }
  };

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-16 shrink-0 items-center gap-2 border-b">
          <div className="flex items-center gap-2 px-3">
            <SidebarTrigger />
            <Separator orientation="vertical" className="mr-2 h-4" />
            <Breadcrumb>
              <BreadcrumbList>
                <BreadcrumbItem className="hidden md:block">
                  <BreadcrumbLink href="#">
                    County Cloud
                  </BreadcrumbLink>
                </BreadcrumbItem>
                <BreadcrumbSeparator className="hidden md:block" />
                <BreadcrumbItem>
                  <BreadcrumbPage>Dashboard</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>
        </header>
        <div className="flex flex-1 flex-col gap-4 p-4">
          <div className="min-h-[100vh] flex-1 rounded-xl bg-muted/50 md:min-h-min">
            <div style={{ height: 600, width: '100%', background: 'white', borderRadius: 8, padding: 16 }}>
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
                density="compact"
              />
            </div>
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
