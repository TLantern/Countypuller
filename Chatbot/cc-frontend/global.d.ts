/// <reference types="react" />
/// <reference types="react-dom" />

import * as React from 'react';

declare global {
  namespace JSX {
    interface IntrinsicElements {
      [elemName: string]: any;
    }
    interface Element extends React.ReactElement<any, any> { }
    interface ElementClass extends React.Component<any> {
      render(): React.ReactNode;
    }
    interface ElementAttributesProperty {
      props: {};
    }
    interface ElementChildrenAttribute {
      children: {};
    }
  }
}

declare module 'react' {
  export function useState<T>(initialState: T | (() => T)): [T, (value: T | ((prev: T) => T)) => void];
  export function useEffect(effect: () => void | (() => void), deps?: any[]): void;
  export function useRef<T>(initialValue: T): { current: T };
  export function useCallback<T extends (...args: any[]) => any>(callback: T, deps: any[]): T;
  export function useMemo<T>(factory: () => T, deps: any[]): T;
  export * from 'react';
}

declare module 'next-auth/react' {
  export function useSession(): { data: any; status: string };
  export function signOut(options?: any): void;
}

declare module 'next/navigation' {
  export function useRouter(): any;
}

declare module '@mui/x-data-grid' {
  interface GridColDef {
    field: string;
    headerName: string;
    minWidth?: number;
    maxWidth?: number;
    flex?: number;
    type?: string;
    renderCell?: (params: any) => React.ReactNode;
  }
  const DataGrid: React.FC<any>;
  export { DataGrid, GridColDef };
}

declare module 'lucide-react' {
  export const MessageSquare: React.FC<any>;
}

declare module 'file-saver' {
  export function saveAs(blob: Blob, filename: string): void;
  export default saveAs;
}

declare module 'xlsx' {
  export const utils: {
    json_to_sheet: (data: any[]) => any;
    book_new: () => any;
    book_append_sheet: (workbook: any, worksheet: any, name: string) => void;
  };
  export function writeFile(workbook: any, filename: string): void;
}

declare module 'jspdf' {
  export class jsPDF {
    constructor();
    setFontSize(size: number): void;
    text(text: string, x: number, y: number): void;
    addPage(): void;
    save(filename: string): void;
  }
}

declare module 'jspdf-autotable' {}

declare module 'react-dom' {
  export = ReactDOM;
  export as namespace ReactDOM;
}

declare module 'csv-parser' {
  import { Transform } from 'stream';
  
  interface Options {
    separator?: string;
    quote?: string;
    escape?: string;
    newline?: string;
    strict?: boolean;
    skipEmptyLines?: boolean;
    skipLinesWithError?: boolean;
    maxRowBytes?: number;
    headers?: string[] | boolean;
    skipFirstLine?: boolean;
  }
  
  function csv(options?: Options): Transform;
  export = csv;
} 