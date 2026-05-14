import React, { useState, useRef, useEffect } from 'react';
import {
  Send,
  Paperclip,
  User,
  Shield,
  Plus,
  ShieldAlert,
  MessageSquare,
  ArrowLeft,
  Loader2,
  Lock,
  FileText
} from 'lucide-react';
import { motion } from 'motion/react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { cn } from '../lib/utils';

interface Message {
  id: string;
  type: 'user' | 'ai';
  content: string;
  timestamp: Date;
  status?: 'warning' | 'info' | 'success';
  isBlocked?: boolean;
}

interface ChatHistory {
  id: string;
  title: string;
  timestamp: Date;
}

interface Agent {
  id: string;
  name: string;
  description?: string;
  status: string;
}

export const ChatbotPage = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      type: 'ai',
      content: '반갑습니다! SafeAgent 보안 비서입니다. 사내 보안 정책이나 시스템 이용 수칙에 대해 궁금한 점이 있으신가요?',
      timestamp: new Date(),
    }
  ]);
  const [history] = useState<ChatHistory[]>([
    // { id: 'h1', title: '비밀번호 변경 정책 문의', timestamp: new Date() },
    // { id: 'h2', title: '외부망 VPN 접속 가이드', timestamp: new Date() }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        const response = await api.get('/api/agents');
        const agentList = response.data;
        setAgents(agentList);
        if (agentList.length > 0) {
          setSelectedAgent(agentList[0]);
        }
      } catch (error) {
        console.error('Failed to fetch agents:', error);
      }
    };
    fetchAgents();
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isTyping]);

  const handleExit = () => {
    logout();
    navigate('/');
  };

  const handleNewChat = () => {
    setMessages([{
      id: Date.now().toString(),
      type: 'ai',
      content: '새로운 보안 세션을 시작합니다. 모든 대화는 거버넌스 정책에 의해 보호됩니다.',
      timestamp: new Date(),
    }]);
  };

  const handleSend = async () => {
    if (!input.trim() || isTyping) return;

    const userText = input;
    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: userText,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    try {
      // 1. 백엔드 보안 프록시 호출: POST /v1/proxy/chat
      const response = await api.post('/v1/proxy/chat', {
        query: userText,
        agent_id: selectedAgent?.id || "AGENT-FINANCE-01",
        context: `User: ${user?.id || 'demo_employee'}, Dept: Security` // 객체에서 문자열로 변경
      });

      const data = response.data;

      // 2. 백엔드 ProxyChatResponse 구조에 맞게 매핑
      // status: APPROVED, BLOCKED_BY_QUERY, REJECTED_BY_RESPONSE, FAILED 등
      let aiContent = data.final_response || "답변을 생성할 수 없습니다.";
      let messageStatus: 'warning' | 'info' | 'success' | undefined;
      let isBlocked = false;

      // 쿼리 차단 또는 응답 거부 시 처리
      if (data.status === 'BLOCKED_BY_QUERY' || data.status === 'REJECTED_BY_RESPONSE') {
        messageStatus = 'warning';
        isBlocked = true;
      } else if (data.status === 'APPROVED') {
        messageStatus = 'success';
      } else if (data.status === 'FAILED') {
        aiContent = `처리 중 오류가 발생했습니다: ${data.error_message || 'Unknown error'}`;
        messageStatus = 'warning';
      }

      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'ai',
        content: aiContent,
        timestamp: new Date(),
        status: messageStatus,
        isBlocked: isBlocked
      };

      setMessages(prev => [...prev, aiMessage]);

    } catch (error: any) {
      console.error("Chat Error:", error);
      const errorMessage: Message = {
        id: Date.now().toString(),
        type: 'ai',
        content: "현재 보안 게이트웨이와 통신할 수 없습니다. 서버 상태를 확인하거나 잠시 후 다시 시도해 주세요.",
        timestamp: new Date(),
        status: 'warning'
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="flex h-screen bg-surface font-sans overflow-hidden">
      {/* Sidebar - Same logic as before */}
      <aside className="w-64 bg-white border-r border-outline-variant flex flex-col h-screen shrink-0 relative z-20">
        <div className="p-6 border-b border-outline-variant">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center text-white shadow-lg shadow-primary/20">
              <Shield className="w-6 h-6" />
            </div>
            <span className="text-xl font-black text-primary tracking-tight font-display">SafeAgent</span>
          </div>
        </div>

        <div className="p-4">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center justify-center gap-2 py-4 bg-primary/5 hover:bg-primary/10 text-primary rounded-2xl transition-all duration-300 font-bold group border border-primary/10 shadow-sm"
          >
            <Plus className="w-5 h-5 group-hover:rotate-90 transition-transform duration-300" />
            <span>New Security Session</span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-2 py-4 space-y-6">
          <div>
            {/* <h3 className="px-4 text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant/40 mb-4">Recent History</h3> */}
            <nav className="space-y-1">
              {history.map((item) => (
                <button
                  key={item.id}
                  className="w-full text-left px-4 py-3 rounded-xl hover:bg-surface-container-low transition-colors group flex items-center gap-3"
                >
                  <MessageSquare className="w-4 h-4 text-on-surface-variant/40 group-hover:text-primary transition-colors shrink-0" />
                  <span className="text-sm font-bold text-on-surface-variant group-hover:text-on-surface truncate">{item.title}</span>
                </button>
              ))}
            </nav>
          </div>
        </div>

        <div className="mt-auto border-t border-outline-variant bg-surface-container-lowest/50 p-4">
          <div className="flex items-center gap-3 mb-4 px-2">
            <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center border border-primary/20 shrink-0">
              <User className="text-primary w-6 h-6" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-black text-on-surface truncate">Demo User</p>
              <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">{user?.role || 'EMPLOYEE'}</p>
            </div>
          </div>

          <button
            onClick={handleExit}
            className="w-full flex items-center gap-3 px-4 py-3 bg-white border border-outline-variant rounded-xl text-on-surface-variant hover:text-primary hover:border-primary transition-all font-bold text-xs"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Gateway로 돌아가기</span>
          </button>
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col relative max-w-6xl mx-auto">
        <header className="h-[72px] px-8 flex justify-between items-center border-b border-outline-variant bg-white/80 backdrop-blur-md sticky top-0 z-10 w-full">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
              <Shield className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h1 className="text-sm font-black text-on-surface tracking-tight uppercase">
                {selectedAgent ? `${selectedAgent.name} Chat` : 'SafeAgent Chat'}
              </h1>
              <div className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></div>
                <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">
                  {selectedAgent ? 'Active Security Guard' : 'Loading Security Guard...'}
                </span>
              </div>
            </div>
          </div>
        </header>

        {/* Message Feed */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto p-8 space-y-8 h-full pb-32"
        >
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex items-start gap-4 ${msg.type === 'user' ? 'flex-row-reverse' : ''}`}
            >
              <div className={`w-10 h-10 rounded-[14px] flex items-center justify-center shrink-0 shadow-sm ${msg.type === 'user' ? 'bg-primary' : 'bg-white border border-outline-variant'
                }`}>
                {msg.type === 'user' ? (
                  <User className="w-6 h-6 text-on-primary" />
                ) : (
                  <Shield className="w-6 h-6 text-primary" />
                )}
              </div>

              <div className={`flex flex-col gap-2 max-w-[75%] ${msg.type === 'user' ? 'items-end' : 'items-start'}`}>
                <div className={`
                  p-6 rounded-[2rem] text-[13px] leading-relaxed shadow-sm whitespace-pre-wrap
                  ${msg.type === 'user'
                    ? 'bg-primary text-on-primary rounded-tr-none'
                    : msg.isBlocked ? 'bg-error/5 text-error border border-error/20 rounded-tl-none font-bold' : 'bg-white text-on-surface border border-outline-variant rounded-tl-none'}
                `}>
                  {msg.status === 'warning' && !msg.isBlocked && (
                    <div className="flex items-center gap-2 mb-3 p-2 bg-amber-50 rounded-lg border border-amber-100 text-amber-600 font-black text-[10px] uppercase tracking-widest">
                      <ShieldAlert className="w-4 h-4" />
                      Security Awareness Warning
                    </div>
                  )}
                  {msg.isBlocked && (
                    <div className="flex items-center gap-2 mb-3 p-2 bg-error/10 rounded-lg text-error font-black text-[10px] uppercase tracking-widest">
                      <ShieldAlert className="w-4 h-4" />
                      Access Denied by Policy
                    </div>
                  )}
                  {msg.content}
                </div>
                <span className="text-[9px] font-bold text-on-surface-variant/40 uppercase tracking-[0.2em] px-2 mt-1">
                  {msg.type === 'user' ? 'You' : 'Guard'} • {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            </motion.div>
          ))}
          {isTyping && (
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-[14px] bg-white border border-outline-variant flex items-center justify-center">
                <Shield className="w-5 h-5 text-primary/40" />
              </div>
              <div className="flex gap-1.5 p-4 bg-surface-container rounded-2xl rounded-tl-none">
                <div className="w-1.5 h-1.5 rounded-full bg-primary/40 animate-bounce"></div>
                <div className="w-1.5 h-1.5 rounded-full bg-primary/40 animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                <div className="w-1.5 h-1.5 rounded-full bg-primary/40 animate-bounce" style={{ animationDelay: '0.4s' }}></div>
              </div>
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="absolute bottom-8 left-8 right-8 z-10">
          <div className="max-w-4xl mx-auto relative">
            <div className="relative bg-white/90 backdrop-blur-xl border border-outline-variant rounded-[2.5rem] shadow-[0_20px_50px_rgba(0,0,0,0.1)] p-2.5 flex items-center gap-3 group focus-within:ring-2 focus-within:ring-primary/20 transition-all">
              <input
                type="text"
                placeholder={isTyping ? "보안 검토 중..." : "인증된 보안 채널을 통해 질문하세요..."}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                disabled={isTyping}
                className="flex-1 bg-transparent border-none outline-none pl-6 pr-4 py-3 text-sm font-bold text-on-surface placeholder:text-on-surface-variant/40 disabled:opacity-40"
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || isTyping}
                className={cn(
                  "w-12 h-12 rounded-full bg-primary text-on-primary flex items-center justify-center shadow-lg shadow-primary/20 hover:scale-105 active:scale-95 transition-all shrink-0",
                  (!input.trim() || isTyping) && "opacity-40 scale-100 grayscale hover:scale-100"
                )}
              >
                {isTyping ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
              </button>
            </div>
          </div>
        </div>
      </main>

      {/* Right Sidebar - Shortcuts */}
      <aside className="w-80 bg-white border-l border-outline-variant hidden xl:flex flex-col p-8 gap-8">
        <div className="flex flex-col gap-6">
          <h3 className="text-[10px] font-black uppercase tracking-[0.3em] text-on-surface-variant/40">Quick Guard Actions</h3>
          <div className="space-y-3">
            <ShortcutItem icon={<Shield />} label="Security Handbook" />
            <ShortcutItem icon={<Lock />} label="Request Access" />
            <ShortcutItem icon={<FileText />} label="Protocol Guide" />
          </div>
        </div>
        <div className="mt-auto p-6 bg-surface-container-low rounded-[2rem] border border-outline-variant/30 flex flex-col gap-4">
          <div className="flex items-center gap-3 text-primary">
            <ShieldCheck className="w-5 h-5" />
            <span className="text-[10px] font-black uppercase tracking-widest">Gateway Verified</span>
          </div>
          <p className="text-[11px] font-bold text-on-surface-variant leading-relaxed">모든 대화 내용은 거버넌스 규정에 따라 감사 로그로 기록되며, 위반 사항 발생 시 즉시 차단될 수 있습니다.</p>
        </div>
      </aside>
    </div>
  );
};

const ShortcutItem = ({ icon, label }: { icon: React.ReactNode, label: string }) => (
  <button className="w-full flex items-center gap-4 p-4 rounded-2xl hover:bg-surface-container-low transition-all group border border-transparent hover:border-outline-variant/20">
    <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-on-surface-variant group-hover:text-primary group-hover:bg-primary/5 transition-all shadow-sm">
      {React.cloneElement(icon as React.ReactElement, { size: 14 })}
    </div>
    <span className="text-xs font-black text-on-surface-variant group-hover:text-on-surface transition-colors uppercase tracking-tight">{label}</span>
  </button>
);

const ShieldCheck = ({ className }: { className?: string }) => (
  <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /><polyline points="9 12 11 14 15 10" /></svg>
);
