import React from 'react';
import { NavLink, Link } from 'react-router-dom';
import { ShieldCheck, UserPlus, Shield, ChevronRight, ArrowLeft } from 'lucide-react';

export const RoleSelectionPage = () => {
  return (
    <div className="min-h-screen bg-surface flex flex-col justify-between text-on-surface font-sans overflow-hidden">
      {/* Header */}
      <header className="px-10 py-6 flex justify-between items-center bg-white border-b border-outline-variant backdrop-blur-md">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3">
            <Shield className="w-8 h-8 text-primary" />
            <h1 className="text-2xl font-bold font-display tracking-tight text-primary">SafeAgent</h1>
          </div>
        </div>
        <div className="flex items-center gap-6">
          <Link to="/help" className="text-sm font-medium text-on-surface-variant hover:text-primary transition-colors">Help</Link>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex flex-col items-center justify-center p-10 mt-[-5vh]">
        <div className="max-w-4xl w-full text-center space-y-12 animate-in fade-in slide-in-from-bottom-8 duration-700">
          <div className="space-y-4">
            <h2 className="text-5xl font-extrabold font-display tracking-tighter text-on-surface">Role Selection Gateway</h2>
            <p className="text-lg text-on-surface-variant font-medium">시작하시려면 본인의 권한에 맞는 카드를 선택해 주세요.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 text-left">
            {/* Admin Card */}
            <div className="bg-white rounded-[2rem] p-8 flex flex-col gap-6 group hover:scale-[1.02] transition-all duration-300 shadow-xl overflow-hidden relative border border-outline-variant">
              <div className="absolute top-0 left-0 w-full h-48 overflow-hidden">
                <img 
                  src="https://images.unsplash.com/photo-1550751827-4bd374c3f58b?auto=format&fit=crop&q=80&w=600" 
                  alt="Admin background" 
                  className="w-full h-full object-cover grayscale opacity-30 group-hover:grayscale-0 group-hover:opacity-40 transition-all duration-700"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-white via-white/80 to-transparent"></div>
              </div>
              
              <div className="relative z-10 pt-40">
                <div className="w-14 h-14 rounded-2xl bg-primary/5 flex items-center justify-center border border-primary/10 mb-6">
                  <ShieldCheck className="w-8 h-8 text-primary" />
                </div>
                <h3 className="text-2xl font-black text-on-surface tracking-tight font-display mb-3">기업 관리자 설정</h3>
                <p className="text-on-surface-variant leading-relaxed text-sm font-medium mb-8">
                  시스템의 최초 구성을 담당하며, 보안 정책 및 사원 관리를 초기화합니다.
                </p>
                <Link 
                  to="/signup/admin" 
                  className="flex items-center gap-2 text-primary font-bold text-sm uppercase tracking-widest hover:underline group-hover:translate-x-1 transition-transform"
                >
                  Initial Setup 시작하기 <ChevronRight className="w-4 h-4" />
                </Link>
              </div>
            </div>

            {/* Employee Card */}
            <div className="bg-white rounded-[2rem] p-8 flex flex-col gap-6 group hover:scale-[1.02] transition-all duration-300 shadow-xl overflow-hidden relative border border-outline-variant">
              <div className="absolute top-0 left-0 w-full h-48 overflow-hidden">
                <img 
                  src="https://images.unsplash.com/photo-1558494949-ef010cbdcc51?auto=format&fit=crop&q=80&w=600" 
                  alt="Employee background" 
                  className="w-full h-full object-cover grayscale opacity-30 group-hover:grayscale-0 group-hover:opacity-40 transition-all duration-700"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-white via-white/80 to-transparent"></div>
              </div>

              <div className="relative z-10 pt-40">
                <div className="w-14 h-14 rounded-2xl bg-primary/5 flex items-center justify-center border border-primary/10 mb-6">
                  <UserPlus className="w-8 h-8 text-primary" />
                </div>
                <h3 className="text-2xl font-black text-on-surface tracking-tight font-display mb-3">사원 회원가입</h3>
                <p className="text-on-surface-variant leading-relaxed text-sm font-medium mb-8">
                  기존에 구축된 SafeAgent 시스템에 접속하기 위해 신규 계정을 생성합니다.
                </p>
                <Link 
                  to="/signup/employee" 
                   className="flex items-center gap-2 text-primary font-bold text-sm uppercase tracking-widest hover:underline group-hover:translate-x-1 transition-transform"
                >
                  Employee Sign-up 시작하기 <ChevronRight className="w-4 h-4" />
                </Link>
              </div>
            </div>
          </div>

          <div className="pt-8">
            <p className="text-on-surface-variant text-sm font-medium">
              이미 계정이 있으신가요? <Link to="/login" className="text-primary font-bold hover:underline ml-2">로그인하기</Link>
            </p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="px-10 py-8 border-t border-outline-variant flex justify-between items-center text-[10px] font-bold text-on-surface-variant/30 uppercase tracking-[0.2em]">
        <div className="flex flex-col gap-1 text-left">
          <span>SafeAgent</span>
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
