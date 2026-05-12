import React from 'react';
import { 
  Settings, 
  Save, 
  Download, 
  Activity, 
  Cpu, 
  Globe, 
  Lock, 
  Database, 
  Radio, 
  Search,
  Plus,
  Terminal,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle
} from 'lucide-react';
import { cn } from '@/src/lib/utils';

const ipAllowlist = [
  { id: 'HQ-MAIN-SERVER', ip: '10.0.4.128 / 24', access: 'Full Access', last: '2분 전 (추론 요청)', status: 'Active' },
  { id: 'SEOUL-EDGE-NODE-01', ip: '172.16.8.54', access: 'Read Only', last: '1시간 전 (로그 동기화)', status: 'Active' },
  { id: 'ADMIN-VM-LOCAL', ip: '192.168.1.100', access: 'Full Access', last: '대기 중', status: 'Idle' },
  { id: 'DEV-SANDBOX-CLUSTER', ip: '10.0.99.0 / 24', access: 'Restricted', last: '15분 전 (테스트)', status: 'Blocked' },
];

const SystemSettingsPage = () => {
  return (
    <div className="flex flex-col gap-8 animate-in fade-in slide-in-from-left-4 duration-500">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-outline-variant/30 pb-8">
        <div>
          <h1 className="text-3xl font-bold text-primary font-display tracking-tight uppercase">시스템 설정 및 모니터링</h1>
          <p className="text-on-surface-variant font-medium mt-1 uppercase tracking-tighter">엔터프라이즈 보안 게이트웨이 및 소버린 AI 인프라 관리</p>
        </div>
        <div className="flex gap-3">
          <button className="flex items-center gap-2 px-6 py-2 bg-white border border-primary text-primary font-bold text-xs uppercase tracking-widest rounded-lg hover:bg-primary/5 transition-all">
            <Download className="w-4 h-4" /> 구성 내보내기
          </button>
          <button className="flex items-center gap-2 px-6 py-2 bg-primary text-on-primary font-bold text-xs uppercase tracking-widest rounded-lg hover:brightness-110 shadow-lg shadow-primary/20 transition-all">
            <Save className="w-4 h-4" /> 설정 저장
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Sovereign AI Status */}
        <div className="lg:col-span-7 glass-panel p-8 rounded-[2rem] flex flex-col gap-8 relative overflow-hidden group shadow-xl">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-2xl bg-primary-container flex items-center justify-center text-on-primary shadow-lg shadow-primary/20">
                <Cpu className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-primary tracking-tight font-display">Sovereign AI Status</h3>
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">실시간 모델 추론 인프라</p>
              </div>
            </div>
            <div className="flex items-center gap-2 bg-[#e6f4ea] px-4 py-2 rounded-full border border-[#48bb78]/20">
              <div className="w-2.5 h-2.5 bg-[#48bb78] rounded-full animate-pulse shadow-[0_0_10px_rgba(72,187,120,0.5)]"></div>
              <span className="text-xs font-black text-[#2e7d32] uppercase tracking-widest">정상 연결됨</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="p-5 bg-surface-container-low rounded-2xl border border-outline-variant/30 group-hover:border-primary/20 transition-colors">
              <span className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2 block">Active Model</span>
              <p className="text-lg font-bold text-primary">SAFE-LLM-V4-ENTERPRISE</p>
            </div>
            <div className="p-5 bg-surface-container-low rounded-2xl border border-outline-variant/30 group-hover:border-primary/20 transition-colors">
              <span className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2 block">Hardware Accel</span>
              <p className="text-lg font-bold text-on-surface">NVIDIA H100 (8 Nodes)</p>
            </div>
          </div>

          <div className="space-y-5">
            <div className="flex flex-col gap-2">
              <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Sovereign AI API Endpoint</label>
              <div className="p-4 bg-white border border-outline-variant/30 rounded-xl font-mono text-xs text-primary flex items-center justify-between group-hover:ring-1 group-hover:ring-primary/20 transition-all">
                <code>SOVEREIGN_AI_URL=https://core-inference.safeagent.internal:8443/v1</code>
                <Lock className="w-4 h-4 text-on-surface-variant/40" />
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Environment Scope</label>
              <div className="p-4 bg-white border border-outline-variant/30 rounded-xl font-mono text-xs text-on-surface flex items-center group-hover:ring-1 group-hover:ring-primary/20 transition-all">
                <code>AUTH_PROVIDER=ENT_IDENTITY_VAULT_PROD</code>
              </div>
            </div>
          </div>
          
          <div className="absolute -right-16 -bottom-16 w-64 h-64 bg-primary/5 rounded-full blur-[100px] pointer-events-none group-hover:bg-primary/10 transition-all duration-700"></div>
        </div>

        {/* System Health */}
        <div className="lg:col-span-5 flex flex-col gap-8">
          <div className="glass-panel p-8 rounded-[2rem] border-l-4 border-l-primary shadow-lg flex flex-col justify-between">
            <div className="flex justify-between items-start">
              <div className="flex flex-col">
                <span className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">시스템 가동 시간 (Uptime)</span>
                <div className="mt-4 flex items-baseline gap-2">
                  <span className="text-5xl font-black text-primary tracking-tighter">322</span>
                  <span className="text-lg font-bold text-on-surface-variant">일</span>
                  <span className="text-5xl font-black text-primary tracking-tighter">14</span>
                  <span className="text-lg font-bold text-on-surface-variant">시간</span>
                </div>
              </div>
              <Activity className="w-6 h-6 text-primary animate-pulse" />
            </div>
            <div className="mt-8 space-y-4">
              <div className="w-full h-1.5 bg-surface-container-high rounded-full overflow-hidden shadow-inner">
                <div className="h-full bg-primary shadow-[0_0_8px_rgba(0,32,69,0.3)] animate-pulse" style={{ width: '99.9%' }}></div>
              </div>
              <div className="flex items-center gap-2 text-[#2e7d32]">
                <CheckCircle2 className="w-4 h-4" />
                <span className="text-xs font-black uppercase tracking-widest tracking-tighter">가용성 99.999% 유지 중</span>
              </div>
            </div>
          </div>

          <div className="glass-panel p-8 rounded-[2rem] border-l-4 border-l-secondary shadow-lg flex flex-col justify-between bg-surface-container-low/50">
            <div className="flex justify-between items-start">
              <div className="flex flex-col">
                <span className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">데이터 흐름 무결성 (Secure Flow)</span>
                <div className="mt-4">
                  <span className="text-4xl font-black text-primary tracking-tight">1.2 TB</span>
                  <p className="text-xs font-bold text-on-surface-variant mt-1">오늘 암호화된 데이터</p>
                </div>
              </div>
              <Radio className="w-6 h-6 text-secondary animate-pulse" />
            </div>
            <div className="mt-8 flex gap-1 items-end h-12 px-2">
              {[40, 70, 50, 90, 80, 100, 60, 40].map((h, i) => (
                <div key={i} className="flex-1 bg-primary/20 rounded-t-sm" style={{ height: `${h}%` }}>
                  {h >= 80 && <div className="w-full bg-primary h-full rounded-t-sm animate-bounce" style={{ animationDuration: `${1 + i * 0.2}s` }}></div>}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Data Sovereignty Guard */}
        <div className="lg:col-span-12 glass-panel p-8 rounded-[2rem] shadow-xl">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-8">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-2xl bg-primary/5 flex items-center justify-center text-primary border border-primary/10">
                <ShieldCheck className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-primary tracking-tight font-display uppercase">Data Sovereignty Guard</h3>
                <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">허용된 내부 IP 주소 관리 (Allowlist)</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="relative w-64">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-on-surface-variant" />
                <input className="w-full h-11 pl-10 pr-4 bg-white border border-outline-variant/30 rounded-xl outline-none focus:ring-1 focus:ring-primary transition-all text-sm font-medium" placeholder="IP 검색..." />
              </div>
              <button className="flex items-center gap-2 h-11 px-6 bg-primary text-on-primary font-bold text-xs uppercase tracking-widest rounded-xl hover:brightness-110 shadow-lg shadow-primary/20 transition-all">
                <Plus className="w-4 h-4" /> 주소 추가
              </button>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-surface-container-high/50 border-b border-outline-variant/30 text-[10px] font-black uppercase tracking-[0.2em] text-primary">
                  <th className="px-8 py-5">식별자</th>
                  <th className="px-8 py-5">IP 주소 / 대역</th>
                  <th className="px-8 py-5">접근 수준</th>
                  <th className="px-8 py-5">최근 활동</th>
                  <th className="px-8 py-5 text-right">상태</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/10">
                {ipAllowlist.map((item) => (
                  <tr key={item.id} className="hover:bg-primary/5 transition-colors group">
                    <td className="px-8 py-5 font-black text-primary text-sm tracking-tight">{item.id}</td>
                    <td className="px-8 py-5 font-mono text-xs text-on-surface">{item.ip}</td>
                    <td className="px-8 py-5">
                      <span className={cn(
                        "text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded border shadow-sm",
                        item.access === 'Full Access' ? "bg-primary-container/10 text-primary border-primary/20" :
                        item.access === 'Restricted' ? "bg-error-container/20 text-error border-error/20" :
                        "bg-surface-container-highest text-on-surface-variant border-outline-variant/30"
                      )}>
                        {item.access}
                      </span>
                    </td>
                    <td className="px-8 py-5 text-xs font-bold text-on-surface-variant tracking-tighter">{item.last}</td>
                    <td className="px-8 py-5 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <div className={cn(
                          "w-1.5 h-1.5 rounded-full",
                          item.status === 'Active' ? "bg-green-600 animate-pulse shadow-[0_0_8px_rgba(72,187,120,0.5)]" : 
                          item.status === 'Blocked' ? "bg-error" : "bg-outline"
                        )} />
                        <span className={cn(
                          "text-[10px] font-black uppercase tracking-widest",
                          item.status === 'Active' ? "text-green-700 font-bold" : 
                          item.status === 'Blocked' ? "text-error" : "text-outline"
                        )}>
                          {item.status === 'Active' ? '활성' : item.status === 'Blocked' ? '차단됨' : '유휴'}
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Security Event Stream */}
        <div className="lg:col-span-12 glass-panel p-8 rounded-[2rem] border-t-4 border-t-primary shadow-xl bg-white/95">
          <div className="flex items-center gap-3 mb-6">
            <Terminal className="w-5 h-5 text-primary" />
            <h4 className="text-[10px] font-black uppercase tracking-[0.3em] text-primary">Raw Security Event Stream</h4>
          </div>
          <div className="bg-surface-container-lowest p-6 rounded-2xl border border-outline-variant/30 font-mono text-[11px] leading-loose max-h-[300px] overflow-y-auto custom-scrollbar shadow-inner text-primary/80">
            <div className="space-y-1">
              <div className="flex gap-4 opacity-50 px-2 py-1 rounded hover:bg-primary/5 transition-colors">
                <span className="text-on-surface-variant font-bold">[2024-05-20 14:22:01]</span>
                <span className="text-green-700 font-black">INFO</span>
                <span className="text-on-surface">Sovereign Guard heartbeat received from 10.0.4.128</span>
              </div>
              <div className="flex gap-4 px-2 py-1 rounded bg-primary/5 border-l-2 border-primary">
                <span className="text-on-surface-variant font-bold">[2024-05-20 14:22:05]</span>
                <span className="text-primary font-black uppercase">Query</span>
                <span className="text-on-surface font-bold">SAFE-LLM-V4 responding to inference request ID: #9928-XA</span>
              </div>
              <div className="flex gap-4 px-2 py-1 rounded bg-error/5 border-l-2 border-error">
                <span className="text-on-surface-variant font-bold">[2024-05-20 14:22:12]</span>
                <span className="text-error font-black uppercase">Warn</span>
                <span className="text-error font-bold italic underline decoration-error/30">Unauthorized access attempt blocked from 192.168.1.155 (Protocol: SSH)</span>
              </div>
              <div className="flex gap-4 opacity-50 px-2 py-1 rounded hover:bg-primary/5 transition-colors">
                <span className="text-on-surface-variant font-bold">[2024-05-20 14:22:30]</span>
                <span className="text-green-700 font-black uppercase">Info</span>
                <span className="text-on-surface">Encrypted data tunnel re-established: Node 04 {'->'} Gateway Alpha</span>
              </div>
              <div className="flex gap-4 opacity-50 px-2 py-1 rounded hover:bg-primary/5 transition-colors">
                <span className="text-on-surface-variant font-bold">[2024-05-20 14:22:45]</span>
                <span className="text-secondary font-black uppercase">Debug</span>
                <span className="text-on-surface-variant">Garbage collection completed in 0.45ms (Inference Engine)</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SystemSettingsPage;
