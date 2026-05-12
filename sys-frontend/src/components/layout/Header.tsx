import React from 'react';
import { Bell, Search, RefreshCw, HelpCircle, Shield } from 'lucide-react';

export const Header = () => {
  return (
    <header className="h-16 border-b border-outline-variant bg-white/80 backdrop-blur-md flex items-center justify-between px-10 sticky top-0 z-40 ml-64">
      <div className="flex items-center gap-3">
        <Shield className="w-5 h-5 text-primary" />
        <h2 className="text-lg font-bold text-on-surface">보안 모니터링 대시보드</h2>
        <span className="ml-2 px-2 py-0.5 bg-primary text-on-primary text-[10px] font-bold rounded uppercase tracking-widest">
          관리자 모드
        </span>
      </div>

      <div className="flex items-center gap-6">
        <div className="relative w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant w-4 h-4" />
          <input 
            type="text" 
            placeholder="에이전트 ID 또는 이벤트 검색..." 
            className="w-full h-9 bg-surface-container border-none rounded-lg pl-10 text-sm focus:ring-1 focus:ring-primary text-on-surface outline-none"
          />
        </div>
        
        <div className="flex items-center gap-4">
          <button className="relative p-2 text-on-surface-variant hover:text-primary transition-colors">
            <Bell className="w-5 h-5" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-error rounded-full border-2 border-white"></span>
          </button>
          <button className="p-2 text-on-surface-variant hover:text-primary transition-colors">
            <RefreshCw className="w-5 h-5" />
          </button>
          <button className="p-2 text-on-surface-variant hover:text-primary transition-colors">
            <HelpCircle className="w-5 h-5" />
          </button>
        </div>
        
        <div className="h-8 w-8 rounded-full overflow-hidden border border-outline-variant">
          <img 
            src="https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=100&h=100&fit=crop" 
            alt="Profile" 
            className="w-full h-full object-cover"
          />
        </div>
      </div>
    </header>
  );
};
