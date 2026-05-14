import React, { useState, useEffect } from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts';
import { 
  History, Shield, AlertCircle, Loader2, CheckCircle2, Server, Database, Activity
} from 'lucide-react';
import { cn } from '../lib/utils';
import { api } from '../lib/api';
import { Link } from 'react-router-dom';

const DashboardPage = () => {
  const [stats, setStats] = useState([
    { label: '활성 에이전트', value: '0', trend: '-', icon: <Server />, color: 'text-primary' },
    { label: '보안 위협(NEW)', value: '0', trend: '-', icon: <Shield />, color: 'text-error' },
    { label: '감사 로그 총합', value: '0', trend: '-', icon: <Database />, color: 'text-secondary' },
    { label: 'DB 연결 상태', value: '-', trend: '-', icon: <Activity />, color: 'text-green-600' },
  ]);

  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [chartData, setChartData] = useState<any[]>([]);
  const [healthScore, setHealthScore] = useState(100);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        // 1. 상세 시스템 헬스 정보
        let systemStats: any = null;
        try {
          const sysRes = await api.get('/health/system');
          systemStats = sysRes.data;
        } catch (e) {
          console.warn("System stats API fail");
        }

        // 2. 위반 리포트 요약
        let violationsCount = 0;
        try {
          const vRes = await api.get('/v1/violation-reports?status=NEW&limit=1');
          violationsCount = vRes.data.total || vRes.data.items?.length || 0;
        } catch (e) {
          console.warn("Violation reports API fail");
        }

        // 3. 감사 로그 목록 및 분석 데이터 생성
        let recentLogs: any[] = [];
        let distribution = { PASS: 0, WARN: 0, BLOCK: 0 };

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
          const allLogs: any[] = [];
          
          auditResults.forEach((res: any, index: number) => {
            const agent = agents[index];
            const data = res.data;

            // 질의 로그 매핑
            data.query_audits?.forEach((q: any) => {
              allLogs.push({
                id: q.audit_id,
                agent: agent.name,
                user: 'Admin', 
                created_at: q.created_at,
                status: q.status === 'Blocked' ? 'Blocked' : q.status === 'Warned' ? 'Warning' : 'Passed',
                type: 'QUERY',
                reason: (q.risk_reasons && q.risk_reasons.length > 0) ? q.risk_reasons[0] : '보안 필터링 검사 완료'
              });
            });

            // 응답 로그 매핑
            data.response_audits?.forEach((r: any) => {
              allLogs.push({
                id: r.audit_id,
                agent: agent.name,
                user: 'Admin',
                created_at: r.created_at,
                status: r.status === 'Blocked' ? 'Blocked' : r.status === 'Warned' ? 'Warning' : 'Passed',
                type: 'RESPONSE',
                reason: (r.violations && r.violations.length > 0) ? (r.violations[0].reason || r.violations[0].type) : '보안 필터링 검사 완료'
              });
            });
          });

          // 4단계: 최신순 정렬
          allLogs.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
          
          // 5단계: 분석 및 최근 7개 슬라이싱 (최대 50개 기준 분석)
          const timeSeriesData: Record<string, any> = {};
          
          allLogs.slice(0, 50).reverse().forEach((item: any) => {
            const date = new Date(item.created_at);
            const timeKey = `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, '0')}:00`;

            if (!timeSeriesData[timeKey]) {
              timeSeriesData[timeKey] = { time: timeKey, 안전: 0, 경고: 0, 차단: 0 };
            }

            if (item.status === 'Blocked') {
               timeSeriesData[timeKey].차단++;
               distribution.BLOCK++;
            }
            else if (item.status === 'Warning') {
               timeSeriesData[timeKey].경고++;
               distribution.WARN++;
            }
            else {
               timeSeriesData[timeKey].안전++;
               distribution.PASS++;
            }
          });

          recentLogs = allLogs.slice(0, 7).map((item: any) => ({
            id: item.id,
            time: new Date(item.created_at).toLocaleTimeString('ko-KR'),
            type: item.type,
            user: item.user,
            desc: item.reason,
            status: item.status === 'Blocked' ? '차단됨' : item.status === 'Warning' ? '경고' : '안전'
          }));

          setChartData(Object.values(timeSeriesData));
        } catch (e) {
          console.error("Audit logs API fail", e);
        }

        // 최종 통계 업데이트
        const counts = systemStats?.counts || {};
        const dbReady = systemStats?.db_available ? '정상' : '오류';
        
        setStats([
          { 
            label: '활성 에이전트', 
            value: (counts.agents || 0).toString(), 
            trend: 'ACTIVE', 
            icon: <Server className="w-5 h-5"/>, 
            color: 'text-primary' 
          },
          { 
            label: '보안 위협(NEW)', 
            value: violationsCount.toString(), 
            trend: violationsCount > 0 ? '조치 필요' : '안전', 
            icon: <Shield className="w-5 h-5"/>, 
            color: 'text-error' 
          },
          { 
            label: '감사 로그 총합', 
            value: (counts.query_audit_logs || 0).toString(), 
            trend: 'LOGGED', 
            icon: <Database className="w-5 h-5"/>, 
            color: 'text-secondary' 
          },
          { 
            label: 'DB 연결 상태', 
            value: dbReady, 
            trend: 'STABLE', 
            icon: <CheckCircle2 className="w-5 h-5"/>, 
            color: 'text-green-600' 
          },
        ]);

        setAuditLogs(recentLogs);
        
        // 실제 데이터 기반 헬스 스코어 (위반 수 및 차단 건수 반영)
        const totalEvents = distribution.PASS + distribution.WARN + distribution.BLOCK;
        const penalty = (violationsCount * 15) + (distribution.BLOCK * 5);
        setHealthScore(Math.max(0, 100 - penalty));

      } catch (error) {
        console.error("Dashboard calculation error:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchDashboardData();
  }, []);

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-[500px] w-full bg-surface-container-lowest">
        <Loader2 className="w-12 h-12 text-primary animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500 pb-12">
      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat, idx) => (
          <div key={idx} className="bg-white p-6 rounded-2xl border border-outline-variant shadow-sm hover:shadow-md transition-all group">
            <div className="flex justify-between items-start">
               <span className="text-on-surface-variant text-[11px] font-black opacity-40 uppercase tracking-widest">{stat.label}</span>
               <div className={cn("p-2 rounded-xl bg-surface-container/50 group-hover:bg-primary/5 transition-colors", stat.color)}>
                  {stat.icon}
               </div>
            </div>
            <div className="flex items-end justify-between mt-4">
              <span className={cn("text-3xl font-black tracking-tighter", stat.color)}>{stat.value}</span>
              <span className="text-[9px] font-black px-2 py-1 bg-surface-container rounded-lg text-on-surface-variant uppercase tracking-widest">
                {stat.trend}
              </span>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Real Security Distribution Chart */}
        <div className="bg-white p-8 rounded-[2rem] border border-outline-variant shadow-sm lg:col-span-2 flex flex-col min-h-[400px]">
          <div className="flex justify-between items-center mb-10">
            <h3 className="text-on-surface text-sm font-black uppercase tracking-widest opacity-40">Security Event Distribution</h3>
            <span className="text-[10px] font-bold text-on-surface-variant bg-surface-container px-3 py-1 rounded-full">실제 분석 데이터</span>
          </div>
          <div className="flex-1 w-full flex flex-col items-center justify-center pt-4">
            <div className="w-full h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                  <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#64748b', fontWeight: 600 }} dy={10} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#64748b' }} allowDecimals={false} />
                  <Tooltip 
                    cursor={{ fill: '#f8fafc' }}
                    contentStyle={{ borderRadius: '16px', border: 'none', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)' }}
                  />
                  <Legend wrapperStyle={{ fontSize: '10px', fontWeight: 700, paddingTop: '10px' }} />
                  <Bar dataKey="안전" stackId="a" fill="#002045" maxBarSize={40} />
                  <Bar dataKey="경고" stackId="a" fill="#f59e0b" maxBarSize={40} />
                  <Bar dataKey="차단" stackId="a" fill="#ef4444" radius={[4, 4, 0, 0]} maxBarSize={40} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Health Score Gauge */}
        <div className="bg-white p-8 rounded-[2rem] border border-outline-variant shadow-sm flex flex-col items-center justify-center min-h-[400px]">
          <h3 className="text-on-surface text-sm font-black self-start mb-8 uppercase tracking-widest opacity-40">Security Posture Rank</h3>
          <div className="relative w-48 h-48 flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={[{ value: 100 - healthScore }, { value: healthScore }]}
                  innerRadius={75}
                  outerRadius={90}
                  startAngle={180}
                  endAngle={-180}
                  dataKey="value"
                  stroke="none"
                >
                  <Cell fill="#f1f5f9" />
                  <Cell fill={healthScore > 80 ? "#002045" : "#ef4444"} />
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="absolute flex flex-col items-center">
              <span className={cn("text-5xl font-black tracking-tighter", healthScore > 80 ? "text-primary" : "text-error")}>
                {healthScore}
              </span>
              <span className="text-[10px] text-on-surface-variant font-bold uppercase tracking-widest mt-1">Integrity Score</span>
            </div>
          </div>
          <div className="mt-8 text-center space-y-2">
            <p className="text-xs font-bold text-on-surface leading-tight">
              {healthScore > 90 ? "Optimal Protection" : healthScore > 70 ? "Stable with Warnings" : "Attention Required"}
            </p>
            <p className="text-[10px] text-on-surface-variant font-medium opacity-60">
              실제 차단 건수 및 미처리 리포트 기반 점수
            </p>
          </div>
        </div>
      </div>

      {/* Recent Audit Logs Table */}
      <div className="bg-white rounded-[2rem] border border-outline-variant shadow-sm overflow-hidden">
        <div className="px-8 py-6 flex justify-between items-center border-b border-outline-variant">
          <div className="flex items-center gap-3">
             <Activity className="w-4 h-4 text-primary" />
             <h3 className="text-on-surface text-sm font-black uppercase tracking-widest opacity-40">Live Security Event Stream</h3>
          </div>
          <Link to="/admin/logs" className="text-[10px] text-primary font-black uppercase tracking-widest bg-primary/5 px-4 py-2 rounded-full hover:bg-primary/10 transition-colors">View All Streams</Link>
        </div>
        <div className="overflow-x-auto">
          {auditLogs.length > 0 ? (
            <table className="w-full text-left">
              <thead>
                <tr className="bg-surface-container-low text-on-surface-variant text-[10px] font-black uppercase tracking-[0.2em]">
                  <th className="px-8 py-4">Timestamp</th>
                  <th className="px-8 py-4">Event Group</th>
                  <th className="px-8 py-4">User Identity</th>
                  <th className="px-8 py-4">Context / Reason</th>
                  <th className="px-8 py-4 text-right">Protection</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/30 text-sm">
                {auditLogs.map((log, idx) => (
                  <tr key={idx} className="hover:bg-surface-container-lowest transition-colors group">
                    <td className="px-8 py-4 text-[11px] font-mono font-medium text-on-surface-variant opacity-60">{log.time}</td>
                    <td className="px-8 py-4">
                      <span className="px-2 py-0.5 rounded border border-primary/10 text-[9px] font-black uppercase tracking-widest bg-primary/5 text-primary">
                        {log.type}
                      </span>
                    </td>
                    <td className="px-8 py-4 font-bold text-on-surface text-xs">{log.user}</td>
                    <td className="px-8 py-4 text-on-surface-variant text-xs max-w-md truncate" title={log.desc}>{log.desc}</td>
                    <td className="px-8 py-4 text-right">
                       <span className={cn(
                        "text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded border",
                        log.status === '차단됨' ? "bg-error/5 text-error border-error/20" : 
                        log.status === '경고' ? "bg-amber-50 text-amber-600 border-amber-200" : 
                        "bg-green-50 text-green-600 border-green-200"
                      )}>
                        {log.status === '안전' ? 'SECURED' : log.status === '차단됨' ? 'BLOCKED' : 'WARNING'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="p-20 text-center text-sm text-on-surface-variant font-medium opacity-40 italic">
              활성 보안 로그 스트림을 찾을 수 없습니다.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
