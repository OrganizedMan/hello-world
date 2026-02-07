const API_BASE = '/api';

class ApiClient {
  private token: string | null = null;

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem('zb_token', token);
    } else {
      localStorage.removeItem('zb_token');
    }
  }

  getToken(): string | null {
    if (!this.token) {
      this.token = localStorage.getItem('zb_token');
    }
    return this.token;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      this.setToken(null);
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || 'Request failed');
    }

    return data;
  }

  // Auth
  login(email: string, password: string) {
    return this.request<{ token: string; user: any }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  }

  register(email: string, password: string, name: string) {
    return this.request<{ token: string; user: any }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, name }),
    });
  }

  getMe() {
    return this.request<{ user: any }>('/auth/me');
  }

  // Accounts
  getAccounts() {
    return this.request<{ accounts: any[] }>('/accounts');
  }

  createAccount(data: { name: string; type: string; balance: number }) {
    return this.request<{ account: any }>('/accounts', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  updateAccount(id: string, data: any) {
    return this.request<{ account: any }>(`/accounts/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  deleteAccount(id: string) {
    return this.request<{ success: boolean }>(`/accounts/${id}`, {
      method: 'DELETE',
    });
  }

  // Categories
  getCategories() {
    return this.request<{ categoryGroups: any[] }>('/categories');
  }

  createCategoryGroup(data: { name: string }) {
    return this.request<{ group: any }>('/categories/groups', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  updateCategoryGroup(id: string, data: any) {
    return this.request<{ group: any }>(`/categories/groups/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  deleteCategoryGroup(id: string) {
    return this.request<{ success: boolean }>(`/categories/groups/${id}`, {
      method: 'DELETE',
    });
  }

  createCategory(data: any) {
    return this.request<{ category: any }>('/categories', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  updateCategory(id: string, data: any) {
    return this.request<{ category: any }>(`/categories/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  deleteCategory(id: string) {
    return this.request<{ success: boolean }>(`/categories/${id}`, {
      method: 'DELETE',
    });
  }

  // Budget
  getBudget(month: string) {
    return this.request<{ month: string; categoryGroups: any[]; readyToAssign: number }>(`/budget/${month}`);
  }

  allocateBudget(month: string, category_id: string, amount: number) {
    return this.request<any>(`/budget/${month}/allocate`, {
      method: 'POST',
      body: JSON.stringify({ category_id, amount }),
    });
  }

  autoBudget(month: string, strategy: string, category_ids?: string[]) {
    return this.request<any>(`/budget/${month}/auto-budget`, {
      method: 'POST',
      body: JSON.stringify({ strategy, category_ids }),
    });
  }

  coverOverspending(month: string, from_category_id: string, to_category_id: string, amount: number) {
    return this.request<any>(`/budget/${month}/cover`, {
      method: 'POST',
      body: JSON.stringify({ from_category_id, to_category_id, amount }),
    });
  }

  // Transactions
  getTransactions(params: Record<string, string> = {}) {
    const query = new URLSearchParams(params).toString();
    return this.request<{ transactions: any[]; total: number }>(`/transactions?${query}`);
  }

  createTransaction(data: any) {
    return this.request<{ transaction: any }>('/transactions', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  updateTransaction(id: string, data: any) {
    return this.request<{ transaction: any }>(`/transactions/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  deleteTransaction(id: string) {
    return this.request<{ success: boolean }>(`/transactions/${id}`, {
      method: 'DELETE',
    });
  }

  getPayees() {
    return this.request<{ payees: any[] }>('/transactions/payees');
  }

  // Reports
  getNetWorthReport() {
    return this.request<any>('/reports/net-worth');
  }

  getSpendingReport(params: Record<string, string> = {}) {
    const query = new URLSearchParams(params).toString();
    return this.request<any>(`/reports/spending?${query}`);
  }

  getIncomeExpenseReport() {
    return this.request<any>('/reports/income-expense');
  }

  getAgeOfMoneyReport() {
    return this.request<any>('/reports/age-of-money');
  }
}

export const api = new ApiClient();
