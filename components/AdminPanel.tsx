import React, { useState, useEffect } from 'react';
import { Shield, Users, Activity, DollarSign, TrendingUp, Search, Download, RefreshCw, Eye, XCircle, AlertTriangle } from 'lucide-react';
import { API_BASE_URL } from '../services/api';

// shadcn-style components
const Card = ({ className = '', children, ...props }: any) => (
  <div className={`rounded-lg border bg-card text-card-foreground shadow-sm ${className}`} {...props}>
    {children}
  </div>
);

const CardHeader = ({ className = '', children, ...props }: any) => (
  <div className={`flex flex-col space-y-1.5 p-6 ${className}`} {...props}>
    {children}
  </div>
);

const CardTitle = ({ className = '', children, ...props }: any) => (
  <h3 className={`text-2xl font-semibold leading-none tracking-tight ${className}`} {...props}>
    {children}
  </h3>
);

const CardContent = ({ className = '', children, ...props }: any) => (
  <div className={`p-6 pt-0 ${className}`} {...props}>
    {children}
  </div>
);

const Tabs = ({ value, onValueChange, children, className = '' }: any) => (
  <div className={`${className}`} data-value={value}>
    {React.Children.map(children, child =>
      React.cloneElement(child, { value, onValueChange })
    )}
  </div>
);

const TabsList = ({ children, className = '' }: any) => (
  <div className={`inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground ${className}`}>
    {children}
  </div>
);

const TabsTrigger = ({ value, onValueChange, currentValue, children, className = '' }: any) => (
  <button
    onClick={() => onValueChange?.(value)}
    className={`inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 ${
      currentValue === value ? 'bg-background text-foreground shadow-sm' : ''
    } ${className}`}
  >
    {children}
  </button>
);

const TabsContent = ({ value, currentValue, children, className = '' }: any) => {
  if (value !== currentValue) return null;
  return (
    <div className={`mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${className}`}>
      {children}
    </div>
  );
};

const Button = ({ variant = 'default', size = 'default', className = '', children, ...props }: any) => {
  const baseStyles = 'inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50';
  
  const variants = {
    default: 'bg-primary text-primary-foreground hover:bg-primary/90',
    destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90',
    outline: 'border border-input bg-background hover:bg-accent hover:text-accent-foreground',
    secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80',
    ghost: 'hover:bg-accent hover:text-accent-foreground',
    link: 'text-primary underline-offset-4 hover:underline',
  };
  
  const sizes = {
    default: 'h-10 px-4 py-2',
    sm: 'h-9 rounded-md px-3',
    lg: 'h-11 rounded-md px-8',
    icon: 'h-10 w-10',
  };
  
  return (
    <button
      className={`${baseStyles} ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
};

const Input = ({ className = '', ...props }: any) => (
  <input
    className={`flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
    {...props}
  />
);

const Badge = ({ variant = 'default', className = '', children, ...props }: any) => {
  const variants = {
    default: 'bg-primary text-primary-foreground hover:bg-primary/80',
    secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80',
    destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/80',
    outline: 'text-foreground border border-input',
  };
  
  return (
    <div className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 ${variants[variant]} ${className}`} {...props}>
      {children}
    </div>
  );
};

interface AdminStats {
  total_users: number;
  active_subscriptions: number;
  total_revenue_monthly: number;
  total_predictions: number;
  active_users_24h: number;
  new_users_7d: number;
}

interface Customer {
  id: string;
  email: string;
  username: string;
  tier: string;
  created_at: string;
  last_login: string;
  simulations_today: number;
  subscription_status?: string;
  is_admin: boolean;
}

interface ActivityLog {
  id: string;
  timestamp: string;
  user_email: string;
  action: string;
  details: any;
}

const AdminPanel: React.FC = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [activityLogs, setActivityLogs] = useState<ActivityLog[]>([]);
  const [frontendLogs, setFrontendLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCustomer, setSelectedCustomer] = useState<any>(null);

  const getAuthHeaders = () => {
    const token = localStorage.getItem('token');
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    };
  };

  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/panel/stats`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    }
  };

  const fetchCustomers = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/panel/customers?limit=100`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setCustomers(data.customers);
      }
    } catch (error) {
      console.error('Failed to fetch customers:', error);
    }
  };

  const fetchActivityLogs = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/panel/activity-logs?limit=100`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setActivityLogs(data.logs);
      }
    } catch (error) {
      console.error('Failed to fetch activity logs:', error);
    }
  };

  const fetchFrontendLogs = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/panel/frontend-logs?limit=100`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setFrontendLogs(data.logs);
      }
    } catch (error) {
      console.error('Failed to fetch frontend logs:', error);
    }
  };

  const cancelSubscription = async (userId: string, reason: string) => {
    if (!confirm('Are you sure you want to cancel this subscription?')) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/panel/billing/cancel-subscription`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ user_id: userId, action: 'cancel', reason }),
      });
      
      if (response.ok) {
        alert('Subscription cancelled successfully');
        fetchCustomers();
      } else {
        alert('Failed to cancel subscription');
      }
    } catch (error) {
      console.error('Failed to cancel subscription:', error);
    }
  };

  const updateTier = async (userId: string, tier: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/panel/customers/${userId}/tier`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({ tier }),
      });
      
      if (response.ok) {
        alert('Tier updated successfully');
        fetchCustomers();
      } else {
        alert('Failed to update tier');
      }
    } catch (error) {
      console.error('Failed to update tier:', error);
    }
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([
        fetchStats(),
        fetchCustomers(),
        fetchActivityLogs(),
        fetchFrontendLogs(),
      ]);
      setLoading(false);
    };
    
    loadData();
  }, []);

  const refreshData = () => {
    fetchStats();
    fetchCustomers();
    fetchActivityLogs();
    fetchFrontendLogs();
  };

  const filteredCustomers = customers.filter(c =>
    c.email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    c.username?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-linear-to-br from-slate-900 via-purple-900 to-slate-900 text-white p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <Shield className="w-8 h-8 text-purple-400" />
            <h1 className="text-3xl font-bold">Admin Panel</h1>
          </div>
          <Button onClick={refreshData} variant="outline" className="gap-2">
            <RefreshCw className="w-4 h-4" />
            Refresh
          </Button>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-5 mb-8">
            <TabsTrigger value="dashboard" currentValue={activeTab}>
              <TrendingUp className="w-4 h-4 mr-2" />
              Dashboard
            </TabsTrigger>
            <TabsTrigger value="customers" currentValue={activeTab}>
              <Users className="w-4 h-4 mr-2" />
              Customers
            </TabsTrigger>
            <TabsTrigger value="activity" currentValue={activeTab}>
              <Activity className="w-4 h-4 mr-2" />
              Activity
            </TabsTrigger>
            <TabsTrigger value="billing" currentValue={activeTab}>
              <DollarSign className="w-4 h-4 mr-2" />
              Billing
            </TabsTrigger>
            <TabsTrigger value="logs" currentValue={activeTab}>
              <AlertTriangle className="w-4 h-4 mr-2" />
              Frontend Logs
            </TabsTrigger>
          </TabsList>

          {/* Dashboard Tab */}
          <TabsContent value="dashboard" currentValue={activeTab}>
            {stats && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Total Users</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-4xl font-bold">{stats.total_users.toLocaleString()}</p>
                    <p className="text-sm text-muted-foreground mt-2">
                      +{stats.new_users_7d} in last 7 days
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Active Subscriptions</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-4xl font-bold">{stats.active_subscriptions.toLocaleString()}</p>
                    <p className="text-sm text-muted-foreground mt-2">
                      {((stats.active_subscriptions / stats.total_users) * 100).toFixed(1)}% conversion
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Monthly Revenue</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-4xl font-bold">${stats.total_revenue_monthly.toLocaleString()}</p>
                    <p className="text-sm text-muted-foreground mt-2">
                      Estimated MRR
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Total Predictions</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-4xl font-bold">{stats.total_predictions.toLocaleString()}</p>
                    <p className="text-sm text-muted-foreground mt-2">
                      Published to users
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Active Users (24h)</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-4xl font-bold">{stats.active_users_24h.toLocaleString()}</p>
                    <p className="text-sm text-muted-foreground mt-2">
                      {((stats.active_users_24h / stats.total_users) * 100).toFixed(1)}% DAU
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">ARPU</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-4xl font-bold">
                      ${(stats.total_revenue_monthly / stats.total_users).toFixed(2)}
                    </p>
                    <p className="text-sm text-muted-foreground mt-2">
                      Average revenue per user
                    </p>
                  </CardContent>
                </Card>
              </div>
            )}
          </TabsContent>

          {/* Customers Tab */}
          <TabsContent value="customers" currentValue={activeTab}>
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>Customer Management</CardTitle>
                  <div className="flex gap-2">
                    <Input
                      placeholder="Search customers..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="w-64"
                    />
                    <Button variant="outline" size="icon">
                      <Search className="w-4 h-4" />
                    </Button>
                    <Button variant="outline" size="icon">
                      <Download className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-gray-700">
                        <th className="text-left p-2">Email</th>
                        <th className="text-left p-2">Tier</th>
                        <th className="text-left p-2">Created</th>
                        <th className="text-left p-2">Last Login</th>
                        <th className="text-left p-2">Simulations</th>
                        <th className="text-left p-2">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredCustomers.map((customer) => (
                        <tr key={customer.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                          <td className="p-2">
                            <div>
                              <p className="font-medium">{customer.email}</p>
                              {customer.is_admin && (
                                <Badge variant="secondary" className="text-xs">Admin</Badge>
                              )}
                            </div>
                          </td>
                          <td className="p-2">
                            <Badge variant={
                              customer.tier === 'founder' ? 'default' :
                              customer.tier === 'elite' ? 'secondary' :
                              customer.tier === 'sharps_room' ? 'outline' :
                              'outline'
                            }>
                              {customer.tier}
                            </Badge>
                          </td>
                          <td className="p-2 text-sm text-gray-400">
                            {customer.created_at ? new Date(customer.created_at).toLocaleDateString() : 'N/A'}
                          </td>
                          <td className="p-2 text-sm text-gray-400">
                            {customer.last_login ? new Date(customer.last_login).toLocaleDateString() : 'Never'}
                          </td>
                          <td className="p-2 text-sm">
                            {customer.simulations_today}
                          </td>
                          <td className="p-2">
                            <div className="flex gap-2">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setSelectedCustomer(customer)}
                              >
                                <Eye className="w-4 h-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                  const newTier = prompt('Enter new tier (free, elite, sharps_room, founder):');
                                  if (newTier) updateTier(customer.id, newTier);
                                }}
                              >
                                Edit
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Activity Logs Tab */}
          <TabsContent value="activity" currentValue={activeTab}>
            <Card>
              <CardHeader>
                <CardTitle>System Activity</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {activityLogs.map((log) => (
                    <div key={log.id} className="p-3 bg-gray-800/50 rounded border border-gray-700">
                      <div className="flex justify-between items-start">
                        <div>
                          <p className="font-medium">{log.action}</p>
                          <p className="text-sm text-gray-400">{log.user_email || 'System'}</p>
                        </div>
                        <p className="text-xs text-gray-500">
                          {new Date(log.timestamp).toLocaleString()}
                        </p>
                      </div>
                      {log.details && Object.keys(log.details).length > 0 && (
                        <pre className="mt-2 text-xs bg-gray-900 p-2 rounded overflow-x-auto">
                          {JSON.stringify(log.details, null, 2)}
                        </pre>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Billing Tab */}
          <TabsContent value="billing" currentValue={activeTab}>
            <Card>
              <CardHeader>
                <CardTitle>Billing Management</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <p className="text-sm text-gray-400">
                    Manage customer subscriptions, issue refunds, and view revenue metrics.
                  </p>
                  
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {customers.filter(c => c.tier !== 'free').map((customer) => (
                      <div key={customer.id} className="p-4 bg-gray-800/50 rounded border border-gray-700">
                        <p className="font-medium">{customer.email}</p>
                        <Badge variant="secondary" className="mt-2">{customer.tier}</Badge>
                        <div className="mt-4 flex gap-2">
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => cancelSubscription(customer.id, 'Admin action')}
                          >
                            <XCircle className="w-4 h-4 mr-1" />
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Frontend Logs Tab */}
          <TabsContent value="logs" currentValue={activeTab}>
            <Card>
              <CardHeader>
                <CardTitle>Frontend Logs & Errors</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {frontendLogs.map((log) => (
                    <div
                      key={log._id}
                      className={`p-3 rounded border ${
                        log.level === 'error' ? 'bg-red-900/20 border-red-700' :
                        log.level === 'warning' ? 'bg-yellow-900/20 border-yellow-700' :
                        'bg-gray-800/50 border-gray-700'
                      }`}
                    >
                      <div className="flex justify-between items-start">
                        <div>
                          <Badge variant={log.level === 'error' ? 'destructive' : 'outline'} className="mb-2">
                            {log.level}
                          </Badge>
                          <p className="font-medium">{log.message}</p>
                          <p className="text-sm text-gray-400">{log.user_email || 'Anonymous'}</p>
                          {log.url && <p className="text-xs text-gray-500 mt-1">{log.url}</p>}
                        </div>
                        <p className="text-xs text-gray-500">
                          {new Date(log.timestamp).toLocaleString()}
                        </p>
                      </div>
                      {log.details && Object.keys(log.details).length > 0 && (
                        <pre className="mt-2 text-xs bg-gray-900 p-2 rounded overflow-x-auto">
                          {JSON.stringify(log.details, null, 2)}
                        </pre>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default AdminPanel;
