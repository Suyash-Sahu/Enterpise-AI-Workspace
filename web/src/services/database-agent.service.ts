import { apiClient, ApiResponse } from "@/lib/api-client";

export interface DatabaseResultData {
    question?: string;
    sql: string;
    columns: string[];
    rows: Record<string, any>[];
    row_count: number;
    explanation?: string;
    execution_time: number;
}

export interface DatabaseColumnSchema {
    name: string;
    type: string;
}

export interface DatabaseTableSchema {
    name: string;
    columns: DatabaseColumnSchema[];
}

export interface DatabaseSchemaData {
    tables: DatabaseTableSchema[];
}

export interface DatabaseHealthData {
    status: string;
    db_agent_enabled: boolean;
    raw_sql_enabled: boolean;
    allowed_tables_count: number;
    query_timeout_seconds: number;
    max_limit: number;
}

export const databaseAgentService = {
    async queryDatabase(params: {
        question: string;
        limit?: number;
        owner_id?: string;
    }): Promise<DatabaseResultData> {
        const response = await apiClient.post<ApiResponse<DatabaseResultData>>(
            "/db-agent/query",
            params
        );
        return response.data.data;
    },

    async executeSQL(params: {
        sql: string;
        limit?: number;
        owner_id?: string;
    }): Promise<DatabaseResultData> {
        const response = await apiClient.post<ApiResponse<DatabaseResultData>>(
            "/db-agent/sql",
            params
        );
        return response.data.data;
    },

    async getSchema(): Promise<DatabaseSchemaData> {
        const response = await apiClient.get<ApiResponse<DatabaseSchemaData>>(
            "/db-agent/schema"
        );
        return response.data.data;
    },

    async getHealth(): Promise<DatabaseHealthData> {
        const response = await apiClient.get<ApiResponse<DatabaseHealthData>>(
            "/db-agent/health"
        );
        return response.data.data;
    },
};
