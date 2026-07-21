'use client';

import { useState } from 'react';
import { Download, FileSpreadsheet, AlertCircle, CheckCircle2, Loader2, Scale, Info } from 'lucide-react';
import { exportsApi, downloadBlob } from '@/lib/api';
import { CITATION } from '@/lib/constants';

type ExportState = 'idle' | 'loading' | 'done' | 'error';

function ExportCard({
  title,
  description,
  details,
  buttonLabel,
  onExport,
  warning,
}: {
  title: string;
  description: string;
  details: string[];
  buttonLabel: string;
  onExport: () => Promise<void>;
  warning?: string;
}) {
  const [state, setState] = useState<ExportState>('idle');
  const [error, setError] = useState('');

  const handleExport = async () => {
    setState('loading');
    setError('');
    try {
      await onExport();
      setState('done');
      setTimeout(() => setState('idle'), 3000);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Export failed.');
      setState('error');
    }
  };

  return (
    <div className="store-utility-card flex flex-col">
      {/* Icon */}
      <div className="w-12 h-12 rounded-full flex items-center justify-center mb-6"
        style={{ backgroundColor: 'rgba(0, 102, 204, 0.08)', border: '1px solid rgba(0, 102, 204, 0.15)' }}>
        <FileSpreadsheet size={22} style={{ color: 'var(--primary)' }} />
      </div>

      <h3 className="typography-tagline mb-2" style={{ color: 'var(--ink)' }}>{title}</h3>
      <p className="typography-body mb-6" style={{ color: 'var(--ink-muted-80)' }}>{description}</p>

      {/* Details */}
      <div className="mb-6 space-y-3 flex-1">
        {details.map((d, i) => (
          <div key={i} className="flex items-start gap-3">
            <div className="w-1.5 h-1.5 rounded-full mt-2 flex-shrink-0" style={{ backgroundColor: 'var(--primary)' }} />
            <span className="typography-caption" style={{ color: 'var(--ink-muted-80)' }}>{d}</span>
          </div>
        ))}
      </div>

      {/* Warning */}
      {warning && (
        <div className="flex items-start gap-3 p-4 rounded-[11px] mb-6"
          style={{ backgroundColor: 'rgba(230, 153, 0, 0.06)', border: '1px solid rgba(230, 153, 0, 0.2)' }}>
          <AlertCircle size={14} style={{ color: 'var(--vc-amber)' }} className="flex-shrink-0 mt-0.5" />
          <span className="typography-caption" style={{ color: 'var(--ink-muted-80)' }}>{warning}</span>
        </div>
      )}

      {/* Export button */}
      <button
        onClick={handleExport}
        disabled={state === 'loading'}
        className="button-primary w-full flex items-center justify-center gap-2"
        style={state === 'done' ? {
          backgroundColor: 'var(--vc-green)',
        } : state === 'error' ? {
          backgroundColor: 'transparent',
          color: 'var(--vc-red)',
          border: '1px solid var(--vc-red)',
        } : state === 'loading' ? {
          opacity: 0.7,
        } : {}}
      >
        {state === 'loading' && <Loader2 size={16} className="animate-spin" />}
        {state === 'done' && <CheckCircle2 size={16} />}
        {state === 'error' && <AlertCircle size={16} />}
        {state === 'idle' && <Download size={16} />}
        {state === 'loading' ? 'Generating…' :
          state === 'done' ? 'Downloaded!' :
            state === 'error' ? (error || 'Export failed') :
              buttonLabel}
      </button>
    </div>
  );
}

export default function ExportsPage() {
  const currentFY = '2025-26';
  const currentHalfYear = 'April–September 2025';

  return (
    <div className="p-8 max-w-5xl mx-auto" style={{ backgroundColor: 'var(--canvas-parchment)' }}>
      {/* Header */}
      <div className="mb-10">
        <h1 className="typography-display-lg mb-2" style={{ color: 'var(--ink)' }}>Compliance Exports</h1>
        <p className="typography-lead" style={{ color: 'var(--ink-muted-80)' }}>
          One-click, audit-ready Excel exports for your CA and filing requirements
        </p>
      </div>

      {/* CA disclaimer */}
      <div className="flex items-start gap-4 p-5 rounded-[11px] mb-10 bg-canvas border" style={{ borderColor: 'var(--hairline)' }}>
        <Info size={18} style={{ color: 'var(--primary)' }} className="flex-shrink-0 mt-0.5" />
        <div className="typography-body" style={{ color: 'var(--ink-muted-80)' }}>
          <span className="typography-body-strong" style={{ color: 'var(--ink)' }}>Important: </span>
          These exports are informational.
          GST inclusion in the disallowance base and the dispute clock reset trigger are pending CA confirmation.
          Validate all numbers with your qualified CA or tax auditor before filing Form 3CD or MSME-1.
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-10">
        {/* Form 3CD */}
        <ExportCard
          title="Form 3CD — Tax Audit Export"
          description={`One-click export of all delayed MSE dues for your tax auditor — FY ${currentFY}.`}
          details={[
            'Vendor name, Udyam number, invoice date',
            '(Deemed) acceptance date, statutory due date',
            'Actual payment date, days delayed',
            'Disallowed principal, MSMED compound interest',
            'Both section citations printed in every cell',
            'RED/AMBER rows highlighted for auditor clarity',
          ]}
          buttonLabel={`Download Form 3CD (FY ${currentFY})`}
          warning="⚠ GST inclusion in taxable base is pending CA confirmation. Validate before filing."
          onExport={async () => {
            const blob = await exportsApi.form3cd(currentFY);
            downloadBlob(blob, `VendorClock_Form3CD_${currentFY.replace('-', '_')}.xlsx`);
          }}
        />

        {/* MSME-1 */}
        <ExportCard
          title="Form MSME-1 — ROC Half-Yearly"
          description={`Half-yearly disclosure of dues to Micro/Small suppliers >45 days outstanding — ${currentHalfYear}.`}
          details={[
            'Only Micro and Small enterprise dues included',
            'Medium enterprises auto-excluded (confirmed — not a gray area)',
            'Only invoices outstanding beyond 45 days',
            'Required for ROC filing twice a year',
            'Same underlying data as Form 3CD',
            `Period: ${currentHalfYear}`,
          ]}
          buttonLabel="Download Form MSME-1"
          onExport={async () => {
            const blob = await exportsApi.msme1(currentHalfYear);
            downloadBlob(blob, `VendorClock_MSME1_${new Date().toISOString().slice(0, 10)}.xlsx`);
          }}
        />
      </div>

      {/* Citation footer */}
      <div className="store-utility-card" style={{ backgroundColor: 'var(--canvas-parchment)' }}>
        <h4 className="typography-caption-strong mb-4" style={{ color: 'var(--ink)' }}>Statutory References</h4>
        <div className="space-y-3">
          {[
            ['Section 43B(h)', 'Income Tax Act (FY ≤ 2025-26 filings)'],
            ['Section 37(2)(g)', 'Income Tax Act 2025 (FY ≥ 2026-27 filings). Same rule, new citation.'],
            ['MSMED Act Section 16', 'Compound interest = 3× RBI Bank Rate, monthly compounding. Non-deductible.'],
            ['MSME-1 exclusion', 'Medium enterprises excluded per MSMED Act (confirmed — no gray area).'],
          ].map(([ref, desc]) => (
            <div key={ref} className="flex gap-3 items-start">
              <span className="typography-caption-strong flex-shrink-0 w-40" style={{ color: 'var(--ink)' }}>{ref}</span>
              <span className="typography-caption" style={{ color: 'var(--ink-muted-48)' }}>{desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
