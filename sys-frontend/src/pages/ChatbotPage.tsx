import React, { useState, useRef, useEffect } from 'react';
import { 
  Send, 
  Paperclip, 
  Mic, 
  User, 
  Shield, 
  MoreVertical, 
  Sparkles, 
  ChevronRight,
  ShieldAlert,
  Search,
  MessageSquare,
  Home,
  Settings,
  MoreHorizontal,
  Plus,
  ShieldCheck,
  Lock,
  FileText,
  LogOut,
  History,
  Trash2,
  ArrowLeft
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { useAuth } from '@/src/contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { GoogleGenAI } from "@google/genai";

interface Message {
  id: string;
  type: 'user' | 'ai';
  content: string;
  timestamp: Date;
  status?: 'warning' | 'info' | 'success';
}

interface ChatHistory {
  id: string;
  title: string;
  timestamp: Date;
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
  const [history, setHistory] = useState<ChatHistory[]>([
    { id: 'h1', title: '비밀번호 변경 정책 문의', timestamp: new Date() },
    { id: 'h2', title: '외부망 VPN 접속 가이드', timestamp: new Date() },
    { id: 'h3', title: '보안 USB 신청 절차', timestamp: new Date() }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isTyping]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const handleNewChat = () => {
    setMessages([{
      id: Date.now().toString(),
      type: 'ai',
      content: '새로운 대화를 시작합니다. 무엇을 도와드릴까요?',
      timestamp: new Date(),
    }]);
  };

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: input,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    try {
      // Simple logic check for "security violation" simulation
      const contentLower = input.toLowerCase();
      let responseContent = "";
      let status: 'warning' | 'info' | 'success' | undefined;

      if (contentLower.includes("비밀번호") || contentLower.includes("password")) {
        responseContent = "보안 규정 4.2조에 따라, 비밀번호는 절대 타인과 공유해서는 안 되며 3개월마다 갱신해야 합니다. 현재 사용자의 비밀번호 보안 등급은 '양호'입니다.";
        status = 'info';
      } else if (contentLower.includes("외부망") || contentLower.includes("vpn")) {
        responseContent = "외부망 접속 시 반드시 지정된 VPN을 사용해야 하며, 비가용 IP에서의 접근은 자동 차단됩니다. 사외 접속 승인이 필요하신가요?";
        status = 'warning';
      } else {
        // Mock AI response
        responseContent = `"${input}"에 대한 사내 가이드를 확인 중입니다. 현재 시스템 상에서는 특별한 제약 사항이 발견되지 않았습니다. 추가로 도움 드릴 내용이 있을까요?`;
      }

      // Simulate network delay
      await new Promise(resolve => setTimeout(resolve, 1500));

      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'ai',
        content: responseContent,
        timestamp: new Date(),
        status
      };

      setMessages(prev => [...prev, aiMessage]);
    } catch (error) {
      console.error(error);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="flex h-screen bg-surface font-sans overflow-hidden">
      {/* Expanded Sidebar (Matching Admin Sidebar Width) */}
      <aside className="w-64 bg-white border-r border-outline-variant flex flex-col h-screen shrink-0 relative z-20">
        {/* Sidebar Header */}
        <div className="p-6 border-b border-outline-variant">
          <div className="flex items-center gap-3">
             <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center text-white shadow-lg shadow-primary/20">
                <Shield className="w-6 h-6" />
             </div>
             <span className="text-xl font-black text-primary tracking-tight font-display">SafeAgent</span>
          </div>
        </div>

        {/* Action Button */}
        <div className="p-4">
           <button 
            onClick={handleNewChat}
            className="w-full flex items-center justify-center gap-2 py-4 bg-primary/5 hover:bg-primary/10 text-primary rounded-2xl transition-all duration-300 font-bold group border border-primary/10 shadow-sm"
          >
             <Plus className="w-5 h-5 group-hover:rotate-90 transition-transform duration-300" />
             <span>New Security Session</span>
           </button>
        </div>
        
        {/* Chat History List */}
        <div className="flex-1 overflow-y-auto px-2 py-4 space-y-6">
           <div>
              <h3 className="px-4 text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant/40 mb-4">Recent History</h3>
              <nav className="space-y-1">
                {history.map((item) => (
                   <button 
                    key={item.id}
                    className="w-full text-left px-4 py-3 rounded-xl hover:bg-surface-container-low transition-colors group relative flex items-center gap-3"
                   >
                     <MessageSquare className="w-4 h-4 text-on-surface-variant/40 group-hover:text-primary transition-colors shrink-0" />
                     <span className="text-sm font-bold text-on-surface-variant group-hover:text-on-surface truncate">{item.title}</span>
                     <div className="absolute right-4 opacity-0 group-hover:opacity-100 transition-opacity">
                        <MoreVertical className="w-3.5 h-3.5 text-on-surface-variant" />
                     </div>
                   </button>
                ))}
              </nav>
           </div>
        </div>

        {/* Sidebar Footer: Profile & Logout */}
        <div className="mt-auto border-t border-outline-variant bg-surface-container-lowest/50 p-4">
           <div className="flex items-center gap-3 mb-4 px-2">
              <div className="w-10 h-10 rounded-full overflow-hidden border-2 border-primary/10 shadow-sm bg-white shrink-0">
                 <img src={`https://api.dicebear.com/7.x/avataaars/svg?seed=${user?.name}`} alt="Avatar" className="w-full h-full object-cover" />
              </div>
              <div className="flex-1 min-w-0">
                 <p className="text-sm font-black text-on-surface truncate">{user?.name || 'User'}</p>
                 <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">{user?.role || 'Employee'}</p>
              </div>
           </div>
           
           <button 
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-4 py-3 bg-white border border-outline-variant rounded-xl text-on-surface-variant hover:text-red-500 hover:bg-red-50 hover:border-red-100 transition-all font-bold text-xs"
          >
              <LogOut className="w-4 h-4" />
              <span>로그아웃 (Sign Out)</span>
           </button>
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col relative max-w-6xl mx-auto">
        {/* Header */}
        <header className="h-[72px] px-8 flex justify-between items-center border-b border-outline-variant bg-white/80 backdrop-blur-md sticky top-0 z-10 w-full">
           <div className="flex items-center gap-4">
              {user?.role === 'ADMIN' && (
                <button 
                  onClick={() => navigate('/admin/dashboard')}
                  className="flex items-center gap-2 px-3 py-2 rounded-xl bg-surface hover:bg-surface-dim text-on-surface-variant hover:text-primary transition-all font-bold text-xs border border-outline-variant mr-2"
                >
                  <ArrowLeft className="w-4 h-4" />
                  <span>대시보드로 돌아가기</span>
                </button>
              )}
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                 <Shield className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h1 className="text-sm font-black text-on-surface tracking-tight uppercase">SafeAgent Chat</h1>
                <div className="flex items-center gap-1.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse"></div>
                  <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Active Security Guard</span>
                </div>
              </div>
           </div>
           
           <div className="flex items-center gap-2">
             <button className="w-10 h-10 rounded-xl hover:bg-surface-container-low flex items-center justify-center text-on-surface-variant transition-colors border border-outline-variant">
                <Sparkles className="w-4 h-4" />
             </button>
             <button className="w-10 h-10 rounded-xl hover:bg-surface-container-low flex items-center justify-center text-on-surface-variant transition-colors border border-outline-variant">
                <MoreHorizontal className="w-4 h-4" />
             </button>
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
              <div className={`w-8 h-8 rounded-[12px] flex items-center justify-center shrink-0 shadow-sm ${
                msg.type === 'user' ? 'bg-primary' : 'bg-white border border-outline-variant'
              }`}>
                {msg.type === 'user' ? (
                  <User className="w-5 h-5 text-on-primary" />
                ) : (
                  <Shield className="w-5 h-5 text-primary" />
                )}
              </div>

              <div className={`flex flex-col gap-2 max-w-[70%] ${msg.type === 'user' ? 'items-end' : 'items-start'}`}>
                <div className={`
                  p-5 rounded-[1.5rem] text-sm leading-relaxed shadow-sm
                  ${msg.type === 'user' 
                    ? 'bg-primary text-on-primary rounded-tr-none' 
                    : 'bg-white text-on-surface border border-outline-variant rounded-tl-none'}
                `}>
                  {msg.status === 'warning' && (
                    <div className="flex items-center gap-2 mb-2 p-2 bg-red-50 rounded-lg border border-red-100 text-red-600 font-bold text-xs">
                       <ShieldAlert className="w-4 h-4" />
                       보안 주의 알림
                    </div>
                  )}
                  {msg.content}
                </div>
                <span className="text-[10px] font-bold text-on-surface-variant/40 uppercase tracking-widest px-1">
                  {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            </motion.div>
          ))}

          {isTyping && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-3 bg-white p-3 rounded-full border border-outline-variant w-fit shadow-sm">
               <div className="flex gap-1">
                  <div className="w-1.5 h-1.5 bg-primary/40 rounded-full animate-bounce"></div>
                  <div className="w-1.5 h-1.5 bg-primary/40 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                  <div className="w-1.5 h-1.5 bg-primary/40 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
               </div>
               <span className="text-[10px] font-black uppercase tracking-widest text-primary/60">Secure Analysis...</span>
            </motion.div>
          )}
        </div>

        {/* Input Area */}
        <div className="absolute bottom-8 left-8 right-8 z-10">
          <div className="max-w-4xl mx-auto relative group">
            <div className="absolute -inset-1 bg-gradient-to-r from-primary/10 to-primary/5 rounded-[2.5rem] blur opacity-0 group-focus-within:opacity-100 transition-opacity"></div>
            <div className="relative bg-white border border-outline-variant rounded-[2.5rem] shadow-xl p-2 flex items-center gap-2">
              <button className="w-10 h-10 rounded-full hover:bg-surface-container-low flex items-center justify-center text-on-surface-variant transition-colors shrink-0">
                <Paperclip className="w-5 h-5" />
              </button>
              <input 
                type="text" 
                placeholder="Ask me anything about security..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                className="flex-1 bg-transparent border-none outline-none px-4 py-2 text-sm font-medium text-on-surface placeholder:text-on-surface-variant/40"
              />
              <button className="w-10 h-10 rounded-full hover:bg-surface-container-low flex items-center justify-center text-on-surface-variant transition-colors shrink-0">
                <Mic className="w-5 h-5" />
              </button>
              <button 
                onClick={handleSend}
                className="w-12 h-12 rounded-full bg-primary text-on-primary flex items-center justify-center shadow-lg shadow-primary/20 hover:scale-105 active:scale-95 transition-all shrink-0"
              >
                <Send className="w-5 h-5" />
              </button>
            </div>
          </div>
          <div className="mt-4 text-center">
            <p className="text-[10px] font-black text-on-surface-variant uppercase tracking-[0.3em] flex items-center justify-center gap-2">
               <Shield className="w-3 h-3 text-primary" />
               Enterprise AI Protection Active
            </p>
          </div>
        </div>
      </main>

      {/* Right Sidebar (Contextual) */}
      <aside className="w-80 bg-white border-l border-outline-variant hidden xl:flex flex-col p-8 gap-8">
         <div className="flex flex-col gap-4">
            <h3 className="text-xs font-black uppercase tracking-widest text-on-surface-variant">Active Task</h3>
            <div className="p-5 rounded-2xl bg-surface-container-low border border-outline-variant space-y-3">
               <div className="flex items-center gap-2 text-primary">
                  <ShieldCheck className="w-4 h-4" />
                  <span className="text-xs font-bold">Policy Audit</span>
               </div>
               <p className="text-xs font-medium text-on-surface-variant leading-relaxed">
                  Analyzing current workspace for compliance with ISO/IEC 27001 standards.
               </p>
               <div className="w-full bg-surface-container-high rounded-full h-1 overflow-hidden">
                  <div className="bg-primary h-full w-[65%] rounded-full"></div>
               </div>
            </div>
         </div>

         <div className="flex flex-col gap-4">
            <h3 className="text-xs font-black uppercase tracking-widest text-on-surface-variant">Quick Shortcuts</h3>
            <div className="space-y-2">
               <ShortcutItem icon={<Shield />} label="Security Report" />
               <ShortcutItem icon={<Lock />} label="Vault Access" />
               <ShortcutItem icon={<FileText />} label="Company Handbook" />
            </div>
         </div>

         <div className="mt-auto p-6 bg-primary-container/10 border border-primary/20 rounded-[2rem] flex flex-col items-center text-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-primary flex items-center justify-center text-white shadow-lg">
               <Sparkles className="w-6 h-6" />
            </div>
            <h4 className="text-sm font-black text-primary tracking-tight">Need Support?</h4>
            <p className="text-[10px] font-bold text-primary leading-relaxed opacity-70">
               Connect with a human security officer for urgent threats.
            </p>
            <button className="mt-2 w-full py-3 bg-primary text-on-primary rounded-xl text-xs font-black uppercase tracking-widest hover:brightness-110 transition-all font-bold">
               Connect Now
            </button>
         </div>
      </aside>
    </div>
  );
};

const SidebarIcon = ({ icon, active = false }: { icon: React.ReactNode, active?: boolean }) => (
  <button className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all ${
    active 
      ? 'bg-primary text-on-primary shadow-lg shadow-primary/20 scale-110' 
      : 'text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface'
  }`}>
    {React.cloneElement(icon as React.ReactElement, { size: 20 })}
  </button>
);

const ShortcutItem = ({ icon, label }: { icon: React.ReactNode, label: string }) => (
  <button className="w-full flex items-center gap-3 p-3 rounded-xl hover:bg-surface-container-low transition-colors group">
    <div className="text-on-surface-variant group-hover:text-primary transition-colors">
       {React.cloneElement(icon as React.ReactElement, { size: 16 })}
    </div>
    <span className="text-xs font-bold text-on-surface-variant group-hover:text-on-surface transition-colors">{label}</span>
    <ChevronRight className="w-3 h-3 ml-auto text-on-surface-variant opacity-0 group-hover:opacity-100 transition-all" />
  </button>
);


