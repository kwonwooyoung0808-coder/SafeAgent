import React, { useState, useEffect } from 'react';
import { 
  AlertTriangle, 
  Clock, 
  Shield, 
  MoreHorizontal, 
  ChevronRight,
  User,
  CheckCircle2,
  Loader2,
  AlertCircle
} from 'lucide-react';
import { cn } from '../lib/utils';
import { api } from '../lib/api';

// 프론트엔드 UI용 Report 타입 (기존 구조 완벽 보존용)
interface FrontendReport {
  id: string;
  column: string;
  severity: string;
  title: string;
  desc: string;
  time: string;
  layer: string;
  assignee: string | null;
  resolvedAt?: string;
  originalQuery?: string;
}

const ViolationReportsPage = () => {
  const [reports, setReports] = useState<FrontendReport[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchReports = async () => {
      try {
        setError(null);
        // 백엔드: GET /v1/violation-reports
        const response = await api.get('/v1/violation-reports');
        
        // 백엔드 응답은 { items: [], total: number } 형태
        const data = response.data.items || [];
        
        const mappedReports: FrontendReport[] = data.map((item: any) => {
          // 상태(status)를 칸반 컬럼으로 매핑
          let columnId = 'new';
          if (item.status === 'REVIEWING') columnId = 'reviewing';
          if (item.status === 'RESOLVED' || item.status === 'DISMISSED') columnId = 'resolved';

          const dateObj = new Date(item.created_at);
          const timeStr = dateObj.toLocaleString('ko-KR');

          return {
            id: item.id || 'SEC-UNKNOWN',
            column: columnId,
            severity: item.severity || 'HIGH',
            title: item.primary_category || 'Security Breach Detected',
            desc: item.summary || 'Summary not provided by system.',
            time: timeStr,
            layer: item.stage || 'GATEWAY',
            assignee: item.admin_note ? 'Assigned' : null,
            resolvedAt: item.resolved_at ? new Date(item.resolved_at).toLocaleString('ko-KR') : undefined,
            originalQuery: item.masked_query || item.original_query
          };
        });

        setReports(mappedReports);
      } catch (err: any) {
        console.error('Failed to fetch violation reports', err);
        setError("데이터를 불러오는데 실패했습니다. (인증 만료 또는 서버 오류)");
      } finally {
        setIsLoading(false);
      }
    };

    fetchReports();
  }, []);

  const columns = [
    { id: 'new', name: 'NEW', count: reports.filter(r => r.column === 'new').length, color: 'text-error' },
    { id: 'reviewing', name: 'REVIEWING', count: reports.filter(r => r.column === 'reviewing').length, color: 'text-amber-500' },
    { id: 'resolved', name: 'RESOLVED', count: reports.filter(r => r.column === 'resolved').length, color: 'text-green-600' },
  ];

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-[500px] w-full bg-surface-container-lowest">
        <Loader2 className="w-12 h-12 text-primary animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8 animate-in fade-in slide-in-from-bottom-4 duration-500 pb-12">
      <div className="flex items-end justify-between border-b border-outline-variant/30 pb-8">
        <div>
          <h1 className="text-3xl font-black text-on-surface tracking-tighter font-display uppercase">보안 위반 관리</h1>
          <p className="text-on-surface-variant font-medium mt-1 uppercase tracking-widest text-[10px] opacity-60">Policy Violation Queue & Response Management</p>
        </div>
        <div className="flex gap-2">
           <div className="bg-surface-container-high px-4 py-2 rounded-xl flex items-center gap-3">
              <span className="text-[10px] font-black uppercase tracking-widest opacity-40">Queue Status</span>
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
              <span className="text-xs font-bold text-on-surface">Monitoring Active</span>
           </div>
        </div>
      </div>

      {error ? (
        <div className="bg-error-container/10 border border-error/20 p-8 rounded-[2rem] flex flex-col items-center justify-center text-center gap-4">
           <AlertCircle className="w-12 h-12 text-error opacity-40" />
           <p className="text-on-surface font-bold">{error}</p>
           <button onClick={() => window.location.reload()} className="text-xs font-black text-primary uppercase underline">다시 시도</button>
        </div>
      ) : (
        <div className="flex gap-8 overflow-x-auto pb-6 custom-scrollbar min-h-[600px]">
          {columns.map((col) => (
            <div key={col.id} className="flex-1 min-w-[380px] max-w-[420px] flex flex-col gap-6">
              <div className="flex items-center justify-between pb-2">
                <div className="flex items-center gap-4">
                  <h3 className={cn("text-sm font-black tracking-[0.2em] uppercase", col.color)}>{col.name}</h3>
                  <span className="bg-surface-container-high text-on-surface-variant font-black text-[10px] px-3 py-1 rounded-full shadow-sm">
                    {col.count}
                  </span>
                </div>
                <MoreHorizontal className="w-5 h-5 text-on-surface-variant/40 cursor-pointer hover:text-primary transition-colors" />
              </div>

              <div className="flex-1 space-y-5">
                {reports.filter(r => r.column === col.id).length > 0 ? (
                  reports.filter(r => r.column === col.id).map((report) => (
                    <div 
                      key={report.id} 
                      className={cn(
                        "bg-white p-6 rounded-[2rem] flex flex-col gap-5 group cursor-pointer transition-all duration-300 border border-outline-variant hover:shadow-[0_20px_40px_rgba(0,0,0,0.06)] hover:border-primary/20",
                        col.id === 'resolved' && "opacity-75 grayscale-[0.2]"
                      )}
                    >
                      <div className="flex justify-between items-start">
                        <span className={cn(
                          "text-[9px] font-black uppercase tracking-widest px-2.5 py-1 rounded-lg border",
                          report.severity === 'HIGH' || report.severity === 'CRITICAL' ? "bg-error/5 text-error border-error/10" : 
                          report.severity === 'MEDIUM' ? "bg-amber-50 text-amber-600 border-amber-200" : 
                          "bg-surface-container-highest text-on-surface-variant border-outline-variant/30"
                        )}>
                          {report.severity} Priority
                        </span>
                        <span className="text-[10px] font-mono text-on-surface-variant opacity-40 font-bold" title={report.id}>#{report.id.slice(0, 8)}</span>
                      </div>

                      <div className="space-y-1">
                        <h4 className={cn(
                          "text-lg font-black text-on-surface group-hover:text-primary transition-colors leading-tight tracking-tight",
                          col.id === 'resolved' && "line-through opacity-40"
                        )}>
                          {report.title}
                        </h4>
                        <p className="text-xs text-on-surface-variant line-clamp-2 leading-relaxed opacity-80">
                          {report.desc}
                        </p>
                      </div>

                      <div className="flex items-center gap-4 text-[9px] font-black text-on-surface-variant uppercase tracking-widest opacity-60">
                        <div className="flex items-center gap-1.5">
                          {col.id === 'resolved' ? (
                            <CheckCircle2 className="w-3.5 h-3.5 text-green-600" />
                          ) : (
                            <Clock className="w-3.5 h-3.5" />
                          )}
                          <span>{report.time}</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <Shield className="w-3.5 h-3.5" />
                          <span>{report.layer}</span>
                        </div>
                      </div>

                      {report.originalQuery && (
                         <div className="p-3 bg-surface-container/30 rounded-xl border border-outline-variant/10">
                            <p className="text-[10px] font-mono text-on-surface-variant line-clamp-1 italic">"{report.originalQuery}"</p>
                         </div>
                      )}

                      <div className="flex justify-between items-center pt-5 border-t border-outline-variant/30">
                        <div className="flex items-center gap-2">
                          <div className={cn(
                             "w-7 h-7 rounded-full flex items-center justify-center border border-outline-variant/30 shadow-sm",
                             report.assignee ? "bg-primary text-white" : "bg-surface-container text-on-surface-variant"
                          )}>
                            <User className="w-4 h-4" />
                          </div>
                          <span className="text-[9px] font-black text-on-surface-variant uppercase tracking-tighter">
                            {report.assignee || 'Unassigned'}
                          </span>
                        </div>
                        <button className="flex items-center gap-1 text-[10px] font-black text-primary uppercase tracking-widest group-hover:translate-x-1 transition-transform">
                          Resolve
                          <ChevronRight className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="h-32 rounded-[2rem] border-2 border-dashed border-outline-variant/20 flex items-center justify-center">
                     <span className="text-[10px] font-black text-on-surface-variant opacity-20 uppercase tracking-widest">Empty Queue</span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ViolationReportsPage;
