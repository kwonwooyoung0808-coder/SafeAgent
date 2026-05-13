import React, { useState, useEffect } from 'react';
import { 
  Search, 
  RotateCcw, 
  CheckCircle2, 
  Download,
  Share2,
  Database,
  Fingerprint,
  Loader2,
  AlertCircle,
  Clock,
  ShieldAlert
} from 'lucide-react';
import { cn } from '../lib/utils';
import { api } from '../lib/api';

// 프론트엔드 UI용 Log 타입 (기존 구조 완벽 보존용)
interface FrontendLog {
  id: string;
  run_id: string;
  agent: string;
  user: string;
  time: string;
  compliance: number;
  status: string;
  reason?: string;
  rawContext?: any;
}

const AuditLogsPage = () => {
  const [activityLogs, setActivityLogs] = useState<FrontendLog[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedLogId, setSelectedLogId] = useState<string | null>(null);

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        setError(null);
        // 백엔드: GET /api/v1/audit-logs
        const response = await api.get('/api/v1/audit-logs?limit=100');
        const data = response.data || [];

        const mappedLogs: FrontendLog[] = data.map((item: any) => {
          // 백엔드 event_type 기반 상태 및 점수 매핑
          let compliance = 100;
          let statusStr = 'Passed';
          
          if (item.event_type === 'BLOCKED') {
            compliance = 30; // 심각한 보안 위반
            statusStr = 'Blocked';
          } else if (item.event_type === 'WARNING') {
            compliance = 75; // 주의 필요
            statusStr = 'Warning';
          }

          // context 가 문자열일 경우 파싱 시도 (백엔드 구조 대응)
          let ctx = item.context;
          if (typeof ctx === 'string') {
            try { ctx = JSON.parse(ctx); } catch(e) {}
          }

          return {
            id: item.id || 'EV-UNK',
            run_id: item.run_id || 'TR-UNK',
            agent: item.entity_id || ctx?.agent_id || 'SYSTEM',
            user: ctx?.username || ctx?.user_id || 'SYSTEM',
            time: new Date(item.created_at).toLocaleString('ko-KR'),
            compliance,
            status: statusStr,
            reason: item.reason,
            rawContext: ctx
          };
        });

        setActivityLogs(mappedLogs);
        if (mappedLogs.length > 0) {
          setSelectedLogId(mappedLogs[0].id);
        }
      } catch (err: any) {
        console.error('Failed to fetch audit logs', err);
        setError("감사 로그를 불러오지 못했습니다. (권한 오류 또는 서버 연결 확인)");
      } finally {
        setIsLoading(false);
      }
    };

    fetchLogs();
  }, []);

  const selectedLog = activityLogs.find(log => log.id === selectedLogId);

  return (
    <div className="flex flex-col gap-8 animate-in fade-in slide-in-from-top-4 duration-500 pb-12">
      <div className="flex justify-between items-end border-b border-outline-variant/30 pb-8">
        <div>
          <h1 className="text-3xl font-black text-on-surface tracking-tighter font-display uppercase">Audit & Trace Logs</h1>
          <p className="text-on-surface-variant font-medium mt-1 uppercase tracking-widest text-[10px] opacity-60">Full-spectrum Immutable record of agent interactions</p>
        </div>
        <div className="flex gap-2">
           <button className="h-10 px-6 bg-primary text-on-primary font-black text-[10px] uppercase tracking-widest rounded-xl hover:brightness-110 shadow-lg shadow-primary/20 transition-all flex items-center gap-2">
              <Download className="w-3.5 h-3.5" /> Export Audit Report
           </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center items-center h-[500px] w-full">
          <Loader2 className="w-12 h-12 text-primary animate-spin" />
        </div>
      ) : error ? (
        <div className="bg-surface-container-high p-20 rounded-[2.5rem] text-center flex flex-col items-center gap-4">
           <AlertCircle className="w-12 h-12 text-on-surface-variant/20" />
           <p className="text-on-surface-variant font-bold">{error}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 min-h-[600px]">
          {/* Main Logs Table */}
          <div className="lg:col-span-8 bg-white rounded-[2.5rem] border border-outline-variant shadow-sm overflow-hidden flex flex-col">
            <div className="px-8 py-5 border-b border-outline-variant/30 flex justify-between items-center bg-surface-container-low/30">
               <span className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">Activity Stream (Latest 100)</span>
               <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
                  <span className="text-[9px] font-black text-on-surface-variant uppercase tracking-widest">Live Updates</span>
               </div>
            </div>
            <div className="flex-1 overflow-auto custom-scrollbar">
               {activityLogs.length > 0 ? (
                <table className="w-full text-left">
                  <thead>
                    <tr className="bg-surface-container-low/50 text-[9px] font-black uppercase tracking-widest text-on-surface-variant sticky top-0 z-10">
                      <th className="px-8 py-4">Run ID / Trace</th>
                      <th className="px-8 py-4">Agent</th>
                      <th className="px-8 py-4">User</th>
                      <th className="px-8 py-4">Compliance</th>
                      <th className="px-8 py-4 text-right">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-outline-variant/10">
                    {activityLogs.map((log) => (
                      <tr 
                        key={log.id} 
                        onClick={() => setSelectedLogId(log.id)}
                        className={cn(
                          "cursor-pointer transition-all hover:bg-primary/5 group",
                          selectedLogId === log.id && "bg-primary/5 border-l-4 border-primary"
                        )}
                      >
                        <td className="px-8 py-5">
                           <div className="flex flex-col">
                              <span className="font-mono text-xs font-black text-primary tracking-tight">#{log.run_id.slice(0,10)}</span>
                              <span className="text-[9px] text-on-surface-variant/60 font-bold uppercase tracking-widest">{log.time}</span>
                           </div>
                        </td>
                        <td className="px-8 py-5 text-xs font-bold text-on-surface tracking-tight truncate max-w-[120px]">{log.agent}</td>
                        <td className="px-8 py-5 text-[11px] font-medium text-on-surface-variant font-mono truncate max-w-[120px]">{log.user}</td>
                        <td className="px-8 py-5">
                          <div className="flex items-center gap-3">
                            <div className="w-24 h-1.5 bg-surface-container-highest rounded-full overflow-hidden shadow-inner">
                              <div 
                                className={cn("h-full transition-all duration-1000", log.compliance > 90 ? "bg-primary" : log.compliance > 60 ? "bg-amber-500" : "bg-error")} 
                                style={{ width: `${log.compliance}%` }} 
                              />
                            </div>
                            <span className={cn("text-[10px] font-black tracking-widest", log.compliance > 90 ? "text-primary" : log.compliance > 60 ? "text-amber-600" : "text-error")}>
                              {log.compliance}%
                            </span>
                          </div>
                        </td>
                        <td className="px-8 py-5 text-right">
                          <span className={cn(
                            "text-[9px] font-black uppercase tracking-widest px-2.5 py-1 rounded-lg border",
                            log.status === 'Passed' ? "bg-primary/5 text-primary border-primary/10" : 
                            log.status === 'Blocked' ? "bg-error/5 text-error border-error/10" : 
                            "bg-amber-50 text-amber-600 border-amber-200"
                          )}>
                            {log.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
               ) : (
                <div className="h-full flex flex-col items-center justify-center p-20 gap-4 opacity-30">
                   <Clock className="w-12 h-12" />
                   <span className="text-xs font-black uppercase tracking-widest">No activity sequences found</span>
                </div>
               )}
            </div>
          </div>

          {/* Trace Inspector Sidebar */}
          <div className="lg:col-span-4 flex flex-col gap-6">
            <div className="bg-white p-8 rounded-[2.5rem] border border-outline-variant shadow-xl shadow-primary/5 flex flex-col gap-8 sticky top-24">
               <div>
                  <h3 className="text-[10px] font-black uppercase tracking-[0.3em] text-primary mb-2">Trace Inspector</h3>
                  <p className="text-lg font-black text-on-surface tracking-tighter">#{selectedLog?.run_id.slice(0, 14) || 'NO_RUN_SELECTED'}</p>
               </div>

               {selectedLog ? (
                 <div className="space-y-8 animate-in fade-in duration-500">
                    <div className="space-y-4">
                       <label className="flex items-center gap-2 text-[10px] font-black text-on-surface-variant uppercase tracking-widest opacity-60">
                          <Fingerprint className="w-3.5 h-3.5" /> Interaction Context
                       </label>
                       <div className="p-5 bg-surface-container-low rounded-2xl border border-outline-variant/30 space-y-4">
                          <div>
                            <span className="text-[9px] font-black uppercase tracking-widest opacity-40">User Query</span>
                            <p className="text-xs font-bold leading-relaxed mt-1 text-on-surface italic">
                               "{selectedLog.rawContext?.query || 'Query data unavailable'}"
                            </p>
                          </div>
                          <div className="pt-4 border-t border-outline-variant/30">
                            <span className="text-[9px] font-black uppercase tracking-widest text-primary">PII Masked Trace</span>
                            <p className="text-xs font-mono leading-relaxed mt-2 text-primary bg-primary/5 p-3 rounded-xl border border-primary/10">
                               {selectedLog.rawContext?.masked_query || '[NO_PII_SENSITIVE_DATA_RECORDED]'}
                            </p>
                          </div>
                       </div>
                    </div>

                    <div className="space-y-4">
                       <label className="flex items-center gap-2 text-[10px] font-black text-on-surface-variant uppercase tracking-widest opacity-60">
                          <ShieldAlert className="w-3.5 h-3.5" /> Guard Verification
                       </label>
                       <div className="grid grid-cols-2 gap-4">
                          <div className="p-4 bg-white border border-outline-variant rounded-2xl text-center">
                             <span className="text-[9px] font-black uppercase tracking-widest opacity-40">Verdict</span>
                             <p className={cn("text-sm font-black mt-1", selectedLog.status === 'Blocked' ? "text-error" : "text-primary")}>
                                {selectedLog.status.toUpperCase()}
                             </p>
                          </div>
                          <div className="p-4 bg-white border border-outline-variant rounded-2xl text-center">
                             <span className="text-[9px] font-black uppercase tracking-widest opacity-40">Confidence</span>
                             <p className="text-sm font-black text-on-surface mt-1">98.4%</p>
                          </div>
                       </div>
                    </div>

                    {selectedLog.reason && (
                      <div className="space-y-2">
                        <span className="text-[10px] font-black text-error uppercase tracking-widest ml-1">Refusal Reason</span>
                        <div className="p-4 bg-error/5 border border-error/10 rounded-2xl text-xs font-medium text-error leading-relaxed italic">
                           "{selectedLog.reason}"
                        </div>
                      </div>
                    )}

                    <div className="flex gap-2 pt-4">
                       <button className="flex-1 h-12 flex items-center justify-center gap-2 bg-on-surface text-white font-black text-[10px] uppercase tracking-widest rounded-2xl hover:brightness-110 transition-all shadow-lg shadow-on-surface/20">
                          <Share2 className="w-3.5 h-3.5" /> Share Report
                       </button>
                    </div>
                 </div>
               ) : (
                 <div className="flex flex-col items-center justify-center py-20 opacity-20 gap-4">
                    <Database className="w-12 h-12" />
                    <p className="text-xs font-bold uppercase tracking-widest text-center">실행 로그를 선택하여<br/>상세 내역을 확인하세요</p>
                 </div>
               )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AuditLogsPage;
