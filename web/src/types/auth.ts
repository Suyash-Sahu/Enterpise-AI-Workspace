export interface User {
  id: string;
  name: string;
  fullName?: string;
  email: string;
  picture: string;
  emailVerified?: boolean;
  role?: string;
}

export interface Session {
  user: User;
  expiresAt?: string;
}

export interface AuthState {
  user: User | null;
  status: "loading" | "authenticated" | "unauthenticated";
  logout: () => Promise<void>;
  refetchSession: () => Promise<void>;
}

export interface GoogleProfile {
  sub: string;
  name: string;
  given_name?: string;
  family_name?: string;
  picture: string;
  email: string;
  email_verified: boolean;
}
