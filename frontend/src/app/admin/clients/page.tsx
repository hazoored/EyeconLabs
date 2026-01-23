"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { api, getToken } from "@/lib/api";

interface Client {
    id: number;
    name: string;
    telegram_username: string | null;
    access_token: string;
    subscription_type: string;
    expires_at: string | null;
    is_active: number;
    notes: string | null;
    account_count: number;
    created_at: string;
}

export default function ClientsPage() {
    const router = useRouter();
    const [clients, setClients] = useState<Client[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [showModal, setShowModal] = useState(false);
    const [newClient, setNewClient] = useState({
        name: "",
        telegram_username: "",
        subscription_type: "basic",
        expires_days: 7,
        notes: "",
    });
    const [createdToken, setCreatedToken] = useState<string | null>(null);

    useEffect(() => {
        const token = getToken("admin");
        if (!token) {
            router.push("/admin/login");
            return;
        }
        fetchClients(token);
    }, [router]);

    const fetchClients = async (token: string) => {
        const response = await api<{ clients: Client[] }>("/admin/clients", { token });
        setLoading(false);

        if (!response.ok) {
            setError(response.error || "Failed to load clients");
            return;
        }

        setClients(response.data?.clients || []);
    };

    const handleCreateClient = async (e: React.FormEvent) => {
        e.preventDefault();
        const token = getToken("admin");
        if (!token) return;

        const response = await api<{ client: Client; access_token: string }>(
            "/admin/clients",
            {
                method: "POST",
                body: newClient,
                token,
            }
        );

        if (!response.ok) {
            setError(response.error || "Failed to create client");
            return;
        }

        setCreatedToken(response.data?.access_token || null);
        fetchClients(token);
        setNewClient({
            name: "",
            telegram_username: "",
            subscription_type: "basic",
            expires_days: 7,
            notes: "",
        });
    };

    const handleRegenerateToken = async (clientId: number) => {
        const token = getToken("admin");
        if (!token) return;

        const response = await api<{ new_token: string }>(
            `/admin/clients/${clientId}/regenerate-token`,
            { method: "POST", token }
        );

        if (response.ok) {
            alert(`New token: ${response.data?.new_token}`);
            fetchClients(token);
        }
    };

    const handleDeleteClient = async (clientId: number, clientName: string) => {
        if (!confirm(`Delete client "${clientName}"? This cannot be undone.`)) return;

        const token = getToken("admin");
        if (!token) return;

        await api(`/admin/clients/${clientId}`, { method: "DELETE", token });
        fetchClients(token);
    };

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
                {/* Header */}
                <div className="page-header">
                    <div>
                        <h1 className="page-title">Clients</h1>
                        <p className="page-subtitle">Manage your agency clients</p>
                    </div>
                    <button
                        onClick={() => {
                            setShowModal(true);
                            setCreatedToken(null);
                        }}
                        className="btn-primary"
                    >
                        + Add Client
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
                        <div className="stat-value">{clients.length}</div>
                        <div className="stat-label">Total Clients</div>
                    </div>
                    <div className="glass-card">
                        <div className="stat-value" style={{ color: "#4ade80" }}>{clients.filter(c => c.is_active).length}</div>
                        <div className="stat-label">Active</div>
                    </div>
                    <div className="glass-card">
                        <div className="stat-value">{clients.reduce((sum, c) => sum + c.account_count, 0)}</div>
                        <div className="stat-label">Total Accounts</div>
                    </div>
                </div>

                {/* Clients Table */}
                <div className="glass-card">
                    {clients.length > 0 ? (
                        <div className="responsive-table">
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Name</th>
                                        <th className="hide-mobile">Telegram</th>
                                        <th>Token</th>
                                        <th className="hide-mobile">Plan</th>
                                        <th className="hide-mobile">Accounts</th>
                                        <th>Status</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {clients.map((client) => (
                                        <tr key={client.id}>
                                            <td style={{ color: "white", fontWeight: 500 }}>{client.name}</td>
                                            <td className="hide-mobile" style={{ color: "#9ca3af" }}>
                                                {client.telegram_username
                                                    ? `@${client.telegram_username}`
                                                    : "-"}
                                            </td>
                                            <td>
                                                <code style={{ background: "rgba(255,255,255,0.1)", padding: "0.25rem 0.5rem", borderRadius: "0.25rem", color: "#22d3ee", fontFamily: "monospace" }}>
                                                    {client.access_token}
                                                </code>
                                            </td>
                                            <td className="hide-mobile capitalize">{client.subscription_type}</td>
                                            <td className="hide-mobile" style={{ textAlign: "center" }}>{client.account_count}</td>
                                            <td>
                                                <span className={`badge ${client.is_active ? "badge-success" : "badge-error"}`}>
                                                    {client.is_active ? "Active" : "Inactive"}
                                                </span>
                                            </td>
                                            <td>
                                                <div style={{ display: "flex", gap: "0.5rem" }}>
                                                    <button
                                                        onClick={() => handleRegenerateToken(client.id)}
                                                        style={{ color: "#22d3ee", background: "none", border: "none", cursor: "pointer" }}
                                                        title="Regenerate token"
                                                    >
                                                        🔄
                                                    </button>
                                                    <button
                                                        onClick={() => handleDeleteClient(client.id, client.name)}
                                                        style={{ color: "#f87171", background: "none", border: "none", cursor: "pointer" }}
                                                        title="Delete"
                                                    >
                                                        🗑️
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    ) : (
                        <p style={{ color: "#9ca3af", textAlign: "center", padding: "2rem" }}>
                            No clients yet. Click &quot;Add Client&quot; to create your first client.
                        </p>
                    )}
                </div>

                {/* Create Client Modal */}
                {showModal && (
                    <div className="modal-overlay">
                        <div className="glass-card modal-content">
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
                                <h2 style={{ fontSize: "1.25rem", fontWeight: 600, color: "white" }}>
                                    {createdToken ? "Client Created!" : "Add New Client"}
                                </h2>
                                <button
                                    onClick={() => setShowModal(false)}
                                    style={{ color: "#9ca3af", background: "none", border: "none", cursor: "pointer", fontSize: "1.25rem" }}
                                >
                                    ✕
                                </button>
                            </div>

                            {createdToken ? (
                                <div style={{ textAlign: "center" }}>
                                    <p style={{ color: "#9ca3af", marginBottom: "1rem" }}>
                                        Share this token with your client:
                                    </p>
                                    <code style={{ display: "block", background: "rgba(34,211,238,0.2)", color: "#22d3ee", fontSize: "1.875rem", fontFamily: "monospace", padding: "1rem 1.5rem", borderRadius: "0.5rem", marginBottom: "1rem" }}>
                                        {createdToken}
                                    </code>
                                    <p style={{ fontSize: "0.875rem", color: "#6b7280", marginBottom: "1.5rem" }}>
                                        The client can use this token to log in at the client portal.
                                    </p>
                                    <button
                                        onClick={() => setShowModal(false)}
                                        className="btn-primary"
                                    >
                                        Done
                                    </button>
                                </div>
                            ) : (
                                <form onSubmit={handleCreateClient} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                                    <div>
                                        <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>
                                            Client Name *
                                        </label>
                                        <input
                                            type="text"
                                            value={newClient.name}
                                            onChange={(e) =>
                                                setNewClient({ ...newClient, name: e.target.value })
                                            }
                                            className="input-field"
                                            placeholder="Enter client name"
                                            required
                                        />
                                    </div>

                                    <div>
                                        <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>
                                            Telegram Username
                                        </label>
                                        <input
                                            type="text"
                                            value={newClient.telegram_username}
                                            onChange={(e) =>
                                                setNewClient({
                                                    ...newClient,
                                                    telegram_username: e.target.value,
                                                })
                                            }
                                            className="input-field"
                                            placeholder="@username (optional)"
                                        />
                                    </div>

                                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                                        <div>
                                            <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>
                                                Plan
                                            </label>
                                            <select
                                                value={newClient.subscription_type}
                                                onChange={(e) =>
                                                    setNewClient({
                                                        ...newClient,
                                                        subscription_type: e.target.value,
                                                    })
                                                }
                                                className="input-field"
                                            >
                                                <option value="basic">Basic ($7/week, $17/month, $47/3mo)</option>
                                                <option value="gold">Gold ($18/week, $50/month, $120/3mo)</option>
                                                <option value="premium">Premium ($40/week, $100/month, $250/3mo)</option>
                                            </select>
                                        </div>

                                        <div>
                                            <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>
                                                Expires (days)
                                            </label>
                                            <input
                                                type="number"
                                                value={newClient.expires_days}
                                                onChange={(e) =>
                                                    setNewClient({
                                                        ...newClient,
                                                        expires_days: parseInt(e.target.value) || 30,
                                                    })
                                                }
                                                className="input-field"
                                                min="1"
                                            />
                                        </div>
                                    </div>

                                    <div>
                                        <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>
                                            Notes
                                        </label>
                                        <textarea
                                            value={newClient.notes}
                                            onChange={(e) =>
                                                setNewClient({ ...newClient, notes: e.target.value })
                                            }
                                            className="input-field"
                                            rows={3}
                                            placeholder="Optional notes about this client"
                                        />
                                    </div>

                                    <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.5rem" }}>
                                        <button
                                            type="button"
                                            onClick={() => setShowModal(false)}
                                            className="btn-secondary"
                                            style={{ flex: 1 }}
                                        >
                                            Cancel
                                        </button>
                                        <button type="submit" className="btn-primary" style={{ flex: 1 }}>
                                            Create Client
                                        </button>
                                    </div>
                                </form>
                            )}
                        </div>
                    </div>
                )}
            </main>
        </>
    );
}
