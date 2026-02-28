const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api";

class ApiClient {
  private token: string | null = null;

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem("tb_token", token);
    } else {
      localStorage.removeItem("tb_token");
    }
  }

  getToken(): string | null {
    if (!this.token && typeof window !== "undefined") {
      this.token = localStorage.getItem("tb_token");
    }
    return this.token;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string>),
    };

    const token = this.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    // Don't set Content-Type for FormData
    if (!(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }

    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(body.detail || `Request failed: ${res.status}`);
    }

    if (res.status === 204) return undefined as T;
    return res.json();
  }

  // Auth
  async signup(data: { email: string; password: string; full_name: string; countries: string[] }) {
    return this.request<{ access_token: string }>("/auth/signup", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async login(data: { email: string; password: string }) {
    return this.request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async getMe() {
    return this.request<{ id: string; email: string; full_name: string; countries: string[] }>("/auth/me");
  }

  // Documents
  async uploadDocument(file: File) {
    const form = new FormData();
    form.append("file", file);
    return this.request<any>("/documents/upload", { method: "POST", body: form });
  }

  async getDocuments() {
    return this.request<any[]>("/documents/");
  }

  async getDocument(id: string) {
    return this.request<any>(`/documents/${id}`);
  }

  async getDocumentStatus(id: string) {
    return this.request<{ id: string; status: string; document_type: string | null; error_message: string | null }>(
      `/documents/${id}/status`
    );
  }

  // Reputation
  async getProfile() {
    return this.request<any>("/reputation/profile");
  }

  async getClaims() {
    return this.request<any[]>("/reputation/claims");
  }

  async recalculate() {
    return this.request<any>("/reputation/recalculate", { method: "POST" });
  }

  // Credentials
  async generateCredential(data: { claim_ids: string[]; disclosure_rules?: any; expires_hours?: number }) {
    return this.request<any>("/credentials/generate", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async getCredentials() {
    return this.request<any[]>("/credentials/");
  }

  async revokeCredential(id: string) {
    return this.request<void>(`/credentials/${id}`, { method: "DELETE" });
  }

  async verifyCredential(token: string) {
    return this.request<any>(`/credentials/verify/${token}`);
  }
}

export const api = new ApiClient();
