import { useQuery, useQueryClient } from "@tanstack/react-query";
import { googleService, GoogleDriveFile } from "@/services/google.service";

export function useDriveFiles() {
    return useQuery<GoogleDriveFile[]>({
        queryKey: ["drive-files"],
        queryFn: () => googleService.fetchDriveFiles(),
        staleTime: 15000,
    });
}

export function useDriveSearch(query: string) {
    return useQuery<GoogleDriveFile[]>({
        queryKey: ["drive-search", query],
        queryFn: () => googleService.searchDriveFiles(query),
        enabled: query.length > 0,
    });
}

export function useRecentDriveFiles() {
    return useQuery<GoogleDriveFile[]>({
        queryKey: ["drive-recent"],
        queryFn: () => googleService.getRecentDriveFiles(),
    });
}

export function useDriveFolders() {
    return useQuery<any[]>({
        queryKey: ["drive-folders"],
        queryFn: () => googleService.getDriveFolders(),
    });
}
