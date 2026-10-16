import { useQuery, useSuspenseQuery, useMutation } from "@tanstack/react-query";
import type { UseQueryOptions, UseSuspenseQueryOptions, UseMutationOptions } from "@tanstack/react-query";
export class ApiError extends Error {
    status: number;
    statusText: string;
    body: unknown;
    constructor(status: number, statusText: string, body: unknown){
        super(`HTTP ${status}: ${statusText}`);
        this.name = "ApiError";
        this.status = status;
        this.statusText = statusText;
        this.body = body;
    }
}
export interface AnalysisSummary {
    analysis_id: string;
    brand_input_value?: string;
    city?: string;
    country?: string;
    created_at?: string;
}
export interface AnalyzeRequest {
    beta?: number;
    brand_input: BrandInput;
    catchment_km?: number;
    categories: string[];
    city: string;
    competitor_brand?: string;
    country: string;
    enable_competition?: boolean;
    include_buildings?: boolean;
    include_radiance?: boolean;
    resolution?: number;
}
export interface AnalyzeResultOut {
    analysis_mode?: string;
    brand_locations: BrandLocationData[];
    center_lat: number;
    center_lon: number;
    city_polygon_geojson?: Record<string, unknown> | null;
    competitor_brand?: string;
    competitor_locations?: CompetitorLocationData[];
    existing_target_locations?: BrandLocationData[];
    has_competition?: boolean;
    hexagons: HexagonData[];
    session_id: string;
}
export interface AppConfigOut {
    building_category_groups: CategoryGroup[];
    category_groups: CategoryGroup[];
    default_resolution: number;
    h3_resolutions: number[];
}
export interface AssetLink {
    asset_type: string;
    name: string;
    url: string;
}
export interface AssetsOut {
    links?: AssetLink[];
    recent_analyses?: AnalysisSummary[];
    workspace_url?: string;
}
export interface BrandInput {
    geojson?: Record<string, unknown> | null;
    mode: string;
    selected_poi_ids?: string[] | null;
    value?: string;
}
export interface BrandLocationData {
    address?: string;
    count?: number;
    hex_id: string;
    is_source?: boolean;
    lat: number;
    lon: number;
}
export interface BrandPOIRow {
    brand?: string;
    category: string;
    h3_cell?: string;
    lat?: number | null;
    lon?: number | null;
    name: string;
}
export interface BrandProfileOut {
    avg_profile: CategoryAvgItem[];
    cell_breakdown: CellBreakdownRow[];
}
export interface CategoryAvgItem {
    avg_count: number;
    category: string;
    feature_type: string;
    group: string;
    pct_within_type: number;
}
export interface CategoryGroup {
    categories: string[];
    name: string;
}
export interface CellBreakdownRow {
    category: string;
    count: number;
    location: string;
}
export interface CellPOI {
    address?: string;
    brand?: string;
    category: string;
    name: string;
}
export interface CompetitionInfo {
    competition_score: number;
    competitor_count: number;
    opportunity_score: number;
    top_competitors: string;
    vibe_score: number;
}
export interface CompetitorLocationData {
    count?: number;
    hex_id: string;
    lat: number;
    lon: number;
    name?: string;
}
export interface CompetitorPOI {
    address?: string;
    brand?: string;
    category: string;
    name: string;
}
export interface FingerprintRow {
    brand_average: number;
    brand_average_pct: number;
    category: string;
    feature_type: string;
    group: string;
    this_location: number;
    this_location_pct: number;
}
export interface GenieDebugOut {
    brand_pois: BrandPOIRow[];
    competitor_pois_total?: number;
    total_brand_pois?: number;
}
export interface HTTPValidationError {
    detail?: ValidationError[];
}
export interface HexagonData {
    address?: string;
    cannibalization_risk?: number | null;
    cat_detail?: string;
    competitor_count?: number;
    h3_cell: number;
    hex_id: string;
    is_brand_cell: boolean;
    lat: number;
    lon: number;
    nearest_store_km?: number | null;
    opportunity_score?: number | null;
    poi_density?: number;
    radiance?: number | null;
    similarity: number;
    top_competitors?: string;
}
export interface HexagonDetailOut {
    address: string;
    cannibalization_risk?: number | null;
    cell_pois?: CellPOI[];
    cell_pois_title?: string;
    competition?: CompetitionInfo | null;
    competitor_pois?: CompetitorPOI[];
    explanation_summary?: string;
    fingerprint: FingerprintRow[];
    h3_cell: number;
    hex_id: string;
    nearest_store_km?: number | null;
    opportunity_score?: number | null;
    poi_density?: number;
    similarity: number;
}
export interface PersistResultOut {
    analysis_id: string;
    tables_written: string[];
}
export interface ResolveAddressesRequest {
    addresses: string;
    resolution?: number;
}
export interface ResolveAddressesResponse {
    results?: ResolvedAddress[];
}
export interface ResolvedAddress {
    address: string;
    lat: number;
    lon: number;
    pois?: ResolvedPOI[];
}
export interface ResolvedPOI {
    brand?: string;
    category?: string;
    name: string;
    poi_id: string;
}
export interface ShortlistAddIn {
    hex_id: string;
    note?: string;
    session_id: string;
}
export interface ShortlistItemOut {
    address?: string | null;
    brand?: string | null;
    cannibalization_risk?: number | null;
    city?: string | null;
    competitor_count?: number | null;
    country?: string | null;
    created_at: string;
    created_by?: string;
    hex_id: string;
    id: number;
    lat?: number | null;
    lon?: number | null;
    nearest_store_km?: number | null;
    note?: string;
    opportunity_score?: number | null;
    session_id: string;
    similarity?: number | null;
    status: "candidate" | "site_visit" | "negotiating" | "rejected";
    updated_at: string;
}
export interface ShortlistUpdateIn {
    note?: string | null;
    status?: "candidate" | "site_visit" | "negotiating" | "rejected" | null;
}
export interface ValidationError {
    ctx?: Record<string, unknown>;
    input?: unknown;
    loc: (string | number)[];
    msg: string;
    type: string;
}
export interface VersionOut {
    version: string;
}
export interface AnalyzeParams {
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const analyze = async (data: AnalyzeRequest, params?: AnalyzeParams, options?: RequestInit): Promise<{
    data: unknown;
}> =>{
    const res = await fetch("/api/analyze", {
        ...options,
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useAnalyze(options?: {
    mutation?: UseMutationOptions<{
        data: unknown;
    }, ApiError, {
        params: AnalyzeParams;
        data: AnalyzeRequest;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>analyze(vars.data, vars.params),
        ...options?.mutation
    });
}
export const getAssets = async (options?: RequestInit): Promise<{
    data: AssetsOut;
}> =>{
    const res = await fetch("/api/assets", {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const getAssetsKey = ()=>{
    return [
        "/api/assets"
    ] as const;
};
export function useGetAssets<TData = {
    data: AssetsOut;
}>(options?: {
    query?: Omit<UseQueryOptions<{
        data: AssetsOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: getAssetsKey(),
        queryFn: ()=>getAssets(),
        ...options?.query
    });
}
export function useGetAssetsSuspense<TData = {
    data: AssetsOut;
}>(options?: {
    query?: Omit<UseSuspenseQueryOptions<{
        data: AssetsOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: getAssetsKey(),
        queryFn: ()=>getAssets(),
        ...options?.query
    });
}
export interface ListCitiesParams {
    country: string;
}
export const listCities = async (params: ListCitiesParams, options?: RequestInit): Promise<{
    data: string[];
}> =>{
    const searchParams = new URLSearchParams();
    if (params.country != null) searchParams.set("country", String(params.country));
    const queryString = searchParams.toString();
    const url = queryString ? `/api/cities?${queryString}` : "/api/cities";
    const res = await fetch(url, {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const listCitiesKey = (params?: ListCitiesParams)=>{
    return [
        "/api/cities",
        params
    ] as const;
};
export function useListCities<TData = {
    data: string[];
}>(options: {
    params: ListCitiesParams;
    query?: Omit<UseQueryOptions<{
        data: string[];
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: listCitiesKey(options.params),
        queryFn: ()=>listCities(options.params),
        ...options?.query
    });
}
export function useListCitiesSuspense<TData = {
    data: string[];
}>(options: {
    params: ListCitiesParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: string[];
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: listCitiesKey(options.params),
        queryFn: ()=>listCities(options.params),
        ...options?.query
    });
}
export const getConfig = async (options?: RequestInit): Promise<{
    data: AppConfigOut;
}> =>{
    const res = await fetch("/api/config", {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const getConfigKey = ()=>{
    return [
        "/api/config"
    ] as const;
};
export function useGetConfig<TData = {
    data: AppConfigOut;
}>(options?: {
    query?: Omit<UseQueryOptions<{
        data: AppConfigOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: getConfigKey(),
        queryFn: ()=>getConfig(),
        ...options?.query
    });
}
export function useGetConfigSuspense<TData = {
    data: AppConfigOut;
}>(options?: {
    query?: Omit<UseSuspenseQueryOptions<{
        data: AppConfigOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: getConfigKey(),
        queryFn: ()=>getConfig(),
        ...options?.query
    });
}
export const listCountries = async (options?: RequestInit): Promise<{
    data: string[];
}> =>{
    const res = await fetch("/api/countries", {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const listCountriesKey = ()=>{
    return [
        "/api/countries"
    ] as const;
};
export function useListCountries<TData = {
    data: string[];
}>(options?: {
    query?: Omit<UseQueryOptions<{
        data: string[];
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: listCountriesKey(),
        queryFn: ()=>listCountries(),
        ...options?.query
    });
}
export function useListCountriesSuspense<TData = {
    data: string[];
}>(options?: {
    query?: Omit<UseSuspenseQueryOptions<{
        data: string[];
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: listCountriesKey(),
        queryFn: ()=>listCountries(),
        ...options?.query
    });
}
export const resolveAddresses = async (data: ResolveAddressesRequest, options?: RequestInit): Promise<{
    data: ResolveAddressesResponse;
}> =>{
    const res = await fetch("/api/resolve-addresses", {
        ...options,
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useResolveAddresses(options?: {
    mutation?: UseMutationOptions<{
        data: ResolveAddressesResponse;
    }, ApiError, ResolveAddressesRequest>;
}) {
    return useMutation({
        mutationFn: (data)=>resolveAddresses(data),
        ...options?.mutation
    });
}
export interface GetResultsParams {
    session_id: string;
}
export const getResults = async (params: GetResultsParams, options?: RequestInit): Promise<{
    data: AnalyzeResultOut;
}> =>{
    const res = await fetch(`/api/results/${params.session_id}`, {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const getResultsKey = (params?: GetResultsParams)=>{
    return [
        "/api/results/{session_id}",
        params
    ] as const;
};
export function useGetResults<TData = {
    data: AnalyzeResultOut;
}>(options: {
    params: GetResultsParams;
    query?: Omit<UseQueryOptions<{
        data: AnalyzeResultOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: getResultsKey(options.params),
        queryFn: ()=>getResults(options.params),
        ...options?.query
    });
}
export function useGetResultsSuspense<TData = {
    data: AnalyzeResultOut;
}>(options: {
    params: GetResultsParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: AnalyzeResultOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: getResultsKey(options.params),
        queryFn: ()=>getResults(options.params),
        ...options?.query
    });
}
export interface GetBrandProfileParams {
    session_id: string;
}
export const getBrandProfile = async (params: GetBrandProfileParams, options?: RequestInit): Promise<{
    data: BrandProfileOut;
}> =>{
    const res = await fetch(`/api/results/${params.session_id}/brand-profile`, {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const getBrandProfileKey = (params?: GetBrandProfileParams)=>{
    return [
        "/api/results/{session_id}/brand-profile",
        params
    ] as const;
};
export function useGetBrandProfile<TData = {
    data: BrandProfileOut;
}>(options: {
    params: GetBrandProfileParams;
    query?: Omit<UseQueryOptions<{
        data: BrandProfileOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: getBrandProfileKey(options.params),
        queryFn: ()=>getBrandProfile(options.params),
        ...options?.query
    });
}
export function useGetBrandProfileSuspense<TData = {
    data: BrandProfileOut;
}>(options: {
    params: GetBrandProfileParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: BrandProfileOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: getBrandProfileKey(options.params),
        queryFn: ()=>getBrandProfile(options.params),
        ...options?.query
    });
}
export interface GetGenieDebugParams {
    session_id: string;
}
export const getGenieDebug = async (params: GetGenieDebugParams, options?: RequestInit): Promise<{
    data: GenieDebugOut;
}> =>{
    const res = await fetch(`/api/results/${params.session_id}/debug`, {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const getGenieDebugKey = (params?: GetGenieDebugParams)=>{
    return [
        "/api/results/{session_id}/debug",
        params
    ] as const;
};
export function useGetGenieDebug<TData = {
    data: GenieDebugOut;
}>(options: {
    params: GetGenieDebugParams;
    query?: Omit<UseQueryOptions<{
        data: GenieDebugOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: getGenieDebugKey(options.params),
        queryFn: ()=>getGenieDebug(options.params),
        ...options?.query
    });
}
export function useGetGenieDebugSuspense<TData = {
    data: GenieDebugOut;
}>(options: {
    params: GetGenieDebugParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: GenieDebugOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: getGenieDebugKey(options.params),
        queryFn: ()=>getGenieDebug(options.params),
        ...options?.query
    });
}
export interface GetHexagonDetailParams {
    session_id: string;
    hex_id: string;
}
export const getHexagonDetail = async (params: GetHexagonDetailParams, options?: RequestInit): Promise<{
    data: HexagonDetailOut;
}> =>{
    const res = await fetch(`/api/results/${params.session_id}/hexagon/${params.hex_id}`, {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const getHexagonDetailKey = (params?: GetHexagonDetailParams)=>{
    return [
        "/api/results/{session_id}/hexagon/{hex_id}",
        params
    ] as const;
};
export function useGetHexagonDetail<TData = {
    data: HexagonDetailOut;
}>(options: {
    params: GetHexagonDetailParams;
    query?: Omit<UseQueryOptions<{
        data: HexagonDetailOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: getHexagonDetailKey(options.params),
        queryFn: ()=>getHexagonDetail(options.params),
        ...options?.query
    });
}
export function useGetHexagonDetailSuspense<TData = {
    data: HexagonDetailOut;
}>(options: {
    params: GetHexagonDetailParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: HexagonDetailOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: getHexagonDetailKey(options.params),
        queryFn: ()=>getHexagonDetail(options.params),
        ...options?.query
    });
}
export interface PersistAnalysisParams {
    session_id: string;
}
export const persistAnalysis = async (params: PersistAnalysisParams, options?: RequestInit): Promise<{
    data: PersistResultOut;
}> =>{
    const res = await fetch(`/api/results/${params.session_id}/persist`, {
        ...options,
        method: "POST"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function usePersistAnalysis(options?: {
    mutation?: UseMutationOptions<{
        data: PersistResultOut;
    }, ApiError, {
        params: PersistAnalysisParams;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>persistAnalysis(vars.params),
        ...options?.mutation
    });
}
export interface PersistAnalysisWithContextParams {
    session_id: string;
}
export const persistAnalysisWithContext = async (params: PersistAnalysisWithContextParams, data: AnalyzeRequest, options?: RequestInit): Promise<{
    data: PersistResultOut;
}> =>{
    const res = await fetch(`/api/results/${params.session_id}/persist-with-context`, {
        ...options,
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function usePersistAnalysisWithContext(options?: {
    mutation?: UseMutationOptions<{
        data: PersistResultOut;
    }, ApiError, {
        params: PersistAnalysisWithContextParams;
        data: AnalyzeRequest;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>persistAnalysisWithContext(vars.params, vars.data),
        ...options?.mutation
    });
}
export interface ListShortlistParams {
    session_id?: string | null;
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const listShortlist = async (params?: ListShortlistParams, options?: RequestInit): Promise<{
    data: ShortlistItemOut[];
}> =>{
    const searchParams = new URLSearchParams();
    if (params?.session_id != null) searchParams.set("session_id", String(params?.session_id));
    const queryString = searchParams.toString();
    const url = queryString ? `/api/shortlist?${queryString}` : "/api/shortlist";
    const res = await fetch(url, {
        ...options,
        method: "GET",
        headers: {
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        }
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const listShortlistKey = (params?: ListShortlistParams)=>{
    return [
        "/api/shortlist",
        params
    ] as const;
};
export function useListShortlist<TData = {
    data: ShortlistItemOut[];
}>(options?: {
    params?: ListShortlistParams;
    query?: Omit<UseQueryOptions<{
        data: ShortlistItemOut[];
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: listShortlistKey(options?.params),
        queryFn: ()=>listShortlist(options?.params),
        ...options?.query
    });
}
export function useListShortlistSuspense<TData = {
    data: ShortlistItemOut[];
}>(options?: {
    params?: ListShortlistParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: ShortlistItemOut[];
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: listShortlistKey(options?.params),
        queryFn: ()=>listShortlist(options?.params),
        ...options?.query
    });
}
export interface AddToShortlistParams {
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const addToShortlist = async (data: ShortlistAddIn, params?: AddToShortlistParams, options?: RequestInit): Promise<{
    data: ShortlistItemOut;
}> =>{
    const res = await fetch("/api/shortlist", {
        ...options,
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useAddToShortlist(options?: {
    mutation?: UseMutationOptions<{
        data: ShortlistItemOut;
    }, ApiError, {
        params: AddToShortlistParams;
        data: ShortlistAddIn;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>addToShortlist(vars.data, vars.params),
        ...options?.mutation
    });
}
export interface UpdateShortlistItemParams {
    item_id: number;
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const updateShortlistItem = async (params: UpdateShortlistItemParams, data: ShortlistUpdateIn, options?: RequestInit): Promise<{
    data: ShortlistItemOut;
}> =>{
    const res = await fetch(`/api/shortlist/${params.item_id}`, {
        ...options,
        method: "PATCH",
        headers: {
            "Content-Type": "application/json",
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useUpdateShortlistItem(options?: {
    mutation?: UseMutationOptions<{
        data: ShortlistItemOut;
    }, ApiError, {
        params: UpdateShortlistItemParams;
        data: ShortlistUpdateIn;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>updateShortlistItem(vars.params, vars.data),
        ...options?.mutation
    });
}
export interface RemoveShortlistItemParams {
    item_id: number;
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const removeShortlistItem = async (params: RemoveShortlistItemParams, options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const res = await fetch(`/api/shortlist/${params.item_id}`, {
        ...options,
        method: "DELETE",
        headers: {
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        }
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useRemoveShortlistItem(options?: {
    mutation?: UseMutationOptions<{
        data: Record<string, unknown>;
    }, ApiError, {
        params: RemoveShortlistItemParams;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>removeShortlistItem(vars.params),
        ...options?.mutation
    });
}
export const version = async (options?: RequestInit): Promise<{
    data: VersionOut;
}> =>{
    const res = await fetch("/api/version", {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const versionKey = ()=>{
    return [
        "/api/version"
    ] as const;
};
export function useVersion<TData = {
    data: VersionOut;
}>(options?: {
    query?: Omit<UseQueryOptions<{
        data: VersionOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: versionKey(),
        queryFn: ()=>version(),
        ...options?.query
    });
}
export function useVersionSuspense<TData = {
    data: VersionOut;
}>(options?: {
    query?: Omit<UseSuspenseQueryOptions<{
        data: VersionOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: versionKey(),
        queryFn: ()=>version(),
        ...options?.query
    });
}
