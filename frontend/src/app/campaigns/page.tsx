"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { api, getToken } from "@/lib/api";

interface Campaign {
    id: number;
    name: string;
    status: string;
    target_groups: string[];
    message_type: string;
    message_content: string | null;
    delay_seconds: number;
    created_at: string;
}

interface Account {
    id: number;
    phone_number: string;
    display_name: string | null;
    is_premium: boolean;
}

interface MessageTemplate {
    id: number;
    name: string;
    text_content: string;
    has_media: number;
}

export default function ClientCampaignsPage() {
    const router = useRouter();
    const [campaigns, setCampaigns] = useState<Campaign[]>([]);
    const [accounts, setAccounts] = useState<Account[]>([]);
    const [templates, setTemplates] = useState<MessageTemplate[]>([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [newCampaign, setNewCampaign] = useState({
        name: "",
        message_content: "",
        delay_seconds: 30,
        template_id: 0,
        account_ids: [] as number[],
        target_topic: ""
    });

    useEffect(() => {
        const token = getToken("client");
        if (!token) {
            router.push("/login");
            return;
        }
        fetchData(token);
    }, [router]);

    const fetchData = async (token: string) => {
        const [campaignsRes, accountsRes, templatesRes] = await Promise.all([
            api<{ campaigns: Campaign[] }>("/client/campaigns", { token }),
            api<{ accounts: Account[] }>("/client/accounts", { token }),
            api<{ templates: MessageTemplate[] }>("/client/templates", { token })
        ]);

        setLoading(false);
        if (campaignsRes.ok) setCampaigns(campaignsRes.data?.campaigns || []);
        if (accountsRes.ok) setAccounts(accountsRes.data?.accounts || []);
        if (templatesRes.ok) setTemplates(templatesRes.data?.templates || []);
    };

    const handleCreateCampaign = async (e: React.FormEvent) => {
        e.preventDefault();
        const token = getToken("client");
        if (!token) return;

        const response = await api<{ campaign: Campaign }>("/client/campaigns", {
            method: "POST",
            body: {
                name: newCampaign.name,
                message_content: newCampaign.message_content,
                delay_seconds: newCampaign.delay_seconds,
                template_id: newCampaign.template_id || null,
                account_ids: newCampaign.account_ids.length > 0 ? newCampaign.account_ids : null,
                target_topic: newCampaign.target_topic || null
            },
            token
        });

        if (response.ok) {
            setShowModal(false);
            setNewCampaign({ name: "", message_content: "", delay_seconds: 300, template_id: 0, account_ids: [], target_topic: "" });
            fetchData(token);
        } else {
            alert(response.error || "Failed to create campaign");
        }
    };

    const handleCampaignAction = async (campaignId: number, action: "start" | "stop") => {
        const token = getToken("client");
        if (!token) return;

        const res = await api<{ message: string }>(`/client/campaigns/${campaignId}/${action}`, { method: "POST", token });
        if (res.ok) {
            fetchData(token);
        } else {
            alert(res.error || `Failed to ${action} campaign`);
        }
    };

    const getStatusBadge = (status: string) => {
        switch (status) {
            case "running": return "badge-success";
            case "paused": case "stopped": return "badge-warning";
            case "completed": return "badge-info";
            default: return "badge-info";
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div style={{ color: "#22d3ee", fontSize: "1.25rem" }}>Loading...</div>
            </div>
        );
    }

    return (
        <>
            <Sidebar userType="client" />

            <main className="main-content">
                <div className="page-header">
                    <div>
                        <h1 className="page-title">My Campaigns</h1>
                        <p className="page-subtitle">Create and manage your broadcast campaigns</p>
                    </div>
                    <button className="btn-primary" onClick={() => setShowModal(true)}>
                        + New Campaign
                    </button>
                </div>

                <div className="glass-card">
                    {campaigns.length > 0 ? (
                        <div className="responsive-table">
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Name</th>
                                        <th>Type</th>
                                        <th>Delay</th>
                                        <th>Status</th>
                                        <th>Created</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {campaigns.map((campaign) => (
                                        <tr key={campaign.id}>
                                            <td style={{ color: "white", fontWeight: 500 }}>{campaign.name}</td>
                                            <td style={{ textTransform: "capitalize" }}>{campaign.message_type}</td>
                                            <td>{campaign.delay_seconds}s</td>
                                            <td>
                                                <span className={`badge ${getStatusBadge(campaign.status)}`}>
                                                    {campaign.status}
                                                </span>
                                            </td>
                                            <td style={{ color: "#9ca3af" }}>
                                                {new Date(campaign.created_at).toLocaleDateString()}
                                            </td>
                                            <td>
                                                <div style={{ display: "flex", gap: "0.5rem" }}>
                                                    {campaign.status === "running" ? (
                                                        <button
                                                            onClick={() => handleCampaignAction(campaign.id, "stop")}
                                                            style={{
                                                                padding: "0.35rem 0.75rem",
                                                                fontSize: "0.75rem",
                                                                background: "rgba(239, 68, 68, 0.2)",
                                                                border: "1px solid rgba(239, 68, 68, 0.3)",
                                                                borderRadius: "0.25rem",
                                                                color: "#ef4444",
                                                                cursor: "pointer"
                                                            }}
                                                        >
                                                            Stop
                                                        </button>
                                                    ) : (
                                                        <button
                                                            onClick={() => handleCampaignAction(campaign.id, "start")}
                                                            style={{
                                                                padding: "0.35rem 0.75rem",
                                                                fontSize: "0.75rem",
                                                                background: "rgba(74, 222, 128, 0.2)",
                                                                border: "1px solid rgba(74, 222, 128, 0.3)",
                                                                borderRadius: "0.25rem",
                                                                color: "#4ade80",
                                                                cursor: "pointer"
                                                            }}
                                                        >
                                                            Start
                                                        </button>
                                                    )}
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    ) : (
                        <div style={{ textAlign: "center", padding: "3rem" }}>
                            <p style={{ color: "#9ca3af", marginBottom: "1rem" }}>
                                No campaigns yet. Create your first campaign!
                            </p>
                            <button className="btn-primary" onClick={() => setShowModal(true)}>
                                + Create Campaign
                            </button>
                        </div>
                    )}
                </div>
            </main>

            {/* Create Campaign Modal */}
            {showModal && (
                <div style={{
                    position: "fixed",
                    inset: 0,
                    background: "#0a0f1a",
                    zIndex: 1000,
                    overflowY: "auto",
                    animation: "slideInRight 0.3s ease-out"
                }}>
                    {/* Header */}
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

                    <div style={{ padding: "1.5rem", paddingBottom: "6rem" }}>
                        <form onSubmit={handleCreateCampaign} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                            {/* Campaign Name */}
                            <div>
                                <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>Campaign Name *</label>
                                <input
                                    type="text"
                                    value={newCampaign.name}
                                    onChange={(e) => setNewCampaign({ ...newCampaign, name: e.target.value })}
                                    className="input-field"
                                    required
                                    placeholder="My Campaign"
                                />
                            </div>

                            {/* Account Selection - Multi-select checkboxes */}
                            {accounts.length > 0 && (
                                <div>
                                    <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>
                                        Select Accounts {newCampaign.account_ids.length > 0 && `(${newCampaign.account_ids.length} selected)`}
                                    </label>
                                    <div style={{
                                        background: "rgba(255,255,255,0.05)",
                                        border: "1px solid rgba(255,255,255,0.1)",
                                        borderRadius: "0.5rem",
                                        padding: "0.75rem",
                                        maxHeight: "200px",
                                        overflowY: "auto"
                                    }}>
                                        {/* Select All / None */}
                                        <div style={{
                                            display: "flex",
                                            gap: "1rem",
                                            marginBottom: "0.75rem",
                                            paddingBottom: "0.5rem",
                                            borderBottom: "1px solid rgba(255,255,255,0.1)"
                                        }}>
                                            <button
                                                type="button"
                                                onClick={() => setNewCampaign({ ...newCampaign, account_ids: accounts.map(a => a.id) })}
                                                style={{ fontSize: "0.75rem", color: "#22d3ee", background: "none", border: "none", cursor: "pointer" }}
                                            >
                                                Select All
                                            </button>
                                            <button
                                                type="button"
                                                onClick={() => setNewCampaign({ ...newCampaign, account_ids: [] })}
                                                style={{ fontSize: "0.75rem", color: "#9ca3af", background: "none", border: "none", cursor: "pointer" }}
                                            >
                                                Clear All
                                            </button>
                                        </div>
                                        {accounts.map((acc) => (
                                            <label
                                                key={acc.id}
                                                style={{
                                                    display: "flex",
                                                    alignItems: "center",
                                                    gap: "0.5rem",
                                                    padding: "0.5rem",
                                                    cursor: "pointer",
                                                    borderRadius: "0.25rem",
                                                    background: newCampaign.account_ids.includes(acc.id) ? "rgba(34, 211, 238, 0.1)" : "transparent"
                                                }}
                                            >
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
                                                    style={{ accentColor: "#22d3ee" }}
                                                />
                                                <span style={{ color: "white", fontSize: "0.875rem" }}>
                                                    {acc.display_name || acc.phone_number} {acc.is_premium ? "⭐" : ""}
                                                </span>
                                            </label>
                                        ))}
                                    </div>
                                    <p style={{ fontSize: "0.7rem", color: "#6b7280", marginTop: "0.5rem" }}>
                                        Leave empty to use all accounts
                                    </p>
                                </div>
                            )}

                            
                            {/* Target Topic Selection */}
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

                            {/* Template Selection */}
                            <div>
                                <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>Message Template</label>

                                {/* Help Box */}
                                <div style={{
                                    background: "linear-gradient(135deg, rgba(34, 211, 238, 0.1), rgba(139, 92, 246, 0.1))",
                                    border: "1px solid rgba(34, 211, 238, 0.2)",
                                    borderRadius: "0.5rem",
                                    padding: "0.75rem",
                                    marginBottom: "0.75rem",
                                    fontSize: "0.75rem"
                                }}>
                                    <div style={{ color: "#22d3ee", fontWeight: 600, marginBottom: "0.5rem" }}>
                                        💡 Use Premium Emojis & Formatting
                                    </div>
                                    <p style={{ color: "#9ca3af", margin: 0 }}>
                                        Send your formatted message to <a href="https://t.me/EyeconBumpsAdsTemplateBot" target="_blank" rel="noopener noreferrer" style={{ color: "#22d3ee" }}>@EyeconBumpsAdsTemplateBot</a> with your Client Token to save it as a template!
                                    </p>
                                </div>

                                <select
                                    value={newCampaign.template_id}
                                    onChange={(e) => {
                                        const templateId = parseInt(e.target.value);
                                        const template = templates.find(t => t.id === templateId);
                                        setNewCampaign({
                                            ...newCampaign,
                                            template_id: templateId,
                                            message_content: template ? template.text_content : newCampaign.message_content
                                        });
                                    }}
                                    className="input-field"
                                >
                                    <option value={0}>Manual input (type below)</option>
                                    {templates.map((t) => (
                                        <option key={t.id} value={t.id}>
                                            {t.name} {t.has_media ? "(with media)" : ""}
                                        </option>
                                    ))}
                                </select>
                            </div>

                            {/* Message Content */}
                            {newCampaign.template_id === 0 && (
                                <div>
                                    <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>Message Content</label>
                                    <textarea
                                        value={newCampaign.message_content}
                                        onChange={(e) => setNewCampaign({ ...newCampaign, message_content: e.target.value })}
                                        className="input-field"
                                        rows={4}
                                        placeholder="Your ad message..."
                                    />
                                </div>
                            )}

                            {/* Template Preview */}
                            {newCampaign.template_id > 0 && (
                                <div style={{
                                    background: "rgba(74, 222, 128, 0.1)",
                                    border: "1px solid rgba(74, 222, 128, 0.3)",
                                    borderRadius: "0.5rem",
                                    padding: "0.75rem"
                                }}>
                                    <div style={{ fontSize: "0.7rem", color: "#4ade80", marginBottom: "0.5rem", fontWeight: 600 }}>
                                        TEMPLATE SELECTED - Formatting preserved
                                    </div>
                                    <div style={{ fontSize: "0.85rem", color: "white", whiteSpace: "pre-wrap" }}>
                                        {newCampaign.message_content.substring(0, 200)}
                                        {newCampaign.message_content.length > 200 && "..."}
                                    </div>
                                </div>
                            )}

                            {/* Delay */}
                            <div>
                                <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>Delay (seconds)</label>
                                <input
                                    type="number"
                                    value={newCampaign.delay_seconds}
                                    onChange={(e) => setNewCampaign({ ...newCampaign, delay_seconds: parseInt(e.target.value) || 300 })}
                                    className="input-field"
                                    min={300} max={3600}
                                />
                            </div>

                            {/* Buttons */}
                            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginTop: "1rem" }}>
                                <button
                                    type="button"
                                    onClick={() => setShowModal(false)}
                                    style={{
                                        padding: "0.75rem",
                                        background: "rgba(255,255,255,0.1)",
                                        border: "1px solid rgba(255,255,255,0.2)",
                                        borderRadius: "0.5rem",
                                        color: "white",
                                        cursor: "pointer"
                                    }}
                                >
                                    Cancel
                                </button>
                                <button type="submit" className="btn-primary">
                                    Create Campaign
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </>
    );
}
