import axios from 'axios';

// Create an Axios instance with base configuration
export const api = axios.create({
  // 백엔드 통신용 Proxy 설정 기반 (v1 API 사용)
  baseURL: '/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request Interceptor: 토큰 자동 주입
api.interceptors.request.use(
  (config) => {
    const savedUser = localStorage.getItem('safeagent_user');
    if (savedUser) {
      try {
        const parsed = JSON.parse(savedUser);
        // localStorage 내부에 저장된 access_token 확인
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

// Response Interceptor: 401 발생 시 refresh_token으로 자동 갱신
api.interceptors.response.use(
  (response) => {
    return response;
  },
  async (error) => {
    const originalRequest = error.config;

    // 에러 상태가 401(만료/거부)이고, 재시도한 적이 없을 때만 실행
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const savedUser = localStorage.getItem('safeagent_user');
        if (!savedUser) throw new Error('No user data found in localStorage');
        
        const userObj = JSON.parse(savedUser);
        const { refresh_token } = userObj;

        if (!refresh_token) {
          throw new Error('No refresh token available');
        }

        // 루프 방지를 위해 기본 axios를 사용하여 refresh API 호출
        const response = await axios.post('/v1/auth/refresh', {
          refresh_token: refresh_token,
        });

        const { access_token } = response.data;

        // 성공 시 로컬 스토리지 데이터 업데이트
        userObj.access_token = access_token;
        localStorage.setItem('safeagent_user', JSON.stringify(userObj));

        // 실패했던 기존 요청의 헤더를 새 토큰으로 교체 후 재요청
        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return api(originalRequest);

      } catch (refreshError) {
        // Refresh 마저 실패한 경우, 즉시 로그아웃 처리 후 로그인 페이지로 강제 이동
        console.error('Token refresh failed. Forcing logout.', refreshError);
        localStorage.removeItem('safeagent_user');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);
