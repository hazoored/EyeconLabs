"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { api, getToken } from "@/lib/api";

interface Campaign {
    id: number;
    client_id: number;
    client_name: string;
    name: string;
    status: string;
    target_groups: string[];
    message_type: string;
    message_content: string | null;
    delay_seconds: number;
    created_at: string;
    group_count?: number;
    groups_sent?: number;
    total_sent?: number;
    total_failed?: number;
}

interface Client {
    id: number;
    name: string;
}

interface AssignedAccount {
    id: number;
    phone_number: string;
    display_name: string | null;
    is_premium: boolean;
    synced_groups?: number;
    synced_forums?: number;
}

interface MessageTemplate {
    id: number;
    name: string;
    text_content: string;
    entities_json: string | null;
    has_media: number;
    media_type: string | null;
    created_at: string;
}

export default function CampaignsPage() {
    const router = useRouter();
    const [campaigns, setCampaigns] = useState<Campaign[]>([]);
    const [clients, setClients] = useState<Client[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [showModal, setShowModal] = useState(false);
    const [newCampaign, setNewCampaign] = useState({
        client_id: 0,
        name: "",
        target_groups: [] as string[],
        target_topic: "",
        is_custom_list: false,
        custom_links: "",
        message_type: "text",
        message_content: "",
        delay_seconds: 30,
        send_mode: "send",  // "send" or "forward"
        forward_link: "",   // t.me/c/xxx/123 format for forwarding
        account_ids: [] as number[],  // Selected accounts (empty = all assigned accounts)
        template_id: 0,     // Selected message template (0 = manual input)
    });
    const [groupFiles, setGroupFiles] = useState<{ filename: string; group_count: number }[]>([]);
    const [selectedGroupFile, setSelectedGroupFile] = useState("");

    // Account selection state
    const [clientAccounts, setClientAccounts] = useState<AssignedAccount[]>([]);
    const [syncingAccount, setSyncingAccount] = useState<number | null>(null);

    // Message templates state
    const [templates, setTemplates] = useState<MessageTemplate[]>([]);

    // Live progress state
    const [showProgressModal, setShowProgressModal] = useState(false);
    const [watchingCampaignId, setWatchingCampaignId] = useState<number | null>(null);
    const [liveProgress, setLiveProgress] = useState<{
        status: string;
        mode?: string;
        total: number;
        sent: number;
        failed: number;
        current_group: string | null;
        recent_logs: { group: string; status: string; error: string | null; index: number; cycle?: number; account?: string }[];
        progress_percent: number;
        cycle?: number;
        accounts?: Record<string, { phone: string; status: string; sent: number; failed: number; total?: number; current_group: string | null; delay?: number }>;
    } | null>(null);
    const pollingRef = useRef<NodeJS.Timeout | null>(null);

    useEffect(() => {
        const token = getToken("admin");
        if (!token) {
            router.push("/admin/login");
            return;
        }
        fetchData(token);
    }, [router]);

    const fetchData = async (token: string) => {
        const [campaignsRes, clientsRes] = await Promise.all([
            api<{ campaigns: Campaign[] }>("/admin/campaigns", { token }),
            api<{ clients: Client[] }>("/admin/clients", { token }),
        ]);

        setLoading(false);

        if (campaignsRes.ok) setCampaigns(campaignsRes.data?.campaigns || []);
        if (clientsRes.ok) setClients(clientsRes.data?.clients || []);

        // Fetch group files
        const groupsRes = await api<{ files: { filename: string; group_count: number }[] }>("/admin/groups/files", { token });
        if (groupsRes.ok) setGroupFiles(groupsRes.data?.files || []);
    };

    // Fetch accounts assigned to a client
    const fetchClientAccounts = async (clientId: number) => {
        const token = getToken("admin");
        if (!token || !clientId) {
            setClientAccounts([]);
            return;
        }

        const res = await api<{ accounts: AssignedAccount[] }>(`/admin/clients/${clientId}/accounts`, { token });
        if (res.ok && res.data?.accounts) {
            setClientAccounts(res.data.accounts);
        } else {
            setClientAccounts([]);
        }
    };

    // Fetch message templates for a client (from Message Collector Bot)
    const fetchClientTemplates = async (clientId: number) => {
        const token = getToken("admin");
        if (!token || !clientId) {
            setTemplates([]);
            return;
        }

        const res = await api<{ templates: MessageTemplate[] }>(`/admin/templates/client/${clientId}`, { token });
        if (res.ok && res.data?.templates) {
            setTemplates(res.data.templates);
        } else {
            setTemplates([]);
        }
    };

    // Sync groups for an account (loads count from Telegram)
    const syncAccountGroups = async (accountId: number) => {
        const token = getToken("admin");
        if (!token) return;

        setSyncingAccount(accountId);

        const res = await api<{ total: number; groups_count: number; forums_count: number }>(`/admin/accounts/${accountId}/dialogs`, { token });

        if (res.ok && res.data) {
            // Update the account in the list with synced counts
            setClientAccounts(prev => prev.map(acc =>
                acc.id === accountId
                    ? { ...acc, synced_groups: res.data!.groups_count, synced_forums: res.data!.forums_count }
                    : acc
            ));
        }

        setSyncingAccount(null);
    };

    const handleCreateCampaign = async (e: React.FormEvent) => {
        e.preventDefault();
        const token = getToken("admin");
        if (!token) return;

        // Create campaign first
        const response = await api<{ campaign: { id: number } }>("/admin/campaigns", {
            method: "POST",
            body: {
                ...newCampaign,
                target_groups: [], // We use selectedGroupFile or custom_links backend logic
            },
            token,
        });

        if (!response.ok) {
            setError(response.error || "Failed to create campaign");
            return;
        }

        // If group file selected, add those groups
        if (selectedGroupFile && response.data?.campaign?.id) {
            await api(`/admin/campaigns/${response.data.campaign.id}/groups`, {
                method: "POST",
                body: { groups: [], group_file: selectedGroupFile },
                token,
            });
        }

        setShowModal(false);
        setSelectedGroupFile("");
        setNewCampaign({
            client_id: 0,
            name: "",
            target_groups: [],
            target_topic: "",
            is_custom_list: false,
            custom_links: "",
            message_type: "text",
            message_content: "",
            delay_seconds: 30,
            send_mode: "send",
            forward_link: "",
            account_ids: [],
            template_id: 0,
        });
        setClientAccounts([]);
        fetchData(token);
    };

    const handleCampaignAction = async (campaignId: number, action: "start" | "stop") => {
        const token = getToken("admin");
        if (!token) return;

        const res = await api<{ message?: string; detail?: string }>(`/admin/campaigns/${campaignId}/${action}`, { method: "POST", token });

        if (!res.ok) {
            alert(res.error || res.data?.detail || `Failed to ${action} campaign`);
        }

        fetchData(token);
    };

    const handleRemoveAccountFromCampaign = async (accountId: string) => {
        if (!watchingCampaignId) return;
        if (!confirm("Remove this account from the running campaign?")) return;

        const token = getToken("admin");
        if (!token) return;

        const res = await api<{ message: string }>(`/admin/campaigns/${watchingCampaignId}/remove-account/${accountId}`, {
            method: "POST",
            token
        });

        if (!res.ok) {
            alert(res.error || "Failed to remove account");
        }
    };

    const getStatusBadge = (status: string) => {
        switch (status) {
            case "running":
                return "badge-success";
            case "paused":
            case "stopped":
                return "badge-warning";
            case "completed":
                return "badge-info";
            default:
                return "badge-info";
        }
    };

    const handleDeleteCampaign = async (campaignId: number, campaignName: string) => {
        if (!confirm(`Delete campaign "${campaignName}"? This cannot be undone.`)) return;

        const token = getToken("admin");
        if (!token) return;

        const res = await api<{ message?: string; detail?: string }>(`/admin/campaigns/${campaignId}`, {
            method: "DELETE",
            token
        });

        if (!res.ok) {
            alert(res.error || res.data?.detail || "Failed to delete campaign");
            return;
        }

        fetchData(token);
    };

    // Live progress polling
    const startWatching = (campaignId: number) => {
        const token = getToken("admin");
        if (!token) return;

        setWatchingCampaignId(campaignId);
        setShowProgressModal(true);

        // Fetch immediately
        const fetchProgress = async () => {
            const res = await api<{
                status: string;
                total: number;
                sent: number;
                failed: number;
                current_group: string | null;
                recent_logs: { group: string; status: string; error: string | null; index: number }[];
                progress_percent: number;
            }>(`/admin/campaigns/${campaignId}/status`, { token });

            if (res.ok && res.data) {
                setLiveProgress(res.data);

                // Stop polling if completed or stopped
                if (res.data.status === "completed" || res.data.status === "stopped" || res.data.status === "idle") {
                    stopWatching();
                }
            }
        };

        fetchProgress();

        // Poll every 2 seconds
        pollingRef.current = setInterval(fetchProgress, 2000);
    };

    const stopWatching = () => {
        if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
        }
    };

    // Cleanup on unmount
    useEffect(() => {
        return () => stopWatching();
    }, []);

    if (loading) {
        return (
            <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <div style={{ color: "#22d3ee", fontSize: "1.25rem" }}>Loading...</div>
            </div>
        );
    }

    return (
        <>
            <Sidebar userType="admin" />

            <main className="main-content">
                <div className="page-header">
                    <div>
                        <h1 className="page-title">Campaigns</h1>
                        <p className="page-subtitle">Manage broadcast campaigns</p>
                    </div>
                    <button onClick={() => setShowModal(true)} className="btn-primary">
                        + New Campaign
                    </button>
                </div>

                {error && (
                    <div style={{ background: "rgba(239,68,68,0.1)", color: "#f87171", padding: "0.75rem 1rem", borderRadius: "0.5rem", marginBottom: "1.5rem" }}>
                        {error}
                    </div>
                )}

                {/* Stats */}
                <div className="stats-grid" style={{ marginBottom: "1.5rem" }}>
                    <div className="glass-card">
                        <div className="stat-value">{campaigns.length}</div>
                        <div className="stat-label">Total Campaigns</div>
                    </div>
                    <div className="glass-card">
                        <div className="stat-value" style={{ color: "#4ade80" }}>{campaigns.filter(c => c.status === "running").length}</div>
                        <div className="stat-label">Running</div>
                    </div>
                    <div className="glass-card">
                        <div className="stat-value" style={{ color: "#facc15" }}>{campaigns.filter(c => c.status === "paused").length}</div>
                        <div className="stat-label">Paused</div>
                    </div>
                </div>

                <div className="glass-card">
                    {campaigns.length > 0 ? (
                        <div className="responsive-table">
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Name</th>
                                        <th>Client</th>
                                        <th className="hide-mobile">Type</th>
                                        <th className="hide-mobile">Groups</th>
                                        <th className="hide-mobile">Delay</th>
                                        <th>Status</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {campaigns.map((campaign) => (
                                        <tr key={campaign.id}>
                                            <td style={{ color: "white", fontWeight: 500 }}>{campaign.name}</td>
                                            <td style={{ color: "#22d3ee" }}>{campaign.client_name}</td>
                                            <td className="hide-mobile capitalize">{campaign.message_type}</td>
                                            <td className="hide-mobile">
                                                {(campaign.group_count || 0) > 0 ? (
                                                    <>
                                                        {campaign.group_count || campaign.target_groups?.length || 0} groups
                                                        {campaign.status === "running" && (
                                                            <div style={{ fontSize: "0.7rem", color: "#4ade80" }}>
                                                                {campaign.total_sent || 0} sent
                                                            </div>
                                                        )}
                                                    </>
                                                ) : (
                                                    <span style={{ color: "#22d3ee", fontSize: "0.8rem" }}>Auto-detect</span>
                                                )}
                                            </td>
                                            <td className="hide-mobile">{campaign.delay_seconds}s</td>
                                            <td>
                                                <span className={`badge ${getStatusBadge(campaign.status)}`}>
                                                    {campaign.status}
                                                </span>
                                            </td>
                                            <td>
                                                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                                                    {campaign.status === "running" ? (
                                                        <>
                                                            <button
                                                                onClick={() => startWatching(campaign.id)}
                                                                style={{ color: "#22d3ee", background: "none", border: "none", cursor: "pointer" }}
                                                                title="Watch Live"
                                                            >
                                                                Watch
                                                            </button>
                                                            <button
                                                                onClick={() => handleCampaignAction(campaign.id, "stop")}
                                                                style={{ color: "#facc15", background: "none", border: "none", cursor: "pointer" }}
                                                                title="Stop"
                                                            >
                                                                Stop
                                                            </button>
                                                        </>
                                                    ) : (
                                                        <>
                                                            <button
                                                                onClick={() => handleCampaignAction(campaign.id, "start")}
                                                                style={{ color: "#4ade80", background: "none", border: "none", cursor: "pointer" }}
                                                                title="Start"
                                                            >
                                                                Start
                                                            </button>
                                                            <button
                                                                onClick={() => handleDeleteCampaign(campaign.id, campaign.name)}
                                                                style={{ color: "#ef4444", background: "none", border: "none", cursor: "pointer", fontSize: "0.9rem" }}
                                                                title="Delete Campaign"
                                                            >
                                                                Delete
                                                            </button>
                                                        </>
                                                    )}
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    ) : (
                        <p style={{ color: "#9ca3af", textAlign: "center", padding: "2rem" }}>No campaigns yet.</p>
                    )}
                </div>

                {/* Live Progress Modal - Full Screen Mobile Style */}
                {showProgressModal && liveProgress && (
                    <div style={{
                        position: "fixed",
                        inset: 0,
                        background: "#0a0f1a",
                        zIndex: 1000,
                        overflowY: "auto",
                        animation: "slideInRight 0.3s ease-out"
                    }}>
                        {/* Header with Back Arrow */}
                        <div style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "1rem",
                            padding: "1rem 1.5rem",
                            borderBottom: "1px solid rgba(255,255,255,0.1)",
                            background: "rgba(0,0,0,0.3)",
                            position: "sticky",
                            top: 0,
                            zIndex: 10
                        }}>
                            <button
                                onClick={() => { setShowProgressModal(false); stopWatching(); }}
                                style={{
                                    color: "white",
                                    background: "none",
                                    border: "none",
                                    cursor: "pointer",
                                    fontSize: "1.5rem",
                                    padding: "0.5rem",
                                    display: "flex",
                                    alignItems: "center"
                                }}
                            >
                                ←
                            </button>
                            <h2 style={{ fontSize: "1.25rem", fontWeight: 600, color: "white", margin: 0 }}>
                                Live Broadcast {liveProgress.cycle ? `(Cycle ${liveProgress.cycle})` : ""}
                            </h2>
                        </div>

                        <div style={{ padding: "1.5rem" }}>

                            {/* Stats */}
                            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "0.5rem", marginBottom: "1rem" }}>
                                <div style={{ textAlign: "center", background: "rgba(255,255,255,0.05)", padding: "0.5rem", borderRadius: "0.5rem" }}>
                                    <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: "white" }}>{liveProgress.sent}</div>
                                    <div style={{ fontSize: "0.7rem", color: "#4ade80" }}>Sent</div>
                                </div>
                                <div style={{ textAlign: "center", background: "rgba(255,255,255,0.05)", padding: "0.5rem", borderRadius: "0.5rem" }}>
                                    <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: "white" }}>{liveProgress.failed}</div>
                                    <div style={{ fontSize: "0.7rem", color: "#f87171" }}>Failed</div>
                                </div>
                                <div style={{ textAlign: "center", background: "rgba(255,255,255,0.05)", padding: "0.5rem", borderRadius: "0.5rem" }}>
                                    <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: "white" }}>{liveProgress.total}</div>
                                    <div style={{ fontSize: "0.7rem", color: "#9ca3af" }}>Total</div>
                                </div>
                                <div style={{ textAlign: "center", background: "rgba(255,255,255,0.05)", padding: "0.5rem", borderRadius: "0.5rem" }}>
                                    <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: "#22d3ee" }}>{liveProgress.progress_percent}%</div>
                                    <div style={{ fontSize: "0.7rem", color: "#9ca3af" }}>Done</div>
                                </div>
                                <div style={{ textAlign: "center", background: "rgba(168, 85, 247, 0.15)", padding: "0.5rem", borderRadius: "0.5rem", border: "1px solid rgba(168, 85, 247, 0.3)" }}>
                                    <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: "#a855f7" }}>{liveProgress.cycle || 1}</div>
                                    <div style={{ fontSize: "0.7rem", color: "#a855f7" }}>Cycle</div>
                                </div>
                            </div>

                            {/* Progress Bar */}
                            <div style={{ background: "rgba(255,255,255,0.1)", borderRadius: "0.5rem", height: "0.5rem", marginBottom: "1rem" }}>
                                <div style={{
                                    background: "linear-gradient(90deg, #22d3ee, #4ade80)",
                                    height: "100%",
                                    borderRadius: "0.5rem",
                                    width: `${liveProgress.progress_percent}%`,
                                    transition: "width 0.3s"
                                }} />
                            </div>

                            {/* Per-Account Status (Parallel Mode) */}
                            {liveProgress.accounts && Object.keys(liveProgress.accounts).length > 0 && (
                                <div style={{
                                    background: "rgba(255,255,255,0.03)",
                                    borderRadius: "0.75rem",
                                    padding: "0.75rem",
                                    marginBottom: "1rem",
                                    border: "1px solid rgba(255,255,255,0.05)"
                                }}>
                                    <div style={{
                                        fontSize: "0.75rem",
                                        fontWeight: 600,
                                        color: "#9ca3af",
                                        marginBottom: "0.5rem",
                                        display: "flex",
                                        alignItems: "center",
                                        gap: "0.5rem"
                                    }}>
                                        <span style={{
                                            background: "rgba(139, 92, 246, 0.2)",
                                            color: "#a78bfa",
                                            padding: "0.15rem 0.4rem",
                                            borderRadius: "0.25rem",
                                            fontSize: "0.65rem",
                                            fontWeight: 700
                                        }}>PARALLEL</span>
                                        Account Status
                                    </div>
                                    <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                                        {Object.entries(liveProgress.accounts).map(([id, acc]) => {
                                            const statusColor = acc.status.includes("running") ? "#4ade80"
                                                : acc.status.includes("flood") ? "#fb923c"
                                                    : acc.status.includes("limited") ? "#f87171"
                                                        : acc.status.includes("done") ? "#22d3ee"
                                                            : "#9ca3af";
                                            return (
                                                <div key={id} style={{
                                                    background: "rgba(0,0,0,0.3)",
                                                    borderRadius: "0.5rem",
                                                    padding: "0.5rem 0.75rem",
                                                    display: "flex",
                                                    alignItems: "center",
                                                    gap: "0.75rem",
                                                    fontSize: "0.75rem"
                                                }}>
                                                    {/* Status dot */}
                                                    <div style={{
                                                        width: "8px",
                                                        height: "8px",
                                                        borderRadius: "50%",
                                                        background: statusColor,
                                                        boxShadow: `0 0 6px ${statusColor}`
                                                    }} />

                                                    {/* Phone */}
                                                    <div style={{
                                                        fontFamily: "monospace",
                                                        color: "#d1d5db",
                                                        minWidth: "80px"
                                                    }}>
                                                        •••{acc.phone.slice(-4)}
                                                    </div>

                                                    {/* Status */}
                                                    <div style={{
                                                        color: statusColor,
                                                        fontWeight: 500,
                                                        minWidth: "100px",
                                                        fontSize: "0.7rem"
                                                    }}>
                                                        {acc.status}
                                                    </div>

                                                    {/* Stats */}
                                                    <div style={{
                                                        display: "flex",
                                                        gap: "0.75rem",
                                                        marginLeft: "auto",
                                                        fontSize: "0.7rem",
                                                        alignItems: "center"
                                                    }}>
                                                        <span style={{ color: "#4ade80", fontWeight: 500 }}>{acc.sent}{acc.total ? `/${acc.total}` : ''} sent</span>
                                                        <span style={{ color: "#f87171", fontWeight: 500 }}>{acc.failed} failed</span>
                                                        {acc.delay && <span style={{ color: "#6b7280" }}>{acc.delay}s</span>}

                                                        {/* Remove button */}
                                                        {acc.status !== "removed" && acc.status !== "done" && (
                                                            <button
                                                                onClick={() => handleRemoveAccountFromCampaign(id)}
                                                                style={{
                                                                    background: "rgba(239, 68, 68, 0.2)",
                                                                    border: "1px solid rgba(239, 68, 68, 0.3)",
                                                                    borderRadius: "0.25rem",
                                                                    color: "#f87171",
                                                                    padding: "0.15rem 0.4rem",
                                                                    cursor: "pointer",
                                                                    fontSize: "0.65rem",
                                                                    fontWeight: 600,
                                                                    marginLeft: "0.25rem"
                                                                }}
                                                                title="Remove from campaign"
                                                            >
                                                                remove
                                                            </button>
                                                        )}
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            )}

                            {/* Current Group */}
                            {liveProgress.current_group && (
                                <div style={{
                                    background: "rgba(34, 211, 238, 0.1)",
                                    border: "1px solid rgba(34, 211, 238, 0.3)",
                                    borderRadius: "0.5rem",
                                    padding: "0.75rem",
                                    marginBottom: "1rem"
                                }}>
                                    <div style={{ fontSize: "0.7rem", color: "#9ca3af", marginBottom: "0.25rem" }}>Sending to:</div>
                                    <div style={{ color: "#22d3ee", fontWeight: 500 }}>{liveProgress.current_group}</div>
                                </div>
                            )}

                            {/* Recent Logs */}
                            <div>
                                <div style={{ fontSize: "0.8rem", color: "#9ca3af", marginBottom: "0.5rem" }}>Recent Activity:</div>
                                <div style={{
                                    maxHeight: "200px",
                                    overflowY: "auto",
                                    background: "rgba(0,0,0,0.3)",
                                    borderRadius: "0.5rem",
                                    padding: "0.5rem"
                                }}>
                                    {liveProgress.recent_logs.slice().reverse().map((log, idx) => (
                                        <div key={idx} style={{
                                            display: "flex",
                                            gap: "0.5rem",
                                            fontSize: "0.75rem",
                                            padding: "0.25rem 0",
                                            borderBottom: idx < liveProgress.recent_logs.length - 1 ? "1px solid rgba(255,255,255,0.05)" : "none"
                                        }}>
                                            <span style={{ color: "#6b7280" }}>#{log.index}</span>
                                            <span style={{
                                                color: log.status === "sent" ? "#4ade80" : log.status === "flood_wait" ? "#facc15" : log.status === "skipped" ? "#fb923c" : "#f87171"
                                            }}>
                                                {log.status === "sent" ? "OK" : log.status === "flood_wait" ? "WAIT" : log.status === "skipped" ? "SKIP" : "X"}
                                            </span>
                                            {log.account && (
                                                <span style={{
                                                    fontFamily: "monospace",
                                                    color: "#a78bfa",
                                                    fontSize: "0.65rem",
                                                    background: "rgba(139, 92, 246, 0.15)",
                                                    padding: "0.1rem 0.3rem",
                                                    borderRadius: "0.2rem"
                                                }}>
                                                    {log.account.slice(-4)}
                                                </span>
                                            )}
                                            <span style={{ color: "white", flex: 1 }}>{log.group}</span>
                                            {log.error && <span style={{ color: "#f87171" }}>{log.error}</span>}
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* Status */}
                            <div style={{ textAlign: "center", marginTop: "1rem" }}>
                                <span className={`badge ${liveProgress.status === "running" ? "badge-success" : liveProgress.status === "completed" ? "badge-info" : "badge-warning"}`}>
                                    {liveProgress.status === "running" ? "Broadcasting..." : liveProgress.status === "batch_pause" ? "Batch Pause" : liveProgress.status}
                                </span>
                            </div>
                        </div>
                    </div>
                )}

                {/* Create Campaign Modal - Full Screen Mobile Style */}
                {showModal && (
                    <div style={{
                        position: "fixed",
                        inset: 0,
                        background: "#0a0f1a",
                        zIndex: 1000,
                        overflowY: "auto",
                        animation: "slideInRight 0.3s ease-out"
                    }}>
                        {/* Header with Back Arrow */}
                        <div style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "1rem",
                            padding: "1rem 1.5rem",
                            borderBottom: "1px solid rgba(255,255,255,0.1)",
                            background: "rgba(0,0,0,0.3)",
                            position: "sticky",
                            top: 0,
                            zIndex: 10
                        }}>
                            <button
                                onClick={() => setShowModal(false)}
                                style={{
                                    color: "white",
                                    background: "none",
                                    border: "none",
                                    cursor: "pointer",
                                    fontSize: "1.5rem",
                                    padding: "0.5rem",
                                    display: "flex",
                                    alignItems: "center"
                                }}
                            >
                                ←
                            </button>
                            <h2 style={{ fontSize: "1.25rem", fontWeight: 600, color: "white", margin: 0 }}>New Campaign</h2>
                        </div>

                        <div style={{ padding: "1.5rem" }}>

                            <form onSubmit={handleCreateCampaign} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                                    <div>
                                        <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>Client *</label>
                                        <select
                                            value={newCampaign.client_id}
                                            onChange={(e) => {
                                                const clientId = parseInt(e.target.value);
                                                setNewCampaign({ ...newCampaign, client_id: clientId, account_ids: [], template_id: 0 });
                                                fetchClientAccounts(clientId);
                                                fetchClientTemplates(clientId);
                                            }}
                                            className="input-field"
                                            required
                                        >
                                            <option value={0}>Select client</option>
                                            {clients.map((c) => (
                                                <option key={c.id} value={c.id}>{c.name}</option>
                                            ))}
                                        </select>
                                    </div>

                                    <div>
                                        <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>Campaign Name *</label>
                                        <input
                                            type="text"
                                            value={newCampaign.name}
                                            onChange={(e) =>
                                                setNewCampaign({ ...newCampaign, name: e.target.value })
                                            }
                                            className="input-field"
                                            placeholder="My Campaign"
                                            required
                                        />
                                    </div>
                                </div>

                                

                                {/* Account Selection Section */}
                                {newCampaign.client_id > 0 && (
                                    <div style={{
                                        background: "rgba(255,255,255,0.03)",
                                        borderRadius: "0.75rem",
                                        padding: "1rem",
                                        border: "1px solid rgba(255,255,255,0.05)"
                                    }}>
                                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                                            <label style={{ fontSize: "0.75rem", fontWeight: 600, color: "#9ca3af", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                                                Broadcasting Account
                                            </label>
                                            {clientAccounts.length === 0 && (
                                                <span style={{ fontSize: "0.7rem", color: "#f87171" }}>No accounts assigned</span>
                                            )}
                                        </div>

                                        {clientAccounts.length > 0 ? (
                                            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                                                {/* Select All / Clear All buttons */}
                                                <div style={{
                                                    display: "flex",
                                                    gap: "1rem",
                                                    marginBottom: "0.5rem",
                                                    paddingBottom: "0.5rem",
                                                    borderBottom: "1px solid rgba(255,255,255,0.1)"
                                                }}>
                                                    <button
                                                        type="button"
                                                        onClick={() => setNewCampaign({ ...newCampaign, account_ids: clientAccounts.map(a => a.id) })}
                                                        style={{ fontSize: "0.75rem", color: "#22d3ee", background: "none", border: "none", cursor: "pointer" }}
                                                    >
                                                        Select All ({clientAccounts.length})
                                                    </button>
                                                    <button
                                                        type="button"
                                                        onClick={() => setNewCampaign({ ...newCampaign, account_ids: [] })}
                                                        style={{ fontSize: "0.75rem", color: "#9ca3af", background: "none", border: "none", cursor: "pointer" }}
                                                    >
                                                        Clear All
                                                    </button>
                                                    {newCampaign.account_ids.length > 0 && (
                                                        <span style={{ fontSize: "0.75rem", color: "#4ade80", marginLeft: "auto" }}>
                                                            {newCampaign.account_ids.length} selected
                                                        </span>
                                                    )}
                                                </div>

                                                {/* Individual account checkboxes */}
                                                {clientAccounts.map((acc) => (
                                                    <label key={acc.id} style={{
                                                        display: "flex",
                                                        alignItems: "center",
                                                        justifyContent: "space-between",
                                                        padding: "0.75rem",
                                                        background: newCampaign.account_ids.includes(acc.id) ? "rgba(139, 92, 246, 0.15)" : "rgba(255,255,255,0.02)",
                                                        borderRadius: "0.5rem",
                                                        border: newCampaign.account_ids.includes(acc.id) ? "1px solid rgba(139, 92, 246, 0.3)" : "1px solid rgba(255,255,255,0.05)",
                                                        cursor: "pointer",
                                                        transition: "all 0.2s"
                                                    }}>
                                                        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                                                            <input
                                                                type="checkbox"
                                                                checked={newCampaign.account_ids.includes(acc.id)}
                                                                onChange={(e) => {
                                                                    if (e.target.checked) {
                                                                        setNewCampaign({ ...newCampaign, account_ids: [...newCampaign.account_ids, acc.id] });
                                                                    } else {
                                                                        setNewCampaign({ ...newCampaign, account_ids: newCampaign.account_ids.filter(id => id !== acc.id) });
                                                                    }
                                                                }}
                                                                style={{ accentColor: "#8b5cf6" }}
                                                            />
                                                            <div>
                                                                <span style={{ color: "white", fontWeight: 500 }}>
                                                                    {acc.display_name || acc.phone_number}
                                                                    {acc.is_premium && <span style={{ marginLeft: "0.5rem", fontSize: "0.65rem", color: "#a78bfa" }}>Premium</span>}
                                                                </span>
                                                                <p style={{ fontSize: "0.65rem", color: "#6b7280", marginTop: "0.1rem" }}>{acc.phone_number}</p>
                                                            </div>
                                                        </div>
                                                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                                            {acc.synced_groups !== undefined ? (
                                                                <span style={{ fontSize: "0.7rem", color: "#4ade80" }}>
                                                                    {acc.synced_groups} groups, {acc.synced_forums} forums
                                                                </span>
                                                            ) : (
                                                                <button
                                                                    type="button"
                                                                    onClick={(e) => { e.preventDefault(); syncAccountGroups(acc.id); }}
                                                                    disabled={syncingAccount === acc.id}
                                                                    style={{
                                                                        padding: "0.25rem 0.5rem",
                                                                        fontSize: "0.65rem",
                                                                        background: "rgba(34, 211, 238, 0.2)",
                                                                        border: "1px solid rgba(34, 211, 238, 0.3)",
                                                                        borderRadius: "0.25rem",
                                                                        color: "#22d3ee",
                                                                        cursor: syncingAccount === acc.id ? "wait" : "pointer"
                                                                    }}
                                                                >
                                                                    {syncingAccount === acc.id ? "..." : "Sync"}
                                                                </button>
                                                            )}
                                                        </div>
                                                    </label>
                                                ))}

                                                <p style={{ fontSize: "0.7rem", color: "#6b7280", marginTop: "0.25rem" }}>
                                                    Leave empty to use all assigned accounts
                                                </p>
                                            </div>
                                        ) : (
                                            <p style={{ fontSize: "0.8rem", color: "#6b7280", textAlign: "center", padding: "1rem" }}>
                                                Assign accounts to this client first
                                            </p>
                                        )}
                                    </div>
                                )}

                                {/* Send Mode Toggle */}
                                <div>
                                    <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>Mode</label>
                                    <div style={{ display: "flex", gap: "1rem" }}>
                                        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", color: "white" }}>
                                            <input
                                                type="radio"
                                                name="send_mode"
                                                value="send"
                                                checked={newCampaign.send_mode === "send"}
                                                onChange={() => setNewCampaign({ ...newCampaign, send_mode: "send" })}
                                            />
                                            Send Message
                                        </label>
                                        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", color: "white" }}>
                                            <input
                                                type="radio"
                                                name="send_mode"
                                                value="forward"
                                                checked={newCampaign.send_mode === "forward"}
                                                onChange={() => setNewCampaign({ ...newCampaign, send_mode: "forward" })}
                                            />
                                            Forward Message
                                        </label>
                                    </div>
                                </div>

                                {/* Message Content - Show based on mode */}
                                {newCampaign.send_mode === "send" ? (
                                    <div>
                                        <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>
                                            Message Template
                                        </label>

                                        {/* Help Box - How Templates Work */}
                                        <div style={{
                                            background: "linear-gradient(135deg, rgba(34, 211, 238, 0.1), rgba(139, 92, 246, 0.1))",
                                            border: "1px solid rgba(34, 211, 238, 0.2)",
                                            borderRadius: "0.5rem",
                                            padding: "0.75rem",
                                            marginBottom: "0.75rem",
                                            fontSize: "0.75rem"
                                        }}>
                                            <div style={{ color: "#22d3ee", fontWeight: 600, marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                                💡 How to use Premium Emojis & Formatting
                                            </div>
                                            <ol style={{ color: "#9ca3af", margin: 0, paddingLeft: "1.25rem", lineHeight: 1.6 }}>
                                                <li>Send your formatted message to <a href="https://t.me/EyeconBumpsAdsTemplateBot" target="_blank" rel="noopener noreferrer" style={{ color: "#22d3ee", fontWeight: 500, textDecoration: "none" }}>@EyeconBumpsAdsTemplateBot</a></li>
                                                <li>Enter your Client Token when asked</li>
                                                <li>Name your template and save it</li>
                                                <li>Select it here to broadcast with formatting preserved!</li>
                                            </ol>
                                            <p style={{ color: "#6b7280", marginTop: "0.5rem", marginBottom: 0, fontSize: "0.7rem" }}>
                                                ✨ Supports: Premium emojis, bold, italic, links, spoilers & more
                                            </p>
                                        </div>

                                        {/* Template Selector */}
                                        <select
                                            value={newCampaign.template_id}
                                            onChange={(e) => {
                                                const templateId = parseInt(e.target.value);
                                                const selectedTemplate = templates.find(t => t.id === templateId);
                                                setNewCampaign({
                                                    ...newCampaign,
                                                    template_id: templateId,
                                                    message_content: selectedTemplate ? selectedTemplate.text_content : newCampaign.message_content
                                                });
                                            }}
                                            className="input-field"
                                            style={{ marginBottom: "0.75rem" }}
                                        >
                                            <option value={0}>Manual input (type below)</option>
                                            {templates.map((t) => (
                                                <option key={t.id} value={t.id}>
                                                    {t.name} {t.has_media ? "(with media)" : ""}
                                                </option>
                                            ))}
                                        </select>

                                        {templates.length === 0 && newCampaign.client_id > 0 && (
                                            <p style={{ fontSize: "0.75rem", color: "#6b7280", marginBottom: "0.75rem", background: "rgba(255,255,255,0.03)", padding: "0.75rem", borderRadius: "0.5rem" }}>
                                                No saved templates. Send formatted messages (with premium emojis, bold, etc.) to @EyeconBumpsCollectorBot to save them!
                                            </p>
                                        )}

                                        {/* Preview or Manual Input */}
                                        {newCampaign.template_id > 0 ? (
                                            <div style={{
                                                background: "rgba(74, 222, 128, 0.1)",
                                                border: "1px solid rgba(74, 222, 128, 0.3)",
                                                borderRadius: "0.5rem",
                                                padding: "0.75rem"
                                            }}>
                                                <div style={{ fontSize: "0.7rem", color: "#4ade80", marginBottom: "0.5rem", fontWeight: 600 }}>
                                                    TEMPLATE SELECTED - Formatting preserved
                                                </div>
                                                <div style={{ fontSize: "0.85rem", color: "white", whiteSpace: "pre-wrap", maxHeight: "100px", overflow: "auto" }}>
                                                    {newCampaign.message_content.substring(0, 200)}
                                                    {newCampaign.message_content.length > 200 && "..."}
                                                </div>
                                            </div>
                                        ) : (
                                            <>
                                                <label style={{ display: "block", fontSize: "0.75rem", color: "#6b7280", marginBottom: "0.25rem" }}>Message Content</label>
                                                <textarea
                                                    value={newCampaign.message_content}
                                                    onChange={(e) =>
                                                        setNewCampaign({ ...newCampaign, message_content: e.target.value })
                                                    }
                                                    className="input-field"
                                                    rows={4}
                                                    placeholder="Your ad message..."
                                                />
                                            </>
                                        )}
                                    </div>
                                ) : (
                                    <div>
                                        <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>Message Link to Forward</label>
                                        <input
                                            type="text"
                                            value={newCampaign.forward_link}
                                            onChange={(e) =>
                                                setNewCampaign({ ...newCampaign, forward_link: e.target.value })
                                            }
                                            className="input-field"
                                            placeholder="https://t.me/c/1234567/123"
                                        />
                                        <p style={{ fontSize: "0.7rem", color: "#6b7280", marginTop: "0.25rem" }}>
                                            Right-click message → Copy Link → Paste here
                                        </p>
                                    </div>
                                )}

                                {/* Target Groups - Optional */}
                                <div>
                                    <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>
                                        Target Groups
                                    </label>
                                    <div style={{ display: "flex", gap: "1rem", marginBottom: "0.75rem" }}>
                                        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", color: "white", fontSize: "0.85rem" }}>
                                            <input
                                                type="radio"
                                                name="group_mode"
                                                checked={!newCampaign.is_custom_list}
                                                onChange={() => setNewCampaign({ ...newCampaign, is_custom_list: false })}
                                            />
                                            Auto-detect
                                        </label>
                                        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", color: "white", fontSize: "0.85rem" }}>
                                            <input
                                                type="radio"
                                                name="group_mode"
                                                checked={newCampaign.is_custom_list}
                                                onChange={() => setNewCampaign({ ...newCampaign, is_custom_list: true })}
                                            />
                                            Custom List
                                        </label>
                                    </div>

                                    {!newCampaign.is_custom_list ? (
                                        <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.5rem" }}>
                                            <select
                                                value={selectedGroupFile}
                                                onChange={(e) => setSelectedGroupFile(e.target.value)}
                                                className="input-field"
                                                style={{ flex: 1 }}
                                            >
                                                <option value="">All joined groups (auto-detect)</option>
                                                {groupFiles.map((f) => (
                                                    <option key={f.filename} value={f.filename}>
                                                        {f.filename} ({f.group_count} groups)
                                                    </option>
                                                ))}
                                            </select>
                                        </div>
                                    ) : (
                                        <textarea
                                            value={newCampaign.custom_links}
                                            onChange={(e) => setNewCampaign({ ...newCampaign, custom_links: e.target.value })}
                                            className="input-field"
                                            rows={4}
                                            placeholder="Paste group/folder links (one per line)..."
                                            style={{ marginBottom: "0.5rem" }}
                                        />
                                    )}
                                </div>

                                
                                <div>
                                    <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>Select Topic</label>
                                    <select
                                        value={newCampaign.target_topic}
                                        onChange={(e) => setNewCampaign({ ...newCampaign, target_topic: e.target.value })}
                                        className="input-field"
                                    >
                                        <option value="">None (All groups)</option>
                                        <option value="Instagram">Instagram</option>
                                        <option value="Telegram">Telegram</option>
                                        <option value="TikTok">TikTok</option>
                                        <option value="WhatsApp">WhatsApp</option>
                                        <option value="Snapchat">Snapchat</option>
                                        <option value="YouTube">YouTube</option>
                                        <option value="Discord">Discord</option>
                                        <option value="Twitter/X">Twitter/X</option>
                                        <option value="Others">Others</option>
                                    </select>
                                </div>

                                <div>
                                    <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>Delay (seconds)</label>
                                    <input
                                        type="number"
                                        value={newCampaign.delay_seconds}
                                        onChange={(e) =>
                                            setNewCampaign({ ...newCampaign, delay_seconds: parseInt(e.target.value) || 300 })
                                        }
                                        className="input-field"
                                        min="300" max="3600"
                                    />
                                </div>

                                <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.5rem" }}>
                                    <button type="button" onClick={() => setShowModal(false)} className="btn-secondary" style={{ flex: 1 }}>
                                        Cancel
                                    </button>
                                    <button type="submit" className="btn-primary" style={{ flex: 1 }}>
                                        Create Campaign
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div >
                )
                }
            </main >
        </>
    );
}
