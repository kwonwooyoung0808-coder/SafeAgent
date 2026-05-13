import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { ShieldCheck, Copy, CheckCircle2, Shield, Info, Mail, User, Key, ArrowLeft } from 'lucide-react';
import { useAuth } from '@/src/contexts/AuthContext';

export const AdminSetupPage = () => {
  const navigate = useNavigate();
  const { signup } = useAuth();
  const [copied, setCopied] = useState(false);
  const [companyCode, setCompanyCode] = useState("SA-9921-X");
  const [adminId, setAdminId] = useState("admin_01");
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: ''
  });
  const [errorMsg, setErrorMsg] = useState('');

  const handleCopy = () => {
    navigator.clipboard.writeText(companyCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleComplete = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');
    try {
      await signup({
        name: formData.name || adminId,
        email: formData.email,
        password: formData.password,
        role: 'ADMIN',
        companyCode
      });
      navigate('/admin/dashboard');
    } catch (error: any) {
      setErrorMsg(error.response?.data?.detail || '관리자 계정 생성 중 오류가 발생했습니다.');
    }
  };

  return (
    <div className="min-h-screen bg-surface flex flex-col justify-between font-sans">
      <header className="px-10 py-6 flex justify-between items-center bg-white border-b border-outline-variant">
        <div className="flex items-center gap-6">
          <Link to="/auth/roles" className="flex items-center gap-3">
            <Shield className="w-8 h-8 text-primary" />
            <h1 className="text-2xl font-bold font-display tracking-tight text-primary">SafeAgent</h1>
          </Link>
          <button
            onClick={() => navigate('/auth/roles')}
            className="flex items-center gap-2 text-xs font-bold text-on-surface-variant hover:text-primary transition-colors uppercase tracking-widest border-l border-outline-variant pl-6"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>
        </div>
        <Link to="/help" className="text-sm font-medium text-on-surface-variant hover:text-primary transition-colors">Help</Link>
      </header>

      <main className="flex-1 flex flex-col items-center justify-center p-10">
        <div className="max-w-4xl w-full flex flex-col items-center gap-12">
          <div className="text-center space-y-2">
            <p className="text-[10px] font-black uppercase tracking-[0.4em] text-primary/60">Setup Process</p>
            <h2 className="text-4xl font-black text-primary font-display tracking-tight">Step 1: 관리자 계정 생성 및 기업 코드 발급</h2>
          </div>

          <form onSubmit={handleComplete} className="glass-panel p-2 rounded-[2.5rem] w-full max-w-4xl overflow-hidden shadow-2xl border-on-surface/5">
            {errorMsg && (
              <div className="mx-12 mt-8 mb-4 p-4 bg-error/10 text-error rounded-xl flex items-center gap-3 text-sm font-bold">
                <Info className="w-5 h-5 flex-shrink-0" />
                {errorMsg}
              </div>
            )}
            <div className="bg-white p-12 rounded-[2rem] flex flex-col md:flex-row gap-12 items-start">
              {/* Left Side: System IDs (ReadOnly/Issued) */}
              <div className="w-full md:w-1/3 flex flex-col gap-6">
                <div className="space-y-4">
                  <div className="p-6 bg-surface-container-low rounded-2xl border border-outline-variant">
                    <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-3 block">Issued Admin ID</label>
                    <div className="flex items-center gap-3 text-primary">
                      <Shield className="w-5 h-5" />
                      <span className="text-xl font-black font-mono">{adminId}</span>
                    </div>
                  </div>

                  <div className="p-6 bg-primary/5 rounded-2xl border border-primary/10">
                    <label className="text-[10px] font-black uppercase tracking-widest text-primary mb-3 block">Company Code</label>
                    <input
                      type="text"
                      required
                      value={companyCode}
                      onChange={(e) => setCompanyCode(e.target.value.toUpperCase())}
                      className="w-full bg-transparent border-none outline-none font-black text-xl tracking-widest uppercase text-primary placeholder:text-primary/20"
                      placeholder="SA-XXXX-X"
                    />
                  </div>
                </div>

                <button
                  type="button"
                  onClick={handleCopy}
                  className="w-full h-14 bg-surface border border-outline-variant rounded-xl flex items-center justify-center gap-3 font-bold text-on-surface hover:bg-surface-dim transition-all text-sm"
                >
                  <Copy className="w-4 h-4 text-on-surface-variant" />
                  {copied ? '번호 복사 완료' : '기업 코드 복사'}
                </button>

                <div className="p-4 bg-primary-container/5 rounded-xl border border-primary/10 flex gap-4 items-start">
                  <Info className="w-4 h-4 text-primary mt-0.5 shrink-0" />
                  <p className="text-[10px] font-medium text-on-surface-variant leading-relaxed">
                    이 식별 번호를 복사하여 사내 구성원들에게 공유해 주세요.
                  </p>
                </div>
              </div>

              {/* Right Side: Personal Info Registration */}
              <div className="flex-1 flex flex-col gap-6 w-full pt-2">
                <div className="space-y-1">
                  <h3 className="text-lg font-black text-on-surface">보안 관리자 인적사항 등록</h3>
                  <p className="text-xs text-on-surface-variant font-medium">관리자 계정으로 사용할 정보를 입력해 주세요.</p>
                </div>

                <div className="grid grid-cols-1 gap-5">
                  {/* Name */}
                  <div className="space-y-2">
                    <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant ml-1">Full Name</label>
                    <div className="relative">
                      <input
                        type="text"
                        required
                        placeholder="홍길동"
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        className="w-full h-14 pl-12 pr-4 bg-surface-container-low border-none rounded-xl font-bold text-on-surface outline-none focus:ring-1 focus:ring-primary transition-all placeholder:text-on-surface-variant/30"
                      />
                      <div className="absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant/40">
                        <User className="w-5 h-5" />
                      </div>
                    </div>
                  </div>

                  {/* Email */}
                  <div className="space-y-2">
                    <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant ml-1">Email Address</label>
                    <div className="relative">
                      <input
                        type="email"
                        required
                        placeholder="admin@company.com"
                        value={formData.email}
                        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                        className="w-full h-14 pl-12 pr-4 bg-surface-container-low border-none rounded-xl font-bold text-on-surface outline-none focus:ring-1 focus:ring-primary transition-all placeholder:text-on-surface-variant/30"
                      />
                      <div className="absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant/40">
                        <Mail className="w-5 h-5" />
                      </div>
                    </div>
                  </div>

                  {/* Password */}
                  <div className="space-y-2">
                    <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant ml-1">System Password</label>
                    <div className="relative">
                      <input
                        type="password"
                        required
                        placeholder="••••••••"
                        value={formData.password}
                        onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                        className="w-full h-14 pl-12 pr-4 bg-surface-container-low border-none rounded-xl font-bold text-on-surface outline-none focus:ring-1 focus:ring-primary transition-all placeholder:text-on-surface-variant/30"
                      />
                      <div className="absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant/40">
                        <Key className="w-5 h-5" />
                      </div>
                    </div>
                  </div>
                </div>

                <button
                  type="submit"
                  className="w-full h-14 mt-4 bg-primary text-on-primary rounded-xl flex items-center justify-center gap-3 font-bold hover:brightness-110 shadow-xl shadow-primary/20 transition-all uppercase tracking-widest text-sm"
                >
                  <CheckCircle2 className="w-5 h-5" />
                  보안 정책 초기화 및 설정 완료
                </button>
              </div>
            </div>
          </form>
        </div>
      </main>

      <footer className="px-10 py-8 border-t border-outline-variant flex justify-between items-center text-[10px] font-bold text-on-surface-variant/30 uppercase tracking-[0.2em]">
        <div className="flex flex-col gap-1">
          <span>SafeAgent Security</span>
          <span>© 2024 SafeAgent Security. All rights reserved.</span>
        </div>
        <div className="flex gap-8">
          <Link to="/privacy" className="hover:text-primary transition-colors">Privacy Policy</Link>
          <Link to="/terms" className="hover:text-primary transition-colors">Terms of Service</Link>
          <Link to="/standards" className="hover:text-primary transition-colors">Security Standards</Link>
        </div>
      </footer>
    </div>
  );
};
