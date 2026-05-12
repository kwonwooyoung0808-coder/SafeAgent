import React from 'react';
import { 
  Filter, 
  UserPlus, 
  MoreVertical, 
  ChevronLeft, 
  ChevronRight,
  ShieldCheck,
  History,
  AlertOctagon,
  Search,
  Check,
  X,
  Edit2,
  AlertCircle
} from 'lucide-react';
import { cn } from '@/src/lib/utils';

const users = [
  { id: 1, initials: 'JK', name: '김정훈 (Jung-hoon Kim)', email: 'jh.kim@safeagent.com', role: 'ADMIN', status: 'Active', joined: '2024-01-15' },
  { id: 2, image: 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=100&h=100&fit=crop', name: '이서연 (Seo-yeon Lee)', email: 'sy.lee@safeagent.com', role: 'OPERATOR', status: 'Pending', joined: '2024-03-21' },
  { id: 3, initials: 'PW', name: '박원석 (Won-seok Park)', email: 'ws.park@safeagent.com', role: 'VIEWER', status: 'Inactive', joined: '2023-11-02' },
  { id: 4, initials: 'CH', name: '최현준 (Hyun-jun Choi)', email: 'hj.choi@safeagent.com', role: 'OPERATOR', status: 'Active', joined: '2024-02-14' },
];

const UserManagementPage = () => {
  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-right-4 duration-500">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
        <div>
          <h1 className="text-3xl font-bold text-primary font-display tracking-tight">사용자 및 Agent 관리</h1>
          <p className="text-on-surface-variant font-medium mt-1">신규 사원 가입 승인 및 에이전트 권한 설정</p>
        </div>
        <div className="flex gap-3">
          <button className="flex items-center gap-2 px-4 py-2 bg-white border border-outline-variant rounded-xl text-sm font-bold text-on-surface hover:bg-surface-container transition-colors shadow-sm">
            <Filter className="w-4 h-4" />
            필터
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-primary text-on-primary rounded-xl text-sm font-bold hover:brightness-110 shadow-lg shadow-primary/20 transition-all">
            <UserPlus className="w-4 h-4" />
            사용자 추가
          </button>
        </div>
      </div>

      <div className="glass-panel rounded-2xl overflow-hidden border border-outline-variant/30 flex flex-col shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-surface-container-low border-b border-outline-variant/30 text-[10px] font-black uppercase tracking-widest text-on-surface-variant">
                <th className="px-8 py-5">이름 / 이메일</th>
                <th className="px-8 py-5">권한</th>
                <th className="px-8 py-5">상태</th>
                <th className="px-8 py-5">가입일</th>
                <th className="px-8 py-5 text-right">관리 액션</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/20 italic-serif-headers">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-surface-container-high/20 transition-colors group">
                  <td className="px-8 py-4">
                    <div className="flex items-center gap-4">
                      {u.image ? (
                        <img src={u.image} alt={u.name} className="w-10 h-10 rounded-full object-cover ring-2 ring-surface-container-highest" />
                      ) : (
                        <div className="w-10 h-10 rounded-full bg-primary-container/20 flex items-center justify-center text-primary font-black text-sm">
                          {u.initials}
                        </div>
                      )}
                      <div className="flex flex-col">
                        <span className="text-sm font-bold text-on-surface tracking-tight">{u.name}</span>
                        <span className="text-[11px] text-on-surface-variant font-medium">{u.email}</span>
                      </div>
                    </div>
                  </td>
                  <td className="px-8 py-4">
                    <span className={cn(
                      "px-2 py-0.5 rounded text-[9px] font-black uppercase tracking-tighter border",
                      u.role === 'ADMIN' ? "bg-primary-container text-on-primary-container border-primary/20" : "bg-surface-container-highest text-on-surface-variant border-outline-variant/30"
                    )}>
                      {u.role}
                    </span>
                  </td>
                  <td className="px-8 py-4">
                    {u.status === 'Pending' ? (
                      <span className="bg-amber-100 text-amber-700 font-black text-[9px] uppercase tracking-tighter px-2 py-0.5 rounded border border-amber-200">
                        {u.status}
                      </span>
                    ) : (
                      <div className="flex items-center gap-2">
                        <div className={cn(
                          "w-8 h-4 rounded-full relative transition-colors cursor-pointer",
                          u.status === 'Active' ? "bg-primary/20" : "bg-outline-variant/30"
                        )}>
                          <div className={cn(
                            "absolute top-0.5 w-3 h-3 rounded-full shadow-sm transition-all duration-300",
                            u.status === 'Active' ? "right-0.5 bg-primary" : "left-0.5 bg-outline"
                          )} />
                        </div>
                        <span className={cn("text-[10px] font-bold", u.status === 'Active' ? "text-primary" : "text-on-surface-variant")}>
                          {u.status}
                        </span>
                      </div>
                    )}
                  </td>
                  <td className="px-8 py-4 text-xs font-mono text-on-surface-variant">{u.joined}</td>
                  <td className="px-8 py-4 text-right">
                    {u.status === 'Pending' ? (
                      <div className="flex justify-end gap-2">
                        <button className="p-1 px-3 bg-primary/10 text-primary text-[10px] font-black rounded-lg border border-primary/20 hover:bg-primary hover:text-on-primary transition-all">승인</button>
                        <button className="p-1 px-3 bg-error-container/20 text-error text-[10px] font-black rounded-lg border border-error/20 hover:bg-error hover:text-on-error transition-all">거절</button>
                      </div>
                    ) : (
                      <button className="p-2 text-on-surface-variant hover:text-primary transition-colors">
                        <MoreVertical className="w-5 h-5" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="px-8 py-4 bg-surface-container-low flex justify-between items-center text-[10px] font-bold text-on-surface-variant border-t border-outline-variant/20 uppercase tracking-widest">
          <span>Showing 1 to {users.length} of 48 Users</span>
          <div className="flex gap-2">
            <button className="w-8 h-8 flex items-center justify-center rounded-lg border border-outline-variant/30 hover:bg-white transition-colors">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button className="w-8 h-8 flex items-center justify-center rounded-lg bg-primary text-on-primary font-black">1</button>
            <button className="w-8 h-8 flex items-center justify-center rounded-lg border border-outline-variant/30 hover:bg-white transition-colors">2</button>
            <button className="w-8 h-8 flex items-center justify-center rounded-lg border border-outline-variant/30 hover:bg-white transition-colors">3</button>
            <button className="w-8 h-8 flex items-center justify-center rounded-lg border border-outline-variant/30 hover:bg-white transition-colors">
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="glass-panel p-6 rounded-2xl flex flex-col gap-4">
          <div className="flex items-center gap-3 text-primary">
            <ShieldCheck className="w-5 h-5" />
            <h3 className="font-bold tracking-tight">계정 보안 현황</h3>
          </div>
          <div className="space-y-4">
            <div className="flex justify-between items-center text-xs font-bold uppercase tracking-widest text-on-surface-variant">
              <span>2단계 인증 활성화</span>
              <span className="text-primary font-black">92%</span>
            </div>
            <div className="w-full h-1.5 bg-surface-container-highest rounded-full overflow-hidden">
              <div className="h-full bg-primary" style={{ width: '92%' }}></div>
            </div>
            <div className="flex justify-between items-center font-bold text-xs uppercase tracking-widest text-on-surface-variant mt-2">
              <span>평균 패스워드 수명</span>
              <span className="text-error">42 Days</span>
            </div>
          </div>
        </div>

        <div className="glass-panel p-6 rounded-2xl flex flex-col items-center justify-center text-center gap-1">
          <AlertOctagon className="w-10 h-10 text-error mb-1" />
          <h4 className="font-bold text-on-surface">보안 정책 미준수</h4>
          <p className="text-xs text-on-surface-variant font-medium">가입 후 24시간 내 승인되지 않은 요청</p>
          <span className="text-4xl font-black text-error mt-2">03</span>
        </div>

        <div className="glass-panel p-6 rounded-2xl flex flex-col gap-4">
          <div className="flex items-center gap-3 text-primary">
            <History className="w-5 h-5" />
            <h3 className="font-bold tracking-tight">최근 권한 변경 내역</h3>
          </div>
          <div className="space-y-4">
            <div className="flex items-start gap-3">
              <div className="w-5 h-5 rounded-full bg-primary/10 flex items-center justify-center text-primary mt-0.5">
                <Edit2 className="w-3 h-3" />
              </div>
              <div className="flex flex-col gap-1">
                <p className="text-[11px] font-bold text-on-surface leading-tight">김정훈님이 이서연님의 권한을 Operator로 변경</p>
                <span className="text-[10px] font-bold uppercase text-on-surface-variant tracking-widest leading-none">15분 전</span>
              </div>
            </div>
            <div className="flex items-start gap-3 pt-4 border-t border-outline-variant/30">
              <div className="w-5 h-5 rounded-full bg-error/10 flex items-center justify-center text-error mt-0.5">
                <AlertCircle className="w-3 h-3" />
              </div>
              <div className="flex flex-col gap-1">
                <p className="text-[11px] font-bold text-on-surface leading-tight">System이 박원석님의 계정을 비활성 처리</p>
                <span className="text-[10px] font-bold uppercase text-on-surface-variant tracking-widest leading-none">2시간 전</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UserManagementPage;
