import React, { useEffect, useState } from "react";
import { fetchLeads, fetchOwners, patchLead, createLead, Owner, fetchLeadActivity, createNote, ActivityItem, fetchLeadSummary, extractLeadFromText } from "./api";
import { getTenantFromToken } from "./auth";
import type Keycloak from "keycloak-js";
import CommandCenter from "./pages/CommandCenter";
import OperatorDashboard from "./pages/OperatorDashboard";

const STATUS_OPTIONS = ["new", "contacted", "qualified", "proposal", "won", "lost"];
const VIEW_KEY = "aetherlink.crm.view";

function App({ keycloak }: { keycloak: Keycloak }) {
    const token = keycloak.token || "";
    const username = keycloak.tokenParsed?.preferred_username || "";
    const [activeTab, setActiveTab] = useState<"leads" | "command-center" | "operator">("leads");
    const [leads, setLeads] = useState<any[]>([]);
    const [total, setTotal] = useState(0);
    const [limit, setLimit] = useState(25);
    const [offset, setOffset] = useState(0);
    const [view, setView] = useState<"all" | "mine" | "unassigned">(() => {
        const saved = localStorage.getItem(VIEW_KEY);
        if (saved === "mine" || saved === "unassigned") return saved;
        return "all";
    });
    const [showUnassigned, setShowUnassigned] = useState(false);
    const [statusFilter, setStatusFilter] = useState<string>("");
    const [owners, setOwners] = useState<Owner[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [selectedLead, setSelectedLead] = useState<any | null>(null);
    const [activities, setActivities] = useState<ActivityItem[]>([]);
    const [noteBody, setNoteBody] = useState("");
    const [notesLoading, setNotesLoading] = useState(false);
    const [aiSummary, setAiSummary] = useState<string | null>(null);
    const [aiLoading, setAiLoading] = useState(false);
    const [aiError, setAiError] = useState<string | null>(null);
    const [aiNoteSaving, setAiNoteSaving] = useState(false);
    const [aiNoteError, setAiNoteError] = useState<string | null>(null);

    // AI Extract for create lead
    const [showCreatePanel, setShowCreatePanel] = useState(false);
    const [extractText, setExtractText] = useState("");
    const [extracting, setExtracting] = useState(false);
    const [extractError, setExtractError] = useState<string | null>(null);
    const [newLeadName, setNewLeadName] = useState("");
    const [newLeadEmail, setNewLeadEmail] = useState("");
    const [newLeadCompany, setNewLeadCompany] = useState("");
    const [newLeadPhone, setNewLeadPhone] = useState("");
    const [newLeadStatus, setNewLeadStatus] = useState("new");
    const [newLeadTags, setNewLeadTags] = useState<string[]>(["ai-extracted"]);
    const [creatingLead, setCreatingLead] = useState(false);
    const [createError, setCreateError] = useState<string | null>(null);

    function handleViewChange(nextView: "all" | "mine" | "unassigned") {
        setView(nextView);
        localStorage.setItem(VIEW_KEY, nextView);
        setOffset(0);
        if (nextView === "unassigned") {
            setShowUnassigned(false); // Not needed since unassigned is now its own view
        } else if (nextView === "all") {
            setShowUnassigned(false);
        }
    }

    async function handleAssignToMe(leadId: number) {
        if (!token || !username) return;
        try {
            await patchLead(token, leadId, { assigned_to: username });
            await loadLeads();
        } catch (err) {
            alert("Failed to assign lead: " + (err instanceof Error ? err.message : "Unknown error"));
        }
    }

    async function loadLeads() {
        try {
            setLoading(true);
            setError(null);

            const params: any = {
                status: statusFilter || undefined,
                limit,
                offset,
                order_by: "created_at",
                order: "desc",
            };

            // Filter by current user if "My Leads" view is active
            if (view === "mine" && username) {
                params.assigned_to = username;
            } else if (view === "unassigned") {
                params.assigned_to = "UNASSIGNED";
            } else if (view === "all" && showUnassigned) {
                params.assigned_to = "UNASSIGNED";
            }

            const data = await fetchLeads(token, params);
            setLeads(data.items);
            setTotal(data.total);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load leads");
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        loadLeads();
    }, [view, statusFilter, limit, offset, token, username]);

    useEffect(() => {
        (async () => {
            try {
                const o = await fetchOwners(token);
                setOwners(o);
            } catch (err) {
                console.error("Failed to load owners:", err);
            }
        })();
    }, [token]);

    async function updateStatus(id: number, newStatus: string) {
        try {
            await patchLead(token, id, { status: newStatus });
            await loadLeads();
        } catch (err) {
            alert("Failed to update status: " + (err instanceof Error ? err.message : "Unknown error"));
        }
    }

    async function updateAssignment(id: number, newOwner: string) {
        try {
            await patchLead(token, id, { assigned_to: newOwner || null });
            await loadLeads();
        } catch (err) {
            alert("Failed to update assignment: " + (err instanceof Error ? err.message : "Unknown error"));
        }
    }

    async function openLeadDetail(lead: any) {
        setSelectedLead(lead);
        setNotesLoading(true);
        try {
            const leadActivities = await fetchLeadActivity(token, lead.id);
            setActivities(leadActivities);
        } catch (err) {
            console.error("Failed to load activity:", err);
        } finally {
            setNotesLoading(false);
        }
    }

    async function addNote() {
        if (!selectedLead || !noteBody.trim()) return;
        try {
            await createNote(token, selectedLead.id, noteBody);
            setNoteBody("");
            const leadActivities = await fetchLeadActivity(token, selectedLead.id);
            setActivities(leadActivities);
        } catch (err) {
            alert("Failed to add note: " + (err instanceof Error ? err.message : "Unknown error"));
        }
    }

    async function handleFetchAiSummary() {
        if (!selectedLead) return;
        const tenant = getTenantFromToken(keycloak.token) ?? "acme";

        setAiLoading(true);
        setAiError(null);
        setAiSummary(null);
        try {
            const data = await fetchLeadSummary(selectedLead.id, tenant);
            // Handle stub mode gracefully
            if (data.summary?.startsWith("No Claude API key configured")) {
                setAiSummary("✨ AI is wired correctly, but no Claude API key is configured on the server. Add CLAUDE_API_KEY to enable real summaries.");
            } else {
                setAiSummary(data.summary);
            }
        } catch (err: any) {
            setAiError(err.message ?? "Failed to fetch AI summary");
        } finally {
            setAiLoading(false);
        }
    }

    async function handleSaveAiSummaryAsNote() {
        if (!selectedLead || !aiSummary) return;
        setAiNoteSaving(true);
        setAiNoteError(null);
        try {
            if (!token) throw new Error("Not authenticated");

            // Use existing createNote API to save AI summary as a note
            await createNote(token, selectedLead.id, aiSummary);

            // Reload activity to show the new note immediately
            const leadActivities = await fetchLeadActivity(token, selectedLead.id);
            setActivities(leadActivities);

            setAiNoteSaving(false);
        } catch (err: any) {
            setAiNoteSaving(false);
            setAiNoteError(err.message ?? "Failed to save AI note");
        }
    }

    async function handleExtractLead() {
        setExtracting(true);
        setExtractError(null);
        try {
            const tenant = getTenantFromToken(keycloak.token) ?? "acme";
            const data = await extractLeadFromText(tenant, extractText);

            // Autofill the create form fields
            if (data.name) setNewLeadName(data.name);
            if (data.email) setNewLeadEmail(data.email);
            if (data.company) setNewLeadCompany(data.company);
            if (data.phone) setNewLeadPhone(data.phone);
            if (data.status) setNewLeadStatus(data.status);
            if (data.tags && data.tags.length > 0) setNewLeadTags(data.tags);

            setExtracting(false);
            setExtractText(""); // Clear the input after extraction
        } catch (err: any) {
            setExtractError(err.message ?? "Failed to extract lead data");
            setExtracting(false);
        }
    }

    async function handleCreateLeadFromAi() {
        if (!keycloak.token) return;
        setCreatingLead(true);
        setCreateError(null);
        try {
            await createLead(keycloak.token, {
                name: newLeadName || undefined,
                email: newLeadEmail || undefined,
                company: newLeadCompany || undefined,
                phone: newLeadPhone || undefined,
                status: newLeadStatus || "new",
                tags: newLeadTags && newLeadTags.length ? newLeadTags : ["ai-extracted"],
            });

            // Refresh the leads list
            await loadLeads();

            // Clear the form
            setNewLeadName("");
            setNewLeadEmail("");
            setNewLeadCompany("");
            setNewLeadPhone("");
            setNewLeadStatus("new");
            setNewLeadTags(["ai-extracted"]);
            setShowCreatePanel(false); // Close the panel after success

            setCreatingLead(false);
        } catch (err: any) {
            setCreateError(err.message ?? "Failed to create lead");
            setCreatingLead(false);
        }
    }

    const currentPage = Math.floor(offset / limit) + 1;
    const totalPages = Math.max(1, Math.ceil(total / limit));
    const displayUsername = username || "Unknown User";
    const viewLabel = view === "mine" ? "My leads" : view === "unassigned" ? "Unassigned leads" : "All leads";

    return (
        <div style={{ fontFamily: "system-ui, sans-serif", background: "#f5f5f5", minHeight: "100vh" }}>
            {/* Top Navigation Bar */}
            <div style={{ background: "white", borderBottom: "2px solid #e5e7eb", padding: "0 1.5rem" }}>
                <div style={{ maxWidth: "1400px", margin: "0 auto", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    {/* Left side - App name and tabs */}
                    <div style={{ display: "flex", alignItems: "center", gap: "0rem" }}>
                        <h1 style={{ fontSize: "1.25rem", fontWeight: 700, color: "#111827", padding: "1rem 1.5rem 1rem 0", margin: 0 }}>
                            AetherLink
                        </h1>
                        <div style={{ display: "flex", gap: "0rem" }}>
                            <button
                                onClick={() => setActiveTab("leads")}
                                style={{
                                    padding: "1rem 1.5rem",
                                    background: "transparent",
                                    border: "none",
                                    borderBottom: activeTab === "leads" ? "3px solid #3b82f6" : "3px solid transparent",
                                    color: activeTab === "leads" ? "#3b82f6" : "#6b7280",
                                    cursor: "pointer",
                                    fontSize: "0.9375rem",
                                    fontWeight: 500,
                                    transition: "all 0.2s"
                                }}
                            >
                                📋 Leads
                            </button>
                            <button
                                onClick={() => setActiveTab("command-center")}
                                style={{
                                    padding: "1rem 1.5rem",
                                    background: "transparent",
                                    border: "none",
                                    borderBottom: activeTab === "command-center" ? "3px solid #3b82f6" : "3px solid transparent",
                                    color: activeTab === "command-center" ? "#3b82f6" : "#6b7280",
                                    cursor: "pointer",
                                    fontSize: "0.9375rem",
                                    fontWeight: 500,
                                    transition: "all 0.2s"
                                }}
                            >
                                🎛️ Command Center
                            </button>
                            <button
                                onClick={() => setActiveTab("operator")}
                                style={{
                                    padding: "1rem 1.5rem",
                                    background: "transparent",
                                    border: "none",
                                    borderBottom: activeTab === "operator" ? "3px solid #3b82f6" : "3px solid transparent",
                                    color: activeTab === "operator" ? "#3b82f6" : "#6b7280",
                                    cursor: "pointer",
                                    fontSize: "0.9375rem",
                                    fontWeight: 500,
                                    transition: "all 0.2s"
                                }}
                            >
                                📊 Operator
                            </button>
                        </div>
                    </div>

                    {/* Right side - User info and logout */}
                    <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                        <div style={{ textAlign: "right" }}>
                            <div style={{ fontSize: "0.75rem", color: "#9ca3af" }}>Signed in as</div>
                            <div style={{ fontSize: "0.875rem", fontWeight: 500, color: "#374151" }}>{username}</div>
                        </div>
                        <button
                            onClick={() => keycloak.logout({ redirectUri: "http://localhost:5173" })}
                            style={{
                                padding: "0.5rem 1rem",
                                background: "#ef4444",
                                color: "white",
                                border: "none",
                                borderRadius: "4px",
                                cursor: "pointer",
                                fontSize: "0.875rem",
                                fontWeight: 500
                            }}
                        >
                            Logout
                        </button>
                    </div>
                </div>
            </div>

            {/* Content Area */}
            {activeTab === "command-center" ? (
                <CommandCenter />
            ) : activeTab === "operator" ? (
                <OperatorDashboard />
            ) : (
                <div style={{ padding: "1.5rem" }}>
                    <div style={{ maxWidth: "1400px", margin: "0 auto" }}>
                        {/* Leads Page Title */}
                        <div style={{ marginBottom: "1rem" }}>
                            <h2 style={{ fontSize: "1.5rem", marginBottom: "0.5rem", fontWeight: 600, color: "#111827" }}>
                                Leads Management
                            </h2>
                            <p style={{ color: "#6b7280", marginBottom: 0, fontSize: "0.875rem" }}>
                                Showing: <strong>{viewLabel}</strong> ({total} total)
                            </p>
                        </div>

                        {/* AI Extract / Create Lead Panel */}
                        <div style={{
                            marginBottom: "1.5rem",
                            background: "white",
                            border: "1px solid #e5e7eb",
                            borderRadius: "8px",
                            overflow: "hidden"
                        }}>
                            <button
                                onClick={() => setShowCreatePanel(!showCreatePanel)}
                                style={{
                                    width: "100%",
                                    padding: "1rem 1.5rem",
                                    background: showCreatePanel ? "#f9fafb" : "white",
                                    border: "none",
                                    cursor: "pointer",
                                    display: "flex",
                                    justifyContent: "space-between",
                                    alignItems: "center",
                                    fontSize: "0.875rem",
                                    fontWeight: 600,
                                    color: "#374151"
                                }}
                            >
                                <span>✨ Create New Lead (with AI Extract)</span>
                                <span>{showCreatePanel ? "▼" : "▶"}</span>
                            </button>

                            {showCreatePanel && (
                                <div style={{ padding: "1.5rem", borderTop: "1px solid #e5e7eb" }}>
                                    {/* AI Extract Section */}
                                    <div style={{
                                        marginBottom: "1.5rem",
                                        padding: "1rem",
                                        background: "#f9fafb",
                                        border: "1px solid #e5e7eb",
                                        borderRadius: "6px"
                                    }}>
                                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                                            <h4 style={{ margin: 0, fontSize: "0.875rem", fontWeight: 600, color: "#374151" }}>
                                                ✨ AI Extract (paste email/signature/notes)
                                            </h4>
                                            <button
                                                onClick={handleExtractLead}
                                                disabled={extracting || !extractText.trim()}
                                                style={{
                                                    padding: "0.375rem 0.75rem",
                                                    background: (extracting || !extractText.trim()) ? "#9ca3af" : "#1f2937",
                                                    color: "white",
                                                    border: "none",
                                                    borderRadius: "4px",
                                                    cursor: (extracting || !extractText.trim()) ? "not-allowed" : "pointer",
                                                    fontSize: "0.75rem",
                                                    fontWeight: 500
                                                }}
                                            >
                                                {extracting ? "Extracting..." : "Run AI Extract"}
                                            </button>
                                        </div>
                                        <textarea
                                            value={extractText}
                                            onChange={(e) => setExtractText(e.target.value)}
                                            style={{
                                                width: "100%",
                                                padding: "0.75rem",
                                                border: "1px solid #d1d5db",
                                                borderRadius: "4px",
                                                fontSize: "0.875rem",
                                                fontFamily: "monospace",
                                                background: "white",
                                                resize: "vertical"
                                            }}
                                            rows={4}
                                            placeholder="Jane Doe, VP Operations at Acme Corp&#10;jane.doe@acme.com&#10;+1 (555) 123-4567&#10;Met at CloudConf 2024..."
                                        />
                                        {extractError && (
                                            <p style={{ marginTop: "0.5rem", fontSize: "0.75rem", color: "#ef4444" }}>
                                                {extractError}
                                            </p>
                                        )}
                                    </div>

                                    {/* Lead Form Fields */}
                                    <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "1rem" }}>
                                        <div>
                                            <label style={{ display: "block", fontSize: "0.875rem", fontWeight: 500, marginBottom: "0.25rem", color: "#374151" }}>
                                                Name
                                            </label>
                                            <input
                                                type="text"
                                                value={newLeadName}
                                                onChange={(e) => setNewLeadName(e.target.value)}
                                                style={{
                                                    width: "100%",
                                                    padding: "0.5rem",
                                                    border: "1px solid #d1d5db",
                                                    borderRadius: "4px",
                                                    fontSize: "0.875rem"
                                                }}
                                                placeholder="Jane Doe"
                                            />
                                        </div>
                                        <div>
                                            <label style={{ display: "block", fontSize: "0.875rem", fontWeight: 500, marginBottom: "0.25rem", color: "#374151" }}>
                                                Email
                                            </label>
                                            <input
                                                type="email"
                                                value={newLeadEmail}
                                                onChange={(e) => setNewLeadEmail(e.target.value)}
                                                style={{
                                                    width: "100%",
                                                    padding: "0.5rem",
                                                    border: "1px solid #d1d5db",
                                                    borderRadius: "4px",
                                                    fontSize: "0.875rem"
                                                }}
                                                placeholder="jane@acme.com"
                                            />
                                        </div>
                                        <div>
                                            <label style={{ display: "block", fontSize: "0.875rem", fontWeight: 500, marginBottom: "0.25rem", color: "#374151" }}>
                                                Company
                                            </label>
                                            <input
                                                type="text"
                                                value={newLeadCompany}
                                                onChange={(e) => setNewLeadCompany(e.target.value)}
                                                style={{
                                                    width: "100%",
                                                    padding: "0.5rem",
                                                    border: "1px solid #d1d5db",
                                                    borderRadius: "4px",
                                                    fontSize: "0.875rem"
                                                }}
                                                placeholder="Acme Corp"
                                            />
                                        </div>
                                        <div>
                                            <label style={{ display: "block", fontSize: "0.875rem", fontWeight: 500, marginBottom: "0.25rem", color: "#374151" }}>
                                                Phone
                                            </label>
                                            <input
                                                type="tel"
                                                value={newLeadPhone}
                                                onChange={(e) => setNewLeadPhone(e.target.value)}
                                                style={{
                                                    width: "100%",
                                                    padding: "0.5rem",
                                                    border: "1px solid #d1d5db",
                                                    borderRadius: "4px",
                                                    fontSize: "0.875rem"
                                                }}
                                                placeholder="+1 (555) 123-4567"
                                            />
                                        </div>
                                        <div>
                                            <label style={{ display: "block", fontSize: "0.875rem", fontWeight: 500, marginBottom: "0.25rem", color: "#374151" }}>
                                                Status
                                            </label>
                                            <select
                                                value={newLeadStatus}
                                                onChange={(e) => setNewLeadStatus(e.target.value)}
                                                style={{
                                                    width: "100%",
                                                    padding: "0.5rem",
                                                    border: "1px solid #d1d5db",
                                                    borderRadius: "4px",
                                                    fontSize: "0.875rem",
                                                    background: "white"
                                                }}
                                            >
                                                {STATUS_OPTIONS.map(status => (
                                                    <option key={status} value={status}>{status}</option>
                                                ))}
                                            </select>
                                        </div>
                                    </div>

                                    {/* Create Lead Button */}
                                    <div style={{ marginTop: "1.5rem", display: "flex", gap: "0.75rem", alignItems: "center" }}>
                                        <button
                                            onClick={handleCreateLeadFromAi}
                                            disabled={creatingLead || !newLeadName.trim()}
                                            style={{
                                                display: "inline-flex",
                                                alignItems: "center",
                                                gap: "0.5rem",
                                                padding: "0.625rem 1.25rem",
                                                background: (creatingLead || !newLeadName.trim()) ? "#9ca3af" : "#10b981",
                                                color: "white",
                                                border: "none",
                                                borderRadius: "6px",
                                                cursor: (creatingLead || !newLeadName.trim()) ? "not-allowed" : "pointer",
                                                fontSize: "0.875rem",
                                                fontWeight: 600,
                                                transition: "background 0.2s"
                                            }}
                                            onMouseEnter={(e) => {
                                                if (!creatingLead && newLeadName.trim()) {
                                                    e.currentTarget.style.background = "#059669";
                                                }
                                            }}
                                            onMouseLeave={(e) => {
                                                if (!creatingLead && newLeadName.trim()) {
                                                    e.currentTarget.style.background = "#10b981";
                                                }
                                            }}
                                        >
                                            {creatingLead ? "Creating..." : "✅ Create Lead"}
                                        </button>
                                        {createError && (
                                            <span style={{ fontSize: "0.75rem", color: "#ef4444" }}>
                                                {createError}
                                            </span>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>

                        <div style={{ marginBottom: "1rem", display: "flex", gap: "1rem", alignItems: "center", flexWrap: "wrap" }}>
                            {/* View Switcher */}
                            <div style={{ display: "flex", gap: "0.25rem", background: "#f3f4f6", padding: "0.25rem", borderRadius: "6px" }}>
                                <button
                                    onClick={() => handleViewChange("all")}
                                    style={{
                                        padding: "0.5rem 1rem",
                                        background: view === "all" ? "white" : "transparent",
                                        color: view === "all" ? "#374151" : "#6b7280",
                                        border: "none",
                                        borderRadius: "4px",
                                        cursor: "pointer",
                                        fontSize: "0.875rem",
                                        fontWeight: view === "all" ? 600 : 500,
                                        boxShadow: view === "all" ? "0 1px 2px rgba(0,0,0,0.05)" : "none"
                                    }}
                                >
                                    All Leads
                                </button>
                                <button
                                    onClick={() => handleViewChange("mine")}
                                    style={{
                                        padding: "0.5rem 1rem",
                                        background: view === "mine" ? "white" : "transparent",
                                        color: view === "mine" ? "#374151" : "#6b7280",
                                        border: "none",
                                        borderRadius: "4px",
                                        cursor: "pointer",
                                        fontSize: "0.875rem",
                                        fontWeight: view === "mine" ? 600 : 500,
                                        boxShadow: view === "mine" ? "0 1px 2px rgba(0,0,0,0.05)" : "none"
                                    }}
                                >
                                    My Leads
                                </button>
                                <button
                                    onClick={() => handleViewChange("unassigned")}
                                    style={{
                                        padding: "0.5rem 1rem",
                                        background: view === "unassigned" ? "white" : "transparent",
                                        color: view === "unassigned" ? "#10b981" : "#6b7280",
                                        border: "none",
                                        borderRadius: "4px",
                                        cursor: "pointer",
                                        fontSize: "0.875rem",
                                        fontWeight: view === "unassigned" ? 600 : 500,
                                        boxShadow: view === "unassigned" ? "0 1px 2px rgba(0,0,0,0.05)" : "none"
                                    }}
                                >
                                    🎯 Unassigned
                                </button>
                            </div>

                            {/* Filters row */}
                            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                                <label style={{ fontWeight: 500 }}>Status:</label>
                                <select
                                    value={statusFilter}
                                    onChange={(e) => setStatusFilter(e.target.value)}
                                    style={{ padding: "0.5rem", borderRadius: "4px", border: "1px solid #ddd" }}
                                >
                                    <option value="">(All)</option>
                                    {STATUS_OPTIONS.map((s) => (
                                        <option key={s} value={s}>
                                            {s}
                                        </option>
                                    ))}
                                </select>
                            </div>

                            {/* Unassigned Filter (only on All Leads view) */}
                            {view === "all" && (
                                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                                    <label style={{ display: "flex", alignItems: "center", gap: "0.25rem", cursor: "pointer", fontSize: "0.875rem" }}>
                                        <input
                                            type="checkbox"
                                            checked={showUnassigned}
                                            onChange={(e) => { setShowUnassigned(e.target.checked); setOffset(0); }}
                                            style={{ cursor: "pointer" }}
                                        />
                                        Unassigned only
                                    </label>
                                </div>
                            )}

                            {loading && <span style={{ color: "#666" }}>Loading...</span>}
                        </div>

                        {error && (
                            <div style={{ background: "#fee", padding: "1rem", borderRadius: "4px", marginBottom: "1rem", color: "#c00" }}>
                                Error: {error}
                            </div>
                        )}

                        <div style={{ background: "white", borderRadius: "8px", overflow: "hidden", boxShadow: "0 1px 3px rgba(0,0,0,0.1)" }}>
                            <table style={{ width: "100%", borderCollapse: "collapse" }}>
                                <thead>
                                    <tr style={{ background: "#f9fafb", borderBottom: "2px solid #e5e7eb" }}>
                                        <th style={{ textAlign: "left", padding: "0.75rem 1rem", fontWeight: 600, fontSize: "0.875rem", color: "#374151" }}>Name</th>
                                        <th style={{ textAlign: "left", padding: "0.75rem 1rem", fontWeight: 600, fontSize: "0.875rem", color: "#374151" }}>Email</th>
                                        <th style={{ textAlign: "left", padding: "0.75rem 1rem", fontWeight: 600, fontSize: "0.875rem", color: "#374151" }}>Status</th>
                                        <th style={{ textAlign: "left", padding: "0.75rem 1rem", fontWeight: 600, fontSize: "0.875rem", color: "#374151" }}>Assigned To</th>
                                        <th style={{ textAlign: "left", padding: "0.75rem 1rem", fontWeight: 600, fontSize: "0.875rem", color: "#374151" }}>Tags</th>
                                        <th style={{ textAlign: "left", padding: "0.75rem 1rem", fontWeight: 600, fontSize: "0.875rem", color: "#374151" }}>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {leads.map((lead) => (
                                        <tr key={lead.id} style={{ borderBottom: "1px solid #e5e7eb" }}>
                                            <td style={{ padding: "0.75rem 1rem" }}>
                                                <div style={{ fontWeight: 500 }}>{lead.name}</div>
                                                <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>ID: {lead.id}</div>
                                            </td>
                                            <td style={{ padding: "0.75rem 1rem", fontSize: "0.875rem" }}>{lead.email}</td>
                                            <td style={{ padding: "0.75rem 1rem" }}>
                                                <span style={{
                                                    padding: "0.25rem 0.5rem",
                                                    borderRadius: "4px",
                                                    fontSize: "0.75rem",
                                                    fontWeight: 500,
                                                    background: lead.status === "won" ? "#d1fae5" : lead.status === "lost" ? "#fee" : "#e0e7ff",
                                                    color: lead.status === "won" ? "#065f46" : lead.status === "lost" ? "#991b1b" : "#3730a3"
                                                }}>
                                                    {lead.status}
                                                </span>
                                            </td>
                                            <td style={{ padding: "0.75rem 1rem" }}>
                                                <select
                                                    value={lead.assigned_to || ""}
                                                    onChange={(e) => updateAssignment(lead.id, e.target.value)}
                                                    style={{
                                                        padding: "0.375rem 0.5rem",
                                                        borderRadius: "4px",
                                                        border: "1px solid #d1d5db",
                                                        fontSize: "0.875rem",
                                                        cursor: "pointer",
                                                        color: lead.assigned_to ? "#374151" : "#9ca3af"
                                                    }}
                                                >
                                                    <option value="">— Unassigned —</option>
                                                    {owners.map((o) => (
                                                        <option key={o.email} value={o.email}>
                                                            {o.name}
                                                        </option>
                                                    ))}
                                                </select>
                                            </td>
                                            <td style={{ padding: "0.75rem 1rem", fontSize: "0.875rem" }}>
                                                {Array.isArray(lead.tags) && lead.tags.length > 0
                                                    ? lead.tags.map((tag: string) => (
                                                        <span key={tag} style={{
                                                            display: "inline-block",
                                                            padding: "0.125rem 0.5rem",
                                                            background: "#f3f4f6",
                                                            borderRadius: "4px",
                                                            marginRight: "0.25rem",
                                                            fontSize: "0.75rem"
                                                        }}>
                                                            {tag}
                                                        </span>
                                                    ))
                                                    : <span style={{ color: "#9ca3af" }}>—</span>
                                                }
                                            </td>
                                            <td style={{ padding: "0.75rem 1rem", display: "flex", gap: "0.5rem" }}>
                                                {!lead.assigned_to && (
                                                    <button
                                                        onClick={() => handleAssignToMe(lead.id)}
                                                        style={{
                                                            padding: "0.5rem 1rem",
                                                            background: "#10b981",
                                                            color: "white",
                                                            border: "none",
                                                            borderRadius: "4px",
                                                            fontSize: "0.875rem",
                                                            fontWeight: 500,
                                                            cursor: "pointer"
                                                        }}
                                                    >
                                                        Assign to me
                                                    </button>
                                                )}
                                                <button
                                                    onClick={() => openLeadDetail(lead)}
                                                    style={{
                                                        padding: "0.5rem 1rem",
                                                        background: "#3b82f6",
                                                        color: "white",
                                                        border: "none",
                                                        borderRadius: "4px",
                                                        cursor: "pointer",
                                                        fontSize: "0.875rem",
                                                        fontWeight: 500
                                                    }}
                                                >
                                                    View
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                    {leads.length === 0 && !loading && (
                                        <tr>
                                            <td colSpan={6} style={{ padding: "2rem", textAlign: "center", color: "#9ca3af" }}>
                                                {statusFilter ? `No leads found with status "${statusFilter}"` : "No leads found"}
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>

                        {/* Pagination Controls */}
                        <div style={{
                            display: "flex",
                            gap: "1rem",
                            marginTop: "1rem",
                            alignItems: "center",
                            padding: "1rem",
                            background: "white",
                            borderRadius: "8px",
                            boxShadow: "0 1px 3px rgba(0,0,0,0.1)"
                        }}>
                            <button
                                onClick={() => setOffset(Math.max(0, offset - limit))}
                                disabled={offset === 0}
                                style={{
                                    padding: "0.5rem 1rem",
                                    border: "1px solid #d1d5db",
                                    borderRadius: "4px",
                                    background: offset === 0 ? "#f3f4f6" : "white",
                                    cursor: offset === 0 ? "not-allowed" : "pointer",
                                    color: offset === 0 ? "#9ca3af" : "#374151"
                                }}
                            >
                                ← Prev
                            </button>

                            <span style={{ fontWeight: 500 }}>
                                Page {currentPage} of {totalPages}
                            </span>

                            <button
                                onClick={() => {
                                    if (offset + limit < total) setOffset(offset + limit);
                                }}
                                disabled={offset + limit >= total}
                                style={{
                                    padding: "0.5rem 1rem",
                                    border: "1px solid #d1d5db",
                                    borderRadius: "4px",
                                    background: offset + limit >= total ? "#f3f4f6" : "white",
                                    cursor: offset + limit >= total ? "not-allowed" : "pointer",
                                    color: offset + limit >= total ? "#9ca3af" : "#374151"
                                }}
                            >
                                Next →
                            </button>

                            <select
                                value={limit}
                                onChange={(e) => {
                                    setOffset(0);
                                    setLimit(Number(e.target.value));
                                }}
                                style={{
                                    padding: "0.5rem",
                                    border: "1px solid #d1d5db",
                                    borderRadius: "4px",
                                    cursor: "pointer"
                                }}
                            >
                                <option value={10}>10 / page</option>
                                <option value={25}>25 / page</option>
                                <option value={50}>50 / page</option>
                                <option value={100}>100 / page</option>
                            </select>

                            <span style={{ color: "#6b7280", marginLeft: "auto" }}>
                                <strong>{total}</strong> total leads
                            </span>
                        </div>

                        <div style={{ marginTop: "1.5rem", padding: "1rem", background: "white", borderRadius: "8px", fontSize: "0.875rem", color: "#6b7280" }}>
                            <strong>Operator Notes:</strong> Status + assignment changes trigger PATCH /leads/:id → Kafka event → Event Sink → Prometheus metrics.
                            Check Grafana for "Leads by Status" visualization.
                        </div>

                        {/* Lead Detail Drawer */}
                        {selectedLead && (
                            <div
                                style={{
                                    position: "fixed",
                                    top: 0,
                                    right: 0,
                                    bottom: 0,
                                    width: "500px",
                                    background: "white",
                                    boxShadow: "-2px 0 8px rgba(0,0,0,0.2)",
                                    zIndex: 1000,
                                    display: "flex",
                                    flexDirection: "column",
                                    overflowY: "auto"
                                }}
                            >
                                <div style={{ padding: "1.5rem", borderBottom: "1px solid #e5e7eb", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                    <h2 style={{ fontSize: "1.5rem", fontWeight: 600, margin: 0 }}>
                                        {selectedLead.name}
                                    </h2>
                                    <button
                                        onClick={() => setSelectedLead(null)}
                                        style={{
                                            padding: "0.5rem",
                                            background: "#f3f4f6",
                                            border: "none",
                                            borderRadius: "4px",
                                            cursor: "pointer",
                                            fontSize: "1.25rem",
                                            lineHeight: "1"
                                        }}
                                    >
                                        ✕
                                    </button>
                                </div>

                                <div style={{ padding: "1.5rem", borderBottom: "1px solid #e5e7eb" }}>
                                    <div style={{ marginBottom: "0.75rem" }}>
                                        <strong style={{ color: "#6b7280", fontSize: "0.875rem" }}>Email:</strong>
                                        <div>{selectedLead.email}</div>
                                    </div>
                                    <div style={{ marginBottom: "0.75rem" }}>
                                        <strong style={{ color: "#6b7280", fontSize: "0.875rem" }}>Status:</strong>
                                        <div>
                                            <span style={{
                                                padding: "0.25rem 0.5rem",
                                                borderRadius: "4px",
                                                fontSize: "0.875rem",
                                                fontWeight: 500,
                                                background: selectedLead.status === "won" ? "#d1fae5" : selectedLead.status === "lost" ? "#fee" : "#e0e7ff",
                                                color: selectedLead.status === "won" ? "#065f46" : selectedLead.status === "lost" ? "#991b1b" : "#3730a3"
                                            }}>
                                                {selectedLead.status}
                                            </span>
                                        </div>
                                    </div>
                                    <div>
                                        <strong style={{ color: "#6b7280", fontSize: "0.875rem" }}>Assigned To:</strong>
                                        <div>{selectedLead.assigned_to || <span style={{ color: "#9ca3af" }}>Unassigned</span>}</div>
                                    </div>
                                </div>

                                <div style={{ padding: "1.5rem", flex: 1 }}>
                                    {/* AI Summary Section */}
                                    <div style={{ marginBottom: "1.5rem" }}>
                                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
                                            <button
                                                onClick={handleFetchAiSummary}
                                                disabled={aiLoading}
                                                style={{
                                                    padding: "0.5rem 1rem",
                                                    background: aiLoading ? "#e0e7ff" : "#7c3aed",
                                                    color: "white",
                                                    border: "none",
                                                    borderRadius: "6px",
                                                    cursor: aiLoading ? "not-allowed" : "pointer",
                                                    fontSize: "0.875rem",
                                                    fontWeight: 500,
                                                    transition: "background 0.2s"
                                                }}
                                                onMouseEnter={(e) => {
                                                    if (!aiLoading) e.currentTarget.style.background = "#6d28d9";
                                                }}
                                                onMouseLeave={(e) => {
                                                    if (!aiLoading) e.currentTarget.style.background = "#7c3aed";
                                                }}
                                            >
                                                {aiLoading ? "Summarizing..." : "✨ AI Summary"}
                                            </button>
                                            {aiError && <span style={{ fontSize: "0.75rem", color: "#ef4444" }}>{aiError}</span>}
                                        </div>

                                        {aiSummary && (
                                            <div style={{
                                                marginBottom: "0.75rem",
                                                padding: "1rem",
                                                background: "#f5f3ff",
                                                border: "1px solid #e9d5ff",
                                                borderRadius: "8px",
                                                fontSize: "0.875rem",
                                                lineHeight: "1.6"
                                            }}>
                                                <div style={{
                                                    display: "flex",
                                                    justifyContent: "space-between",
                                                    alignItems: "center",
                                                    marginBottom: "0.5rem"
                                                }}>
                                                    <div style={{
                                                        fontSize: "0.75rem",
                                                        fontWeight: 600,
                                                        color: "#7c3aed",
                                                        textTransform: "uppercase",
                                                        letterSpacing: "0.05em"
                                                    }}>
                                                        AI Insight (Claude Sonnet)
                                                    </div>
                                                    <button
                                                        onClick={handleSaveAiSummaryAsNote}
                                                        disabled={aiNoteSaving}
                                                        style={{
                                                            padding: "0.375rem 0.75rem",
                                                            background: aiNoteSaving ? "#c4b5fd" : "#7c3aed",
                                                            color: "white",
                                                            border: "none",
                                                            borderRadius: "4px",
                                                            cursor: aiNoteSaving ? "not-allowed" : "pointer",
                                                            fontSize: "0.75rem",
                                                            fontWeight: 500,
                                                            transition: "background 0.2s"
                                                        }}
                                                        onMouseEnter={(e) => {
                                                            if (!aiNoteSaving) e.currentTarget.style.background = "#6d28d9";
                                                        }}
                                                        onMouseLeave={(e) => {
                                                            if (!aiNoteSaving) e.currentTarget.style.background = "#7c3aed";
                                                        }}
                                                    >
                                                        {aiNoteSaving ? "Saving..." : "📥 Add to timeline"}
                                                    </button>
                                                </div>
                                                <p style={{ color: "#374151", margin: 0, whiteSpace: "pre-wrap" }}>
                                                    {aiSummary}
                                                </p>
                                                {aiNoteError && (
                                                    <p style={{ marginTop: "0.5rem", fontSize: "0.75rem", color: "#ef4444" }}>
                                                        {aiNoteError}
                                                    </p>
                                                )}
                                            </div>
                                        )}
                                    </div>

                                    <h3 style={{ fontSize: "1.125rem", fontWeight: 600, marginBottom: "1rem" }}>Activity Timeline</h3>

                                    {notesLoading ? (
                                        <div style={{ color: "#6b7280" }}>Loading activity...</div>
                                    ) : (
                                        <div style={{ marginBottom: "1.5rem" }}>
                                            {activities.length === 0 ? (
                                                <div style={{ color: "#9ca3af", fontSize: "0.875rem", textAlign: "center", padding: "2rem" }}>
                                                    No activity yet. Add a note below to start the conversation.
                                                </div>
                                            ) : (
                                                activities.map((activity, idx) => {
                                                    const borderColor = activity.type === "created" ? "#10b981" : activity.type === "assigned" ? "#f59e0b" : "#3b82f6";
                                                    const bgColor = activity.is_system ? "#fafafa" : "#f9fafb";

                                                    return (
                                                        <div key={idx} style={{ marginBottom: "1rem", padding: "1rem", background: bgColor, borderRadius: "6px", borderLeft: `3px solid ${borderColor}` }}>
                                                            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
                                                                <span style={{ fontWeight: 500, fontSize: "0.875rem" }}>{activity.actor}</span>
                                                                {activity.is_system && (
                                                                    <span style={{
                                                                        padding: "0.125rem 0.375rem",
                                                                        background: "#e5e7eb",
                                                                        color: "#6b7280",
                                                                        fontSize: "0.625rem",
                                                                        fontWeight: 600,
                                                                        borderRadius: "3px",
                                                                        textTransform: "uppercase"
                                                                    }}>
                                                                        System
                                                                    </span>
                                                                )}
                                                            </div>

                                                            <div style={{ fontSize: "0.875rem", color: "#374151" }}>
                                                                {activity.type === "note" && activity.data.body}
                                                                {activity.type === "created" && (
                                                                    <span>🎉 Created lead <strong>{activity.data.name}</strong> from {activity.data.source}</span>
                                                                )}
                                                                {activity.type === "assigned" && (
                                                                    activity.data.assigned_to ? (
                                                                        activity.data.from ? (
                                                                            <span>🔄 Reassigned from <strong>{activity.data.from}</strong> to <strong>{activity.data.assigned_to}</strong></span>
                                                                        ) : (
                                                                            <span>✅ Assigned to <strong>{activity.data.assigned_to}</strong></span>
                                                                        )
                                                                    ) : (
                                                                        <span>❌ Unassigned (was <strong>{activity.data.from}</strong>)</span>
                                                                    )
                                                                )}
                                                                {activity.type === "status_changed" && (
                                                                    <span>📊 Status: <strong>{activity.data.old_status}</strong> → <strong>{activity.data.new_status}</strong></span>
                                                                )}
                                                            </div>

                                                            <div style={{ fontSize: "0.75rem", color: "#9ca3af", marginTop: "0.5rem" }}>
                                                                {new Date(activity.at).toLocaleString()}
                                                                {activity.is_system && activity.actor !== "system" && (
                                                                    <span style={{ marginLeft: "0.5rem" }}>• by {activity.actor}</span>
                                                                )}
                                                            </div>
                                                        </div>
                                                    );
                                                })
                                            )}
                                        </div>
                                    )}

                                    <div style={{ marginTop: "auto", borderTop: "1px solid #e5e7eb", paddingTop: "1rem" }}>
                                        <label style={{ display: "block", fontWeight: 500, marginBottom: "0.5rem" }}>Add Note</label>
                                        <textarea
                                            value={noteBody}
                                            onChange={(e) => setNoteBody(e.target.value)}
                                            placeholder="Type your note here..."
                                            style={{
                                                width: "100%",
                                                padding: "0.75rem",
                                                border: "1px solid #d1d5db",
                                                borderRadius: "4px",
                                                fontSize: "0.875rem",
                                                minHeight: "80px",
                                                resize: "vertical",
                                                fontFamily: "inherit"
                                            }}
                                        />
                                        <button
                                            onClick={addNote}
                                            disabled={!noteBody.trim()}
                                            style={{
                                                marginTop: "0.5rem",
                                                padding: "0.625rem 1.25rem",
                                                background: noteBody.trim() ? "#3b82f6" : "#e5e7eb",
                                                color: noteBody.trim() ? "white" : "#9ca3af",
                                                border: "none",
                                                borderRadius: "4px",
                                                cursor: noteBody.trim() ? "pointer" : "not-allowed",
                                                fontSize: "0.875rem",
                                                fontWeight: 500
                                            }}
                                        >
                                            Add Note
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Overlay */}
                        {selectedLead && (
                            <div
                                onClick={() => setSelectedLead(null)}
                                style={{
                                    position: "fixed",
                                    top: 0,
                                    left: 0,
                                    right: 0,
                                    bottom: 0,
                                    background: "rgba(0, 0, 0, 0.5)",
                                    zIndex: 999
                                }}
                            />
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

export default App;
