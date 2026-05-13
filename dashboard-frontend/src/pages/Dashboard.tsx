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
          const aRes = await api.get('/api/v1/audit-logs?limit=50'); // 분석을 위해 더 많이 가져옴
          const logs = aRes.data || [];
          
          logs.forEach((item: any) => {
            if (item.event_type === 'BLOCKED') distribution.BLOCK++;
            else if (item.event_type === 'WARNING') distribution.WARN++;
            else distribution.PASS++;
          });

          recentLogs = logs.slice(0, 7).map((item: any) => ({
            id: item.run_id || item.id,
            time: new Date(item.created_at).toLocaleTimeString('ko-KR'),
            type: item.event_type || 'SYSTEM',
            user: item.context?.username || 'SYSTEM',
            desc: item.reason || '보안 필터링 검사 완료',
            status: item.event_type === 'BLOCKED' ? '차단됨' : item.event_type === 'WARNING' ? '경고' : '안전'
          }));
        } catch (e) {
          console.warn("Audit logs API fail");
        }

        // 차트 데이터 업데이트 (가상 데이터 제거, 실제 분포 사용)
        setChartData([
          { name: '안전', value: distribution.PASS, color: '#002045' },
          { name: '경고', value: distribution.WARN, color: '#f59e0b' },
          { name: '차단', value: distribution.BLOCK, color: '#ef4444' },
        ].filter(d => d.value > 0)); // 데이터가 있는 것만 표시

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
          <div className="flex-1 w-full flex flex-col md:flex-row items-center gap-8">
            <div className="w-full md:w-1/2 h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={chartData}
                    innerRadius={70}
                    outerRadius={100}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {chartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip 
                    contentStyle={{ borderRadius: '16px', border: 'none', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)' }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="w-full md:w-1/2 space-y-4">
                {chartData.length > 0 ? chartData.map((item, i) => (
                  <div key={i} className="flex items-center justify-between p-4 bg-surface-container-low rounded-2xl border border-outline-variant/10">
                    <div className="flex items-center gap-3">
                      <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }}></div>
                      <span className="text-xs font-bold text-on-surface">{item.name}</span>
                    </div>
                    <span className="text-sm font-black text-primary">{item.value}건</span>
                  </div>
                )) : (
                  <div className="h-full flex items-center justify-center text-sm text-on-surface-variant italic opacity-40">
                    분석 데이터 없음
                  </div>
                )}
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
