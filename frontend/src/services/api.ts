import axios, {
  type AxiosInstance,
  type AxiosRequestConfig,
  type AxiosResponse
} from "axios";
import { toast } from "sonner";

import { storage } from "@/utils/storage";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/ragent";

interface DataApi extends Omit<AxiosInstance, "get" | "delete" | "post" | "put" | "patch" | "request"> {
  request<T = unknown, R = T, D = unknown>(config: AxiosRequestConfig<D>): Promise<R>;
  get<T = unknown, R = T>(url: string, config?: AxiosRequestConfig): Promise<R>;
  delete<T = unknown, R = T>(url: string, config?: AxiosRequestConfig): Promise<R>;
  post<T = unknown, R = T, D = unknown>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<R>;
  put<T = unknown, R = T, D = unknown>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<R>;
  patch<T = unknown, R = T, D = unknown>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<R>;
}

const axiosApi = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000
});

export const api = axiosApi as DataApi;

export function setAuthToken(token: string | null) {
  if (token) {
    api.defaults.headers.common.Authorization = token;
  } else {
    delete api.defaults.headers.common.Authorization;
  }
}

axiosApi.interceptors.request.use((config) => {
  const token = storage.getToken();
  if (token) {
    config.headers.Authorization = token;
  }
  return config;
});

axiosApi.interceptors.response.use(
  (response): AxiosResponse["data"] => {
    const payload = response.data;
    if (payload && typeof payload === "object" && "code" in payload) {
      if (payload.code !== "0") {
        const message = payload.message || "请求失败";
        const isAuthExpired = typeof message === "string" && message.includes("未登录");
        if (isAuthExpired) {
          storage.clearAuth();
          if (window.location.pathname !== "/login") {
            window.location.href = "/login";
          }
        }
        return Promise.reject(new Error(message));
      }
      return payload.data;
    }
    return payload;
  },
  (error) => {
    if (error?.response?.status === 401) {
      storage.clearAuth();
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    const responseData = error?.response?.data;
    if (responseData && typeof responseData === "object" && "message" in responseData && responseData.message) {
      toast.error(responseData.message);
    } else if (error?.code === "ERR_NETWORK") {
      toast.error("网络错误，请检查网络连接");
    } else {
      toast.error(error?.message || "网络错误");
    }
    return Promise.reject(error);
  }
);
