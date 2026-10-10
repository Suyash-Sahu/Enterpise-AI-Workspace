import { ReactNode } from "react";

import ConnectorErrorState from "./ConnectorErrorState";
import EmptyState from "./EmptyState";
import LoadingSkeleton from "./LoadingSkeleton";

interface Props {
    /** Query is fetching and there is nothing to show yet. */
    isLoading?: boolean;
    /** Query failed. */
    isError?: boolean;
    /** The error object (passed straight to ConnectorErrorState). */
    error?: unknown;
    /** Query succeeded but returned nothing. */
    isEmpty?: boolean;
    /** Retry handler for the error state. */
    onRetry?: () => void;
    /** What failed, for the error message (e.g. "your projects"). */
    resource?: string;

    /** Override the default skeleton. */
    loadingFallback?: ReactNode;
    /** Empty-state content — usually an <EmptyState />. */
    empty?: ReactNode;
    /** Skeleton shape when using the default fallback. */
    skeletonVariant?: "card" | "list" | "table";
    skeletonCount?: number;

    /** The real UI, shown only in the content state. */
    children: ReactNode;
}

/**
 * One wrapper so every data view renders the same four states in the same
 * order: loading -> error -> empty -> content.
 *
 *   <DataState isLoading={q.isLoading} isError={q.isError} error={q.error}
 *             isEmpty={!q.data?.length} onRetry={q.refetch} resource="projects"
 *             empty={<EmptyState .../>}>
 *     {q.data.map(...)}
 *   </DataState>
 */
export default function DataState({
    isLoading,
    isError,
    error,
    isEmpty,
    onRetry,
    resource = "this data",
    loadingFallback,
    empty,
    skeletonVariant = "card",
    skeletonCount = 3,
    children,
}: Props) {
    if (isLoading) {
        return (
            <div aria-busy="true" aria-live="polite">
                {loadingFallback ?? (
                    <LoadingSkeleton variant={skeletonVariant} count={skeletonCount} />
                )}
            </div>
        );
    }

    if (isError) {
        return (
            <ConnectorErrorState
                error={error}
                resource={resource}
                onRetry={onRetry}
            />
        );
    }

    if (isEmpty) {
        return <>{empty ?? <EmptyState title="Nothing here yet" description={`There is no ${resource} to show.`} />}</>;
    }

    return <>{children}</>;
}
