export class ApiError extends Error {
    public statusCode: number;
    public details?: any;

    constructor(message: string, statusCode: number, details?: any) {
        super(message);
        this.name = "ApiError";
        this.statusCode = statusCode;
        this.details = details;
    }
}
