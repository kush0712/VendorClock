'use client';

import { useState, useEffect } from 'react';
import {
  Clock, Scale, Building2, User, Mail, Lock,
  CheckCircle2, XCircle, ArrowRight
} from 'lucide-react';
import { useAuth } from '@/components/providers/AuthProvider';
import { useRouter } from 'next/navigation';
import { CITATION } from '@/lib/constants';

function getPasswordStrength(pw: string): { score: number; label: string; color: string } {
  if (!pw) return { score: 0, label: '', color: '' };
  let score = 0;
  if (pw.length >= 8) score++;
  if (pw.length >= 12) score++;
  if (/[A-Z]/.test(pw)) score++;
  if (/\d/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;

  if (score <= 1) return { score, label: 'Weak', color: 'var(--vc-red)' };
  if (score <= 2) return { score, label: 'Fair', color: 'var(--vc-amber)' };
  if (score <= 3) return { score, label: 'Good', color: 'var(--vc-amber)' };
  return { score, label: 'Strong', color: 'var(--vc-green)' };
}

function InputField({
  id, label, type, value, onChange, placeholder, icon: Icon, required = true, autoComplete
}: {
  id: string; label: string; type: string; value: string;
  onChange: (v: string) => void; placeholder: string;
  icon: React.ElementType; required?: boolean;
  autoComplete?: string;
}) {
  return (
    <div className="mb-4">
      <label htmlFor={id} className="block typography-caption-strong mb-2" style={{ color: 'var(--ink)' }}>
        {label}
      </label>
      <div className="relative">
        <span className="absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: 'var(--ink-muted-48)' }}>
          <Icon size={16} />
        </span>
        <input
          id={id}
          type={type}
          value={value}
          onChange={e => onChange(e.target.value)}
          required={required}
          placeholder={placeholder}
          autoComplete={autoComplete}
          className="w-full pl-11 pr-4 py-3 bg-canvas text-ink rounded-lg border focus:outline-none transition-colors typography-body"
          style={{ borderColor: 'var(--hairline)' }}
          onFocus={e => {
            e.target.style.borderColor = 'var(--primary)';
            e.target.style.boxShadow = '0 0 0 3px rgba(0, 102, 204, 0.15)';
          }}
          onBlur={e => {
            e.target.style.borderColor = 'var(--hairline)';
            e.target.style.boxShadow = 'none';
          }}
        />
      </div>
    </div>
  );
}

export default function LoginPage() {
  const { login, register, user, isLoading } = useAuth();
  const router = useRouter();

  const [tab, setTab] = useState<'login' | 'register'>('login');
  
  // Login State
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState('');

  // Register State
  const [regCompany, setRegCompany] = useState('');
  const [regName, setRegName] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regConfirm, setRegConfirm] = useState('');
  const [regLoading, setRegLoading] = useState(false);
  const [regError, setRegError] = useState('');
  const [regSuccess, setRegSuccess] = useState(false);

  const pwStrength = getPasswordStrength(regPassword);
  const pwMatch = regPassword && regConfirm && regPassword === regConfirm;
  const pwMismatch = regConfirm && regPassword !== regConfirm;

  useEffect(() => {
    if (!isLoading && user) {
      router.replace('/dashboard');
    }
  }, [user, isLoading, router]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginLoading(true);
    setLoginError('');
    try {
      await login(loginEmail, loginPassword);
      router.push('/dashboard');
    } catch (err: unknown) {
      setLoginError(err instanceof Error ? err.message : 'Invalid email or password.');
    } finally {
      setLoginLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setRegError('');
    
    if (regPassword.length < 8) {
      setRegError('Password must be at least 8 characters long.');
      return;
    }
    if (!/\d/.test(regPassword)) {
      setRegError('Password must contain at least one digit.');
      return;
    }
    if (regPassword !== regConfirm) {
      setRegError('Passwords do not match.');
      return;
    }

    setRegLoading(true);
    try {
      await register({
        email: regEmail,
        password: regPassword,
        full_name: regName,
        company_name: regCompany,
      });
      setRegSuccess(true);
      setTimeout(() => router.push('/dashboard'), 800);
    } catch (err: unknown) {
      setRegError(err instanceof Error ? err.message : 'Registration failed.');
    } finally {
      setRegLoading(false);
    }
  };

  if (isLoading) return null;

  return (
    <div className="min-h-screen flex flex-col bg-canvas-parchment font-sf-display">
      
      {/* Global Nav minimal version for Login */}
      <nav className="w-full flex items-center justify-center px-4" style={{ height: '44px', backgroundColor: 'var(--surface-black)' }}>
        <Clock size={16} className="text-white opacity-80" />
      </nav>

      {/* Product Tile Style Login */}
      <div className="flex-1 flex flex-col items-center justify-center py-16 px-4">
        
        <div className="text-center mb-12">
          <h1 className="typography-hero-display mb-2" style={{ color: 'var(--ink)' }}>VendorClock</h1>
          <p className="typography-lead" style={{ color: 'var(--ink-muted-80)' }}>MSE Compliance & Cash Priority</p>
          <div className="mt-4 flex justify-center">
            <span className="citation-badge">
              <Scale size={10} />
              {CITATION}
            </span>
          </div>
        </div>

        <div className="w-full max-w-md bg-canvas rounded-[18px] border overflow-hidden" style={{ borderColor: 'var(--hairline)' }}>
          
          <div className="flex border-b" style={{ borderColor: 'var(--hairline)' }}>
            {(['login', 'register'] as const).map(t => (
              <button
                key={t}
                onClick={() => { setTab(t); setLoginError(''); setRegError(''); }}
                className="flex-1 py-4 typography-body-strong transition-colors relative"
                style={{
                  color: tab === t ? 'var(--ink)' : 'var(--ink-muted-48)',
                  backgroundColor: tab === t ? 'var(--canvas)' : 'var(--canvas-parchment)'
                }}
              >
                {t === 'login' ? 'Sign In' : 'Create Account'}
                {tab === t && (
                  <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary" style={{ backgroundColor: 'var(--primary)' }} />
                )}
              </button>
            ))}
          </div>

          <div className="p-8">
            {tab === 'login' ? (
              <form onSubmit={handleLogin}>
                <InputField id="login-email" label="Work Email" type="email" value={loginEmail} onChange={setLoginEmail} placeholder="cfo@company.com" icon={Mail} autoComplete="email" />
                <InputField id="login-password" label="Password" type="password" value={loginPassword} onChange={setLoginPassword} placeholder="••••••••" icon={Lock} autoComplete="current-password" />
                
                {loginError && (
                  <div className="mb-4 text-sm flex items-center gap-2 p-3 rounded-lg" style={{ backgroundColor: 'rgba(204, 0, 0, 0.05)', color: 'var(--vc-red)' }}>
                    <XCircle size={14} /> {loginError}
                  </div>
                )}
                
                <button type="submit" disabled={loginLoading} className="button-primary w-full mt-4">
                  {loginLoading ? 'Signing in...' : <>Sign in <ArrowRight size={14} className="ml-2" /></>}
                </button>
              </form>
            ) : (
              <form onSubmit={handleRegister}>
                {regSuccess ? (
                  <div className="py-12 text-center">
                    <CheckCircle2 size={48} className="mx-auto mb-4" style={{ color: 'var(--vc-green)' }} />
                    <h3 className="typography-display-md mb-2" style={{ color: 'var(--ink)' }}>Account Created</h3>
                    <p className="typography-body" style={{ color: 'var(--ink-muted-48)' }}>Redirecting to dashboard...</p>
                  </div>
                ) : (
                  <>
                    <InputField id="reg-company" label="Company Name" type="text" value={regCompany} onChange={setRegCompany} placeholder="Acme Pvt Ltd" icon={Building2} />
                    <InputField id="reg-name" label="Your Name" type="text" value={regName} onChange={setRegName} placeholder="Rajesh Kumar" icon={User} />
                    <InputField id="reg-email" label="Work Email" type="email" value={regEmail} onChange={setRegEmail} placeholder="you@company.com" icon={Mail} />
                    
                    <InputField id="reg-password" label="Password" type="password" value={regPassword} onChange={setRegPassword} placeholder="Min 8 chars, 1 number" icon={Lock} />
                    {regPassword && (
                      <div className="mb-4">
                        <div className="flex gap-1 mb-1">
                          {[1, 2, 3, 4].map(i => (
                            <div key={i} className="h-1 flex-1 rounded-full transition-all" style={{ backgroundColor: i <= pwStrength.score ? pwStrength.color : 'var(--hairline)' }} />
                          ))}
                        </div>
                        <p className="typography-caption" style={{ color: pwStrength.color }}>{pwStrength.label}</p>
                      </div>
                    )}
                    
                    <InputField id="reg-confirm" label="Confirm Password" type="password" value={regConfirm} onChange={setRegConfirm} placeholder="Re-enter password" icon={Lock} />
                    {regConfirm && (
                      <p className="typography-caption mb-4 flex items-center gap-1" style={{ color: pwMatch ? 'var(--vc-green)' : 'var(--vc-red)' }}>
                        {pwMatch ? <><CheckCircle2 size={12} /> Passwords match</> : pwMismatch ? <><XCircle size={12} /> Passwords do not match</> : null}
                      </p>
                    )}

                    {regError && (
                      <div className="mb-4 text-sm flex items-center gap-2 p-3 rounded-lg" style={{ backgroundColor: 'rgba(204, 0, 0, 0.05)', color: 'var(--vc-red)' }}>
                        <XCircle size={14} /> {regError}
                      </div>
                    )}

                    <button type="submit" disabled={regLoading || !!pwMismatch} className="button-primary w-full mt-2">
                      {regLoading ? 'Creating account...' : <>Create Account <ArrowRight size={14} className="ml-2" /></>}
                    </button>
                  </>
                )}
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
