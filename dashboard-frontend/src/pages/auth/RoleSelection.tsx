import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ShieldCheck,
  UserCircle2,
  ArrowRight,
  Hexagon,
  Cpu,
  Sparkles,
  Loader2,
  Shield,
  Layers
} from 'lucide-react';
import { cn } from '../../lib/utils';
import { useAuth } from '../../contexts/AuthContext';

const RoleSelectionPage = () => {
  const navigate = useNavigate();
  const { loginAsAdmin, loginAsEmployee } = useAuth();
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  const handleRoleSelect = async (role: 'ADMIN' | 'EMPLOYEE') => {
    setIsLoggingIn(true);
    if (role === 'ADMIN') {
      await loginAsAdmin();
      setIsLoggingIn(false);
      navigate('/admin/dashboard');
    } else {
      await loginAsEmployee();
      setIsLoggingIn(false);
      navigate('/chat');
    }
  };
  return (
    <div className="min-h-screen bg-surface-container-lowest flex flex-col items-center justify-center p-6 relative overflow-hidden transition-all duration-700">
      {/* Background Decorative Elements */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary/5 rounded-full blur-[120px] animate-pulse"></div>
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-secondary/5 rounded-full blur-[120px] animate-pulse" style={{ animationDelay: '1s' }}></div>

      {/* Top Logo Section */}
      <div className="mb-16 flex flex-col items-center animate-in fade-in zoom-in duration-1000 relative z-20">
        <div className="w-20 h-20 bg-primary rounded-3xl flex items-center justify-center text-white shadow-2xl shadow-primary/30 mb-6 group transition-all hover:rotate-[10deg]">
          <Shield className="w-10 h-10 group-hover:scale-110 transition-transform" />
        </div>
        <h1 className="text-4xl font-black text-on-surface tracking-tighter mb-2">SafeAgent</h1>
        <div className="flex items-center gap-2 px-4 py-1.5 bg-primary/5 rounded-full border border-primary/10">
          <Layers className="w-3 h-3 text-primary" />
          <span className="text-[10px] font-black text-primary uppercase tracking-[0.2em]">Governance Gateway</span>
        </div>
      </div>

      <div className="max-w-4xl w-full grid grid-cols-1 md:grid-cols-2 gap-8 relative z-10 animate-in fade-in slide-in-from-bottom-8 duration-1000">
        {/* Admin Card */}
        <div
          onClick={() => !isLoggingIn && handleRoleSelect('ADMIN')}
          className={cn(
            "group relative bg-white border border-outline-variant p-10 rounded-[2.5rem] cursor-pointer transition-all duration-500 hover:shadow-[0_20px_50px_rgba(0,32,69,0.12)] hover:-translate-y-2 hover:border-primary/30 flex flex-col items-center text-center overflow-hidden",
            isLoggingIn && "opacity-50 cursor-wait"
          )}
        >
          <div className="absolute top-0 right-0 p-6 opacity-0 group-hover:opacity-100 transition-opacity translate-x-4 group-hover:translate-x-0 duration-500">
            <Sparkles className="w-6 h-6 text-primary/40" />
          </div>

          <div className="w-24 h-24 bg-primary/5 rounded-[2rem] flex items-center justify-center mb-8 relative transition-transform duration-500 group-hover:scale-110">
            <div className="absolute inset-0 bg-primary/10 rounded-[2rem] animate-ping opacity-20 group-hover:opacity-40"></div>
            {isLoggingIn ? (
              <Loader2 className="w-12 h-12 text-primary animate-spin" />
            ) : (
              <ShieldCheck className="w-12 h-12 text-primary relative z-10" />
            )}
          </div>

          <h2 className="text-3xl font-black text-on-surface mb-4 tracking-tight group-hover:text-primary transition-colors">Admin Portal</h2>
          <p className="text-on-surface-variant font-medium leading-relaxed mb-8">
            {isLoggingIn ? '인증 시퀀스 초기화 중...' : '시스템 정책 관리, 로그 감사 및 위반 리포트 조회를 위한 관리자 전용 대시보드에 진입합니다.'}
          </p>

          <div className="mt-auto flex items-center gap-2 text-primary font-black text-xs uppercase tracking-widest bg-primary/5 px-6 py-3 rounded-full opacity-60 group-hover:opacity-100 transition-all">
            {isLoggingIn ? 'Authenticating...' : 'Enter Dashboard'}
            {!isLoggingIn && <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />}
          </div>
        </div>

        {/* User Card */}
        <div
          onClick={() => !isLoggingIn && handleRoleSelect('EMPLOYEE')}
          className="group relative bg-[#f1f5f9] border border-outline-variant/60 p-10 rounded-[2.5rem] cursor-pointer transition-all duration-500 hover:shadow-[0_20px_50px_rgba(30,41,59,0.08)] hover:-translate-y-2 hover:border-on-surface-variant/20 flex flex-col items-center text-center overflow-hidden"
        >
          <div className="w-24 h-24 bg-white/60 rounded-[2rem] flex items-center justify-center mb-8 shadow-sm transition-transform duration-500 group-hover:scale-110">
            <UserCircle2 className="w-12 h-12 text-on-surface-variant" />
          </div>

          <h2 className="text-3xl font-black text-on-surface mb-4 tracking-tight group-hover:text-primary transition-colors">Employee Chat</h2>
          <p className="text-on-surface-variant font-medium leading-relaxed mb-8">
            안전한 환경에서 AI 어시스턴트와 대화합니다. 입력 필터링 및 응답 무결성 검사가 실시간으로 적용됩니다.
          </p>

          <div className="mt-auto flex items-center gap-2 text-on-surface-variant font-black text-xs uppercase tracking-widest bg-white/60 px-6 py-3 rounded-full opacity-60 group-hover:opacity-100 transition-all">
            Start Conversation
            <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
          </div>
        </div>
      </div>

      {/* Corporate Info Footer */}
      <div className="absolute bottom-10 left-10 right-10 flex flex-col md:flex-row items-center justify-between opacity-30 select-none">
        <div className="flex items-center gap-3">
          <Hexagon className="w-6 h-6 text-primary fill-primary/10" />
          <span className="font-black text-xs uppercase tracking-[0.4em]">SafeAgent Internal Governance</span>
        </div>
        <div className="flex items-center gap-6 mt-4 md:mt-0">
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4" />
            <span className="font-mono text-[10px] font-bold">Node: ENT-GW-AP-01</span>
          </div>
          <span className="font-mono text-[10px] font-bold">© 2024 Corporate Security Compliance</span>
        </div>
      </div>
    </div>
  );
};

export default RoleSelectionPage;
