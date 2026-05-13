import React, { useState, useEffect } from 'react';
import { 
  FileText, 
  Upload, 
  CheckCircle2, 
  Zap, 
  Clock, 
  ChevronRight, 
  AlertCircle,
  FileCode,
  ArrowRight,
  Loader2,
  Trash2,
  Play
} from 'lucide-react';
import { cn } from '../lib/utils';
import { api } from '../lib/api';

interface Policy {
  policy_id: string;
  name: string;
  version: string;
  is_active: boolean;
  created_at: string;
  yaml_path: string;
}

const PolicyCompilerPage = () => {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [policyName, setPolicyName] = useState("");
  const [selectedYaml, setSelectedYaml] = useState<string | null>(null);

  useEffect(() => {
    fetchPolicies();
  }, []);

  const fetchPolicies = async () => {
    try {
      setIsLoading(true);
      const res = await api.get('/v1/policy-compiler');
      setPolicies(res.data || []);
    } catch (e) {
      console.error("Failed to fetch policies");
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile || !policyName) return;

    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', uploadFile);
    formData.append('policy_name', policyName);
    formData.append('effective_date', new Date().toISOString().split('T')[0]);

    try {
      const res = await api.post('/v1/policy-compiler/compile', formData);
      alert("정책 변환 및 등록이 완료되었습니다.");
      setUploadFile(null);
      setPolicyName("");
      fetchPolicies();
    } catch (e) {
      console.error("Compile failed", e);
      alert("변환 실패: .docx 파일 내부 구조를 확인해 주세요.");
    } finally {
      setIsUploading(false);
    }
  };

  const toggleActivate = async (pId: string) => {
    try {
      await api.put(`/v1/policy-compiler/${pId}/activate`);
      fetchPolicies();
    } catch (e) {
      alert("활성화 처리 중 오류가 발생했습니다.");
    }
  };

  const viewYaml = async (pId: string) => {
    try {
      const res = await api.get(`/v1/policy-compiler/${pId}/yaml`);
      setSelectedYaml(res.data);
    } catch (e) {
      alert("YAML 원문을 불러올 수 없습니다.");
    }
  };

  if (isLoading && policies.length === 0) {
    return (
      <div className="flex justify-center items-center h-[500px] w-full">
        <Loader2 className="w-12 h-12 text-primary animate-spin" />
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 animate-in fade-in duration-500 pb-20">
      {/* Left Section: Upload & Tools */}
      <div className="lg:col-span-5 space-y-8">
        <div className="bg-white p-10 rounded-[3rem] border-2 border-outline-variant shadow-sm relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
             <FileText className="w-32 h-32 rotate-12" />
          </div>
          
          <h2 className="text-2xl font-black text-on-surface tracking-tighter mb-2">Policy Compiler</h2>
          <p className="text-sm text-on-surface-variant font-medium mb-8 opacity-60 uppercase tracking-widest leading-relaxed">
            Convert Document to Guardrail YAML
          </p>

          <form onSubmit={handleUpload} className="space-y-6 relative z-10">
            <div className="space-y-2">
               <label className="text-[10px] font-black text-primary uppercase tracking-[0.2em] ml-1">Policy Identity</label>
               <input 
                type="text" 
                value={policyName}
                onChange={(e) => setPolicyName(e.target.value)}
                placeholder="정책 명칭을 입력하세요 (예: 금융보안 가이드 v1)"
                className="w-full h-14 px-6 rounded-2xl bg-surface-container-lowest border border-outline-variant focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all text-sm font-bold"
               />
            </div>

            <div className="space-y-2">
               <label className="text-[10px] font-black text-primary uppercase tracking-[0.2em] ml-1">Document Source (.docx)</label>
               <div className="relative h-40 border-2 border-dashed border-outline-variant rounded-[2rem] flex flex-col items-center justify-center p-6 bg-surface-container-lowest hover:bg-primary/5 hover:border-primary/30 transition-all cursor-pointer group/upload">
                  <input 
                    type="file" 
                    accept=".docx"
                    onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                    className="absolute inset-0 opacity-0 cursor-pointer"
                  />
                  {uploadFile ? (
                    <div className="flex flex-col items-center">
                       <CheckCircle2 className="w-10 h-10 text-primary mb-3" />
                       <span className="text-xs font-black text-on-surface">{uploadFile.name}</span>
                       <span className="text-[10px] text-on-surface-variant font-medium mt-1">파일이 선택되었습니다.</span>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center">
                       <Upload className="w-10 h-10 text-on-surface-variant/20 mb-4 group-hover/upload:scale-110 transition-transform duration-500" />
                       <span className="text-xs font-black text-on-surface-variant uppercase tracking-widest opacity-40">Drop .docx file here</span>
                    </div>
                  )}
               </div>
            </div>

            <button 
              disabled={isUploading || !uploadFile || !policyName}
              className={cn(
                "w-full h-16 bg-primary text-on-primary rounded-[1.5rem] font-black text-xs uppercase tracking-[0.2em] shadow-xl shadow-primary/20 hover:brightness-110 active:scale-95 transition-all flex items-center justify-center gap-3",
                (isUploading || !uploadFile || !policyName) && "opacity-50 grayscale cursor-not-allowed"
              )}
            >
              {isUploading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Zap className="w-5 h-5" />
              )}
              {isUploading ? 'Compiling Rules...' : 'Start Compilation'}
            </button>
          </form>
        </div>

        {/* Translation Status Panel */}
        <div className="bg-surface-container p-8 rounded-[2.5rem] border border-outline-variant/30 space-y-6">
           <h3 className="text-[10px] font-black text-on-surface-variant uppercase tracking-[0.3em] opacity-40">Conversion Logic</h3>
           <div className="space-y-4">
              {[
                { step: "01", name: "DocX Structural Parsing", desc: "분석 엔진이 문서 조문을 벡터화합니다." },
                { step: "02", name: "Semantic Rule Extraction", desc: "보안 정책에 필요한 금칙어와 규칙을 추출합니다." },
                { step: "03", name: "YAML Generation", desc: "시스템이 이해할 수 있는 YAML로 자동 변환합니다." }
              ].map((s, idx) => (
                <div key={idx} className="flex gap-4">
                   <span className="font-mono text-xs font-black text-primary/40">{s.step}</span>
                   <div>
                      <h4 className="text-xs font-black text-on-surface uppercase tracking-tight">{s.name}</h4>
                      <p className="text-[10px] font-bold text-on-surface-variant opacity-60">{s.desc}</p>
                   </div>
                </div>
              ))}
           </div>
        </div>
      </div>

      {/* Right Section: Registered Policies List */}
      <div className="lg:col-span-7 space-y-8">
         <div className="flex items-center justify-between px-2">
            <div>
               <h3 className="text-sm font-black text-on-surface uppercase tracking-widest flex items-center gap-3">
                  <FileCode className="w-5 h-5 text-primary" /> Active Rule Systems
               </h3>
            </div>
            <span className="bg-surface-container-high text-on-surface-variant font-black text-[10px] px-4 py-1.5 rounded-full uppercase tracking-tighter">
              {policies.length} Registered
            </span>
         </div>

         <div className="space-y-4 overflow-y-auto max-h-[800px] pr-2 custom-scrollbar">
            {policies.length > 0 ? policies.map((policy) => (
              <div 
                key={policy.policy_id}
                className={cn(
                  "bg-white p-8 rounded-[2.5rem] border border-outline-variant shadow-sm hover:shadow-md transition-all group flex flex-col gap-6",
                  policy.is_active && "border-primary/30 ring-1 ring-primary/5"
                )}
              >
                <div className="flex justify-between items-start">
                   <div className="flex items-center gap-4">
                      <div className={cn(
                        "w-12 h-12 rounded-2xl flex items-center justify-center transition-all group-hover:rotate-[10deg]",
                        policy.is_active ? "bg-primary text-white shadow-lg shadow-primary/20" : "bg-surface-container text-on-surface-variant opacity-40"
                      )}>
                         <ShieldAlert className="w-6 h-6" />
                      </div>
                      <div>
                         <h4 className="text-xl font-black text-on-surface tracking-tighter group-hover:text-primary transition-colors">{policy.name}</h4>
                         <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest opacity-40 mt-1">ID: {policy.policy_id} • v{policy.version}</p>
                      </div>
                   </div>
                   <div className={cn(
                     "px-4 py-1.5 rounded-full text-[10px] font-black uppercase tracking-widest border transition-all",
                     policy.is_active ? "bg-primary/5 text-primary border-primary/20" : "bg-surface-container text-on-surface-variant border-transparent opacity-40"
                   )}>
                      {policy.is_active ? 'In Operation' : 'Dormant'}
                   </div>
                </div>

                <div className="flex items-center gap-8 py-4 border-y border-outline-variant/30">
                   <div className="flex flex-col">
                      <span className="text-[9px] font-black text-on-surface-variant uppercase tracking-widest opacity-40">Compiled At</span>
                      <span className="text-xs font-bold text-on-surface mt-1">{new Date(policy.created_at).toLocaleDateString('ko-KR')}</span>
                   </div>
                   <div className="flex flex-col">
                      <span className="text-[9px] font-black text-on-surface-variant uppercase tracking-widest opacity-40">Rule Source</span>
                      <span className="text-xs font-mono font-bold text-on-surface mt-1 truncate max-w-[150px]" title={policy.yaml_path}>
                        {policy.yaml_path.split(/[\\/]/).pop()}
                      </span>
                   </div>
                </div>

                <div className="flex items-center justify-between pt-2">
                   <div className="flex gap-2">
                      <button 
                        onClick={() => viewYaml(policy.policy_id)}
                        className="h-10 px-6 rounded-xl bg-surface-container text-on-surface-variant font-black text-[10px] uppercase tracking-widest hover:bg-primary/5 hover:text-primary transition-all border border-transparent hover:border-primary/10"
                      >
                         Inspect YAML
                      </button>
                      {!policy.is_active && (
                        <button 
                          onClick={() => toggleActivate(policy.policy_id)}
                          className="h-10 px-6 rounded-xl bg-primary text-white font-black text-[10px] uppercase tracking-widest hover:brightness-110 shadow-lg shadow-primary/10 flex items-center gap-2"
                        >
                           <Play className="w-3 h-3 fill-white" /> Activate System
                        </button>
                      )}
                   </div>
                   <ArrowRight className="w-5 h-5 text-on-surface-variant opacity-20 group-hover:translate-x-2 group-hover:opacity-100 transition-all cursor-pointer" />
                </div>
              </div>
            )) : (
              <div className="h-[400px] bg-surface-container-lowest/50 border-2 border-dashed border-outline-variant/30 rounded-[3rem] flex flex-col items-center justify-center opacity-40">
                 <FileCode className="w-16 h-16 mb-4" />
                 <p className="text-sm font-black uppercase tracking-widest">No policies deployed yet</p>
              </div>
            )}
         </div>
      </div>

      {/* YAML Preview Modal */}
      {selectedYaml && (
        <div className="fixed inset-0 bg-on-surface/40 backdrop-blur-sm z-[100] flex items-center justify-center p-6 animate-in fade-in duration-300">
           <div className="bg-white w-full max-w-4xl h-[80vh] rounded-[3rem] border border-outline-variant shadow-2xl flex flex-col overflow-hidden animate-in zoom-in-95 duration-500">
              <div className="px-10 py-8 border-b border-outline-variant/30 flex justify-between items-center bg-surface-container-low/30">
                 <div>
                    <h3 className="text-xl font-black text-on-surface tracking-tighter uppercase">YAML Specification</h3>
                    <p className="text-[10px] font-black text-primary uppercase tracking-widest mt-1 opacity-60">System-Generated Security Rule-Set</p>
                 </div>
                 <button 
                  onClick={() => setSelectedYaml(null)}
                  className="w-10 h-10 rounded-full bg-surface-container-high flex items-center justify-center text-on-surface-variant hover:bg-error/5 hover:text-error transition-all"
                 >
                    <ChevronRight className="w-5 h-5" />
                 </button>
              </div>
              <div className="flex-1 p-10 overflow-auto bg-on-surface/[0.02] custom-scrollbar">
                 <pre className="text-xs font-mono text-on-surface leading-loose whitespace-pre-wrap">
                    {selectedYaml}
                 </pre>
              </div>
              <div className="px-10 py-6 bg-white border-t border-outline-variant/30 flex justify-end">
                 <button 
                  onClick={() => setSelectedYaml(null)}
                  className="px-10 h-12 bg-on-surface text-white rounded-2xl font-black text-[10px] uppercase tracking-widest hover:brightness-110 active:scale-95 transition-all"
                 >
                    Close Preview
                 </button>
              </div>
           </div>
        </div>
      )}
    </div>
  );
};

// UI 아이콘 중첩 회피를 위한 임시 아이콘
const ShieldAlert = ({ className }: { className?: string }) => (
  <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
);

export default PolicyCompilerPage;
