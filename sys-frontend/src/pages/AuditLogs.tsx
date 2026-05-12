import React, { useState, useEffect } from 'react';
import { 
  Search, 
  RotateCcw, 
  ChevronRight, 
  CheckCircle2, 
  ShieldAlert, 
  AlertTriangle,
  Download,
  Share2,
  Database,
  Lock,
  Cpu,
  Fingerprint,
  Loader2
} from 'lucide-react';
import { cn } from '@/src/lib/utils';
import { api } from '@/src/lib/api';

// 프론트엔드 UI용 Log 타입 (기존 구조 완벽 보존용)
interface FrontendLog {
  id: string;
  agent: string;
  user: string;
  time: string;
  compliance: number;
  status: string;
  rawContext?: any;
}

const AuditLogsPage = () => {
  const [activityLogs, setActivityLogs] = useState<FrontendLog[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedLogId, setSelectedLogId] = useState<string | null>(null);

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        // 실제 백엔드 감사 로그 호출 (시스템 감사 로그)
        const response = await api.get('/audit-logs');
        const data = response.data || [];

        const mappedLogs: FrontendLog[] = data.map((item: any) => {
          // 백엔드 이벤트 기반 가상 컴플라이언스 및 상태 매핑 (어댑터 패턴)
          let compliance = 100;
          let status = 'Passed';
          
          if (item.event_type === 'BLOCKED' || (item.reason && item.reason.toLowerCase().includes('violation'))) {
            compliance = Math.floor(Math.random() * 30) + 20; // 20~50
            status = 'Blocked';
          } else if (item.event_type === 'WARNING' || item.event_type === 'POLICY_UPDATED') {
            compliance = Math.floor(Math.random() * 20) + 70; // 70~90
            status = 'Warning';
          } else {
            compliance = Math.floor(Math.random() * 10) + 90; // 90~100
          }

          return {
            id: item.run_id || item.id || 'TR-UNKNOWN',
            agent: item.entity_type === 'AGENT' ? item.entity_id : (item.context?.agent_id || 'SYS-BOT'),
            user: item.context?.user_id || item.context?.username || 'SYSTEM_AUTH',
            time: new Date(item.created_at).toLocaleString('ko-KR'),
            compliance,
            status,
            rawContext: item.context
          };
        });

        setActivityLogs(mappedLogs);
        if (mappedLogs.length > 0) {
          setSelectedLogId(mappedLogs[0].id); // 첫 번째 항목 기본 선택
        }
      } catch (error) {
        console.error('Failed to fetch audit logs', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchLogs();
  }, []);

  const selectedLog = activityLogs.find(log => log.id === selectedLogId) || activityLogs[0];

  return (
    <div className="flex flex-col gap-8 animate-in fade-in slide-in-from-top-4 duration-500">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold text-primary font-display tracking-tight">Audit & Trace Logs</h1>
          <p className="text-on-surface-variant font-medium mt-1">Real-time surveillance and immutable record of agent-user interactions.</p>
        </div>
      </div>

      {/* Filter Section (UI 구조 유지) */}
      <div className="glass-panel p-6 rounded-2xl grid grid-cols-1 md:grid-cols-4 gap-6 items-end">
        <div className="space-y-2">
          <label className="text-[10px] font-black uppercase tracking-widest text-primary/60">Trace ID</label>
          <input className="w-full h-10 px-4 bg-white border border-outline-variant/30 rounded-xl outline-none focus:ring-1 focus:ring-primary text-sm font-medium" placeholder="TR-8829-01..." />
        </div>
        <div className="space-y-2">
          <label className="text-[10px] font-black uppercase tracking-widest text-primary/60">Agent ID</label>
          <input className="w-full h-10 px-4 bg-white border border-outline-variant/30 rounded-xl outline-none focus:ring-1 focus:ring-primary text-sm font-medium" placeholder="AGENT_FINANCE_01" />
        </div>
        <div className="space-y-2">
          <label className="text-[10px] font-black uppercase tracking-widest text-primary/60">Date Range</label>
          <input type="date" className="w-full h-10 px-4 bg-white border border-outline-variant/30 rounded-xl outline-none focus:ring-1 focus:ring-primary text-sm font-medium" />
        </div>
        <div className="flex gap-3">
          <button className="flex-1 h-10 flex items-center justify-center gap-2 bg-primary text-on-primary font-bold text-sm rounded-xl hover:brightness-110 shadow-lg shadow-primary/20 transition-all">
            <Search className="w-4 h-4" />
            Search
          </button>
          <button className="h-10 px-4 bg-white border border-outline-variant/40 rounded-xl hover:bg-surface-container transition-colors text-primary shadow-sm">
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center items-center h-64 w-full">
          <Loader2 className="w-10 h-10 text-primary animate-spin" />
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 min-h-[500px]">
          {/* Table View */}
          <div className="lg:col-span-8 glass-panel rounded-2xl overflow-hidden flex flex-col border border-outline-variant/20 shadow-lg">
            <div className="px-6 py-4 bg-surface-container-low/50 border-b border-outline-variant/30 flex justify-between items-center">
              <span className="text-[11px] font-black uppercase tracking-widest text-primary">Activity Log Streams</span>
              <div className="flex items-center gap-2 bg-primary/5 px-2 py-0.5 rounded-full border border-primary/20">
                <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse"></div>
                <span className="text-[9px] font-black uppercase tracking-widest text-primary">Live Monitor</span>
              </div>
            </div>
            <div className="flex-1 overflow-auto custom-scrollbar">
              <table className="w-full text-left">
                <thead>
                  <tr className="bg-surface-container-low text-[10px] font-black uppercase tracking-widest text-on-surface-variant sticky top-0 z-10">
                    <th className="px-6 py-4">Trace ID</th>
                    <th className="px-6 py-4">Agent ID</th>
                    <th className="px-6 py-4">User</th>
                    <th className="px-6 py-4">Compliance</th>
                    <th className="px-6 py-4">Status</th>
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
                      <td className="px-6 py-5 font-mono text-xs font-bold text-primary truncate max-w-[120px]">{log.id}</td>
                      <td className="px-6 py-5 text-xs font-bold text-on-surface tracking-tight truncate max-w-[120px]">{log.agent}</td>
                      <td className="px-6 py-5 text-[11px] font-medium text-on-surface-variant font-mono truncate max-w-[150px]">{log.user}</td>
                      <td className="px-6 py-5">
                        <div className="flex items-center gap-3">
                          <div className="w-24 h-1.5 bg-surface-container-highest rounded-full overflow-hidden">
                            <div 
                              className={cn("h-full", log.compliance > 90 ? "bg-green-600" : log.compliance > 60 ? "bg-amber-500" : "bg-error")} 
                              style={{ width: `${log.compliance}%` }} 
                            />
                          </div>
                          <span className={cn("text-[10px] font-black tracking-widest", log.compliance > 90 ? "text-green-700" : log.compliance > 60 ? "text-amber-600" : "text-error")}>
                            {log.compliance}%
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-5">
                        <span className={cn(
                          "text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded border",
                          log.status === 'Passed' ? "bg-green-100 text-green-700 border-green-200" : 
                          log.status === 'Blocked' ? "bg-error-container text-error border-error-200" : 
                          "bg-amber-100 text-amber-700 border-amber-200"
                        )}>
                          {log.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Trace Inspector Panel (구조와 UI 완벽 유지, 선택된 ID만 반영) */}
          <div className="lg:col-span-4 flex flex-col gap-6">
            <div className="glass-panel p-6 rounded-2xl border-l-4 border-primary shadow-xl shadow-primary/5 flex flex-col gap-6">
              <div className="flex items-center justify-between border-b border-outline-variant/30 pb-4">
                <h3 className="text-xs font-black uppercase tracking-[0.2em] text-primary truncate">Trace Inspector: {selectedLog?.id || 'NO SELECTION'}</h3>
              </div>

              <div className="space-y-5">
                {/* Input Guard */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-primary">
                    <Fingerprint className="w-4 h-4" />
                    <span className="text-[10px] font-black uppercase tracking-widest">F1 Input Guard Results</span>
                  </div>
                  <div className="p-3 bg-surface-container-low/50 rounded-xl border border-outline-variant/30 space-y-2">
                    <span className="text-[9px] font-black uppercase tracking-widest text-primary/60">Original Query</span>
                    <p className="font-mono text-[11px] text-on-surface leading-normal italic">
                      "What is the SSN and direct deposit info for employee ID #4421?"
                    </p>
                  </div>
                  <div className="p-3 bg-primary-container/5 rounded-xl border border-primary/10 space-y-2">
                    <span className="text-[9px] font-black uppercase tracking-widest text-primary/60">PII Masked Query</span>
                    <p className="font-mono text-[11px] text-on-surface leading-normal">
                      "What is the <span className="bg-primary/10 text-primary px-1 rounded font-bold border border-primary/20">[HIDDEN_SSN]</span> and direct deposit info for employee ID <span className="bg-primary/10 text-primary px-1 rounded font-bold border border-primary/20">[HIDDEN_ID]</span>?"
                    </p>
                  </div>
                </div>

                {/* Response Guard */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-primary">
                    <CheckCircle2 className="w-4 h-4" />
                    <span className="text-[10px] font-black uppercase tracking-widest">F2 Response Guard Results</span>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 bg-white border border-outline-variant/20 rounded-xl text-center">
                      <span className="text-[9px] font-black uppercase tracking-widest text-on-surface-variant">Safety Check</span>
                      <p className="text-sm font-black text-green-600 mt-1 uppercase">
                        {selectedLog?.status === 'Blocked' ? 'BLOCKED' : 'SECURE'}
                      </p>
                    </div>
                    <div className="p-3 bg-white border border-outline-variant/20 rounded-xl text-center">
                      <span className="text-[9px] font-black uppercase tracking-widest text-on-surface-variant">Compliance</span>
                      <p className="text-sm font-black text-primary mt-1 uppercase">{selectedLog?.compliance || 98.4}%</p>
                    </div>
                  </div>
                </div>

                {/* System Metadata */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-primary/70">
                    <Database className="w-4 h-4" />
                    <span className="text-[10px] font-black uppercase tracking-widest">System Metadata</span>
                  </div>
                  <div className="p-3 bg-surface-container-low/30 rounded-xl border border-outline-variant/20 text-[10px] font-mono space-y-2">
                    <div className="flex justify-between">
                      <span className="text-on-surface-variant font-bold uppercase tracking-widest">Pipeline Version</span>
                      <span className="text-on-surface">v4.2.0-stable</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-on-surface-variant font-bold uppercase tracking-widest">Total Latency</span>
                      <span className="text-green-600 font-bold uppercase tracking-widest">142ms</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-on-surface-variant font-bold uppercase tracking-widest">Inference Node</span>
                      <span className="text-on-surface">us-east-shrd-02</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex gap-2 pt-4">
                <button className="flex-1 h-10 flex items-center justify-center gap-2 bg-primary text-on-primary font-bold text-xs rounded-xl hover:brightness-110 transition-all uppercase tracking-widest shadow-lg shadow-primary/20">
                  <Download className="w-4 h-4" />
                  Download PDF
                </button>
                <button className="h-10 px-4 glass-panel hover:bg-surface-container transition-colors rounded-xl text-primary font-bold">
                  <Share2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AuditLogsPage;
