import { z } from "zod";

export const loginSchema = z.object({
    email: z
        .string()
        .min(1, "Email address is required")
        .email("Please enter a valid work email address"),
    password: z
        .string()
        .min(1, "Password is required")
        .min(8, "Password must be at least 8 characters long"),
    rememberMe: z.boolean().optional(),
});

export const signupSchema = z
    .object({
        fullName: z
            .string()
            .min(1, "Full name is required")
            .min(2, "Full name must be at least 2 characters"),
        email: z
            .string()
            .min(1, "Work email is required")
            .email("Please enter a valid work email address"),
        password: z
            .string()
            .min(8, "Password must be at least 8 characters long")
            .regex(/[A-Z]/, "Password must contain at least one uppercase letter")
            .regex(/[a-z]/, "Password must contain at least one lowercase letter")
            .regex(/[0-9]/, "Password must contain at least one number")
            .regex(/[^A-Za-z0-9]/, "Password must contain at least one special character"),
        confirmPassword: z.string().min(1, "Please confirm your password"),
        acceptTerms: z
            .boolean()
            .refine((val) => val === true, "You must accept the Terms of Service and Privacy Policy"),
    })
    .refine((data) => data.password === data.confirmPassword, {
        message: "Passwords do not match",
        path: ["confirmPassword"],
    });

export const forgotPasswordSchema = z.object({
    email: z
        .string()
        .min(1, "Email address is required")
        .email("Please enter a valid work email address"),
});

export const resetPasswordSchema = z
    .object({
        password: z
            .string()
            .min(8, "Password must be at least 8 characters long")
            .regex(/[A-Z]/, "Must contain at least one uppercase letter")
            .regex(/[a-z]/, "Must contain at least one lowercase letter")
            .regex(/[0-9]/, "Must contain at least one number")
            .regex(/[^A-Za-z0-9]/, "Must contain at least one special character"),
        confirmPassword: z.string().min(1, "Please confirm your password"),
    })
    .refine((data) => data.password === data.confirmPassword, {
        message: "Passwords do not match",
        path: ["confirmPassword"],
    });

export const otpSchema = z.object({
    code: z
        .string()
        .length(6, "Verification code must be exactly 6 digits")
        .regex(/^[0-9]+$/, "Verification code must contain digits only"),
    trustDevice: z.boolean().optional(),
});