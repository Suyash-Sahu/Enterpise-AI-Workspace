export interface UserDTO {
    id: string;
    email: string;
    full_name: string;
    role: "admin" | "member" | "viewer";
    email_verified: boolean;
    mfa_enabled: boolean;
}

export interface AuthTokenResponse {
    access_token: string;
    refresh_token: string;
    token_type: string;
    expires_in: number;
}
