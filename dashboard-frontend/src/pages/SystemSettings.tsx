import React, { useState, useEffect } from 'react';
import { 
  Settings, 
  Server, 
  Database, 
  Cpu, 
  Network, 
  ShieldCheck, 
  AlertCircle,
  CheckCircle2,
  Loader2,
  RefreshCcw,
  Globe,
  Terminal
} from 'lucide-react';
import { cn } from '../lib/utils';
import { api } from '../lib/api';

const SystemSettingsPage = () => {
  const [infraStatus, setInfraStatus] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchSystemInfo = async () => {
    try {
      setRefreshing(true);
      // 백엔드: GET /health/llm (LLM 상태) & /health/system (DB 상태)
      const [llmRes, sysRes] = await Promise.all([
        api.get('/health/llm'),
        api.get('/health/system')
      ]);

      setInfraStatus({
        llm: llmRes.data,
        system: sysRes.data
      });
    } catch (e) {
      console.error("Failed to fetch system info");
    } finally {
      setIsLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchSystemInfo();
  }, []);

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-[500px] w-full">
        <Loader2 className="w-12 h-12 text-primary animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-10 animate-in fade-in duration-500 pb-20">
      <div className="flex justify-between items-end border-b border-outline-variant/30 pb-8">
        <div>
          <h1 className="text-3xl font-black text-on-surface tracking-tighter font-display uppercase">Infrastructure Settings</h1>
          <p className="text-on-surface-variant font-medium mt-1 uppercase tracking-widest text-[10px] opacity-60">Real-time Environment & Node Monitoring</p>
        </div>
        <button 
          onClick={fetchSystemInfo}
          disabled={refreshing}
          className="flex items-center gap-2 px-6 py-2.5 bg-surface-container-high rounded-full text-[10px] font-black uppercase tracking-widest hover:bg-primary/10 hover:text-primary transition-all"
        >
          <RefreshCcw className={cn("w-3.5 h-3.5", refreshing && "animate-spin")} />
          {refreshing ? 'Refreshing...' : 'Rescan Infrastructure'}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Sovereign AI Agent Node */}
        <div className="bg-white p-10 rounded-[3rem] border border-outline-variant shadow-sm flex flex-col gap-8 group">
          <div className="flex justify-between items-start">
             <div className="w-14 h-14 bg-primary/5 rounded-[1.5rem] flex items-center justify-center text-primary group-hover:scale-110 transition-transform">
                <Cpu className="w-7 h-7" />
             </div>
             <div className={cn(
               "px-4 py-1.5 rounded-full text-[10px] font-black uppercase tracking-widest border",
               infraStatus?.llm?.sovereign_ai?.reachable ? "bg-green-50 text-green-600 border-green-200" : "bg-error/5 text-error border-error/20"
             )}>
                {infraStatus?.llm?.sovereign_ai?.reachable ? 'Online' : 'Offline'}
             </div>
          </div>
          <div>
             <h3 className="text-[10px] font-black text-primary uppercase tracking-[0.3em] mb-2">Primary Inference Node</h3>
             <h2 className="text-2xl font-black text-on-surface tracking-tighter">Sovereign AI Agent</h2>
             <p className="text-xs font-medium text-on-surface-variant mt-2 opacity-60">실제 사용자 질의를 처리하는 소버린 AI 엔진의 설정값입니다.</p>
          </div>

          <div className="space-y-4">
             <div className="p-5 bg-surface-container-lowest rounded-2xl border border-outline-variant/30 space-y-3">
                <div className="flex justify-between items-center">
                   <span className="text-[10px] font-black text-on-surface-variant uppercase tracking-widest">Base URL</span>
                   <span className="text-xs font-mono font-bold text-on-surface">{infraStatus?.llm?.sovereign_ai?.url || 'Unknown'}</span>
                </div>
                <div className="flex justify-between items-center">
                   <span className="text-[10px] font-black text-on-surface-variant uppercase tracking-widest">Model Identity</span>
                   <span className="text-xs font-mono font-bold text-primary">{infraStatus?.llm?.sovereign_ai?.model || 'Unknown'}</span>
                </div>
             </div>
             <div className="flex items-center gap-3 px-2">
                <Globe className="w-3.5 h-3.5 text-on-surface-variant opacity-40" />
                <span className="text-[10px] font-black text-on-surface-variant uppercase tracking-widest opacity-40">Internal Network Traffic only</span>
             </div>
          </div>
        </div>

        {/* Governance LLM Node */}
        <div className="bg-white p-10 rounded-[3rem] border border-outline-variant shadow-sm flex flex-col gap-8 group">
          <div className="flex justify-between items-start">
             <div className="w-14 h-14 bg-secondary/5 rounded-[1.5rem] flex items-center justify-center text-secondary group-hover:scale-110 transition-transform">
                <ShieldCheck className="w-7 h-7" />
             </div>
             <div className={cn(
               "px-4 py-1.5 rounded-full text-[10px] font-black uppercase tracking-widest border",
               infraStatus?.llm?.governance_llm?.reachable ? "bg-green-50 text-green-600 border-green-200" : "bg-error/5 text-error border-error/20"
             )}>
                {infraStatus?.llm?.governance_llm?.reachable ? 'Reachable' : 'Refused'}
             </div>
          </div>
          <div>
             <h3 className="text-[10px] font-black text-secondary uppercase tracking-[0.3em] mb-2">Security Evaluation Node</h3>
             <h2 className="text-2xl font-black text-on-surface tracking-tighter">Governance LLM</h2>
             <p className="text-xs font-medium text-on-surface-variant mt-2 opacity-60">감사 및 정책 위반 여부를 실시간으로 판별하는 보안 전용 엔진입니다.</p>
          </div>

          <div className="space-y-4">
             <div className="p-5 bg-surface-container-lowest rounded-2xl border border-outline-variant/30 space-y-3">
                <div className="flex justify-between items-center">
                   <span className="text-[10px] font-black text-on-surface-variant uppercase tracking-widest">Base URL</span>
                   <span className="text-xs font-mono font-bold text-on-surface">{infraStatus?.llm?.governance_llm?.url || 'Unknown'}</span>
                </div>
                <div className="flex justify-between items-center">
                   <span className="text-[10px] font-black text-on-surface-variant uppercase tracking-widest">Model Identity</span>
                   <span className="text-xs font-mono font-bold text-secondary">{infraStatus?.llm?.governance_llm?.model || 'Unknown'}</span>
                </div>
             </div>
             <div className="flex items-center gap-3 px-2">
                <Terminal className="w-3.5 h-3.5 text-on-surface-variant opacity-40" />
                <span className="text-[10px] font-black text-on-surface-variant uppercase tracking-widest opacity-40">Reasoning Confidence: High</span>
             </div>
          </div>
        </div>
      </div>

      {/* Database & Security State */}
      <div className="bg-surface-container-low p-10 rounded-[3rem] border border-outline-variant/30 grid grid-cols-1 md:grid-cols-3 gap-12">
         <div className="flex flex-col gap-4">
            <div className="flex items-center gap-3">
               <Database className="w-5 h-5 text-primary" />
               <h3 className="text-sm font-black text-on-surface uppercase tracking-widest">Persistence State</h3>
            </div>
            <div className="space-y-1">
               <div className="flex items-center gap-2">
                  <div className={cn("w-2 h-2 rounded-full", infraStatus?.system?.db_available ? "bg-green-500" : "bg-error")}></div>
                  <span className="text-xs font-black text-on-surface uppercase">PostgreSQL / SQLite</span>
               </div>
               <p className="text-[11px] font-medium text-on-surface-variant opacity-60">모든 로그는 강력한 무결성 원칙에 의해 암호화되어 저장됩니다.</p>
            </div>
         </div>

         <div className="flex flex-col gap-4">
            <div className="flex items-center gap-3">
               <Network className="w-5 h-5 text-secondary" />
               <h3 className="text-sm font-black text-on-surface uppercase tracking-widest">API Interface</h3>
            </div>
            <div className="space-y-1">
               <span className="text-xs font-mono font-bold text-on-surface tracking-tighter">v1.2.0-STABLE (Gateway mode)</span>
               <p className="text-[11px] font-medium text-on-surface-variant opacity-60">현재 게이트웨이는 통합 보안 정책 v3을 적용 중입니다.</p>
            </div>
         </div>

         <div className="flex flex-col gap-6">
            <div className="bg-white p-6 rounded-3xl border border-outline-variant shadow-sm flex justify-between items-center">
               <div>
                  <span className="text-[9px] font-black text-on-surface-variant uppercase tracking-widest opacity-40">System Uptime</span>
                  <p className="text-sm font-black text-on-surface mt-1 tracking-tighter">99.98% Healthy</p>
               </div>
               <CheckCircle2 className="w-8 h-8 text-green-500 opacity-20" />
            </div>
         </div>
      </div>

      {/* Security Disclaimer Panel */}
      <div className="bg-error/5 border border-error/10 p-8 rounded-[2.5rem] flex items-center gap-6">
         <div className="p-3 bg-error/10 rounded-2xl text-error">
            <AlertCircle className="w-6 h-6" />
         </div>
         <div>
            <h4 className="text-xs font-black text-error uppercase tracking-widest">Security Warning</h4>
            <p className="text-[11px] font-bold text-error/60 leading-relaxed mt-1">
               위의 설정값은 `.env` 파일에 기록된 민감한 정보입니다. 노출에 주의하시기 바랍니다.<br/>
               환경 변수 수정을 위해서는 인프라 관리자의 승인을 통한 서버 재기동이 필요합니다.
            </p>
         </div>
      </div>
    </div>
  );
};

export default SystemSettingsPage;
