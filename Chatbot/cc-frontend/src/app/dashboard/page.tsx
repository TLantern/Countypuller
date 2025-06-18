'use client';
import React, { useEffect, useState } from "react";
import { useSession, signOut } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
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
import FeedbackPanel from '@/components/FeedbackPanel';
import { useFeedback } from '@/context/FeedbackContext';
import { MessageSquare } from 'lucide-react';
// Dynamic imports used in export functions to avoid SSR issues

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

// Columns for Brevard FL users
const brevardFlColumns: GridColDef[] = [
  { field: 'case_number', headerName: 'Case #', minWidth: 120, maxWidth: 140, flex: 0.8 },
  { field: 'document_url', headerName: 'Doc URL', minWidth: 70, maxWidth: 90, flex: 0.5, renderCell: (params) => params.value ? <a href={params.value} target="_blank" rel="noopener noreferrer" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block', width: '100%' }}>Link</a> : '' },
  { field: 'file_date', headerName: 'Record Date', minWidth: 110, maxWidth: 130, flex: 0.7 },
  { field: 'case_type', headerName: 'Doc Type', minWidth: 100, maxWidth: 120, flex: 0.8 },
  { field: 'party_name', headerName: 'Party Name', minWidth: 150, maxWidth: 200, flex: 1.2 },
  { field: 'property_address', headerName: 'Property Address', minWidth: 150, maxWidth: 200, flex: 1.2, renderCell: (params) => <PropertyAddressCell value={params.value} /> },
  { field: 'county', headerName: 'County', minWidth: 80, maxWidth: 100, flex: 0.6 },
  { field: 'created_at', headerName: 'Created At', minWidth: 120, maxWidth: 160, flex: 1, renderCell: (params) => <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block', width: '100%' }}>{params.value}</span> },
  { field: 'is_new', headerName: 'Is New', minWidth: 60, maxWidth: 70, flex: 0.4, type: 'boolean' },
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
      const XLSX = await import('xlsx');
      const worksheet = XLSX.utils.json_to_sheet(data);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, displayTitle);
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
      const { jsPDF } = await import('jspdf');
      await import('jspdf-autotable');
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
        className="bg-blue-800 hover:bg-blue-900 text-white font-semibold py-2 px-4 rounded-lg shadow-lg transition-all duration-200 flex items-center gap-2"
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
              className="w-full text-left px-4 py-2 text-gray-700 hover:bg-gray-100 flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Export as CSV
            </button>
            <button
              onClick={exportToExcel}
              className="w-full text-left px-4 py-2 text-gray-700 hover:bg-gray-100 flex items-center gap-2"
            >
              <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Export as Excel
            </button>
            <button
              onClick={exportToPDF}
              className="w-full text-left px-4 py-2 text-gray-700 hover:bg-gray-100 flex items-center gap-2"
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

export default function Dashboard() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [selectedCounty, setSelectedCounty] = useState<string | null>(null);
  const onboardingCounties = ["Harris", "Dallas", "Tarrant", "Bexar", "Travis"];
  
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
  
  // Get feedback panel state from context
  const { isFeedbackPanelOpen, setIsFeedbackPanelOpen } = useFeedback();

  const [onboardingStep, setOnboardingStep] = useState(1);
  const [selectedDocTypes, setSelectedDocTypes] = useState<string[]>([]);
  const docTypes = [
    "Lis Pendens",
    "Notice of Default (NOD)",
    "Auction",
    "Bankruptcy"
  ];

  // ALL useEffect hooks must be called before conditional returns
  const fetchData = async () => {
    try {
      const endpoint = userType === 'MD_CASE_SEARCH' ? '/api/md-case-search' : 
                      userType === 'HILLSBOROUGH_NH' ? '/api/hillsborough-nh' : 
                      userType === 'BREVARD_FL' ? '/api/brevard-fl' :
                      userType === 'FULTON_GA' ? '/api/fulton-ga' :
                      userType === 'COBB_GA' ? '/api/cobb-ga' :
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

  // Show onboarding if just logged in or if no county is selected (use sessionStorage to persist)
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const onboarded = sessionStorage.getItem('onboarded');
      if (!onboarded) {
        setShowOnboarding(true);
      }
    }
  }, []);

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

  const handleOnboardingFinish = () => {
    setShowOnboarding(false);
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('onboarded', '1');
      sessionStorage.setItem('selectedDocTypes', JSON.stringify(selectedDocTypes));
    }
  };

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
        : userType === 'BREVARD_FL'
        ? `/api/pull-brevard-fl?job_id=${jobId}`
        : userType === 'FULTON_GA'
        ? `/api/pull-fulton-ga?job_id=${jobId}`
        : userType === 'COBB_GA'
        ? `/api/pull-cobb-ga?job_id=${jobId}`
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
                      userType === 'BREVARD_FL' ? '/api/pull-brevard-fl' :
                      userType === 'FULTON_GA' ? '/api/pull-fulton-ga' :
                      userType === 'COBB_GA' ? '/api/pull-cobb-ga' :
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
      
      // Handle Cobb GA immediate response (no job polling)
      if (userType === 'COBB_GA') {
        if (data.success && data.records_created !== undefined) {
          setPullResult('success');
          setPulling(false);
          // Refresh data immediately
          await fetchData();
        } else {
          setPullResult('error');
          setPulling(false);
        }
      } 
      // Handle other endpoints with job polling
      else if (data.success && data.job_id) {
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
    let recordId;
    if (userType === 'HILLSBOROUGH_NH') {
      recordId = params.row.document_number;
    } else if (userType === 'BREVARD_FL' || userType === 'FULTON_GA' || userType === 'COBB_GA') {
      recordId = params.row.case_number;
    } else {
      recordId = params.row.case_number;
    }
    
    // Only update if is_new is true and we have a valid recordId
    if (!params.row.is_new || !recordId) return;
    
    // Optimistically update UI
    setRows(prev =>
      prev.map(r => {
        const currentId = userType === 'HILLSBOROUGH_NH' ? 
          (r as HillsboroughNhRecord).document_number :
          userType === 'BREVARD_FL' ?
          (r as BrevardFlRecord).case_number :
          userType === 'FULTON_GA' ?
          (r as FultonGaRecord).case_number :
          userType === 'COBB_GA' ?
          (r as CobbGaRecord).case_number :
          (r as LisPendensRecord | MdCaseSearchRecord).case_number;
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
      } else if (userType === 'BREVARD_FL') {
        endpoint = `/api/brevard-fl`;
        body = JSON.stringify({ case_number: recordId, is_new: false });
      } else if (userType === 'FULTON_GA') {
        endpoint = `/api/fulton-ga`;
        body = JSON.stringify({ case_number: recordId, is_new: false });
      } else if (userType === 'COBB_GA') {
        endpoint = `/api/cobb-ga`;
        body = JSON.stringify({ case_number: recordId, is_new: false });
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
                  userType === 'BREVARD_FL' ? brevardFlColumns :
                  userType === 'FULTON_GA' ? fultonGaColumns :
                  userType === 'COBB_GA' ? cobbGaColumns :
                  lphColumns;
  const displayTitle = userType === 'MD_CASE_SEARCH' ? 'Maryland Case Search' : 
                       userType === 'HILLSBOROUGH_NH' ? 'Hillsborough NH Records' : 
                       userType === 'BREVARD_FL' ? 'Brevard FL Records' :
                       userType === 'FULTON_GA' ? 'Fulton GA Records' :
                       userType === 'COBB_GA' ? 'Cobb GA Records' :
                       `${county} County Records`;
  const loadingMessage = userType === 'MD_CASE_SEARCH' 
    ? 'Scraping records from Maryland Case Search...'
    : userType === 'HILLSBOROUGH_NH'
    ? 'Scraping records from Hillsborough NH Registry...'
    : userType === 'BREVARD_FL'
    ? 'Scraping records from Brevard FL Official Records...'
    : userType === 'FULTON_GA'
    ? 'Scraping records from Fulton GA GSCCCA...'
    : userType === 'COBB_GA'
    ? 'Scraping records from Cobb GA GSCCCA...'
    : `Scraping records from ${county} County...`;

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
                      {county} County
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
                  className="bg-blue-500 text-white p-2 rounded-lg shadow-lg hover:bg-blue-600 transition-all duration-200 cursor-pointer"
                  onClick={() => setIsFeedbackPanelOpen(true)}
                  title="Provide Feedback"
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
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-4">
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
                    
                    <ExportButton 
                      data={rows} 
                      userType={userType} 
                      displayTitle={displayTitle}
                    />
                  </div>
                  <div style={{ position: 'relative', color: 'black' }}>
                    <DataGrid
                      rows={rows}
                      columns={columns}
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
          
          {/* Feedback Panel */}
          <FeedbackPanel 
            isOpen={isFeedbackPanelOpen}
            onClose={() => setIsFeedbackPanelOpen(false)}
          />
        </SidebarProvider>
      </div>
    </>
  )
}
