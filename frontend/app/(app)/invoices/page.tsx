'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { invoicesApi } from '@/lib/api';
import {
  formatINR, formatDate, getDaysLabel,
  getClockStatusClass, CITATION, type ClockStatus
} from '@/lib/constants';
import { Clock, Filter, Scale, CheckCircle2, Loader2 } from 'lucide-react';
import { useState } from 'react';

const STATUS_FILTERS: Array<{ label: string; value: string; cls: string }> = [
  { label: 'All', value: '', cls: '' },
  { label: 'Overdue', value: 'RED', cls: 'text-white' },
  { label: 'Due Soon', value: 'AMBER', cls: 'text-white' },
  { label: 'Safe', value: 'GREEN', cls: 'text-white' },
  { label: 'Paid', value: 'PAID', cls: 'text-white' },
];

export default function InvoicesPage() {
  const [statusFilter, setStatusFilter] = useState('');
  const [search, setSearch] = useState('');
  const [markedPaid, setMarkedPaid] = useState<Record<number, boolean>>({});
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['invoices', statusFilter],
    queryFn: () => invoicesApi.list({ clock_status: statusFilter || undefined, limit: 200 }),
    refetchInterval: 30_000,
  });

  const markPaidMutation = useMutation({
    mutationFn: (invoiceId: number) =>
      invoicesApi.update(invoiceId, {
        is_paid: true,
        payment_date: new Date().toISOString(),
      }),
    onSuccess: (_data, invoiceId) => {
      setMarkedPaid(prev => ({ ...prev, [invoiceId]: true }));
      // Refresh invoice list and dashboard summary
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
    },
  });

  const invoices = data?.items || [];
  const filtered = search
    ? invoices.filter((i: any) =>
      i.vendor_name?.toLowerCase().includes(search.toLowerCase()) ||
      i.invoice_number?.toLowerCase().includes(search.toLowerCase())
    )
    : invoices;

  return (
    <div className="p-8 max-w-[1440px] mx-auto bg-canvas-parchment font-sf-display">
      {/* Header */}
      <div className="mb-10">
        <h1 className="typography-display-lg mb-2" style={{ color: 'var(--ink)' }}>Invoice Tracker</h1>
        <p className="typography-lead" style={{ color: 'var(--ink-muted-80)' }}>
          Live compliance clock for all MSE invoices — {data?.total || 0} total
        </p>
      </div>

      {/* Filters */}
      <div className="flex gap-4 mb-8 flex-wrap">
        <div className="relative">
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search vendor or invoice..."
            className="pl-10 pr-5 py-2.5 rounded-full outline-none w-72 typography-body transition-colors"
            style={{
              backgroundColor: 'var(--canvas)',
              border: '1px solid var(--hairline)',
              color: 'var(--ink)',
            }}
            onFocus={e => e.target.style.borderColor = 'var(--primary)'}
            onBlur={e => e.target.style.borderColor = 'var(--hairline)'}
          />
          <Filter size={16} className="absolute left-4 top-1/2 -translate-y-1/2"
            style={{ color: 'var(--ink-muted-48)' }} />
        </div>
        
        <div className="flex bg-canvas rounded-full p-1 border" style={{ borderColor: 'var(--hairline)' }}>
          {STATUS_FILTERS.map(f => (
            <button
              key={f.value}
              onClick={() => setStatusFilter(f.value)}
              className="px-4 py-1.5 rounded-full typography-caption-strong transition-all duration-200"
              style={{
                backgroundColor: statusFilter === f.value 
                  ? (f.value === 'RED' ? 'var(--vc-red)' : f.value === 'AMBER' ? 'var(--vc-amber)' : f.value === 'GREEN' ? 'var(--vc-green)' : f.value === 'PAID' ? 'var(--primary)' : 'var(--ink)')
                  : 'transparent',
                color: statusFilter === f.value ? '#ffffff' : 'var(--ink-muted-48)',
              }}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="store-utility-card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                {['Vendor', 'Invoice No.', 'Invoice Date', 'Due Date', 'Clock', 'Pending (₹)', 'Disallowed (₹)', 'Interest (₹)', 'Priority Score', 'Action'].map(h => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                [...Array(8)].map((_, i) => (
                  <tr key={i}>
                    {[...Array(9)].map((_, j) => (
                      <td key={j}>
                        <div className="h-4 bg-surface-pearl animate-pulse rounded" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-16 text-center">
                    <Clock size={32} className="mx-auto mb-4" style={{ color: 'var(--ink-muted-48)' }} />
                    <p className="typography-body" style={{ color: 'var(--ink-muted-48)' }}>No invoices found</p>
                  </td>
                </tr>
              ) : (
                filtered.map((inv: any) => (
                  <tr key={inv.id} className="transition-colors">
                    <td>
                      <div className="typography-body-strong" style={{ color: 'var(--ink)' }}>{inv.vendor_name}</div>
                    </td>
                    <td>
                      <span className="typography-caption" style={{ color: 'var(--ink-muted-48)' }}>
                        {inv.invoice_number}
                      </span>
                    </td>
                    <td className="typography-body" style={{ color: 'var(--ink)' }}>
                      {formatDate(inv.invoice_date)}
                    </td>
                    <td className="typography-body" style={{ color: 'var(--ink)' }}>
                      {formatDate(inv.statutory_deadline)}
                    </td>
                    <td>
                      <span className={`typography-caption-strong clock-${inv.clock_status}`}>
                        {getDaysLabel(inv.days_remaining, inv.clock_status as ClockStatus)}
                      </span>
                    </td>
                    <td className="typography-body-strong" style={{ color: 'var(--ink)' }}>
                      {formatINR(inv.pending_amount)}
                    </td>
                    <td className="typography-body"
                      style={{ color: inv.disallowed_amount > 0 ? 'var(--vc-red)' : 'var(--ink-muted-48)' }}>
                      {formatINR(inv.disallowed_amount)}
                    </td>
                    <td className="typography-body"
                      style={{ color: inv.accrued_interest > 0 ? 'var(--vc-amber)' : 'var(--ink-muted-48)' }}>
                      {formatINR(inv.accrued_interest)}
                    </td>
                    <td>
                      {inv.priority_score > 0 ? (
                        <div>
                          <div className="typography-caption-strong mb-1" style={{ color: 'var(--ink)' }}>
                            {inv.priority_score.toFixed(4)}
                          </div>
                          <div className="w-16 h-1 rounded-full bg-hairline overflow-hidden" style={{ backgroundColor: 'var(--hairline)' }}>
                            <div className="h-full rounded-full transition-all duration-500"
                              style={{ 
                                width: `${Math.min(100, inv.priority_score * 1000)}%`,
                                backgroundColor: 'var(--vc-amber)' 
                              }} />
                          </div>
                        </div>
                      ) : (
                        <span className="typography-caption" style={{ color: 'var(--ink-muted-48)' }}>—</span>
                      )}
                    </td>
                    {/* Mark as Paid action */}
                    <td>
                      {!inv.is_paid && (inv.clock_status === 'RED' || inv.clock_status === 'AMBER' || inv.clock_status === 'GREEN') ? (
                        <button
                          onClick={() => markPaidMutation.mutate(inv.id)}
                          disabled={markPaidMutation.isPending || markedPaid[inv.id]}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg typography-caption-strong transition-all"
                          style={{
                            backgroundColor: markedPaid[inv.id] ? 'rgba(26,140,60,0.1)' : 'rgba(0,102,204,0.08)',
                            color: markedPaid[inv.id] ? 'var(--vc-green)' : 'var(--primary)',
                            cursor: markPaidMutation.isPending ? 'not-allowed' : 'pointer',
                          }}
                        >
                          {markedPaid[inv.id]
                            ? <><CheckCircle2 size={12} /> Paid</>
                            : markPaidMutation.isPending
                            ? <><Loader2 size={12} className="animate-spin" /> Marking…</>
                            : <><CheckCircle2 size={12} /> Mark Paid</>}
                        </button>
                      ) : (
                        <span className="typography-caption" style={{ color: 'var(--ink-muted-48)' }}>—</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Citation footer */}
      <div className="mt-8 pt-8 border-t" style={{ borderColor: 'var(--hairline)' }}>
        <p className="typography-fine-print" style={{ color: 'var(--ink-muted-48)' }}>
          Statutory reference: {CITATION}. Interest = 3× RBI Bank Rate, monthly compounding (MSMED Act §16). 
          <br/>⚠ Confirm disallowance calculations with your CA before filing.
        </p>
      </div>
    </div>
  );
}
