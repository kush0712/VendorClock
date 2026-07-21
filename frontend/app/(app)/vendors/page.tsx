'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { vendorsApi } from '@/lib/api';
import { getVendorStatusLabel, formatDate, CITATION, type VendorStatus } from '@/lib/constants';
import { Building2, Search, CheckCircle2, Clock, XCircle, Scale, Send, Loader2 } from 'lucide-react';
import { useState } from 'react';

const STATUS_BADGE: Record<VendorStatus, { label: string; color: string }> = {
  ELIGIBLE: { label: 'Eligible MSE', color: 'text-white' },
  EXCLUDED_TRADER: { label: 'Excluded (Trader)', color: 'text-white' },
  EXCLUDED_MEDIUM: { label: 'Excluded (Medium)', color: 'text-white' },
  PENDING_DECLARATION: { label: 'Pending Declaration', color: 'text-white' },
  NOT_REGISTERED: { label: 'Not Registered', color: 'text-white' },
};

export default function VendorsPage() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [declarationSent, setDeclarationSent] = useState<Record<number, boolean>>({});
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['vendors', statusFilter, search],
    queryFn: () => vendorsApi.list({
      search: search || undefined,
      status_filter: statusFilter || undefined,
      limit: 200,
    }),
    refetchInterval: 60_000,
  });

  const declarationMutation = useMutation({
    mutationFn: (vendorId: number) => vendorsApi.sendDeclaration(vendorId),
    onSuccess: (_data, vendorId) => {
      setDeclarationSent(prev => ({ ...prev, [vendorId]: true }));
      setTimeout(() => setDeclarationSent(prev => ({ ...prev, [vendorId]: false })), 4000);
    },
  });

  const summary = data?.status_summary;

  return (
    <div className="p-8 max-w-[1440px] mx-auto bg-canvas-parchment font-sf-display">
      <div className="mb-10">
        <h1 className="typography-display-lg mb-2" style={{ color: 'var(--ink)' }}>Vendor MSME Status</h1>
        <p className="typography-lead" style={{ color: 'var(--ink-muted-80)' }}>
          Classification status for all vendors — {data?.total || 0} total
        </p>
      </div>

      {/* Summary pills */}
      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
          {[
            { label: 'Eligible', count: summary.eligible, cls: 'var(--vc-green)', icon: CheckCircle2 },
            { label: 'Pending', count: summary.pending, cls: 'var(--vc-amber)', icon: Clock },
            { label: 'Excluded Traders', count: summary.excluded_trader, cls: 'var(--ink-muted-48)', icon: XCircle },
            { label: 'Excluded Medium', count: summary.excluded_medium, cls: 'var(--ink-muted-48)', icon: XCircle },
          ].map(({ label, count, cls, icon: Icon }) => (
            <div key={label} className="store-utility-card flex items-center gap-4">
              <div className="w-10 h-10 rounded-full flex items-center justify-center" style={{ backgroundColor: `color-mix(in srgb, ${cls} 15%, transparent)` }}>
                <Icon size={20} style={{ color: cls }} />
              </div>
              <div>
                <div className="typography-display-md" style={{ color: 'var(--ink)' }}>{count}</div>
                <div className="typography-caption-strong" style={{ color: 'var(--ink-muted-48)' }}>{label}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-4 mb-8 flex-wrap">
        <div className="relative">
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by name, PAN, GSTIN..."
            className="pl-10 pr-5 py-2.5 rounded-full outline-none w-72 typography-body transition-colors"
            style={{
              backgroundColor: 'var(--canvas)',
              border: '1px solid var(--hairline)',
              color: 'var(--ink)',
            }}
            onFocus={e => e.target.style.borderColor = 'var(--primary)'}
            onBlur={e => e.target.style.borderColor = 'var(--hairline)'}
          />
          <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2"
            style={{ color: 'var(--ink-muted-48)' }} />
        </div>
        
        <div className="flex bg-canvas rounded-full p-1 border" style={{ borderColor: 'var(--hairline)' }}>
          {['', 'ELIGIBLE', 'PENDING_DECLARATION', 'EXCLUDED_TRADER', 'EXCLUDED_MEDIUM'].map(s => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className="px-4 py-1.5 rounded-full typography-caption-strong transition-all duration-200"
              style={{
                backgroundColor: statusFilter === s 
                  ? (s === 'ELIGIBLE' ? 'var(--vc-green)' : s === 'PENDING_DECLARATION' ? 'var(--vc-amber)' : s ? 'var(--ink-muted-48)' : 'var(--ink)')
                  : 'transparent',
                color: statusFilter === s ? '#ffffff' : 'var(--ink-muted-48)',
              }}
            >
              {s ? getVendorStatusLabel(s as VendorStatus) : 'All'}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="store-utility-card p-0 overflow-hidden">
        <table className="data-table">
          <thead>
            <tr>
              {['Vendor Name', 'PAN', 'GSTIN', 'Udyam No.', 'NIC Code', 'Category', 'Status', 'Last Verified', 'Action'].map(h => (
                <th key={h}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              [...Array(6)].map((_, i) => (
                <tr key={i}>{[...Array(8)].map((_, j) => (
                  <td key={j}><div className="h-4 bg-surface-pearl animate-pulse rounded" /></td>
                ))}</tr>
              ))
            ) : (data?.items || []).length === 0 ? (
              <tr>
                <td colSpan={8} className="px-4 py-16 text-center">
                  <Building2 size={32} className="mx-auto mb-4" style={{ color: 'var(--ink-muted-48)' }} />
                  <p className="typography-body" style={{ color: 'var(--ink-muted-48)' }}>No vendors found</p>
                </td>
              </tr>
            ) : (
              (data?.items || []).map((v: any) => {
                const badge = STATUS_BADGE[v.status as VendorStatus];
                const statusColor = v.status === 'ELIGIBLE' ? 'var(--vc-green)' : v.status === 'PENDING_DECLARATION' ? 'var(--vc-amber)' : v.status === 'NOT_REGISTERED' ? 'var(--vc-red)' : 'var(--ink-muted-48)';
                return (
                  <tr key={v.id} className="transition-colors">
                    <td>
                      <div className="typography-body-strong" style={{ color: 'var(--ink)' }}>{v.name}</div>
                    </td>
                    <td>
                      <span className="typography-caption" style={{ color: 'var(--ink-muted-48)' }}>
                        {v.pan || '—'}
                      </span>
                    </td>
                    <td>
                      <span className="typography-caption" style={{ color: 'var(--ink-muted-48)' }}>
                        {v.gstin || '—'}
                      </span>
                    </td>
                    <td>
                      <span className="typography-caption" style={{ color: 'var(--ink-muted-48)' }}>
                        {v.udyam_number || '—'}
                      </span>
                    </td>
                    <td>
                      <span className="typography-caption" style={{ color: 'var(--ink-muted-48)' }}>
                        {v.nic_code || '—'}
                      </span>
                    </td>
                    <td>
                      <span className="typography-caption" style={{ color: 'var(--ink-muted-48)' }}>
                        {v.enterprise_category || '—'}
                      </span>
                    </td>
                    <td>
                      <span className="typography-caption-strong px-3 py-1 rounded-full text-white" style={{ backgroundColor: statusColor }}>
                        {getVendorStatusLabel(v.status as VendorStatus)}
                      </span>
                    </td>
                  <td className="typography-body" style={{ color: 'var(--ink-muted-80)' }}>
                      {formatDate(v.last_verified_at)}
                    </td>
                    <td>
                      {(v.status === 'PENDING_DECLARATION' || v.status === 'NOT_REGISTERED') && v.contact_email ? (
                        <button
                          onClick={() => declarationMutation.mutate(v.id)}
                          disabled={declarationMutation.isPending || declarationSent[v.id]}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg typography-caption-strong transition-all"
                          style={{
                            backgroundColor: declarationSent[v.id] ? 'rgba(26,140,60,0.1)' : 'rgba(0,102,204,0.08)',
                            color: declarationSent[v.id] ? 'var(--vc-green)' : 'var(--primary)',
                            cursor: declarationMutation.isPending ? 'not-allowed' : 'pointer',
                          }}
                          title={`Send Udyam declaration email to ${v.contact_email}`}
                        >
                          {declarationSent[v.id]
                            ? <><CheckCircle2 size={12} /> Sent</>  
                            : declarationMutation.isPending
                            ? <><Loader2 size={12} className="animate-spin" /> Sending…</>
                            : <><Send size={12} /> Send Link</>}
                        </button>
                      ) : (
                        <span className="typography-caption" style={{ color: 'var(--ink-muted-48)' }}>
                          {!v.contact_email ? 'No email' : '—'}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-8 pt-8 border-t" style={{ borderColor: 'var(--hairline)' }}>
        <p className="typography-fine-print" style={{ color: 'var(--ink-muted-48)' }}>
          ⚠ NIC codes 45, 46, 47 (Wholesale/Retail Trade) are automatically EXCLUDED — 
          Section 15 of the MSMED Act does not protect traders. 
          {CITATION} applies only to Micro/Small manufacturers and service providers.
        </p>
      </div>
    </div>
  );
}
