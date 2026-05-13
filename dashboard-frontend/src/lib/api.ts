import axios from 'axios';

// baseURL을 빈 값으로 설정하여 각 서비스별 프리픽스 대응 가능하도록 변경
export const api = axios.create({
  baseURL: '', 
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
          
          // 서버의 /v1/proxy, /v1/input-guard 등 머신용 엔드포인트 대응을 위한 API Key 추가
          // 서버가 DEMO_AUTH_BYPASS=true 인 경우 값에 상관없이 통과되며, 
          // 운영 환경에서는 실제 발급된 키를 사용해야 합니다.
          if (config.url?.includes('/v1/proxy') || 
              config.url?.includes('/v1/input-guard') || 
              config.url?.includes('/v1/response-guard')) {
            config.headers['X-API-Key'] = 'sak_dashboard_demo_key_default';
          }
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
