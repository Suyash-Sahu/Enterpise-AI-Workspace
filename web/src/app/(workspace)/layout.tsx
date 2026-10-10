import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import AppShellLayout from "@/components/layout/AppShellLayout";

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute>
      <AppShellLayout>{children}</AppShellLayout>
    </ProtectedRoute>
  );
}
