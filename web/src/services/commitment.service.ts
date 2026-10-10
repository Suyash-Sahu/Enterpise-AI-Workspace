import { apiClient } from "@/lib/api/client";
import { ENDPOINTS } from "@/lib/api/endpoints";
import { CommitmentDTO, CommitmentScanResultDTO, CommitmentSweepResultDTO } from "@/types/commitment";

export class CommitmentService {
    static async list(status?: string): Promise<CommitmentDTO[]> {
        return apiClient<CommitmentDTO[]>(ENDPOINTS.COMMITMENTS.LIST, {
            method: "GET",
            params: status ? { status_filter: status } : undefined,
        });
    }

    static async scan(): Promise<CommitmentScanResultDTO> {
        return apiClient<CommitmentScanResultDTO>(ENDPOINTS.COMMITMENTS.SCAN, {
            method: "POST",
        });
    }

    static async sweep(): Promise<CommitmentSweepResultDTO> {
        return apiClient<CommitmentSweepResultDTO>(ENDPOINTS.COMMITMENTS.SWEEP, {
            method: "POST",
        });
    }
}
