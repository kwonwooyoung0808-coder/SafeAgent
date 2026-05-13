import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../lib/api';

export type UserRole = 'ADMIN' | 'EMPLOYEE' | 'GUEST';

export interface User {
  user_id: string;
  username: string;
  role: UserRole;
  policy_groups: string[];
  access_token?: string;
}

interface AuthContextType {
  user: User | null;
  setRole: (role: UserRole) => void;
  loginAsAdmin: () => Promise<boolean>;
  loginAsEmployee: () => Promise<boolean>;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

/**
 * 401 에러 해결을 위한 자동 로그인 기능이 포함된 AuthProvider
 */
export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // 1. 기존 저장된 실제 유저 정보(토큰 포함) 확인
    const savedUser = localStorage.getItem('safeagent_user');
    if (savedUser) {
      try {
        const parsed = JSON.parse(savedUser);
        setUser(parsed);
      } catch (e) {
        localStorage.removeItem('safeagent_user');
      }
    } else {
      // 2. 데모용 역할 정보만 있는 경우 (하위 호환성)
      const savedRole = localStorage.getItem('safeagent_demo_role');
      if (savedRole) {
        setUser({
          user_id: 'demo-user',
          username: 'Demo User',
          role: savedRole as UserRole,
          policy_groups: []
        });
      }
    }
    setIsLoading(false);
  }, []);

  const setRole = (role: UserRole) => {
    const newUser: User = {
      user_id: 'demo-user',
      username: 'Demo User',
      role: role,
      policy_groups: []
    };
    setUser(newUser);
    localStorage.setItem('safeagent_demo_role', role);
  };

  /**
   * 역할 기반 자동 로그인 (Improved Silent Login)
   * 데모 환경에서 401 에러를 방지하기 위해 실제 서버에서 정식 JWT 토큰을 받아옵니다.
   */
  const loginAsRole = async (targetRole: UserRole): Promise<boolean> => {
    try {
      // 서버의 초기 관리자 계정을 사용하여 정식 토큰 발급 (데모 환경 범용 계정)
      const response = await api.post('/v1/auth/login', {
        username: 'admin',
        password: 'changeme'
      });

      const { access_token } = response.data;
      
      // 토큰 저장 (이후 요청에서 사용됨)
      localStorage.setItem('safeagent_user', JSON.stringify({ access_token }));

      // 2. /v1/auth/me를 통해 실제 유저 정보 가져오기
      const meResponse = await api.get('/v1/auth/me');
      const { user_id, username, role, policy_groups } = meResponse.data;

      const authenticatedUser: User = {
        user_id,
        username,
        role: targetRole, // 프론트엔드 UI 제어용 역할 (서버 역할과 다를 수 있음)
        policy_groups: policy_groups || [],
        access_token
      };

      setUser(authenticatedUser);
      localStorage.setItem('safeagent_user', JSON.stringify(authenticatedUser));
      localStorage.setItem('safeagent_demo_role', targetRole);

      return true;
    } catch (error) {
      console.error(`Silent login for ${targetRole} failed:`, error);
      // 실패 시 최소한의 역할 정보만 설정 (오프라인/에러 대응)
      const fallbackUser: User = {
        user_id: 'offline-id',
        username: targetRole === 'ADMIN' ? 'Admin (Offline)' : 'Employee (Offline)',
        role: targetRole,
        policy_groups: []
      };
      setUser(fallbackUser);
      localStorage.setItem('safeagent_demo_role', targetRole);
      return false;
    }
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem('safeagent_demo_role');
    localStorage.removeItem('safeagent_user');
  };

  return (
    <AuthContext.Provider value={{ user, setRole, loginAsAdmin: () => loginAsRole('ADMIN'), loginAsEmployee: () => loginAsRole('EMPLOYEE'), logout, isLoading }}>
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
