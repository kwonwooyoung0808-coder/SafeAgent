import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../lib/api';

// 백엔드 시스템 역할(role) 및 프론트엔드 기존 역할 호환
export type UserRole = 'admin' | 'operator' | 'viewer' | 'ADMIN' | 'EMPLOYEE' | 'GUEST';

export interface User {
  user_id: string;
  username: string;
  role: UserRole;
  policy_groups: string[];
}

interface AuthContextType {
  user: User | null;
  login: (credentials: { username: string; password: string }) => Promise<void>;
  logout: () => void;
  signup: (userData: any) => Promise<void>;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // 앱 로드 시: 저장된 토큰이 있다면 백엔드에서 사용자 정보를 갱신(Session Restore)
  useEffect(() => {
    const initAuth = async () => {
      const savedUser = localStorage.getItem('safeagent_user');
      if (savedUser) {
        try {
          const parsed = JSON.parse(savedUser);
          if (parsed.access_token) {
            // api 클라이언트의 Request Interceptor가 알아서 헤더에 토큰을 넣어줍니다.
            const response = await api.get('/auth/me');

            // 권한 대소문자 불일치로 인한 무한 리다이렉트 방지를 위해 대문자로 정규화
            const fetchedUser = response.data;
            if (fetchedUser && fetchedUser.role) {
              fetchedUser.role = fetchedUser.role.toUpperCase();
            }

            setUser(fetchedUser);
          }
        } catch (error) {
          console.error('Session restore failed. Token might be invalid or expired.', error);
          localStorage.removeItem('safeagent_user'); // 유효하지 않은 토큰 파기
        }
      }
      setIsLoading(false);
    };

    initAuth();
  }, []);

  // 실제 백엔드 로그인 로직
  const login = async (credentials: { username: string; password: string }) => {
    try {
      // 1. 백엔드에 아이디/비밀번호를 보내 진짜 토큰을 발급받습니다.
      const tokenResponse = await api.post('/auth/login', credentials);
      const { access_token, refresh_token } = tokenResponse.data;

      // 2. 받은 토큰을 스토리지에 저장합니다. (api.ts가 이후 요청부터 이 토큰을 사용함)
      localStorage.setItem('safeagent_user', JSON.stringify({ access_token, refresh_token }));

      // 3. 발급받은 토큰으로 본인의 진짜 정보를 조회하여 전역 상태(user)를 세팅합니다.
      const meResponse = await api.get('/auth/me');

      const fetchedUser = meResponse.data;
      if (fetchedUser && fetchedUser.role) {
        fetchedUser.role = fetchedUser.role.toUpperCase();
      }

      setUser(fetchedUser);
    } catch (error) {
      console.error('Login failed:', error);
      throw error; // 에러를 던져서 로그인 UI에 실패 메시지를 띄우도록 합니다.
    }
  };

  // 회원가입: 백엔드 /auth/signup 엔드포인트 호출
  const signup = async (userData: any) => {
    try {
      await api.post('/auth/signup', {
        username: userData.email, // email을 username으로 사용
        password: userData.password,
        role: userData.role || 'viewer',
        name: userData.name,
        company_code: userData.companyCode
      });
      // 회원가입 성공 후 자동 로그인 (선택 사항)
      await login({ username: userData.email, password: userData.password });
    } catch (error) {
      console.error('Signup failed:', error);
      throw error;
    }
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem('safeagent_user');
    window.location.href = '/login'; // 모든 상태 초기화를 위해 새로고침 이동
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, signup, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
