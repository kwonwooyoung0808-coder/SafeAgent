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
  Play,
  Save,
  History,
  X,
  ShieldCheck,
  AlertTriangle,
  Download
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

interface PolicyVersion {
  id: string;
  version: string;
  is_current: boolean;
  created_at: string;
  activated_at: string | null;
}

const PolicyCompilerPage = () => {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [policyName, setPolicyName] = useState("");
  const [policyId, setPolicyId] = useState("");

  // YAML Editor / Preview
  const [selectedPolicy, setSelectedPolicy] = useState<Policy | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [currentYaml, setCurrentYaml] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  // Versions
  const [showVersions, setShowVersions] = useState(false);
  const [versions, setVersions] = useState<PolicyVersion[]>([]);
  const [isLoadingVersions, setIsLoadingVersions] = useState(false);

  useEffect(() => {
    fetchPolicies();
  }, []);

  const fetchPolicies = async () => {
    try {
      setIsLoading(true);
      // 서버에 /v1/policy-compiler (List) API가 없으므로 summary에서 추출
      const res = await api.get('/v1/policy-groups/summary');
      const allPolicies: Policy[] = [];

      // 그룹화되지 않은 정책들 추가
      if (res.data.ungrouped_policies) {
        allPolicies.push(...res.data.ungrouped_policies.map((p: any) => ({
          policy_id: p.id,
          name: p.name,
          version: p.version,
          is_active: p.is_active,
          created_at: new Date().toISOString(), // summary에 날짜가 없으면 현재 시간으로 대체
          yaml_path: `${p.id}.yaml`
        })));
      }

      // 그룹 내 정책들 추가 (중복 제거)
      if (res.data.groups) {
        res.data.groups.forEach((group: any) => {
          group.policies.forEach((p: any) => {
            if (!allPolicies.find(existing => existing.policy_id === p.id)) {
              allPolicies.push({
                policy_id: p.id,
                name: p.name,
                version: p.version,
                is_active: p.is_active,
                created_at: new Date().toISOString(),
                yaml_path: `${p.id}.yaml`
              });
            }
          });
        });
      }

      setPolicies(allPolicies);
    } catch (e) {
      console.error("Failed to fetch policies", e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile || !policyName || !policyId) return;

    // ID Validation: uppercase, numbers, _, -
    const idRegex = /^[A-Z0-9][A-Z0-9_-]{2,79}$/;
    if (!idRegex.test(policyId)) {
      alert("Policy ID는 영문 대문자, 숫자, 언더바(_), 하이픈(-)만 사용할 수 있습니다.");
      return;
    }

    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', uploadFile);
    formData.append('policy_id', policyId);
    formData.append('policy_name', policyName);

    try {
      const res = await api.post('/v1/policy-compiler/compile', formData);
      console.log("Compile Result:", res.data);

      if (res.data.status === "SUCCESS") {
        alert("정책 변환 및 등록이 완료되었습니다.");
      } else if (res.data.status === "PARTIAL") {
        alert("정책 변환이 완료되었으나, 일부 규칙 검토가 필요합니다 (Status: PARTIAL).\nInspect YAML 메뉴에서 확인해 주세요.");
      } else if (res.data.status === "FAILED") {
        alert(`정책 변환 실패 (Status: FAILED)\n사유: ${res.data.warnings?.join('\n') || '알 수 없는 오류'}`);
      } else {
        alert(`알 수 없는 상태: ${res.data.status}`);
      }
      setUploadFile(null);
      setPolicyName("");
      setPolicyId("");
      fetchPolicies();
    } catch (e: any) {
      console.error("Compile failed", e);
      const errorMsg = e.response?.data?.detail || "변환 실패: .docx 파일 구조를 확인해 주세요.";
      alert(errorMsg);
    } finally {
      setIsUploading(false);
    }
  };

  const toggleActivate = async (pId: string, currentStatus: boolean) => {
    try {
      const action = currentStatus ? 'deactivate' : 'activate';
      await api.put(`/v1/policy-compiler/${pId}/${action}`);
      alert(currentStatus ? "정책이 비활성화되었습니다." : "정책이 활성화되어 실제 시스템에 적용되었습니다.");
      fetchPolicies();
    } catch (e: any) {
      alert(e.response?.data?.detail || "처리 중 오류가 발생했습니다.");
    }
  };

  const openInspector = async (policy: Policy) => {
    try {
      setSelectedPolicy(policy);
      setIsEditing(false);
      const res = await api.get(`/v1/policy-compiler/${policy.policy_id}/draft`);
      setCurrentYaml(res.data.raw_yaml);
    } catch (e) {
      alert("YAML 원문을 불러올 수 없습니다.");
    }
  };

  const saveDraft = async () => {
    if (!selectedPolicy) return;
    try {
      setIsSaving(true);
      await api.put(`/v1/policy-compiler/${selectedPolicy.policy_id}/draft`, {
        raw_yaml: currentYaml
      });
      alert("새로운 Draft 버전이 저장되었습니다.");
      setIsEditing(false);
      fetchPolicies();
    } catch (e: any) {
      alert(e.response?.data?.detail || "저장 실패: YAML 형식을 확인해 주세요.");
    } finally {
      setIsSaving(false);
    }
  };

  const deletePolicy = async (pId: string) => {
    if (!confirm("정책을 영구 삭제하시겠습니까? DB와 파일이 모두 제거됩니다.")) return;
    try {
      await api.delete(`/v1/policy-compiler/${pId}`);
      alert("정책이 성공적으로 제거되었습니다.");
      fetchPolicies();
    } catch (e: any) {
      alert(e.response?.data?.detail || "삭제 실패: 활성 상태이거나 사용 중인 정책은 삭제할 수 없습니다.");
    }
  };

  const viewVersions = async (pId: string) => {
    try {
      setIsLoadingVersions(true);
      setShowVersions(true);
      const res = await api.get(`/v1/policy-compiler/${pId}/versions`);
      setVersions(res.data.items);
    } catch (e) {
      alert("버전 이력을 불러올 수 없습니다.");
    } finally {
      setIsLoadingVersions(false);
    }
  };

  const rollbackVersion = async (pId: string, ver: string) => {
    if (!confirm(`${ver} 버전으로 롤백(활성화) 하시겠습니까?`)) return;
    try {
      await api.put(`/v1/policy-compiler/${pId}/versions/${ver}/activate`);
      alert(`성공적으로 ${ver} 버전이 활성화되었습니다.`);
      setShowVersions(false);
      fetchPolicies();
    } catch (e: any) {
      alert(e.response?.data?.detail || "롤백 처리 중 오류가 발생했습니다.");
    }
  };

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
            <div className="grid grid-cols-1 gap-6">
              <div className="space-y-2">
                <label className="text-[10px] font-black text-primary uppercase tracking-[0.2em] ml-1">Policy ID (Uppercase/Numbers)</label>
                <input
                  type="text"
                  value={policyId}
                  onChange={(e) => setPolicyId(e.target.value.toUpperCase())}
                  placeholder="EX: FINANCE_SEC_V1"
                  className="w-full h-14 px-6 rounded-2xl bg-surface-container-lowest border border-outline-variant focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all text-sm font-mono font-bold"
                />
              </div>
              <div className="space-y-2">
                <label className="text-[10px] font-black text-primary uppercase tracking-[0.2em] ml-1">Human Readable Name</label>
                <input
                  type="text"
                  value={policyName}
                  onChange={(e) => setPolicyName(e.target.value)}
                  placeholder="정책 명칭 (예: 금융보안 가이드 v1)"
                  className="w-full h-14 px-6 rounded-2xl bg-surface-container-lowest border border-outline-variant focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all text-sm font-bold"
                />
              </div>
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
              disabled={isUploading || !uploadFile || !policyName || !policyId}
              className={cn(
                "w-full h-16 bg-primary text-on-primary rounded-[1.5rem] font-black text-xs uppercase tracking-[0.2em] shadow-xl shadow-primary/20 hover:brightness-110 active:scale-95 transition-all flex items-center justify-center gap-3",
                (isUploading || !uploadFile || !policyName || !policyId) && "opacity-50 grayscale cursor-not-allowed"
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
          <div className="flex items-center gap-2">
            <button
              onClick={fetchPolicies}
              className="p-2 text-on-surface-variant hover:text-primary transition-colors"
            >
              <Clock className="w-4 h-4" />
            </button>
            <span className="bg-surface-container-high text-on-surface-variant font-black text-[10px] px-4 py-1.5 rounded-full uppercase tracking-tighter">
              {policies.length} Registered
            </span>
          </div>
        </div>

        <div className="space-y-4 overflow-y-auto max-h-[800px] pr-2 custom-scrollbar">
          {isLoading ? (
            <div className="h-[400px] flex items-center justify-center">
              <Loader2 className="w-10 h-10 text-primary animate-spin opacity-20" />
            </div>
          ) : policies.length > 0 ? policies.map((policy) => (
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
                    <ShieldCheck className="w-6 h-6" />
                  </div>
                  <div>
                    <h4 className="text-xl font-black text-on-surface tracking-tighter group-hover:text-primary transition-colors">{policy.name}</h4>
                    <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest opacity-40 mt-1">ID: {policy.policy_id} • v{policy.version}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className={cn(
                    "px-4 py-1.5 rounded-full text-[10px] font-black uppercase tracking-widest border transition-all",
                    policy.is_active ? "bg-primary/5 text-primary border-primary/20" : "bg-surface-container text-on-surface-variant border-transparent opacity-40"
                  )}>
                    {policy.is_active ? 'In Operation' : 'Dormant'}
                  </div>
                  {!policy.is_active && (
                    <button
                      onClick={() => deletePolicy(policy.policy_id)}
                      className="p-2 text-on-surface-variant hover:text-error transition-all"
                    >
                      <Trash2 size={16} />
                    </button>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-8 py-4 border-y border-outline-variant/30">
                <div className="flex flex-col">
                  <span className="text-[9px] font-black text-on-surface-variant uppercase tracking-widest opacity-40">Rule Source</span>
                  <span className="text-xs font-mono font-bold text-on-surface mt-1 truncate max-w-[200px]" title={policy.yaml_path}>
                    {policy.policy_id}.yaml
                  </span>
                </div>
                <div className="flex flex-col">
                  <span className="text-[9px] font-black text-on-surface-variant uppercase tracking-widest opacity-40">Status</span>
                  <div className="flex items-center gap-1.5 mt-1">
                    {policy.is_active ? (
                      <div className="flex items-center gap-1.5">
                        <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
                        <span className="text-[10px] font-bold text-primary uppercase">Guarding Traffic</span>
                      </div>
                    ) : (
                      <span className="text-[10px] font-bold text-on-surface-variant opacity-40 uppercase">Ready for Review</span>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between pt-2">
                <div className="flex gap-2">
                  <button
                    onClick={() => openInspector(policy)}
                    className="h-10 px-6 rounded-xl bg-surface-container text-on-surface-variant font-black text-[10px] uppercase tracking-widest hover:bg-primary/5 hover:text-primary transition-all border border-transparent hover:border-primary/10 flex items-center gap-2"
                  >
                    <FileCode className="w-3.5 h-3.5" /> Inspect YAML
                  </button>
                  <button
                    onClick={() => viewVersions(policy.policy_id)}
                    className="h-10 px-6 rounded-xl bg-surface-container text-on-surface-variant font-black text-[10px] uppercase tracking-widest hover:bg-primary/5 hover:text-primary transition-all border border-transparent hover:border-primary/10 flex items-center gap-2"
                  >
                    <History className="w-3.5 h-3.5" /> Versions
                  </button>
                  <button
                    onClick={() => toggleActivate(policy.policy_id, policy.is_active)}
                    className={cn(
                      "h-10 px-6 rounded-xl font-black text-[10px] uppercase tracking-widest transition-all shadow-lg flex items-center gap-2",
                      policy.is_active
                        ? "bg-error/5 text-error hover:bg-error/10 shadow-error/5 border border-error/20"
                        : "bg-primary text-white hover:brightness-110 shadow-primary/10"
                    )}
                  >
                    {policy.is_active ? (
                      <>Deactivate</>
                    ) : (
                      <><Play className="w-3 h-3 fill-white" /> Activate</>
                    )}
                  </button>
                </div>
                {/* <ArrowRight className="w-5 h-5 text-on-surface-variant opacity-20 group-hover:translate-x-2 group-hover:opacity-100 transition-all cursor-pointer" /> */}
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

      {/* YAML Preview & Editor Modal */}
      {selectedPolicy && (
        <div className="fixed inset-0 bg-on-surface/40 backdrop-blur-sm z-[100] flex items-center justify-center p-6 animate-in fade-in duration-300">
          <div className="bg-white w-full max-w-5xl h-[85vh] rounded-[3rem] border border-outline-variant shadow-2xl flex flex-col overflow-hidden animate-in zoom-in-95 duration-500">
            <div className="px-10 py-8 border-b border-outline-variant/30 flex justify-between items-center bg-surface-container-low/30">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center text-primary">
                  <FileCode size={24} />
                </div>
                <div>
                  <h3 className="text-xl font-black text-on-surface tracking-tighter uppercase">{selectedPolicy.name} <span className="opacity-30 ml-2 font-mono text-sm">v{selectedPolicy.version}</span></h3>
                  <p className="text-[10px] font-black text-primary uppercase tracking-widest mt-1 opacity-60">
                    {isEditing ? "Editing Rules — Draft will be saved as new version" : "Reviewing System-Generated Specification"}
                  </p>
                </div>
              </div>
              <button
                onClick={() => { setSelectedPolicy(null); setIsEditing(false); }}
                className="w-10 h-10 rounded-full bg-surface-container-high flex items-center justify-center text-on-surface-variant hover:bg-error/5 hover:text-error transition-all"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 flex overflow-hidden">
              {/* Editor Area */}
              <div className="flex-1 p-0 flex flex-col bg-on-surface/[0.01]">
                <textarea
                  readOnly={!isEditing}
                  value={currentYaml}
                  onChange={(e) => setCurrentYaml(e.target.value)}
                  spellCheck={false}
                  className={cn(
                    "flex-1 p-10 font-mono text-xs leading-relaxed outline-none resize-none bg-transparent custom-scrollbar",
                    isEditing ? "text-primary focus:bg-white transition-all" : "text-on-surface-variant/80"
                  )}
                />
              </div>

              {/* Info Panel */}
              <div className="w-80 border-l border-outline-variant/30 p-8 bg-surface-container-low/50 space-y-8 overflow-y-auto">
                <div className="space-y-4">
                  <h4 className="text-[10px] font-black text-on-surface-variant uppercase tracking-widest opacity-40">System Flags</h4>
                  <div className="space-y-3">
                    <div className="flex items-center gap-3 p-4 rounded-2xl bg-white border border-outline-variant/50">
                      <ShieldCheck className="w-5 h-5 text-primary" />
                      <div>
                        <p className="text-[9px] font-black uppercase opacity-40">Status</p>
                        <p className="text-xs font-bold">{selectedPolicy.is_active ? "Active" : "Draft"}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 p-4 rounded-2xl bg-white border border-outline-variant/50">
                      <AlertTriangle className="w-5 h-5 text-amber-500" />
                      <div>
                        <p className="text-[9px] font-black uppercase opacity-40">Review</p>
                        <p className="text-xs font-bold">Manual Audit Required</p>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="p-6 rounded-3xl bg-primary/5 border border-primary/10">
                  <p className="text-[10px] font-bold text-primary leading-relaxed">
                    YAML 형식이 잘못될 경우 가드레일이 작동하지 않을 수 있습니다. 수정 전 원본 백업을 권장합니다.
                  </p>
                </div>
              </div>
            </div>

            <div className="px-10 py-6 bg-white border-t border-outline-variant/30 flex justify-between items-center">
              <button
                onClick={() => {
                  const blob = new Blob([currentYaml], { type: 'text/yaml' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `${selectedPolicy.policy_id}.yaml`;
                  a.click();
                }}
                className="flex items-center gap-2 text-[10px] font-black text-on-surface-variant uppercase tracking-widest hover:text-primary transition-all"
              >
                <Download className="w-4 h-4" /> Download YAML
              </button>

              <div className="flex gap-3">
                {isEditing ? (
                  <>
                    <button
                      onClick={() => setIsEditing(false)}
                      className="px-6 h-12 bg-surface-container text-on-surface-variant rounded-2xl font-black text-[10px] uppercase tracking-widest hover:bg-error/5 hover:text-error transition-all"
                    >
                      Cancel
                    </button>
                    <button
                      disabled={isSaving}
                      onClick={saveDraft}
                      className="px-10 h-12 bg-primary text-white rounded-2xl font-black text-[10px] uppercase tracking-widest hover:brightness-110 active:scale-95 transition-all shadow-xl shadow-primary/20 flex items-center gap-2"
                    >
                      {isSaving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />} Save as New Draft
                    </button>
                  </>
                ) : (
                  <button
                    onClick={() => setIsEditing(true)}
                    className="px-10 h-12 bg-on-surface text-white rounded-2xl font-black text-[10px] uppercase tracking-widest hover:brightness-110 active:scale-95 transition-all"
                  >
                    Edit Specification
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Version History Slide-over */}
      {showVersions && (
        <div className="fixed inset-0 z-[110] flex justify-end">
          <div
            className="absolute inset-0 bg-on-surface/20 backdrop-blur-[2px] animate-in fade-in"
            onClick={() => setShowVersions(false)}
          />
          <div className="relative w-full max-w-md bg-white h-full shadow-2xl flex flex-col animate-in slide-in-from-right duration-500">
            <div className="p-8 border-b border-outline-variant/30 flex justify-between items-center">
              <div>
                <h3 className="text-xl font-black text-on-surface tracking-tighter flex items-center gap-3">
                  <History className="w-6 h-6 text-primary" /> Version History
                </h3>
                <p className="text-[10px] font-black text-on-surface-variant uppercase tracking-widest opacity-40 mt-1">Audit log & Rollback checkpoints</p>
              </div>
              <button
                onClick={() => setShowVersions(false)}
                className="p-2 rounded-full hover:bg-surface-container transition-all"
              >
                <X size={20} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-4 custom-scrollbar">
              {isLoadingVersions ? (
                <div className="h-40 flex items-center justify-center">
                  <Loader2 className="w-8 h-8 text-primary animate-spin opacity-20" />
                </div>
              ) : versions.length > 0 ? versions.map((v) => (
                <div
                  key={v.id}
                  className={cn(
                    "p-5 rounded-3xl border border-outline-variant transition-all hover:border-primary/30 group relative overflow-hidden",
                    v.is_current ? "bg-primary/5 border-primary/20 ring-1 ring-primary/10" : "bg-white"
                  )}
                >
                  <div className="flex justify-between items-start mb-3">
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-xs font-black text-on-surface">v{v.version}</span>
                      {v.is_current && (
                        <span className="px-2 py-0.5 rounded-full bg-primary text-white text-[8px] font-black uppercase tracking-widest animate-pulse">Live</span>
                      )}
                    </div>
                    {!v.is_current && (
                      <button
                        onClick={() => rollbackVersion(v.id.split('-')[0], v.version)} // Simple ID check
                        className="text-[9px] font-black text-primary uppercase tracking-widest opacity-0 group-hover:opacity-100 transition-all hover:underline"
                      >
                        Rollback to this
                      </button>
                    )}
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 text-on-surface-variant opacity-60">
                      <Clock size={10} />
                      <span className="text-[10px] font-bold">Created: {new Date(v.created_at).toLocaleString('ko-KR')}</span>
                    </div>
                    {v.activated_at && (
                      <div className="flex items-center gap-2 text-primary opacity-80">
                        <ShieldCheck size={10} />
                        <span className="text-[10px] font-bold">Activated: {new Date(v.activated_at).toLocaleString('ko-KR')}</span>
                      </div>
                    )}
                  </div>
                </div>
              )) : (
                <div className="h-40 flex flex-col items-center justify-center opacity-30">
                  <History size={32} className="mb-2" />
                  <p className="text-[10px] font-black uppercase tracking-widest">No previous versions</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PolicyCompilerPage;
