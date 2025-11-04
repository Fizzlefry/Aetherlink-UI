import { getTenantFromToken } from "./auth";

// API calls go through localhost (browser → Keycloak flow) with Host header for Traefik routing
const API_BASE = "http://localhost";

function getHeaders(token: string) {
    const tenant = getTenantFromToken(token) ?? "acme"; // fallback for safety

    return {
        "x-tenant-id": tenant,
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
        "Host": "apexflow.aetherlink.local", // Traefik routing
    };
}

export interface LeadListResponse {
    items: any[];
    total: number;
    limit: number;
    offset: number;
}

export interface Owner {
    email: string;
    name: string;
}

export async function fetchLeads(token: string, params: {
    status?: string;
    assigned_to?: string;
    q?: string;
    limit?: number;
    offset?: number;
    order_by?: string;
    order?: "asc" | "desc";
} = {}): Promise<LeadListResponse> {
    const url = new URL(`${API_BASE}/leads`);
    Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== "") {
            url.searchParams.set(k, String(v));
        }
    });

    const res = await fetch(url.toString(), {
        headers: getHeaders(token),
    });
    if (!res.ok) {
        throw new Error(`Failed to fetch leads: ${res.status}`);
    }
    return res.json();
}

export async function fetchOwners(token: string): Promise<Owner[]> {
    const res = await fetch(`${API_BASE}/owners`, {
        headers: getHeaders(token),
    });
    if (!res.ok) {
        throw new Error("Failed to fetch owners");
    }
    return res.json();
}

export async function patchLead(token: string, id: number, body: any) {
    const res = await fetch(`${API_BASE}/leads/${id}`, {
        method: "PATCH",
        headers: getHeaders(token),
        body: JSON.stringify(body),
    });
    if (!res.ok) {
        throw new Error(`Failed to update lead: ${res.status}`);
    }
    return res.json();
}

export async function createLead(
    token: string,
    body: {
        name?: string;
        email?: string;
        company?: string;
        phone?: string;
        status?: string;
        tags?: string[];
    }
) {
    const res = await fetch(`${API_BASE}/leads`, {
        method: "POST",
        headers: getHeaders(token),
        body: JSON.stringify(body),
    });
    if (!res.ok) {
        const txt = await res.text();
        throw new Error(`Failed to create lead: ${txt}`);
    }
    return res.json();
}

export interface LeadNote {
    id: number;
    lead_id: number;
    body: string;
    author: string;
    created_at: string;
}

export interface ActivityItem {
    type: "note" | "assigned" | "status_changed" | "created";
    actor: string;
    at: string;
    data: any;
    is_system: boolean;
}

export async function fetchLeadNotes(token: string, leadId: number): Promise<LeadNote[]> {
    const res = await fetch(`${API_BASE}/leads/${leadId}/notes`, {
        headers: getHeaders(token),
    });
    if (!res.ok) {
        throw new Error(`Failed to fetch notes: ${res.status}`);
    }
    return res.json();
}

export async function fetchLeadActivity(token: string, leadId: number): Promise<ActivityItem[]> {
    const res = await fetch(`${API_BASE}/leads/${leadId}/activity`, {
        headers: getHeaders(token),
    });
    if (!res.ok) {
        throw new Error(`Failed to fetch activity: ${res.status}`);
    }
    return res.json();
}

export async function createNote(token: string, leadId: number, body: string): Promise<LeadNote> {
    const res = await fetch(`${API_BASE}/leads/${leadId}/notes`, {
        method: "POST",
        headers: getHeaders(token),
        body: JSON.stringify({ body }),
    });
    if (!res.ok) {
        throw new Error(`Failed to create note: ${res.status}`);
    }
    return res.json();
}

// AI Summarizer client
// Chooses localhost in browser dev, service name in container
const AI_BASE =
    window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
        ? "http://localhost:9108"
        : "http://aether-ai-summarizer:9108";

export interface AISummaryResponse {
    lead_id: number;
    tenant_id: string;
    summary: string;
    confidence: number;
    raw_tokens?: number;
}

export async function fetchLeadSummary(leadId: number, tenantId: string): Promise<AISummaryResponse> {
    const res = await fetch(`${AI_BASE}/summaries/lead/${leadId}?tenant_id=${tenantId}`);
    if (!res.ok) {
        throw new Error(`Failed to fetch AI summary: ${res.status}`);
    }
    return res.json();
}

export interface LeadExtractionResponse {
    name?: string | null;
    email?: string | null;
    company?: string | null;
    phone?: string | null;
    status?: string | null;
    tags?: string[] | null;
    raw?: any;
}

export async function extractLeadFromText(
    tenantId: string,
    rawText: string
): Promise<LeadExtractionResponse> {
    const res = await fetch(`${AI_BASE}/summaries/extract-lead`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ tenant_id: tenantId, raw_text: rawText }),
    });
    if (!res.ok) {
        throw new Error("Failed to extract lead from text");
    }
    return res.json();
}
