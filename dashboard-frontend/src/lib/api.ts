import axios from 'axios';

// baseURL을 빈 값으로 설정하여 각 서비스별 프리픽스 대응 가능하도록 변경
export const api = axios.create({
  baseURL: '', 
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request Interceptor: 토큰 자동 주입 (기존 호환성 유지)
api.interceptors.request.use(
  (config) => {
    const savedUser = localStorage.getItem('safeagent_user');
    if (savedUser) {
      try {
        const parsed = JSON.parse(savedUser);
        if (parsed.access_token && config.headers) {
          config.headers.Authorization = `Bearer ${parsed.access_token}`;
        }
      } catch (error) {
        console.error('Failed to parse user from localStorage', error);
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response Interceptor: 401 발생 시 리다이렉트 없이 에러만 로깅
api.interceptors.response.use(
  (response) => {
    return response;
  },
  async (error) => {
    // 401 Unauthorized 발생 시 리다이렉트 로직 제거 (데모 모드 대응)
    if (error.response?.status === 401) {
      console.warn('인증 인증 실패 (401): 데모 환경에서 일부 데이터가 제한될 수 있습니다.');
    }
    return Promise.reject(error);
  }
);
