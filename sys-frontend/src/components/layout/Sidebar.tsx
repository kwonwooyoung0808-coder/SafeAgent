import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { 
  LayoutDashboard, 
  AlertTriangle, 
  Users, 
  History, 
  Settings, 
  FileText,
  LogOut,
  ShieldCheck,
  MessageSquare
} from 'lucide-react';
import { cn } from '@/src/lib/utils';
import { useAuth } from '@/src/contexts/AuthContext';

const navItems = [
  { name: '대시보드', href: '/admin/dashboard', icon: LayoutDashboard },
  { name: '보안 위반 레포트', href: '/admin/reports', icon: AlertTriangle },
  { name: '사내 정책 관리', href: '/admin/policy', icon: FileText },
  { name: '사용자 및 권한 관리', href: '/admin/users', icon: Users },
  { name: '감사 및 추적 로그', href: '/admin/logs', icon: History },
  { name: '시스템 설정', href: '/admin/settings', icon: Settings },
];

export const Sidebar = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <aside className="w-64 border-r border-outline-variant bg-white flex flex-col h-screen fixed left-0 top-0 z-50">
      <div className="p-6">
        <div className="flex items-center gap-3">
          <ShieldCheck className="w-8 h-8 text-primary" />
          <h1 className="text-xl font-bold text-primary tracking-tight font-display">SafeAgent</h1>
        </div>
        <p className="text-[10px] text-on-surface-variant font-black uppercase tracking-widest mt-1">Admin Portal</p>
      </div>

      <nav className="flex-1 px-4 py-6 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.href}
            to={item.href}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 group relative",
                isActive 
                  ? "bg-primary/10 text-primary font-bold shadow-sm" 
                  : "text-on-surface-variant hover:bg-primary/5 hover:text-primary"
              )
            }
          >
            <item.icon className="w-5 h-5" />
            <span className="text-sm font-medium">{item.name}</span>
          </NavLink>
        ))}

        <div className="pt-4 mt-4 border-t border-outline-variant">
           <NavLink
            to="/chat"
            className="flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 text-on-surface-variant hover:bg-primary/5 hover:text-primary"
          >
            <MessageSquare className="w-5 h-5" />
            <span className="text-sm font-medium">보안 비서 (Chat)</span>
          </NavLink>
        </div>
      </nav>

      <div className="p-4 border-t border-outline-variant">
        <div className="p-3 bg-surface-container-low rounded-xl border border-outline-variant mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center text-white font-bold uppercase">
              {user?.name?.slice(0, 2) || 'AD'}
            </div>
            <div className="flex flex-col">
              <span className="text-xs font-bold text-on-surface truncate max-w-[120px]">{user?.name || 'Admin'}</span>
              <span className="text-[10px] text-on-surface-variant">Super Administrator</span>
            </div>
          </div>
        </div>
        <button 
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-4 py-2 text-on-surface-variant hover:text-primary transition-colors text-sm font-medium"
        >
          <LogOut className="w-4 h-4" />
          Logout
        </button>
      </div>
    </aside>
  );
};
