'use client';

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Mail, MessageSquare, CheckCircle2, XCircle, AlertCircle,
  Loader2, Bell, Clock, Info, Send, Scale, Shield
} from 'lucide-react';
import { settingsApi } from '@/lib/api';
import { useAuth } from '@/components/providers/AuthProvider';
import { CITATION } from '@/lib/constants';

type TestState = 'idle' | 'loading' | 'success' | 'error';

function StatusPill({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full typography-caption-strong"
      style={{
        backgroundColor: ok ? 'rgba(26, 140, 60, 0.1)' : 'rgba(230, 130, 10, 0.1)',
        color: ok ? 'var(--vc-green)' : 'var(--vc-amber)',
      }}>
      {ok ? <CheckCircle2 size={12} /> : <AlertCircle size={12} />}
      {label}
    </span>
  );
}

// ─── User view: simple alert preferences ──────────────────────────────────────
function UserAlertPreferences({ status }: { status: any }) {
  const { user } = useAuth();

  return (
    <div className="space-y-6">
      {/* Your alerts card */}
      <div className="store-utility-card">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-full flex items-center justify-center"
            style={{ backgroundColor: 'rgba(0, 102, 204, 0.1)' }}>
            <Bell size={20} style={{ color: 'var(--primary)' }} />
          </div>
          <div>
            <h2 className="typography-body-strong" style={{ color: 'var(--ink)' }}>Your Alert Preferences</h2>
            <p className="typography-caption" style={{ color: 'var(--ink-muted-48)' }}>
              Compliance alerts are sent to your registered email
            </p>
          </div>
        </div>

        <div className="p-4 rounded-[11px] mb-6"
          style={{ backgroundColor: 'var(--surface-pearl)', border: '1px solid var(--hairline)' }}>
          <div className="flex items-center gap-3">
            <Mail size={16} style={{ color: 'var(--primary)' }} />
            <div>
              <p className="typography-caption" style={{ color: 'var(--ink-muted-48)' }}>Alerts sent to</p>
              <p className="typography-body-strong" style={{ color: 'var(--ink)' }}>{user?.email}</p>
            </div>
          </div>
        </div>

        <div className="flex items-start gap-3 p-4 rounded-[11px]"
          style={{ backgroundColor: status?.smtp?.configured ? 'rgba(26, 140, 60, 0.06)' : 'rgba(230, 130, 10, 0.06)',
            border: `1px solid ${status?.smtp?.configured ? 'rgba(26, 140, 60, 0.2)' : 'rgba(230, 130, 10, 0.2)'}` }}>
          {status?.smtp?.configured
            ? <CheckCircle2 size={16} style={{ color: 'var(--vc-green)' }} className="flex-shrink-0 mt-0.5" />
            : <AlertCircle size={16} style={{ color: 'var(--vc-amber)' }} className="flex-shrink-0 mt-0.5" />}
          <p className="typography-caption" style={{ color: 'var(--ink-muted-80)' }}>
            {status?.smtp?.configured
              ? 'Email alerts are active. You will receive daily compliance nudges and weekly CFO reports automatically.'
              : 'Email alerts are not yet active. Contact your VendorClock administrator to configure SMTP.'}
          </p>
        </div>
      </div>

      {/* Schedule card — visible to all */}
      <AlertScheduleCard status={status} />
    </div>
  );
}

// ─── Alert Schedule Card (shared between admin and user views) ────────────────
function AlertScheduleCard({ status }: { status: any }) {
  return (
    <div className="store-utility-card">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-full flex items-center justify-center"
          style={{ backgroundColor: 'rgba(0, 102, 204, 0.1)' }}>
          <Clock size={20} style={{ color: 'var(--primary)' }} />
        </div>
        <div>
          <h2 className="typography-body-strong" style={{ color: 'var(--ink)' }}>Alert Schedule</h2>
          <p className="typography-caption" style={{ color: 'var(--ink-muted-48)' }}>
            Automated compliance alerts
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {[
          { label: 'Daily AP Nudge', time: status?.schedule?.daily_ap_nudge || '09:00 IST', desc: 'Invoices due in ≤7 days or overdue — sent to your email' },
          { label: 'Weekly CFO Report', time: status?.schedule?.weekly_cfo_report || 'Monday 08:00 IST', desc: 'Full exposure summary + Form 3CD draft attached' },
          { label: 'Clock Refresh', time: status?.schedule?.clock_refresh || 'Every hour', desc: 'Recomputes days_remaining for all live invoices' },
          { label: 'Vendor Re-verification', time: status?.schedule?.vendor_reverification || '07:00 IST daily', desc: 'Checks annual Udyam certificate renewal due dates' },
        ].map(({ label, time, desc }) => (
          <div key={label} className="flex items-start justify-between p-4 rounded-[11px]"
            style={{ backgroundColor: 'var(--surface-pearl)', border: '1px solid var(--hairline)' }}>
            <div>
              <p className="typography-caption-strong" style={{ color: 'var(--ink)' }}>{label}</p>
              <p className="typography-caption" style={{ color: 'var(--ink-muted-48)' }}>{desc}</p>
            </div>
            <span className="typography-caption-strong ml-4 flex-shrink-0 px-3 py-1 rounded-full"
              style={{ backgroundColor: 'rgba(0, 102, 204, 0.08)', color: 'var(--primary)' }}>
              {time}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Admin view: full SMTP config, test email, recipient, Slack ───────────────
function AdminSettings({ status, refetch }: { status: any; refetch: () => void }) {
  const [testEmail, setTestEmail] = useState('');
  const [testState, setTestState] = useState<TestState>('idle');
  const [testMsg, setTestMsg] = useState('');
  const [recipientDraft, setRecipientDraft] = useState('');
  const [recipientSaved, setRecipientSaved] = useState(false);

  const updateMutation = useMutation({
    mutationFn: (email: string) => settingsApi.updateRecipient(email),
    onSuccess: () => {
      setRecipientSaved(true);
      refetch();
      setTimeout(() => setRecipientSaved(false), 3000);
    },
  });

  const handleTestEmail = async () => {
    setTestState('loading');
    setTestMsg('');
    try {
      const res = await settingsApi.testEmail(testEmail || undefined);
      setTestMsg(res.message);
      setTestState('success');
      setTimeout(() => setTestState('idle'), 5000);
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      const msg = typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
        ? detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ')
        : 'Test email failed.';
      setTestMsg(msg);
      setTestState('error');
    }
  };

  return (
    <div className="space-y-6">
      {/* Admin badge */}
      <div className="flex items-center gap-2 px-4 py-2 rounded-lg w-fit"
        style={{ backgroundColor: 'rgba(0,102,204,0.06)', border: '1px solid rgba(0,102,204,0.15)' }}>
        <Shield size={14} style={{ color: 'var(--primary)' }} />
        <span className="typography-caption-strong" style={{ color: 'var(--primary)' }}>
          Admin — System Email Configuration
        </span>
      </div>

      {/* SMTP Status Card */}
      <div className="store-utility-card">
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full flex items-center justify-center"
              style={{ backgroundColor: status.smtp.configured ? 'rgba(26, 140, 60, 0.1)' : 'rgba(230, 130, 10, 0.1)' }}>
              <Mail size={20} style={{ color: status.smtp.configured ? 'var(--vc-green)' : 'var(--vc-amber)' }} />
            </div>
            <div>
              <h2 className="typography-body-strong" style={{ color: 'var(--ink)' }}>SMTP Email (Gmail)</h2>
              <p className="typography-caption" style={{ color: 'var(--ink-muted-48)' }}>
                System-wide sender — all users' alerts are sent from this address
              </p>
            </div>
          </div>
          <StatusPill ok={status.smtp.configured} label={status.smtp.configured ? 'Configured' : 'Not Configured'} />
        </div>

        {!status.smtp.configured && (
          <div className="flex items-start gap-3 p-4 rounded-[11px] mb-6"
            style={{ backgroundColor: 'rgba(230, 130, 10, 0.06)', border: '1px solid rgba(230, 130, 10, 0.2)' }}>
            <AlertCircle size={16} style={{ color: 'var(--vc-amber)' }} className="flex-shrink-0 mt-0.5" />
            <div className="typography-caption" style={{ color: 'var(--ink-muted-80)' }}>
              <p className="typography-caption-strong mb-2" style={{ color: 'var(--ink)' }}>
                Set up Gmail SMTP in <code className="px-1 rounded text-xs" style={{ backgroundColor: 'var(--surface-pearl)' }}>backend/.env</code>:
              </p>
              <pre className="p-3 rounded-lg overflow-x-auto text-xs leading-relaxed"
                style={{ backgroundColor: 'var(--surface-pearl)', color: 'var(--ink-muted-80)' }}>
{`SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=you@gmail.com
SMTP_PASSWORD=your-16-char-app-password
SMTP_FROM_NAME=VendorClock
ALERT_DEFAULT_RECIPIENT=cfo@yourcompany.com`}
              </pre>
              <p className="mt-2">
                <span className="typography-caption-strong" style={{ color: 'var(--ink)' }}>Gmail App Password: </span>
                Enable 2FA on your Google account → myaccount.google.com → Security → App Passwords → Generate.
              </p>
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-4 mb-6">
          {[
            ['SMTP Host', status.smtp.host],
            ['SMTP Port', String(status.smtp.port)],
            ['From Name', status.smtp.from_name],
            ['Username', status.smtp.configured ? '✓ Set' : '✗ Not set'],
          ].map(([label, value]) => (
            <div key={label} className="p-3 rounded-[11px]" style={{ backgroundColor: 'var(--surface-pearl)', border: '1px solid var(--hairline)' }}>
              <p className="typography-caption" style={{ color: 'var(--ink-muted-48)' }}>{label}</p>
              <p className="typography-caption-strong" style={{ color: 'var(--ink)' }}>{value}</p>
            </div>
          ))}
        </div>

        {/* Alert Recipient */}
        <div className="mb-6">
          <label className="block typography-caption-strong mb-2" style={{ color: 'var(--ink)' }}>
            Default Alert Recipient (fallback)
          </label>
          <div className="flex gap-3">
            <input
              type="email"
              value={recipientDraft || status.alert_recipient.email}
              onChange={e => setRecipientDraft(e.target.value)}
              placeholder="cfo@yourcompany.com"
              className="flex-1 px-4 py-2.5 rounded-lg typography-body"
              style={{ backgroundColor: 'var(--canvas)', border: '1px solid var(--hairline)', color: 'var(--ink)' }}
              onFocus={e => e.target.style.borderColor = 'var(--primary)'}
              onBlur={e => e.target.style.borderColor = 'var(--hairline)'}
            />
            <button
              onClick={() => updateMutation.mutate(recipientDraft || status.alert_recipient.email)}
              disabled={updateMutation.isPending}
              className="button-secondary-pill px-5 py-2.5 text-sm"
            >
              {recipientSaved ? <><CheckCircle2 size={14} className="mr-1.5" />Saved</> : 'Save'}
            </button>
          </div>
          <p className="typography-caption mt-2" style={{ color: 'var(--ink-muted-48)' }}>
            Each user receives alerts at their registered email. This is the fallback for system-level notifications.
          </p>
        </div>

        {/* Test Email */}
        <div className="pt-5 border-t" style={{ borderColor: 'var(--hairline)' }}>
          <p className="typography-caption-strong mb-3" style={{ color: 'var(--ink)' }}>Send Test Email</p>
          <div className="flex gap-3">
            <input
              type="email"
              value={testEmail}
              onChange={e => setTestEmail(e.target.value)}
              placeholder="Override recipient (optional)"
              className="flex-1 px-4 py-2.5 rounded-lg typography-body"
              style={{ backgroundColor: 'var(--canvas)', border: '1px solid var(--hairline)', color: 'var(--ink)' }}
              onFocus={e => e.target.style.borderColor = 'var(--primary)'}
              onBlur={e => e.target.style.borderColor = 'var(--hairline)'}
            />
            <button
              onClick={handleTestEmail}
              disabled={testState === 'loading'}
              className="button-primary flex items-center gap-2"
              style={testState === 'success' ? { backgroundColor: 'var(--vc-green)' } :
                testState === 'error' ? { backgroundColor: 'var(--vc-red)' } : {}}
            >
              {testState === 'loading' && <Loader2 size={14} className="animate-spin" />}
              {testState === 'success' && <CheckCircle2 size={14} />}
              {testState === 'error' && <XCircle size={14} />}
              {testState === 'idle' && <Send size={14} />}
              {testState === 'loading' ? 'Sending…' : testState === 'success' ? 'Sent!' : testState === 'error' ? 'Failed' : 'Send Test'}
            </button>
          </div>
          {testMsg && (
            <div className="mt-3 flex items-start gap-2 p-3 rounded-lg"
              style={{
                backgroundColor: testState === 'success' ? 'rgba(26, 140, 60, 0.06)' : 'rgba(204, 34, 0, 0.06)',
                border: `1px solid ${testState === 'success' ? 'rgba(26, 140, 60, 0.2)' : 'rgba(204, 34, 0, 0.2)'}`,
              }}>
              {testState === 'success'
                ? <CheckCircle2 size={14} style={{ color: 'var(--vc-green)' }} className="flex-shrink-0 mt-0.5" />
                : <XCircle size={14} style={{ color: 'var(--vc-red)' }} className="flex-shrink-0 mt-0.5" />}
              <span className="typography-caption" style={{ color: 'var(--ink-muted-80)' }}>{testMsg}</span>
            </div>
          )}
        </div>
      </div>

      {/* Slack Status Card */}
      <div className="store-utility-card">
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full flex items-center justify-center"
              style={{ backgroundColor: status.slack.configured ? 'rgba(26, 140, 60, 0.1)' : 'rgba(230, 130, 10, 0.1)' }}>
              <MessageSquare size={20} style={{ color: status.slack.configured ? 'var(--vc-green)' : 'var(--vc-amber)' }} />
            </div>
            <div>
              <h2 className="typography-body-strong" style={{ color: 'var(--ink)' }}>Slack Alerts (Free Tier)</h2>
              <p className="typography-caption" style={{ color: 'var(--ink-muted-48)' }}>
                Channel notifications alongside email
              </p>
            </div>
          </div>
          <StatusPill ok={status.slack.configured} label={status.slack.configured ? 'Configured' : 'Not Configured'} />
        </div>

        {!status.slack.configured && (
          <div className="flex items-start gap-3 p-4 rounded-[11px]"
            style={{ backgroundColor: 'rgba(230, 130, 10, 0.06)', border: '1px solid rgba(230, 130, 10, 0.2)' }}>
            <AlertCircle size={16} style={{ color: 'var(--vc-amber)' }} className="flex-shrink-0 mt-0.5" />
            <div className="typography-caption" style={{ color: 'var(--ink-muted-80)' }}>
              <p className="typography-caption-strong mb-2" style={{ color: 'var(--ink)' }}>
                Set up Slack in <code className="px-1 rounded text-xs" style={{ backgroundColor: 'var(--surface-pearl)' }}>backend/.env</code>:
              </p>
              <pre className="p-3 rounded-lg text-xs leading-relaxed"
                style={{ backgroundColor: 'var(--surface-pearl)', color: 'var(--ink-muted-80)' }}>
{`SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T.../B.../...`}
              </pre>
              <p className="mt-2">
                Go to api.slack.com/apps → Create App → Incoming Webhooks → Activate → Add to Channel → Copy URL.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Schedule card */}
      <AlertScheduleCard status={status} />

      {/* Celery note — admin only */}
      <div className="flex items-start gap-2 p-4 rounded-[11px]"
        style={{ backgroundColor: 'var(--canvas)', border: '1px solid var(--hairline)' }}>
        <Info size={14} style={{ color: 'var(--ink-muted-48)' }} className="flex-shrink-0 mt-0.5" />
        <p className="typography-caption" style={{ color: 'var(--ink-muted-48)' }}>
          Celery Beat requires Redis. Start with:{' '}
          <code className="px-1 rounded text-xs" style={{ backgroundColor: 'var(--surface-pearl)' }}>
            celery -A app.tasks.celery_app beat --loglevel=info
          </code>
          {' '}in the <code className="px-1 rounded text-xs" style={{ backgroundColor: 'var(--surface-pearl)' }}>backend/</code> directory.
        </p>
      </div>
    </div>
  );
}

// ─── Main page component ──────────────────────────────────────────────────────
export default function SettingsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  const { data: status, isLoading, refetch } = useQuery({
    queryKey: ['settings-status'],
    queryFn: settingsApi.getStatus,
    retry: false,
  });

  return (
    <div className="p-8 max-w-4xl mx-auto" style={{ backgroundColor: 'var(--canvas-parchment)' }}>
      {/* Header */}
      <div className="mb-10">
        <h1 className="typography-display-lg mb-2" style={{ color: 'var(--ink)' }}>
          {isAdmin ? 'Alerts & Settings' : 'Alert Preferences'}
        </h1>
        <p className="typography-lead" style={{ color: 'var(--ink-muted-80)' }}>
          {isAdmin
            ? 'System email configuration and alert management'
            : 'Your compliance alert schedule and delivery settings'}
        </p>
      </div>

      {/* Loading skeleton */}
      {isLoading && (
        <div className="space-y-6">
          {[1, 2, 3].map(i => (
            <div key={i} className="store-utility-card h-40 animate-pulse" style={{ backgroundColor: 'var(--surface-pearl)' }} />
          ))}
        </div>
      )}

      {/* Role-based content */}
      {status && (
        <>
          {isAdmin
            ? <AdminSettings status={status} refetch={refetch} />
            : <UserAlertPreferences status={status} />}

          {/* Citation footer */}
          <div className="mt-8 pt-6 border-t" style={{ borderColor: 'var(--hairline)' }}>
            <p className="typography-fine-print flex items-center gap-2" style={{ color: 'var(--ink-muted-48)' }}>
              <Scale size={11} />
              All alerts cite: {CITATION}. Alerts are internal only — never vendor-facing per spec.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
