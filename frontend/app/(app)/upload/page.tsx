'use client';

import { useState, useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, CheckCircle2, AlertCircle, Loader2, ChevronDown, Scale } from 'lucide-react';
import { ingestionApi } from '@/lib/api';
import { CITATION } from '@/lib/constants';

type Phase = 'idle' | 'uploading' | 'processing' | 'done' | 'error';

export default function UploadPage() {
  const [phase, setPhase] = useState<Phase>('idle');
  const [ingestionId, setIngestionId] = useState<number | null>(null);
  const [result, setResult] = useState<any>(null);
  const [file, setFile] = useState<File | null>(null);
  const [errorMsg, setErrorMsg] = useState('');

  const shouldPoll = phase === 'processing' && !!ingestionId;

  useEffect(() => {
    if (!shouldPoll) return;
    const interval = setInterval(async () => {
      try {
        const data = await ingestionApi.getStatus(ingestionId!);
        setResult(data);
        if (data.status === 'COMPLETED' || data.status === 'PARTIAL') {
          setPhase('done');
          clearInterval(interval);
        } else if (data.status === 'FAILED') {
          setErrorMsg(data.error_details?.[0]?.error || 'Processing failed.');
          setPhase('error');
          clearInterval(interval);
        }
      } catch {
        // keep polling silently
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [shouldPoll, ingestionId]);

  const onDrop = useCallback(async (accepted: File[]) => {
    const f = accepted[0];
    if (!f) return;
    setFile(f);
    setPhase('uploading');
    setErrorMsg('');
    setResult(null);
    try {
      const res = await ingestionApi.upload(f);
      setIngestionId(res.ingestion_id);
      if (res.status === 'COMPLETED' || res.status === 'PARTIAL') {
        try {
          const detail = await ingestionApi.getStatus(res.ingestion_id);
          setResult(detail);
        } catch {
          setResult(res);
        }
        setPhase('done');
      } else {
        setPhase('processing');
      }
    } catch (e: any) {
      setErrorMsg(e?.response?.data?.detail || 'Upload failed. Please try again.');
      setPhase('error');
    }
  }, []);

  const reset = () => {
    setPhase('idle');
    setFile(null);
    setIngestionId(null);
    setResult(null);
    setErrorMsg('');
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
      'application/vnd.ms-excel': ['.xls'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
    },
    maxFiles: 1,
    disabled: phase === 'uploading' || phase === 'processing',
  });

  return (
    <div className="p-8 max-w-4xl mx-auto" style={{ backgroundColor: 'var(--canvas-parchment)' }}>
      {/* Header */}
      <div className="mb-10">
        <h1 className="typography-display-lg mb-2" style={{ color: 'var(--ink)' }}>Upload Purchase Register</h1>
        <p className="typography-lead" style={{ color: 'var(--ink-muted-80)' }}>
          Upload your CSV or Excel payables register from Tally, Zoho, or SAP. Columns are auto-detected.
        </p>
      </div>

      {/* Drop Zone */}
      {(phase === 'idle' || phase === 'error') && (
        <div
          {...getRootProps()}
          className={`upload-zone p-20 text-center mb-8 ${isDragActive ? 'drag-active' : ''}`}
        >
          <input {...getInputProps()} id="file-upload" />
          <div className="flex flex-col items-center gap-6">
            <div className="w-20 h-20 rounded-full flex items-center justify-center"
              style={{ backgroundColor: 'rgba(0, 102, 204, 0.08)', border: '1px solid rgba(0, 102, 204, 0.2)' }}>
              <Upload size={32} style={{ color: 'var(--primary)' }} />
            </div>
            <div>
              <p className="typography-tagline mb-2" style={{ color: 'var(--ink)' }}>
                {isDragActive ? 'Drop your file here' : 'Drag & drop or click to upload'}
              </p>
              <p className="typography-body" style={{ color: 'var(--ink-muted-48)' }}>
                Accepts .csv, .xlsx, .xls — up to 50 MB
              </p>
            </div>
            {phase === 'error' && errorMsg && (
              <div className="flex items-center gap-2 px-5 py-3 rounded-full"
                style={{ backgroundColor: 'rgba(204, 0, 0, 0.06)', border: '1px solid rgba(204, 0, 0, 0.2)' }}>
                <AlertCircle size={14} style={{ color: 'var(--vc-red)' }} />
                <span className="typography-caption" style={{ color: 'var(--vc-red)' }}>{errorMsg}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Spinner */}
      {(phase === 'uploading' || phase === 'processing') && (
        <div className="store-utility-card p-12 text-center mb-8">
          <div className="flex flex-col items-center gap-6">
            <div className="w-16 h-16 rounded-full flex items-center justify-center"
              style={{ backgroundColor: 'rgba(0, 102, 204, 0.08)' }}>
              <Loader2 size={32} className="animate-spin" style={{ color: 'var(--primary)' }} />
            </div>
            <div>
              <p className="typography-tagline mb-2" style={{ color: 'var(--ink)' }}>
                {phase === 'uploading' ? `Uploading ${file?.name}…` : 'Processing your register…'}
              </p>
              <p className="typography-body" style={{ color: 'var(--ink-muted-48)' }}>
                {phase === 'processing'
                  ? 'Detecting columns, classifying vendors, starting compliance clocks…'
                  : 'Sending file to server…'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Success screen */}
      {phase === 'done' && (
        <div className="store-utility-card mb-8">
          <div className="flex items-start gap-5">
            <div className="w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0"
              style={{ backgroundColor: 'rgba(0, 153, 51, 0.1)' }}>
              <CheckCircle2 size={28} style={{ color: 'var(--vc-green)' }} />
            </div>
            <div className="flex-1">
              <h2 className="typography-tagline mb-6" style={{ color: 'var(--ink)' }}>Upload Complete!</h2>

              <div className="grid grid-cols-3 gap-4 mb-6">
                {[
                  { label: 'Invoices imported', val: result?.processed_rows ?? '—', color: 'var(--vc-green)' },
                  { label: 'Rows failed', val: result?.failed_rows ?? 0, color: result?.failed_rows > 0 ? 'var(--vc-red)' : 'var(--ink-muted-48)' },
                  { label: 'Total rows', val: result?.total_rows ?? '—', color: 'var(--primary)' },
                ].map(({ label, val, color }) => (
                  <div key={label} className="text-center p-4 rounded-[11px]" style={{ backgroundColor: 'var(--surface-pearl)', border: '1px solid var(--hairline)' }}>
                    <div className="typography-display-md" style={{ color }}>{val}</div>
                    <div className="typography-caption" style={{ color: 'var(--ink-muted-48)' }}>{label}</div>
                  </div>
                ))}
              </div>

              {result?.column_mapping && Object.keys(result.column_mapping).length > 0 && (
                <details className="mb-6">
                  <summary className="typography-caption flex items-center gap-2 cursor-pointer mb-3" style={{ color: 'var(--ink-muted-48)' }}>
                    <ChevronDown size={14} /> Column mapping detected
                  </summary>
                  <div className="grid grid-cols-2 gap-2">
                    {Object.entries(result.column_mapping)
                      .filter(([, v]) => v)
                      .map(([field, col]) => (
                        <div key={field} className="flex items-center gap-2 px-3 py-2 rounded-lg"
                          style={{ backgroundColor: 'var(--surface-pearl)', border: '1px solid var(--hairline)' }}>
                          <span className="typography-caption" style={{ color: 'var(--ink-muted-48)' }}>{field}</span>
                          <span className="typography-caption-strong" style={{ color: 'var(--ink)' }}>→ {col as string}</span>
                        </div>
                      ))}
                  </div>
                </details>
              )}

              {result?.error_details?.length > 0 && (
                <div className="mb-6 p-4 rounded-[11px]"
                  style={{ backgroundColor: 'rgba(230, 153, 0, 0.06)', border: '1px solid rgba(230, 153, 0, 0.2)' }}>
                  <p className="typography-caption-strong mb-2" style={{ color: 'var(--vc-amber)' }}>
                    ⚠ {result.error_details.length} rows had issues:
                  </p>
                  {result.error_details.slice(0, 5).map((e: any, i: number) => (
                    <p key={i} className="typography-caption" style={{ color: 'var(--ink-muted-80)' }}>Row {e.row}: {e.error}</p>
                  ))}
                </div>
              )}

              <div className="flex gap-4">
                <a href="/dashboard" className="button-primary">
                  View Dashboard →
                </a>
                <button onClick={reset} className="button-secondary-pill">
                  Upload Another
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Format guide */}
      <div className="store-utility-card">
        <h3 className="typography-body-strong mb-6" style={{ color: 'var(--ink)' }}>Supported Columns (Auto-Detected)</h3>
        <div className="grid grid-cols-2 gap-3">
          {[
            ['Vendor Name', 'Supplier, Party, Creditor'],
            ['PAN / GSTIN', 'Tax ID, GSTIN/UIN, PAN No'],
            ['Invoice Number', 'Bill No, Voucher No, Ref No'],
            ['Invoice Date', 'Bill Date, Document Date'],
            ['Delivery Date', 'Receipt Date, GR Date'],
            ['Amount', 'Invoice Value, Total Amount'],
            ['Pending Amount', 'Outstanding, Balance Due'],
            ['Payment Date', 'Paid On, Cleared On'],
            ['Credit Days', 'Payment Terms, Credit Period'],
            ['GST Amount', 'IGST, CGST+SGST, Tax Amount'],
          ].map(([field, aliases]) => (
            <div key={field} className="flex gap-3 py-2 border-b last:border-0" style={{ borderColor: 'var(--hairline)' }}>
              <span className="typography-caption-strong w-32 flex-shrink-0" style={{ color: 'var(--ink)' }}>{field}</span>
              <span className="typography-caption" style={{ color: 'var(--ink-muted-48)' }}>{aliases}</span>
            </div>
          ))}
        </div>
        <p className="typography-caption mt-6" style={{ color: 'var(--ink-muted-48)' }}>
          Columns are matched using fuzzy detection — exact names not required.
          If auto-detection misses a column, you can correct the mapping after upload.
        </p>
      </div>
    </div>
  );
}
