import { AuthService } from "@/services/auth.service";
import { ProjectService } from "@/services/project.service";
import { DocumentService } from "@/services/document.service";
import { ApprovalService } from "@/services/approval.service";
import { describe, it, expect } from "vitest";
describe("Phase 5 Services Integration Layer", () => {
    it("should expose AuthService session helpers", () => {
        // Both are backend routes now. This app no longer verifies identities,
        // mints tokens or sets cookies; it points the browser at the API,
        // which Next proxies so the session cookie stays same-site.
        expect(AuthService.getCurrentUser).toBeDefined();
        expect(AuthService.signInUrl).toBe("/api/v1/auth/google/login");
        expect(AuthService.logoutUrl).toBe("/api/v1/auth/logout");
    });

    it("should define ProjectService API endpoints", () => {
        expect(ProjectService.getProjects).toBeDefined();
        expect(ProjectService.getTasks).toBeDefined();
    });

    it("should define DocumentService API endpoints", () => {
        expect(DocumentService.getDocuments).toBeDefined();
        expect(DocumentService.uploadDocument).toBeDefined();
    });

    it("should define ApprovalService endpoints", () => {
        expect(ApprovalService.getApprovals).toBeDefined();
        expect(ApprovalService.approve).toBeDefined();
        expect(ApprovalService.reject).toBeDefined();
    });
});
