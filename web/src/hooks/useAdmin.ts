import { useQuery } from "@tanstack/react-query";
import { adminService, AdminTelemetry } from "@/services/admin.service";

/**
 * Admin telemetry, polled while the page is open.
 *
 * No retry on failure: the expected failure here is a 403 from
 * require_role("admin"), and retrying an authorization refusal just delays
 * showing the user why they cannot see the page.
 */
export function useAdminTelemetry() {
    return useQuery<AdminTelemetry>({
        queryKey: ["admin-telemetry"],
        queryFn: () => adminService.getTelemetry(),
        refetchInterval: 30000,
        retry: false,
    });
}
