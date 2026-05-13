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
  entity_type?: string;
  entity_id?: string;
}

const AuditLogsPage = () => {
  const [activityLogs, setActivityLogs] = useState<FrontendLog[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedLogId, setSelectedLogId] = useState<string | null>(null);
  const [logDetail, setLogDetail] = useState<any>(null);
  const [isDetailLoading, setIsDetailLoading] = useState(false);

  useEffect(() => {
    const fetchLogs = async () => {
      setIsLoading(true);
      setError(null);
      try {
        // 1단계: 모든 에이전트 목록 조회
        const agentsRes = await api.get('/api/agents');
        const agents = agentsRes.data || [];

        // 2단계: 각 에이전트의 감사 로그 병렬 조회
        const auditPromises = agents.map((agent: any) => 
          api.get(`/api/agents/${agent.id}/audit`).catch(err => {
            console.warn(`Failed to fetch audits for agent ${agent.id}`, err);
            return { data: { query_audits: [], response_audits: [] } };
          })
        );
        
        const auditResults = await Promise.all(auditPromises);

        // 3단계: 모든 에이전트의 질의/응답 로그 통합 및 포맷팅
        const allLogs: FrontendLog[] = [];
        
        auditResults.forEach((res: any, index: number) => {
          const agent = agents[index];
          const data = res.data;

          // 질의 로그 매핑
          data.query_audits?.forEach((q: any) => {
            allLogs.push({
              id: q.audit_id,
              run_id: q.audit_id.slice(0, 8).toUpperCase(),
              agent: agent.name,
              user: 'Admin', 
              time: new Date(q.created_at).toLocaleString('ko-KR'),
              compliance: q.risk_score !== undefined ? Math.round((1 - q.risk_score) * 100) : 100,
              status: q.status === 'Blocked' ? 'Blocked' : q.status === 'Warned' ? 'Warning' : 'Passed',
              created_at: q.created_at,
              rawContext: q,
              entity_type: 'query',
              entity_id: q.audit_id
            });
          });

          // 응답 로그 매핑
          data.response_audits?.forEach((r: any) => {
            allLogs.push({
              id: r.audit_id,
              run_id: r.audit_id.slice(0, 8).toUpperCase(),
              agent: agent.name,
              user: 'Admin',
              time: new Date(r.created_at).toLocaleString('ko-KR'),
              compliance: r.compliance_score !== undefined ? Math.round(r.compliance_score * 100) : 100,
              status: r.status === 'Blocked' ? 'Blocked' : r.status === 'Warned' ? 'Warning' : 'Passed',
              created_at: r.created_at,
              rawContext: r,
              entity_type: 'response',
              entity_id: r.audit_id
            });
          });
        });

        // 4단계: 최신순 정렬
        allLogs.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
        
        const finalLogs = allLogs.slice(0, 100);
        setActivityLogs(finalLogs);
        if (finalLogs.length > 0 && !selectedLogId) {
          setSelectedLogId(finalLogs[0].id);
        }
      } catch (err: any) {
        console.error('Audit aggregation failed', err);
        setError('감사 로그 통합 조회에 실패했습니다.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchLogs();
  }, []);

  useEffect(() => {
    const fetchDetail = async () => {
      if (!selectedLogId) {
        setLogDetail(null);
        return;
      }

      const selected = activityLogs.find(log => log.id === selectedLogId);
      if (!selected) return;

      setIsDetailLoading(true);
      try {
        let detailRes;
        if (selected.entity_type === 'query') {
          detailRes = await api.get(`/v1/audit/query/${selected.id}`);
        } else if (selected.entity_type === 'response') {
          detailRes = await api.get(`/v1/audit/response/${selected.id}`);
        } else {
          setLogDetail(selected.rawContext);
          setIsDetailLoading(false);
          return;
        }
        setLogDetail(detailRes.data);
      } catch (err) {
        console.warn('Detail fetch failed', err);
        setLogDetail(selected.rawContext);
      } finally {
        setIsDetailLoading(false);
      }
    };

    fetchDetail();
  }, [selectedLogId, activityLogs]);

  const selectedLog = activityLogs.find(log => log.id === selectedLogId);

  return (
    <div className="flex flex-col gap-8 animate-in fade-in slide-in-from-top-4 duration-500 pb-12">
      <div className="flex justify-between items-end border-b border-outline-variant/30 pb-8">
        <div>
          <h1 className="text-3xl font-black text-on-surface tracking-tighter font-display uppercase">감사 및 트레이스 로그</h1>
          <p className="text-on-surface-variant font-medium mt-1 uppercase tracking-widest text-[10px] opacity-60">에이전트 상호작용에 대한 전체 불변 기록</p>
        </div>
        <div className="flex gap-2">
           <button className="h-10 px-6 bg-primary text-on-primary font-black text-[10px] uppercase tracking-widest rounded-xl hover:brightness-110 shadow-lg shadow-primary/20 transition-all flex items-center gap-2">
              <Download className="w-3.5 h-3.5" /> 감사 보고서 내보내기
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
            <div className="px-6 py-4 border-b border-outline-variant/30 flex justify-between items-center bg-surface-container-low/30">
               <span className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">활동 스트림 (최근 100건)</span>
            </div>
            <div className="flex-1 overflow-auto custom-scrollbar">
               {activityLogs.length > 0 ? (
                <table className="w-full text-left">
                  <thead>
                    <tr className="bg-surface-container-low/50 text-[9px] font-black uppercase tracking-widest text-on-surface-variant sticky top-0 z-10">
                      <th className="px-5 py-3">실행 ID / 트레이스</th>
                      <th className="px-4 py-3">에이전트</th>
                      <th className="px-4 py-3">사용자</th>
                      <th className="px-4 py-3">준수율</th>
                      <th className="px-5 py-3 text-right">상태</th>
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
                        <td className="px-5 py-3">
                           <div className="flex flex-col">
                              <span className="font-mono text-[11px] font-black text-primary tracking-tight">#{log.run_id.slice(0,10)}</span>
                              <span className="text-[9px] text-on-surface-variant/60 font-bold uppercase tracking-tight">{log.time}</span>
                           </div>
                        </td>
                        <td className="px-4 py-3 text-xs font-bold text-on-surface tracking-tight truncate max-w-[140px]">{log.agent}</td>
                        <td className="px-4 py-3 text-[10px] font-medium text-on-surface-variant font-mono truncate max-w-[100px]">{log.user}</td>
                        <td className="px-4 py-3">
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
                        <td className="px-5 py-3 text-right">
                          <span className={cn(
                             "text-[9px] font-black uppercase tracking-normal whitespace-nowrap min-w-[46px] inline-block text-center px-2 py-0.5 rounded-lg border",
                             log.status === 'Passed' ? "bg-primary/5 text-primary border-primary/10" : 
                             log.status === 'Blocked' ? "bg-error/5 text-error border-error/10" : 
                             "bg-amber-50 text-amber-600 border-amber-200"
                           )}>
                             {log.status === 'Passed' ? '통과' : log.status === 'Blocked' ? '차단' : '주의'}
                           </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
               ) : (
                <div className="h-full flex flex-col items-center justify-center p-20 gap-4 opacity-30">
                   <Clock className="w-12 h-12" />
                   <span className="text-xs font-black uppercase tracking-widest">활동 내역을 찾을 수 없습니다</span>
                </div>
               )}
            </div>
          </div>

          {/* Trace Inspector Sidebar */}
          <div className="lg:col-span-4 flex flex-col gap-6">
            <div className="bg-white p-8 rounded-[2.5rem] border border-outline-variant shadow-xl shadow-primary/5 flex flex-col gap-8 sticky top-24">
               <div>
                  <h3 className="text-[10px] font-black uppercase tracking-[0.3em] text-primary mb-2">상세 로그 추적</h3>
                  <p className="text-lg font-black text-on-surface tracking-tighter">#{selectedLog?.run_id.slice(0, 14) || '선택된 로그 없음'}</p>
               </div>

               {selectedLog ? (
                 <div className="space-y-8 animate-in fade-in duration-500">
                    {isDetailLoading ? (
                       <div className="flex flex-col items-center justify-center py-20 gap-4 opacity-50">
                          <Loader2 className="w-8 h-8 animate-spin text-primary" />
                          <p className="text-[10px] font-black uppercase tracking-widest">상세 정보 불러오는 중...</p>
                       </div>
                    ) : (
                       <>
                        <div className="space-y-4">
                           <label className="flex items-center gap-2 text-[10px] font-black text-on-surface-variant uppercase tracking-widest opacity-60">
                              <Fingerprint className="w-3.5 h-3.5" /> 상호작용 컨텍스트
                           </label>
                           <div className="p-5 bg-surface-container-low rounded-2xl border border-outline-variant/30 space-y-4">
                              <div>
                                <span className="text-[9px] font-black uppercase tracking-widest opacity-40">사용자 질문</span>
                                <p className="text-xs font-bold leading-relaxed mt-1 text-on-surface italic">
                                   "{logDetail?.query || logDetail?.masked_query || '질문 데이터 없음'}"
                                </p>
                              </div>
                              {logDetail?.response && (
                                <div className="pt-4 border-t border-outline-variant/30">
                                  <span className="text-[9px] font-black uppercase tracking-widest text-secondary">AI 응답</span>
                                  <p className="text-xs font-medium leading-relaxed mt-1 text-on-surface">
                                     {logDetail.response}
                                  </p>
                                </div>
                              )}
                              <div className="pt-4 border-t border-outline-variant/30">
                                <span className="text-[9px] font-black uppercase tracking-widest text-primary">비식별화된 트레이스 (PII Masked)</span>
                                <p className="text-xs font-mono leading-relaxed mt-2 text-primary bg-primary/5 p-3 rounded-xl border border-primary/10 overflow-x-auto">
                                   {logDetail?.masked_query || '[민감 정보가 감지되지 않았습니다]'}
                                </p>
                              </div>
                           </div>
                        </div>

                        <div className="space-y-4">
                           <label className="flex items-center gap-2 text-[10px] font-black text-on-surface-variant uppercase tracking-widest opacity-60">
                              <ShieldAlert className="w-3.5 h-3.5" /> 가드레일 검증 결과
                           </label>
                           <div className="grid grid-cols-2 gap-4">
                              <div className="p-4 bg-white border border-outline-variant rounded-2xl text-center shadow-sm">
                                 <span className="text-[9px] font-black uppercase tracking-widest opacity-40">최종 판정</span>
                                 <p className={cn("text-sm font-black mt-1", (logDetail?.status || selectedLog.status) === 'Blocked' ? "text-error" : "text-primary")}>
                                    {(logDetail?.status || selectedLog.status).toUpperCase()}
                                 </p>
                              </div>
                              <div className="p-4 bg-white border border-outline-variant rounded-2xl text-center shadow-sm">
                                 <span className="text-[9px] font-black uppercase tracking-widest opacity-40">위험도 점수</span>
                                 <p className="text-sm font-black text-on-surface mt-1">
                                    {logDetail?.risk_score !== undefined ? (logDetail.risk_score * 100).toFixed(1) : logDetail?.compliance_score !== undefined ? (logDetail.compliance_score * 100).toFixed(1) : '0.0'}%
                                 </p>
                              </div>
                           </div>
                        </div>

                        {(logDetail?.risk_reasons?.length > 0 || logDetail?.violations?.length > 0) && (
                          <div className="space-y-2">
                            <span className="text-[10px] font-black text-error uppercase tracking-widest ml-1">거부 / 정책 위반 상세 사유</span>
                            <div className="p-4 bg-error/5 border border-error/10 rounded-2xl text-xs font-medium text-error leading-relaxed italic space-y-2">
                               {logDetail.risk_reasons?.map((r: string, i: number) => (
                                 <p key={i}>• {r}</p>
                               ))}
                               {logDetail.violations?.map((v: any, i: number) => (
                                 <p key={i}>• {v.reason || v.type || '정책 위반이 감지되었습니다'}</p>
                               ))}
                            </div>
                          </div>
                        )}
                       </>
                    )}

                    <div className="flex gap-2 pt-4">
                       <button className="flex-1 h-12 flex items-center justify-center gap-2 bg-on-surface text-white font-black text-[10px] uppercase tracking-widest rounded-2xl hover:brightness-110 transition-all shadow-lg shadow-on-surface/20">
                          <Share2 className="w-3.5 h-3.5" /> 보고서 공유
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
