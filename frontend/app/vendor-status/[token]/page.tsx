'use client';

import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { vendorsApi } from '@/lib/api';
import { CITATION } from '@/lib/constants';
import { Clock, CheckCircle2, AlertCircle, Scale } from 'lucide-react';

export default function VendorStatusPage() {
  const { token } = useParams<{ token: string }>();

  const { data, isLoading, error } = useQuery({
    queryKey: ['vendor-declaration', token],
    queryFn: () => vendorsApi.getDeclaration(token),
    retry: false,
  });

  return (
    <div className="min-h-screen flex items-center justify-center p-6"
      style={{ background: 'hsl(222 47% 6%)' }}>
      <div className="max-w-lg w-full">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"
            style={{ background: 'linear-gradient(135deg, hsl(217 91% 55%), hsl(260 80% 60%))' }}>
            <Clock size={28} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">VendorClock</h1>
          <p className="text-sm mt-1" style={{ color: 'hsl(215 16% 50%)' }}>
            Vendor MSME Status Portal
          </p>
        </div>

        <div className="glass-card rounded-2xl p-8">
          {isLoading && (
            <div className="text-center py-8">
              <div className="animate-spin w-8 h-8 border-2 rounded-full mx-auto mb-3"
                style={{ borderColor: 'hsl(217 91% 60%)', borderTopColor: 'transparent' }} />
              <p style={{ color: 'hsl(215 16% 55%)' }}>Loading...</p>
            </div>
          )}

          {error && (
            <div className="text-center py-8">
              <AlertCircle size={40} className="mx-auto mb-3" style={{ color: 'hsl(0 84% 60%)' }} />
              <h2 className="text-lg font-bold text-white mb-2">Link not found</h2>
              <p className="text-sm" style={{ color: 'hsl(215 16% 55%)' }}>
                This declaration link is invalid or has expired. 
                Please contact your buyer for a new link.
              </p>
            </div>
          )}

          {data && (
            <div>
              <div className="flex items-center gap-3 mb-6">
                {data.certificate_uploaded ? (
                  <CheckCircle2 size={24} style={{ color: 'hsl(142 76% 50%)' }} />
                ) : (
                  <Clock size={24} style={{ color: 'hsl(38 92% 55%)' }} />
                )}
                <div>
                  <h2 className="font-bold text-white">{data.vendor_name}</h2>
                  <p className="text-xs" style={{ color: 'hsl(215 16% 50%)' }}>
                    {data.certificate_uploaded
                      ? 'Your Udyam certificate is on file and verified.'
                      : 'Udyam certificate pending upload.'}
                  </p>
                </div>
              </div>

              <div className="p-4 rounded-xl mb-6"
                style={{ background: 'hsl(222 47% 13%)', border: '1px solid hsl(222 47% 20%)' }}>
                <p className="text-xs font-medium mb-1" style={{ color: 'hsl(215 16% 50%)' }}>
                  Current Status
                </p>
                <span className={`text-sm font-semibold ${
                  data.status === 'ELIGIBLE' ? 'clock-green' :
                  data.status === 'PENDING_DECLARATION' ? 'clock-amber' : 'clock-excluded'
                } px-3 py-1 rounded-full`}>
                  {data.status.replace(/_/g, ' ')}
                </span>
              </div>

              <div className="text-xs p-3 rounded-lg"
                style={{
                  background: 'hsl(217 91% 60% / 0.08)',
                  border: '1px solid hsl(217 91% 60% / 0.2)',
                  color: 'hsl(215 16% 60%)',
                }}>
                <div className="flex items-start gap-2">
                  <Scale size={12} className="flex-shrink-0 mt-0.5" style={{ color: 'hsl(217 91% 60%)' }} />
                  <span>
                    Your buyer is using VendorClock to comply with <strong className="text-white">{CITATION}</strong>. 
                    Your MSME registration status determines whether statutory payment timelines apply.
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>

        <p className="text-center text-xs mt-6" style={{ color: 'hsl(215 16% 35%)' }}>
          This is a read-only status page. For queries, contact your buyer's accounts team.
        </p>
      </div>
    </div>
  );
}
