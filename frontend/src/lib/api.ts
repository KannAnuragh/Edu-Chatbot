const getApiUrl = () => {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }
  if (typeof window !== "undefined") {
    const hostname = window.location.hostname;
    if (hostname === "localhost" || hostname === "127.0.0.1") {
      return "http://localhost:8001/api/v1";
    }
    return "/api/v1";
  }
  return "http://localhost:8001/api/v1";
};

export class ApiClient {
  private getHeaders(): HeadersInit {
    const token = localStorage.getItem("aca_token");
    return {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  }

  private async request(endpoint: string, options: RequestInit = {}) {
    const url = `${getApiUrl()}${endpoint}`;
    const headers = { ...this.getHeaders(), ...options.headers };
    
    // Debug log to ensure token is attached
    if (typeof window !== "undefined" && url.includes("/courses")) {
        console.log(`[API] Requesting ${url}. Token present: ${!!headers["Authorization"]}`);
    }

    const response = await fetch(url, { ...options, headers });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || "API request failed");
    }

    if (response.status === 204 || response.headers.get("content-length") === "0") {
      return null;
    }
    
    // Some endpoints might return empty strings which aren't valid JSON
    const text = await response.text();
    return text ? JSON.parse(text) : null;
  }

  // --- Auth ---
  async login(email: string, password: string) {
    return this.request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  }

  async register(name: string, email: string, password: string) {
    return this.request("/auth/register", {
      method: "POST",
      body: JSON.stringify({ name, email, password }),
    });
  }

  async getMe() {
    return this.request("/auth/me");
  }

  // --- Courses / Projects ---
  async getCourses() {
    return this.request("/courses");
  }

  async getEnrolledCourses() {
    return this.request("/courses/enrolled");
  }

  async getCourse(id: string) {
    return this.request(`/courses/${id}`);
  }

  async createCourse(title: string, desc: string = "", badgeColor: string = "emerald") {
    return this.request('/courses', {
      method: 'POST',
      body: JSON.stringify({ title, description: desc, badge_color: badgeColor }),
    });
  }

  async updateCourse(courseId: string, title?: string, desc?: string, badgeColor?: string) {
    const body: any = {};
    if (title !== undefined) body.title = title;
    if (desc !== undefined) body.description = desc;
    if (badgeColor !== undefined) body.badge_color = badgeColor;
    
    return this.request(`/courses/${courseId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    });
  }

  async deleteCourse(id: string) {
    return this.request(`/courses/${id}`, {
      method: "DELETE",
    });
  }
  
  async enrollCourse(courseId: string) {
    return this.request(`/courses/${courseId}/enroll`, {
      method: "POST",
    });
  }
  
  // Note: For backwards compatibility with reference code
  async getProjects() { return this.getCourses(); }
  async getProject(id: string) { return this.getCourse(id); }
  async createProject(title: string, desc: string, badgeColor?: string) { return this.createCourse(title, desc, badgeColor); }

  async getCourseStats(courseId: string) {
    return this.request(`/stats/course/${courseId}`);
  }

  async getGlobalStats() {
    return this.request('/stats/global');
  }

  // --- Documents ---
  async getDocuments(courseId: string) {
    return this.request(`/courses/${courseId}/documents`);
  }

  async uploadDocument(courseId: string, file: File) {
    const formData = new FormData();
    formData.append("file", file);

    const token = localStorage.getItem("aca_token");
    const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};

    const response = await fetch(`${getApiUrl()}/courses/${courseId}/documents/upload`, {
      method: "POST",
      headers,
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || "Upload failed");
    }

    return response.json();
  }

  async deleteDocument(courseId: string, documentId: string) {
    const url = `${getApiUrl()}/courses/${courseId}/documents/${documentId}`;
    const token = localStorage.getItem("aca_token");
    
    const response = await fetch(url, {
      method: "DELETE",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });

    if (!response.ok) {
      throw new Error("Failed to delete document");
    }
  }

  async reprocessDocument(courseId: string, documentId: string) {
    return this.request(`/courses/${courseId}/documents/${documentId}/reprocess`, {
      method: "POST",
    });
  }

  // --- Chat ---
  async getConversations(courseId: string) {
    return this.request(`/courses/${courseId}/conversations`);
  }

  async getConversation(courseId: string, conversationId: string) {
    return this.request(`/courses/${courseId}/conversations/${conversationId}`);
  }

  async chatStream(
    courseId: string,
    message: string,
    conversationId: string | null,
    onEvent: (event: SSEEvent) => void
  ) {
    const url = `${getApiUrl()}/courses/${courseId}/chat`;
    const token = localStorage.getItem("aca_token");
    const headers: HeadersInit = {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };

    const response = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify({ message, conversation_id: conversationId }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || "Chat request failed");
    }

    if (!response.body) throw new Error("No response body");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || ""; // Keep the last incomplete chunk

        for (const block of lines) {
          if (!block.trim()) continue;

          let type = "unknown";
          let data = null;

          const blockLines = block.split("\n");
          for (const line of blockLines) {
            if (line.startsWith("event: ")) {
              type = line.substring(7).trim();
            } else if (line.startsWith("data: ")) {
              const dataStr = line.substring(6).trim();
              if (dataStr) {
                try {
                  data = JSON.parse(dataStr);
                } catch {
                  data = dataStr;
                }
              }
            }
          }

          if (type !== "unknown") {
            onEvent({ type, data } as SSEEvent);
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }
}

export const api = new ApiClient();
