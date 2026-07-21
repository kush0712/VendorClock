'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Clock, Search, ShoppingBag, LogOut, LayoutDashboard, Upload, Building2, FileText, Download, Scale
} from 'lucide-react';
import { useAuth } from '@/components/providers/AuthProvider';
import { CITATION_SHORT } from '@/lib/constants';

const navItems = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/upload', label: 'Upload' },
  { href: '/invoices', label: 'Invoices' },
  { href: '/vendors', label: 'Vendors' },
  { href: '/exports', label: 'Exports' },
  { href: '/settings', label: 'Alerts' },
];

export default function TopNav() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <div className="w-full flex flex-col fixed top-0 left-0 right-0 z-40">
      {/* Global Nav (True Black, 44px) */}
      <nav 
        className="w-full flex items-center justify-between px-4"
        style={{ height: '44px', backgroundColor: 'var(--surface-black)' }}
      >
        <div className="flex items-center">
          <Link href="/dashboard" className="text-white hover:opacity-80 transition-opacity">
            <Clock size={16} />
          </Link>
        </div>
        
        <div className="flex items-center gap-6">
          {navItems.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className="text-white hover:opacity-80 transition-opacity typography-nav-link"
              style={{ opacity: pathname.startsWith(href) ? 1 : 0.8 }}
            >
              {label}
            </Link>
          ))}
        </div>

        <div className="flex items-center gap-4 text-white">
          <Search size={16} className="cursor-pointer hover:opacity-80 transition-opacity opacity-80" />
          <ShoppingBag size={16} className="cursor-pointer hover:opacity-80 transition-opacity opacity-80" />
        </div>
      </nav>

      {/* Sub Nav Frosted (Parchment, 52px, blur) */}
      {user && (
        <div 
          className="w-full flex items-center justify-between px-6 border-b"
          style={{ 
            height: '52px', 
            backgroundColor: 'rgba(245, 245, 247, 0.8)', 
            backdropFilter: 'saturate(180%) blur(20px)',
            borderColor: 'var(--hairline)'
          }}
        >
          <div className="flex items-center gap-3">
            <span className="typography-tagline" style={{ color: 'var(--ink)' }}>VendorClock</span>
            <span className="citation-badge" style={{ backgroundColor: 'transparent' }}>
              <Scale size={10} />
              {CITATION_SHORT}
            </span>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 mr-4">
              <div 
                className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white"
                style={{ backgroundColor: 'var(--ink-muted-48)' }}
              >
                {user.full_name[0]}
              </div>
              <div className="flex-col hidden sm:flex">
                <span className="typography-caption-strong" style={{ color: 'var(--ink)' }}>{user.full_name}</span>
              </div>
            </div>
            
            <button 
              onClick={logout} 
              className="button-dark-utility flex items-center gap-2"
            >
              Sign Out
              <LogOut size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
