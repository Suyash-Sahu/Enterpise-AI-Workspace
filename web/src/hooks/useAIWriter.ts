import { useMutation } from "@tanstack/react-query";
import { writerService, WriterGeneratePayload } from "@/services/writer.service";

export function useGenerateAIWriter() {
    return useMutation({
        mutationFn: (payload: WriterGeneratePayload) => writerService.generate(payload),
    });
}
