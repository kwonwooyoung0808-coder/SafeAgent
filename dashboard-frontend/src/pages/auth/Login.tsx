import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Shield, Key, User as UserIcon, ArrowRight, Loader2, AlertCircle } from 'lucide-react';
import { useAuth } from '@/src/contexts/AuthContext';

export const LoginPage = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [selectedRole, setSelectedRole] = useState<'ADMIN' | 'EMPLOYEE'>('ADMIN');

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMsg(''); // 에러 초기화
    
    try {
      // 바뀐 실제 백엔드 연동 login 함수 호출
      await login({ username, password });
      
      // 성공 시 메인 라우터로 이동 (내부 로직에 따라 대시보드 등으로 자동 리다이렉트됨)
      navigate('/');
    } catch (error: any) {
      console.error('Login failed:', error);
      setErrorMsg('아이디 또는 비밀번호가 올바르지 않습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface flex flex-col justify-center items-center font-sans p-6 text-on-surface">
      <div className="max-w-md w-full space-y-8 animate-in fade-in slide-in-from-bottom-8 duration-700">
        <div className="flex flex-col items-center gap-4">
          <div className="w-16 h-16 rounded-3xl bg-white shadow-xl flex items-center justify-center border border-outline-variant">
            <Shield className="w-10 h-10 text-primary" />
          </div>
          <div className="text-center">
            <h1 className="text-4xl font-extrabold font-display tracking-tight text-primary">SafeAgent</h1>
            <p className="text-on-surface-variant font-medium">Enterprise Security AI Assistant</p>
          </div>
        </div>

        <form onSubmit={handleLogin} className="bg-white p-8 rounded-[2.5rem] shadow-2xl space-y-6 border border-outline-variant">
          
          {/* 에러 발생 시 경고창 표시 */}
          {errorMsg && (
            <div className="p-4 bg-error/10 text-error rounded-xl flex items-center gap-3 text-sm font-bold animate-in fade-in slide-in-from-top-2">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              {errorMsg}
            </div>
          )}

          <div className="space-y-6">
            {/* Role Selection Tabs */}
            <div className="space-y-2">
              <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant ml-1">접속 권한</label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setSelectedRole('ADMIN')}
                  className={`flex-1 h-12 rounded-xl font-bold text-sm transition-all border ${
                    selectedRole === 'ADMIN'
                      ? 'bg-primary text-on-primary border-primary shadow-md'
                      : 'bg-surface-container-low text-on-surface-variant border-transparent hover:bg-surface-container hover:text-on-surface'
                  }`}
                >
                  관리자
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedRole('EMPLOYEE')}
                  className={`flex-1 h-12 rounded-xl font-bold text-sm transition-all border ${
                    selectedRole === 'EMPLOYEE'
                      ? 'bg-primary text-on-primary border-primary shadow-md'
                      : 'bg-surface-container-low text-on-surface-variant border-transparent hover:bg-surface-container hover:text-on-surface'
                  }`}
                >
                  일반 사원
                </button>
              </div>
            </div>

            {/* Username */}
            <div className="space-y-2">
              <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant ml-1">아이디</label>
              <div className="relative">
                <input 
                  type="text" 
                  required
                  placeholder="관리자 또는 유저 ID"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full h-14 pl-12 pr-4 bg-surface-container-low border-none rounded-xl font-bold text-on-surface outline-none focus:ring-1 focus:ring-primary transition-all placeholder:text-on-surface-variant/30"
                />
                <div className="absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant/40">
                   <UserIcon className="w-5 h-5" />
                </div>
              </div>
            </div>

            {/* Password */}
            <div className="space-y-2">
              <div className="flex justify-between items-center px-1">
                <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">비밀번호</label>
              </div>
              <div className="relative">
                <input 
                  type="password" 
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
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
            disabled={isLoading}
            className="w-full h-14 bg-primary text-on-primary rounded-xl flex items-center justify-center gap-3 font-bold hover:brightness-110 shadow-xl shadow-primary/20 transition-all uppercase tracking-widest text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : (
              <>
                로그인 <ArrowRight className="w-5 h-5" />
              </>
            )}
          </button>
        </form>

        <div className="pt-8 text-center flex flex-col gap-6">
           <p className="text-on-surface-variant text-sm font-medium">
             아직 계정이 없으신가요? <Link to="/auth/roles" className="text-primary font-bold hover:underline ml-2">가입하기</Link>
           </p>
           <p className="text-[10px] font-black text-on-surface-variant/20 uppercase tracking-[0.4em]">Protected by SafeAgent AI Shield</p>
        </div>
      </div>
    </div>
  );
};
