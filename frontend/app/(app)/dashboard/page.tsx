'use client';

import { useQuery } from '@tanstack/react-query';
import {
  AlertTriangle, TrendingDown, DollarSign, Building2, ChevronRight, Scale,
  Upload, ArrowRight
} from 'lucide-react';
import { dashboardApi } from '@/lib/api';
import { formatINR, getDaysLabel, CITATION } from '@/lib/constants';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';
import Link from 'next/link';
import { useState } from 'react';

function MetricCard({
  label, value, sub, color, icon: Icon
}: {
  label: string; value: string; sub?: string; color: string; icon: React.ElementType
}) {
  return (
    <div className="store-utility-card">
      <div className="flex items-start justify-between mb-4">
        <div className="w-10 h-10 rounded-full flex items-center justify-center"
          style={{
            backgroundColor: color === 'red' ? 'rgba(204, 0, 0, 0.1)' :
              color === 'amber' ? 'rgba(230, 153, 0, 0.1)' :
                color === 'green' ? 'rgba(0, 153, 51, 0.1)' : 'rgba(0, 102, 204, 0.1)',
            color: color === 'red' ? 'var(--vc-red)' :
              color === 'amber' ? 'var(--vc-amber)' :
                color === 'green' ? 'var(--vc-green)' : 'var(--primary)'
          }}>
          <Icon size={20} />
        </div>
      </div>
      <div className="typography-display-md" style={{ color: 'var(--ink)' }}>{value}</div>
      <div className="typography-body-strong mb-1" style={{ color: 'var(--ink)' }}>{label}</div>
      {sub && <div className="typography-caption" style={{ color: 'var(--ink-muted-48)' }}>{sub}</div>}
    </div>
  );
}

function ClockDonut({ invoices }: { invoices: { red: number; amber: number; green: number } }) {
  const data = [
    { name: 'Overdue', value: invoices.red, color: 'var(--vc-red)' },
    { name: 'Due Soon', value: invoices.amber, color: 'var(--vc-amber)' },
    { name: 'Safe', value: invoices.green, color: 'var(--vc-green)' },
  ].filter(d => d.value > 0);

  const total = invoices.red + invoices.amber + invoices.green;

  if (total === 0) {
    return (
      <div className="flex items-center justify-center h-40">
        <p className="typography-body" style={{ color: 'var(--ink-muted-48)' }}>No eligible invoices yet</p>
      </div>
    );
  }

  return (
    <div className="relative">
      <ResponsiveContainer width="100%" height={220}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={70}
            outerRadius={100}
            paddingAngle={2}
            dataKey="value"
          >
            {data.map((entry, index) => (
              <Cell key={index} fill={`var(${entry.color.split('var(')[1].split(')')[0]})`} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--canvas)',
              border: '1px solid var(--hairline)',
              borderRadius: '11px',
              color: 'var(--ink)',
              fontFamily: 'SF Pro Text',
              fontSize: '14px'
            }}
            itemStyle={{ color: 'var(--ink)' }}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
        <div className="typography-display-lg" style={{ color: 'var(--ink)' }}>{total}</div>
        <div className="typography-caption-strong" style={{ color: 'var(--ink-muted-48)' }}>invoices</div>
      </div>
      <div className="flex justify-center gap-6 mt-4">
        {data.map(d => (
          <div key={d.name} className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: d.color }} />
            <span className="typography-caption" style={{ color: 'var(--ink)' }}>{d.name}: {d.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<'overview' | 'by-vendor'>('overview');

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: dashboardApi.getSummary,
    refetchInterval: 60_000,
  });

  const { data: queue, isLoading: queueLoading } = useQuery({
    queryKey: ['priority-queue'],
    queryFn: dashboardApi.getPriorityQueue,
    refetchInterval: 60_000,
  });

  const { data: byVendor, isLoading: byVendorLoading } = useQuery({
    queryKey: ['dashboard-by-vendor'],
    queryFn: dashboardApi.getByVendor,
    refetchInterval: 60_000,
    enabled: activeTab === 'by-vendor',
  });

  // Onboarding empty state — no vendors and no invoices yet
  const isEmpty = !summaryLoading
    && (summary?.vendors?.total ?? 0) === 0
    && (summary?.invoices?.total ?? 0) === 0;

  return (
    <div className="p-8 max-w-[1440px] mx-auto bg-canvas-parchment">
      {/* Header */}
      <div className="mb-10">
        <h1 className="typography-display-lg mb-2" style={{ color: 'var(--ink)' }}>CFO Dashboard</h1>
        <p className="typography-lead" style={{ color: 'var(--ink-muted-80)' }}>
          Live compliance exposure and cash-priority queue
          {summary?.ca_note && (
            <span className="ml-3 typography-caption-strong" style={{ color: 'var(--vc-amber)' }}>
              ⚠ {summary.ca_note}
            </span>
          )}
        </p>
      </div>

      {/* Onboarding empty state */}
      {isEmpty && (
        <div className="store-utility-card text-center py-20 mb-10">
          <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-6"
            style={{ backgroundColor: 'rgba(0,102,204,0.08)' }}>
            <Upload size={32} style={{ color: 'var(--primary)' }} />
          </div>
          <h2 className="typography-tagline mb-3" style={{ color: 'var(--ink)' }}>Welcome to VendorClock</h2>
          <p className="typography-body max-w-md mx-auto mb-8" style={{ color: 'var(--ink-muted-80)' }}>
            Upload your purchase register CSV to start tracking MSE invoice compliance.
            Your first vendor with ELIGIBLE status will activate the compliance clock.
          </p>
          <Link href="/upload" className="button-primary inline-flex items-center gap-2">
            Upload Purchase Register <ArrowRight size={16} />
          </Link>
          <p className="typography-caption mt-6" style={{ color: 'var(--ink-muted-48)' }}>
            {CITATION}
          </p>
        </div>
      )}

      {/* Tab switcher */}
      {!isEmpty && (
        <div className="flex gap-1 mb-8 bg-canvas rounded-full p-1 border w-fit" style={{ borderColor: 'var(--hairline)' }}>
          {(['overview', 'by-vendor'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className="px-5 py-2 rounded-full typography-caption-strong transition-all"
              style={{
                backgroundColor: activeTab === tab ? 'var(--ink)' : 'transparent',
                color: activeTab === tab ? '#fff' : 'var(--ink-muted-48)',
              }}
            >
              {tab === 'overview' ? 'Overview' : 'By Vendor'}
            </button>
          ))}
        </div>
      )}

      {/* ─── OVERVIEW TAB ─── */}
      {activeTab === 'overview' && !isEmpty && (
        <>
          {/* Metric cards */}
          {summaryLoading ? (
            <div className="grid grid-cols-4 gap-6 mb-12">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="store-utility-card h-40 animate-pulse bg-surface-pearl" />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
              <MetricCard
                label="Total ₹ at Risk"
                value={formatINR(summary?.exposure?.total_at_risk)}
                sub="Disallowed principal + interest"
                color="red"
                icon={AlertTriangle}
              />
              <MetricCard
                label="Tax Cost of Disallowance"
                value={formatINR(summary?.exposure?.total_tax_cost)}
                sub={`Effective rate: ${((summary?.effective_tax_rate_used || 0.2522) * 100).toFixed(1)}%`}
                color="amber"
                icon={TrendingDown}
              />
              <MetricCard
                label="Accrued Interest"
                value={formatINR(summary?.exposure?.total_interest)}
                sub={`${summary?.rbi_bank_rate_percent}% × 3 = ${((summary?.rbi_bank_rate_percent || 6.5) * 3).toFixed(1)}% p.a.`}
                color="amber"
                icon={DollarSign}
              />
              <MetricCard
                label="Eligible Vendors"
                value={summary?.vendors?.eligible?.toString() || '0'}
                sub={`${summary?.vendors?.pending_declaration || 0} pending declaration`}
                color="blue"
                icon={Building2}
              />
            </div>
          )}

          {/* Main content grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Clock status donut */}
            <div className="store-utility-card">
              <h2 className="typography-body-strong mb-6" style={{ color: 'var(--ink)' }}>
                Invoice Clock Status
              </h2>
              {summaryLoading ? (
                <div className="h-48 animate-pulse bg-surface-pearl rounded-lg" />
              ) : (
                <ClockDonut invoices={summary?.invoices || { red: 0, amber: 0, green: 0 }} />
              )}
            </div>

            {/* Priority queue */}
            <div className="store-utility-card lg:col-span-2">
              <div className="flex items-center justify-between mb-6">
                <h2 className="typography-body-strong" style={{ color: 'var(--ink)' }}>
                  Cash-Priority Queue
                </h2>
                <Link href="/invoices" className="text-link typography-caption-strong flex items-center">
                  View all <ChevronRight size={14} className="ml-1" />
                </Link>
              </div>

              {queueLoading ? (
                <div className="space-y-4">
                  {[...Array(5)].map((_, i) => <div key={i} className="h-16 animate-pulse bg-surface-pearl rounded-lg" />)}
                </div>
              ) : (
                <div className="space-y-3 max-h-[300px] overflow-y-auto pr-2">
                  {queue?.items?.slice(0, 10).map((item: any, idx: number) => (
                    <div key={item.invoice_id}
                      className="flex items-center gap-4 px-4 py-3 rounded-[11px] transition-colors"
                      style={{ backgroundColor: 'var(--surface-pearl)' }}>
                      <span className="w-5 typography-caption-strong" style={{ color: 'var(--ink-muted-48)' }}>
                        {idx + 1}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3">
                          <span className="typography-body-strong truncate" style={{ color: 'var(--ink)' }}>{item.vendor_name}</span>
                          <span className={`typography-caption-strong clock-${item.clock_status}`}>
                            {getDaysLabel(item.days_remaining, item.clock_status)}
                          </span>
                        </div>
                        <span className="typography-caption" style={{ color: 'var(--ink-muted-48)' }}>{item.invoice_number}</span>
                      </div>
                      <div className="text-right">
                        <div className="typography-body-strong" style={{ color: 'var(--ink)' }}>{formatINR(item.pending_amount)}</div>
                        <div className="typography-caption" style={{ color: 'var(--ink-muted-48)' }}>
                          Score: {item.priority_score?.toFixed(4)}
                        </div>
                      </div>
                    </div>
                  ))}
                  {!queue?.items?.length && (
                    <div className="text-center py-12">
                      <p className="typography-body" style={{ color: 'var(--ink-muted-48)' }}>No at-risk invoices — all clear!</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* GST note */}
          {queue?.gst_base_note && (
            <div className="mt-8 px-6 py-4 rounded-[11px] bg-canvas border"
              style={{ borderColor: 'var(--hairline)' }}>
              <p className="typography-caption" style={{ color: 'var(--ink-muted-80)' }}>
                <span style={{ color: 'var(--vc-amber)' }}>⚠</span> {queue.gst_base_note}
              </p>
            </div>
          )}
        </>
      )}



      {/* ─── BY VENDOR TAB ─── */}
      {activeTab === 'by-vendor' && (
        <div className="store-utility-card p-0 overflow-hidden">
          <table className="data-table">
            <thead>
              <tr>
                {['Vendor', 'Status', 'Invoices', '₹ at Risk', 'Disallowed', 'Interest', 'Overdue Days'].map(h => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {byVendorLoading ? (
                [...Array(6)].map((_, i) => (
                  <tr key={i}>{[...Array(7)].map((_, j) => (
                    <td key={j}><div className="h-4 bg-surface-pearl animate-pulse rounded" /></td>
                  ))}</tr>
                ))
              ) : (byVendor?.items || []).length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-16 text-center">
                    <p className="typography-body" style={{ color: 'var(--ink-muted-48)' }}>No vendor data yet</p>
                  </td>
                </tr>
              ) : (
                (byVendor?.items || []).map((v: any) => (
                  <tr key={v.vendor_id}>
                    <td>
                      <div className="typography-body-strong" style={{ color: 'var(--ink)' }}>{v.vendor_name}</div>
                      {v.udyam_number && <div className="typography-caption" style={{ color: 'var(--ink-muted-48)' }}>{v.udyam_number}</div>}
                    </td>
                    <td>
                      <span className="typography-caption-strong px-2 py-1 rounded-full text-white"
                        style={{ backgroundColor: v.vendor_status === 'ELIGIBLE' ? 'var(--vc-green)' : 'var(--vc-amber)', fontSize: '11px' }}>
                        {v.vendor_status?.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="typography-body" style={{ color: 'var(--ink)' }}>{v.invoice_count}</td>
                    <td className="typography-body-strong" style={{ color: v.total_at_risk > 0 ? 'var(--vc-red)' : 'var(--ink)' }}>
                      {formatINR(v.total_at_risk)}
                    </td>
                    <td className="typography-body" style={{ color: v.total_disallowed > 0 ? 'var(--vc-red)' : 'var(--ink-muted-48)' }}>
                      {formatINR(v.total_disallowed)}
                    </td>
                    <td className="typography-body" style={{ color: v.total_interest > 0 ? 'var(--vc-amber)' : 'var(--ink-muted-48)' }}>
                      {formatINR(v.total_interest)}
                    </td>
                    <td className="typography-body" style={{ color: v.max_days_overdue > 0 ? 'var(--vc-red)' : 'var(--ink-muted-48)' }}>
                      {v.max_days_overdue > 0 ? `${v.max_days_overdue}d` : '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
