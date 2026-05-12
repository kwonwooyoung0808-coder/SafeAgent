import React, { useState, useEffect } from 'react';
import { 
  AlertTriangle, 
  Clock, 
  Shield, 
  MoreHorizontal, 
  ExternalLink,
  ChevronRight,
  User,
  CheckCircle2,
  Loader2
} from 'lucide-react';
import { cn } from '@/src/lib/utils';
import { api } from '@/src/lib/api';

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
}

const ViolationReportsPage = () => {
  const [reports, setReports] = useState<FrontendReport[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchReports = async () => {
      try {
        const response = await api.get('/violation-reports');
        const data = response.data.items || [];
        
        // 백엔드 데이터를 기존 UI 구조에 맞게 어댑터(Adapter) 패턴으로 변환
        const mappedReports: FrontendReport[] = data.map((item: any) => {
          let columnId = 'new';
          if (item.status === 'REVIEWING') columnId = 'reviewing';
          if (item.status === 'RESOLVED' || item.status === 'DISMISSED') columnId = 'resolved';

          const dateObj = new Date(item.created_at);
          const timeStr = dateObj.toLocaleString('ko-KR', { 
            year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit', second: '2-digit'
          });

          let resolvedStr;
          if (item.resolved_at) {
            resolvedStr = new Date(item.resolved_at).toLocaleString('ko-KR');
          }

          return {
            id: item.id || 'SEC-UNKNOWN',
            column: columnId,
            // HIGH, CRITICAL 등은 동일하게 처리
            severity: item.severity || 'LOW',
            title: item.primary_category || 'Policy Violation',
            desc: item.summary || '상세 내용 없음',
            time: timeStr,
            layer: item.stage || 'Gateway',
            assignee: item.admin_note ? 'Admin' : null,
            resolvedAt: resolvedStr,
          };
        });

        setReports(mappedReports);
      } catch (error) {
        console.error('Failed to fetch violation reports', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchReports();
  }, []);

  // 기존 컴포넌트 구조 유지를 위해 columns 상수를 컴포넌트 내부로 이동시켜 카운트 자동 계산
  const columns = [
    { id: 'new', name: 'NEW', count: reports.filter(r => r.column === 'new').length, color: 'bg-primary' },
    { id: 'reviewing', name: 'REVIEWING', count: reports.filter(r => r.column === 'reviewing').length, color: 'bg-on-secondary-fixed-variant' },
    { id: 'resolved', name: 'RESOLVED', count: reports.filter(r => r.column === 'resolved').length, color: 'bg-outline-variant' },
  ];

  return (
    <div className="flex flex-col gap-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-bold text-primary tracking-tight font-display uppercase">보안 위반 레포트</h1>
          <p className="text-on-surface-variant font-medium mt-1">시스템에서 탐지된 실시간 보안 위협 및 위반 사항 관리</p>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center items-center h-64 w-full">
          <Loader2 className="w-10 h-10 text-primary animate-spin" />
        </div>
      ) : (
        <div className="flex gap-6 overflow-x-auto pb-6 custom-scrollbar min-h-[600px]">
          {columns.map((col) => (
            <div key={col.id} className="flex-1 min-w-[350px] max-w-[420px] flex flex-col gap-4">
              <div className={cn(
                "flex items-center justify-between pb-3 border-b-2",
                col.id === 'new' ? "border-primary" : "border-outline-variant"
              )}>
                <div className="flex items-center gap-3">
                  <div className={cn("w-2 h-2 rounded-full", col.id === 'new' && "animate-pulse bg-primary", col.id === 'reviewing' && "bg-secondary", col.id === 'resolved' && "bg-outline-variant")} />
                  <h3 className="font-bold text-on-surface tracking-tight uppercase">{col.name}</h3>
                  <span className="bg-surface-container-highest text-on-surface-variant font-bold text-[10px] px-2 py-0.5 rounded-full">
                    {col.count}
                  </span>
                </div>
                <MoreHorizontal className="w-5 h-5 text-on-surface-variant cursor-pointer hover:text-primary transition-colors" />
              </div>

              <div className="flex-1 space-y-4">
                {reports.filter(r => r.column === col.id).map((report) => (
                  <div 
                    key={report.id} 
                    className={cn(
                      "glass-panel p-5 rounded-2xl flex flex-col gap-4 group cursor-pointer transition-all duration-300 hover:shadow-lg hover:border-primary/20",
                      col.id === 'resolved' && "opacity-80 grayscale-[0.3]"
                    )}
                  >
                    <div className="flex justify-between items-start">
                      <span className={cn(
                        "text-[9px] font-black uppercase tracking-widest px-2 py-1 rounded border",
                        report.severity === 'HIGH' || report.severity === 'CRITICAL' ? "bg-error-container text-error border-error/20" : 
                        report.severity === 'MEDIUM' ? "bg-secondary-container text-secondary border-secondary/20" : 
                        "bg-surface-container-highest text-on-surface-variant border-outline-variant/30"
                      )}>
                        {report.severity} Severity
                      </span>
                      <span className="text-[10px] font-mono text-on-surface-variant font-bold truncate max-w-[120px]" title={report.id}>{report.id}</span>
                    </div>

                    <h4 className={cn(
                      "text-lg font-bold text-on-surface group-hover:text-primary transition-colors leading-tight",
                      col.id === 'resolved' && "line-through decoration-1"
                    )}>
                      {report.title}
                    </h4>
                    <p className="text-sm text-on-surface-variant line-clamp-2 leading-relaxed">
                      {report.desc}
                    </p>

                    <div className="flex items-center gap-4 text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">
                      <div className="flex items-center gap-1.5">
                        {col.id === 'resolved' ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-primary" />
                        ) : (
                          <Clock className="w-3.5 h-3.5" />
                        )}
                        <span>{col.id === 'resolved' && report.resolvedAt ? `Resolved ${report.resolvedAt}` : report.time}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Shield className="w-3.5 h-3.5" />
                        <span>{report.layer}</span>
                      </div>
                    </div>

                    <div className="flex justify-between items-center pt-4 border-t border-outline-variant/30">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-full bg-surface-container-high border border-outline-variant/30 flex items-center justify-center">
                          <User className="w-3.5 h-3.5 text-on-surface-variant" />
                        </div>
                        {report.assignee && (
                          <span className="text-[10px] font-black text-on-surface-variant uppercase tracking-tighter truncate max-w-[80px]">
                            Assigned: {report.assignee}
                          </span>
                        )}
                      </div>
                      <button className="flex items-center gap-1 text-[10px] font-black text-primary uppercase tracking-widest group-hover:underline">
                        View Details
                        <ChevronRight className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ViolationReportsPage;
