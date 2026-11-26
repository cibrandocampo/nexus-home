import { createContext, useContext } from 'react';

export const AuthContext = createContext(null);

// { user, status, isNew, loginStart, loginVerify, updateProfile, changePassword, logout } — see AuthProvider.
export function useAuth() {
  return useContext(AuthContext);
}
