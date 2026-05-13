import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Shield, Key, Mail, User, Info, ArrowRight, ArrowLeft } from 'lucide-react';
import { useAuth } from '@/src/contexts/AuthContext';

export const EmployeeSignupPage = () => {
  const navigate = useNavigate();
  const { signup } = useAuth();
  const [formData, setFormData] = useState({
    companyCode: '',
    email: '',
    name: '',
    password: ''
  });

  const [errorMsg, setErrorMsg] = useState('');

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');
    try {
      await signup({ ...formData, role: 'EMPLOYEE' });
      navigate('/');
    } catch (error: any) {
      setErrorMsg(error.response?.data?.detail || '가입 처리 중 오류가 발생했습니다.');
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
        <div className="max-w-md w-full space-y-8">
           <div className="text-center space-y-2">
            <h2 className="text-4xl font-black text-on-surface font-display tracking-tight">사내 SafeAgent 서비스 가입</h2>
            <p className="text-on-surface-variant font-medium">관리자에게 받은 식별 번호를 입력하여 가입을 시작하세요.</p>
          </div>

          <form onSubmit={handleSignup} className="bg-white p-8 rounded-[2.5rem] shadow-2xl space-y-6 border border-on-surface/5">
            {errorMsg && (
              <div className="p-4 bg-error/10 text-error rounded-xl flex items-center gap-3 text-sm font-bold">
                <Info className="w-5 h-5 flex-shrink-0" />
                {errorMsg}
              </div>
            )}
            <div className="space-y-4">
               {/* Company Code */}
              <div className="space-y-2">
                <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant ml-1">기업 식별 번호 (Company Code)</label>
                <div className="relative">
                  <input 
                    type="text" 
                    required
                    placeholder="SA-XXXX-X"
                    value={formData.companyCode}
                    onChange={(e) => setFormData({...formData, companyCode: e.target.value.toUpperCase()})}
                    className="w-full h-14 pl-12 pr-4 bg-surface-container-low border-none rounded-xl font-bold text-on-surface outline-none focus:ring-1 focus:ring-primary transition-all placeholder:text-on-surface-variant/30"
                  />
                  <div className="absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant/40">
                     <Shield className="w-5 h-5" />
                  </div>
                </div>
              </div>

              {/* Email */}
              <div className="space-y-2">
                <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant ml-1">이메일 (Email)</label>
                <div className="relative">
                  <input 
                    type="email" 
                    required
                    placeholder="name@company.com"
                    value={formData.email}
                    onChange={(e) => setFormData({...formData, email: e.target.value})}
                    className="w-full h-14 pl-12 pr-4 bg-surface-container-low border-none rounded-xl font-bold text-on-surface outline-none focus:ring-1 focus:ring-primary transition-all placeholder:text-on-surface-variant/30"
                  />
                  <div className="absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant/40">
                     <Mail className="w-5 h-5" />
                  </div>
                </div>
              </div>

              {/* Name */}
              <div className="space-y-2">
                <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant ml-1">이름 (Name)</label>
                <div className="relative">
                  <input 
                    type="text" 
                    required
                    placeholder="홍길동"
                    value={formData.name}
                    onChange={(e) => setFormData({...formData, name: e.target.value})}
                    className="w-full h-14 pl-12 pr-4 bg-surface-container-low border-none rounded-xl font-bold text-on-surface outline-none focus:ring-1 focus:ring-primary transition-all placeholder:text-on-surface-variant/30"
                  />
                  <div className="absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant/40">
                     <User className="w-5 h-5" />
                  </div>
                </div>
              </div>

              {/* Password */}
              <div className="space-y-2">
                <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant ml-1">비밀번호 (Password)</label>
                <div className="relative">
                  <input 
                    type="password" 
                    required
                    placeholder="••••••••"
                    value={formData.password}
                    onChange={(e) => setFormData({...formData, password: e.target.value})}
                    className="w-full h-14 pl-12 pr-4 bg-surface-container-low border-none rounded-xl font-bold text-on-surface outline-none focus:ring-1 focus:ring-primary transition-all placeholder:text-on-surface-variant/30"
                  />
                  <div className="absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant/40">
                     <Key className="w-5 h-5" />
                  </div>
                </div>
              </div>
            </div>

            <div className="p-4 bg-primary-container/5 rounded-xl border border-primary/10 flex gap-4 items-start">
              <Info className="w-5 h-5 text-primary mt-0.5 shrink-0" />
              <p className="text-[11px] font-medium text-on-surface-variant leading-relaxed">
                이 번호는 사내 보안 정책에 따라 관리자 승인 후 최종 가입이 완료됩니다.
              </p>
            </div>

            <button 
              type="submit"
              className="w-full h-14 bg-primary text-on-primary rounded-xl flex items-center justify-center gap-3 font-bold hover:brightness-110 shadow-xl shadow-primary/20 transition-all uppercase tracking-widest text-sm"
            >
              가입 신청하기
              <ArrowRight className="w-5 h-5" />
            </button>
          </form>

          <p className="text-center text-on-surface-variant text-sm font-medium">
            이미 계정이 있으신가요? <Link to="/login" className="text-primary font-bold hover:underline ml-1">로그인</Link>
          </p>
        </div>
      </main>

      <footer className="px-10 py-8 border-t border-outline-variant flex justify-between items-center text-[10px] font-bold text-on-surface-variant/30 uppercase tracking-[0.2em]">
        <div className="flex justify-start items-center gap-4">
          <Shield className="w-4 h-4 text-primary opacity-50" />
          <span>© 2024 SafeAgent Security. All rights reserved.</span>
        </div>
      </footer>
    </div>
  );
};
