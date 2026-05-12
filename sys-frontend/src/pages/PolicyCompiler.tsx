import React from 'react';
import { 
  Terminal, 
  Upload, 
  Save, 
  Play, 
  RotateCw, 
  Trash2, 
  Edit3, 
  CheckCircle,
  FileCode,
  Maximize2,
  Sparkles
} from 'lucide-react';
import { cn } from '@/src/lib/utils';

const policies = [
  { id: 'SA-POL-24001', name: 'Restricted Data Access', version: '1.0.4', status: 'ACTIVE', modified: '2024-10-24 14:20' },
  { id: 'SA-POL-24002', name: 'Global IP Blocklist', version: '2.1.0', status: 'INACTIVE', modified: '2024-10-23 09:15' },
  { id: 'SA-POL-24003', name: 'MFA Enforcement v2', version: '1.0.0', status: 'ACTIVE', modified: '2024-10-22 17:45' },
];

const mockCode = `policy_metadata:
  id: "SA-POL-2024-001"
  name: "Restricted Data Access Control"
  version: "1.0.4-stable"
  origin: "internal_regulation_doc_v2"

rules:
  - rule_id: "RULE-001"
    scope: ["finance", "legal"]
    condition:
      access_level: "RESTRICTED"
      mfa_required: true
    action: "ALLOW_WITH_LOG"

  - rule_id: "RULE-002"
    scope: ["global"]
    condition:
      source_ip: "BLOCKLIST_EXTERNAL"
    action: "IMMEDIATE_DENY"
    notify: "security_officer_alert"

pipeline_configs:
  conversion_engine: "F3_ALPHA"
  auto_deploy: false
  validation_check: "STRICT"`;

const PolicyCompilerPage = () => {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 h-full animate-in fade-in zoom-in-95 duration-500">
      {/* Left Pane: Policy Management */}
      <div className="flex flex-col gap-6">
        <div>
          <h2 className="text-2xl font-bold text-primary font-display">Policy Management</h2>
          <p className="text-on-surface-variant text-sm font-medium mt-1">규정 문서를 관리하고 정책을 등록합니다.</p>
        </div>

        {/* Upload Card */}
        <div className="glass-panel p-5 rounded-2xl border-dashed border-primary/30 hover:border-primary/60 transition-all cursor-pointer group flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-primary-container/10 flex items-center justify-center border border-primary/20 group-hover:scale-110 transition-transform">
            <Upload className="w-6 h-6 text-primary" />
          </div>
          <div className="flex-1">
            <p className="font-bold text-on-surface">규정(.docx) 업로드</p>
            <p className="text-xs text-on-surface-variant">드래그하거나 클릭하여 새 정책 문서를 추가하세요.</p>
          </div>
          <button className="px-4 py-2 bg-primary text-on-primary text-xs font-bold rounded-lg hover:brightness-110 transition-all shadow-md">
            파일 선택
          </button>
        </div>

        {/* Policy Grid */}
        <div className="glass-panel rounded-2xl overflow-hidden flex-1 flex flex-col">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-surface-container-high/50 border-b border-outline-variant/30 text-[10px] font-black uppercase tracking-widest text-on-surface-variant">
                <th className="px-6 py-4">Policy ID</th>
                <th className="px-6 py-4">Name</th>
                <th className="px-6 py-4 text-center">Status</th>
                <th className="px-6 py-4 text-right">Modified</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/20">
              {policies.map((p) => (
                <tr key={p.id} className="hover:bg-surface-container transition-colors group cursor-pointer">
                  <td className="px-6 py-5 font-mono text-[11px] text-primary font-bold">{p.id}</td>
                  <td className="px-6 py-5">
                    <div className="flex flex-col">
                      <span className="text-xs font-bold text-on-surface">{p.name}</span>
                      <span className="text-[10px] text-on-surface-variant font-medium">v{p.version}</span>
                    </div>
                  </td>
                  <td className="px-6 py-5 text-center">
                    <span className={cn(
                      "text-[9px] font-black uppercase tracking-tighter px-2 py-0.5 rounded-full border",
                      p.status === 'ACTIVE' ? "bg-green-100 text-green-700 border-green-200" : "bg-surface-container-highest text-on-surface-variant border-outline-variant"
                    )}>
                      {p.status}
                    </span>
                  </td>
                  <td className="px-6 py-5 text-right font-mono text-[10px] text-on-surface-variant uppercase">{p.modified}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Right Pane: Code Editor */}
      <div className="flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-primary font-display">YAML Editor</h2>
            <p className="text-sm text-on-surface-variant font-medium mt-1">정책 코드를 편집하고 활성화합니다.</p>
          </div>
          <div className="flex gap-2">
            <button className="p-2 glass-panel hover:bg-surface-container transition-colors rounded-xl text-primary">
              <Save className="w-4 h-4" />
            </button>
            <button className="p-2 glass-panel hover:bg-surface-container transition-colors rounded-xl text-primary">
              <RotateCw className="w-4 h-4" />
            </button>
            <button className="flex items-center gap-2 px-4 py-2 bg-primary text-on-primary font-bold text-xs rounded-xl hover:brightness-110 transition-all shadow-lg shadow-primary/20">
              <CheckCircle className="w-4 h-4" />
              Activate
            </button>
          </div>
        </div>

        <div className="glass-panel flex-1 rounded-2xl overflow-hidden flex flex-col shadow-lg border-primary/10">
          <div className="px-5 py-3 bg-primary-container/10 border-b border-outline-variant/30 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="flex gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-error/30"></div>
                <div className="w-2.5 h-2.5 rounded-full bg-amber-400/30"></div>
                <div className="w-2.5 h-2.5 rounded-full bg-green-500/30"></div>
              </div>
              <span className="font-mono text-[11px] font-bold text-primary/70 tracking-widest uppercase">f3_compiled_policy_v1.yaml</span>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1.5 bg-green-500/10 px-2 py-0.5 rounded border border-green-500/20">
                <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></div>
                <span className="text-[9px] font-black text-green-700 uppercase tracking-widest">Editor Active</span>
              </div>
              <Maximize2 className="w-4 h-4 text-on-surface-variant cursor-pointer hover:text-primary transition-colors" />
            </div>
          </div>
          <div className="flex-1 bg-white relative flex">
            <div className="w-12 bg-surface-container-low/50 border-r border-outline-variant/20 flex flex-col items-center py-6 text-[10px] font-mono text-outline-variant select-none leading-relaxed">
              {Array.from({ length: 25 }).map((_, i) => <span key={i}>{i + 1}</span>)}
            </div>
            <textarea 
              readOnly
              className="flex-1 p-6 font-mono text-xs leading-relaxed text-on-surface outline-none resize-none custom-scrollbar"
              value={mockCode}
            />
          </div>
        </div>
      </div>

      {/* Floating Badge */}
      <div className="fixed bottom-10 right-10 flex items-center gap-4 p-5 glass-panel rounded-2xl border border-primary/20 shadow-2xl z-50 animate-bounce duration-[2000ms]">
        <div className="relative">
          <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center border border-primary/20">
            <Sparkles className="w-6 h-6 text-primary" />
          </div>
          <div className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-green-500 rounded-full border-2 border-white shadow-sm"></div>
        </div>
        <div className="flex flex-col">
          <p className="text-[10px] font-black text-primary tracking-widest uppercase">Auto-Conversion Active</p>
          <p className="text-sm font-bold text-on-surface">Monitoring Doc Influx...</p>
        </div>
      </div>
    </div>
  );
};

export default PolicyCompilerPage;
