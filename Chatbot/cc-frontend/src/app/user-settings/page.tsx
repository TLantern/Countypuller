'use client';
import React, { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { AppSidebar } from "@/components/app-sidebar"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Separator } from "@/components/ui/separator"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { Select, MenuItem, FormControl, InputLabel, Button, Typography, Box, Card, CardContent, Table, TableBody, TableCell, TableHead, TableRow, Chip, IconButton } from '@mui/material';
import { Edit as EditIcon, Save as SaveIcon, Cancel as CancelIcon } from '@mui/icons-material';

// Admin users who can manage all account types
const ADMIN_EMAILS = ['Teniola101@outlook.com'];

interface User {
  id: string;
  email: string;
  userType: string;
  createdAt: string;
}

export default function UserSettings() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);
  const [editingUser, setEditingUser] = useState<string | null>(null);
  const [tempUserType, setTempUserType] = useState<string>('');

  const isAdmin = session?.user?.email && ADMIN_EMAILS.includes(session.user.email);

  useEffect(() => {
    if (status === "loading") return;
    if (!session) {
      router.push("/login");
      return;
    }
    if (isAdmin) {
      fetchAllUsers();
    }
  }, [session, status, router, isAdmin]);

  const fetchAllUsers = async () => {
    try {
      const res = await fetch('/api/admin/users');
      if (res.ok) {
        const data = await res.json();
        setUsers(data.users || []);
      } else {
        setMessage({ type: 'error', text: 'Failed to fetch users' });
      }
    } catch (error) {
      console.error('Error fetching users:', error);
      setMessage({ type: 'error', text: 'Network error occurred' });
    }
  };

  const updateUserType = async (userId: string, newUserType: string) => {
    setLoading(true);
    setMessage(null);
    
    try {
      const res = await fetch('/api/admin/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId, userType: newUserType })
      });
      
      if (res.ok) {
        setMessage({ type: 'success', text: 'User type updated successfully!' });
        await fetchAllUsers(); // Refresh the list
        setEditingUser(null);
      } else {
        const data = await res.json();
        setMessage({ type: 'error', text: data.error || 'Failed to update user type' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Network error occurred' });
    } finally {
      setLoading(false);
    }
  };

  const startEditing = (user: User) => {
    setEditingUser(user.id);
    setTempUserType(user.userType);
  };

  const cancelEditing = () => {
    setEditingUser(null);
    setTempUserType('');
  };

  const saveUserType = async () => {
    if (editingUser && tempUserType) {
      await updateUserType(editingUser, tempUserType);
    }
  };

  if (status === "loading") {
    return <div>Loading...</div>;
  }

  if (!session) {
    return null;
  }

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-16 shrink-0 items-center gap-2 border-b">
          <div className="flex items-center gap-2 px-3">
            <SidebarTrigger />
            <Separator orientation="vertical" className="mr-2 h-4" />
            <Breadcrumb>
              <BreadcrumbList>
                <BreadcrumbItem className="hidden md:block">
                  <BreadcrumbLink href="/dashboard">
                    Dashboard
                  </BreadcrumbLink>
                </BreadcrumbItem>
                <BreadcrumbSeparator className="hidden md:block" />
                <BreadcrumbItem>
                  <BreadcrumbPage>User Settings</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>
        </header>
        
        <div className="p-6">
          <div className="max-w-6xl mx-auto">
            <Typography variant="h4" component="h1" gutterBottom>
              {isAdmin ? 'User Management Dashboard' : 'User Settings'}
            </Typography>
            
            {isAdmin ? (
              // Admin Dashboard
              <Card sx={{ mt: 3 }}>
                <CardContent sx={{ p: 3 }}>
                  <Typography variant="h6" gutterBottom>
                    Account Type Management
                  </Typography>
                  
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                    Manage account types for all users. LPH users access Harris County records, MD users access Maryland case search.
                  </Typography>
                  
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell><strong>Email</strong></TableCell>
                        <TableCell><strong>Current Type</strong></TableCell>
                        <TableCell><strong>Created</strong></TableCell>
                        <TableCell><strong>Actions</strong></TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {users.map((user) => (
                        <TableRow key={user.id}>
                          <TableCell>{user.email}</TableCell>
                          <TableCell>
                            {editingUser === user.id ? (
                              <FormControl size="small" sx={{ minWidth: 200 }}>
                                <Select
                                  value={tempUserType}
                                  onChange={(e) => setTempUserType(e.target.value)}
                                >
                                  <MenuItem value="LPH">Lis Pendens (LPH)</MenuItem>
                                  <MenuItem value="MD_CASE_SEARCH">Maryland Case Search</MenuItem>
                                </Select>
                              </FormControl>
                            ) : (
                              <Chip 
                                label={user.userType === 'MD_CASE_SEARCH' ? 'Maryland Case Search' : 'Lis Pendens (LPH)'} 
                                color={user.userType === 'MD_CASE_SEARCH' ? 'primary' : 'secondary'}
                                size="small"
                              />
                            )}
                          </TableCell>
                          <TableCell>
                            {new Date(user.createdAt).toLocaleDateString()}
                          </TableCell>
                          <TableCell>
                            {editingUser === user.id ? (
                              <Box sx={{ display: 'flex', gap: 1 }}>
                                <IconButton 
                                  size="small" 
                                  color="primary" 
                                  onClick={saveUserType}
                                  disabled={loading}
                                >
                                  <SaveIcon />
                                </IconButton>
                                <IconButton 
                                  size="small" 
                                  onClick={cancelEditing}
                                  disabled={loading}
                                >
                                  <CancelIcon />
                                </IconButton>
                              </Box>
                            ) : (
                              <IconButton 
                                size="small" 
                                onClick={() => startEditing(user)}
                                disabled={loading}
                              >
                                <EditIcon />
                              </IconButton>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                  
                  <Box sx={{ mt: 3 }}>
                    <Button 
                      variant="outlined"
                      onClick={() => router.push('/dashboard')}
                    >
                      Back to Dashboard
                    </Button>
                  </Box>
                  
                  {message && (
                    <Box 
                      sx={{ 
                        p: 2, 
                        mt: 2, 
                        borderRadius: 1, 
                        backgroundColor: message.type === 'success' ? '#e8f5e8' : '#ffeaea',
                        color: message.type === 'success' ? '#2e7d32' : '#c62828'
                      }}
                    >
                      {message.text}
                    </Box>
                  )}
                </CardContent>
              </Card>
            ) : (
              // Regular User Settings (no account type changing)
              <Card sx={{ mt: 3 }}>
                <CardContent sx={{ p: 3 }}>
                  <Typography variant="h6" gutterBottom>
                    Account Information
                  </Typography>
                  
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                    Your account settings and information.
                  </Typography>
                  
                  <Box sx={{ mt: 3, p: 2, backgroundColor: '#f5f5f5', borderRadius: 1 }}>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Account Email:</strong> {session.user?.email}<br/>
                      <strong>Account Type:</strong> Contact your administrator to change account type
                    </Typography>
                  </Box>
                  
                  <Box sx={{ mt: 3 }}>
                    <Button 
                      variant="outlined"
                      onClick={() => router.push('/dashboard')}
                    >
                      Back to Dashboard
                    </Button>
                  </Box>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
} 