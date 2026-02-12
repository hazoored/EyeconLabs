"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { api, getToken } from "@/lib/api";

interface LogBot {
    id: number;
    client_id: number;
    client_name: string;
    bot_token: string;
    target_id: string;
    is_active: boolean;
}

interface Client {
    id: number;
    name: string;
}

export default function AdminLogsPage() {
    const router = useRouter();
    const [bots, setBots] = useState<LogBot[]>([]);
    const [clients, setClients] = useState<Client[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    // Modal state
    const [showModal, setShowModal] = useState(false);
    const [form, setForm] = useState({
        client_id: "",
        bot_token: "",
        target_id: "",
        username: "",
        is_active: true
    });
    const [saving, setSaving] = useState(false);
    const [resolving, setResolving] = useState(false);

    useEffect(() => {
        const token = getToken("admin");
        if (!token) {
            router.push("/admin/login");
            return;
        }
        fetchData(token);
    }, [router]);

    const fetchData = async (token: string) => {
        setLoading(true);
        const [botsRes, clientsRes] = await Promise.all([
            api<{ bots: LogBot[] }>("/admin/log-bots", { token }),
            api<{ clients: Client[] }>("/admin/clients", { token })
        ]);

        if (botsRes.ok && botsRes.data) setBots(botsRes.data.bots);
        if (clientsRes.ok && clientsRes.data) setClients(clientsRes.data.clients);

        if (!botsRes.ok) setError(botsRes.error || "Failed to load log bots");
        setLoading(false);
    };

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        const token = getToken("admin");
        if (!token) return;

        const response = await api("/admin/log-bots", {
            method: "POST",
            token,
            body: {
                client_id: parseInt(form.client_id),
                bot_token: form.bot_token,
                target_id: form.target_id,
                is_active: form.is_active
            }
        });

        if (response.ok) {
            setShowModal(false);
            resetForm();
            fetchData(token);
        } else {
            alert(response.error || "Failed to save log bot");
        }
        setSaving(false);
    };

    const handleResolve = async () => {
        if (!form.username) {
            alert("Please enter a username to resolve");
            return;
        }
        setResolving(true);
        const token = getToken("admin");
        if (!token) return;

        const response = await api<{ telegram_id: number; name: string }>("/admin/resolve-id", {
            method: "POST",
            token,
            body: { username: form.username }
        });

        if (response.ok && response.data) {
            setForm({ ...form, target_id: response.data.telegram_id.toString() });
            alert(`Resolved ${form.username} to ID: ${response.data.telegram_id} (${response.data.name})`);
        } else {
            alert(response.error || "Failed to resolve username. Make sure you have active accounts in the pool.");
        }
        setResolving(false);
    };

    const handleDelete = async (clientId: number) => {
        if (!confirm("Remove this log bot configuration?")) return;
        const token = getToken("admin");
        if (!token) return;

        const response = await api(`/admin/log-bots/${clientId}`, {
            method: "DELETE",
            token
        });

        if (response.ok) {
            fetchData(token);
        } else {
            alert(response.error || "Failed to delete");
        }
    };

    const resetForm = () => {
        setForm({
            client_id: "",
            bot_token: "",
            target_id: "",
            username: "",
            is_active: true
        });
    };

    const openEdit = (bot: LogBot) => {
        setForm({
            client_id: bot.client_id.toString(),
            bot_token: bot.bot_token,
            target_id: bot.target_id,
            username: "",
            is_active: bot.is_active
        });
        setShowModal(true);
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
                <div className="page-header">
                    <div>
                        <h1 className="page-title">Log Bots</h1>
                        <p className="page-subtitle">Configure real-time Telegram logs for clients</p>
                    </div>
                    <button className="btn-primary" onClick={() => { resetForm(); setShowModal(true); }}>
                        + Setup Bot
                    </button>
                </div>

                {error && (
                    <div style={{ background: "rgba(239,68,68,0.1)", color: "#f87171", padding: "0.75rem 1rem", borderRadius: "0.5rem", marginBottom: "1.5rem" }}>
                        {error}
                    </div>
                )}

                <div className="glass-card">
                    {bots.length > 0 ? (
                        <div className="responsive-table">
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Client</th>
                                        <th>Target ID</th>
                                        <th>Status</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {bots.map((bot) => (
                                        <tr key={bot.id}>
                                            <td style={{ color: "white", fontWeight: 500 }}>{bot.client_name}</td>
                                            <td><code>{bot.target_id}</code></td>
                                            <td>
                                                <span style={{
                                                    padding: "0.25rem 0.5rem",
                                                    borderRadius: "9999px",
                                                    fontSize: "0.7rem",
                                                    background: bot.is_active ? "rgba(16, 185, 129, 0.1)" : "rgba(239, 68, 68, 0.1)",
                                                    color: bot.is_active ? "#10b981" : "#f87171"
                                                }}>
                                                    {bot.is_active ? "Active" : "Paused"}
                                                </span>
                                            </td>
                                            <td>
                                                <div style={{ display: "flex", gap: "0.5rem" }}>
                                                    <button onClick={() => openEdit(bot)} className="btn-secondary" style={{ padding: "0.25rem 0.5rem", fontSize: "0.75rem" }}>
                                                        Edit
                                                    </button>
                                                    <button onClick={() => handleDelete(bot.client_id)} className="btn-danger" style={{ padding: "0.25rem 0.5rem", fontSize: "0.75rem", background: "rgba(239,68,68,0.1)", border: "none" }}>
                                                        Delete
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
                            No log bots configured yet.
                        </p>
                    )}
                </div>
            </main>

            {showModal && (
                <div className="modal-overlay" onClick={() => setShowModal(false)}>
                    <div className="glass-card modal-content" style={{ maxWidth: "500px" }} onClick={(e) => e.stopPropagation()}>
                        <h2 style={{ fontSize: "1.25rem", fontWeight: 700, color: "white", marginBottom: "1.5rem" }}>
                            {form.client_id ? "Update Log Bot" : "Setup Log Bot"}
                        </h2>
                        <form onSubmit={handleSave}>
                            <div style={{ marginBottom: "1rem" }}>
                                <label className="input-label">Select Client *</label>
                                <select
                                    className="input-field"
                                    value={form.client_id}
                                    onChange={(e) => setForm({ ...form, client_id: e.target.value })}
                                    required
                                    disabled={!!form.client_id && bots.some(b => b.client_id === parseInt(form.client_id))}
                                >
                                    <option value="">-- Choose Client --</option>
                                    {clients.map(c => (
                                        <option key={c.id} value={c.id}>{c.name}</option>
                                    ))}
                                </select>
                            </div>

                            <div style={{ marginBottom: "1rem" }}>
                                <label className="input-label">Bot Token (from @BotFather) *</label>
                                <input
                                    type="text"
                                    className="input-field"
                                    value={form.bot_token}
                                    onChange={(e) => setForm({ ...form, bot_token: e.target.value })}
                                    placeholder="123456789:ABCDefgh..."
                                    required
                                />
                            </div>

                            <div style={{ marginBottom: "1rem" }}>
                                <label className="input-label">Resolve Username to ID</label>
                                <div style={{ display: "flex", gap: "0.5rem" }}>
                                    <input
                                        type="text"
                                        className="input-field"
                                        value={form.username}
                                        onChange={(e) => setForm({ ...form, username: e.target.value })}
                                        placeholder="@username"
                                    />
                                    <button
                                        type="button"
                                        className="btn-secondary"
                                        onClick={handleResolve}
                                        disabled={resolving}
                                        style={{ whiteSpace: "nowrap" }}
                                    >
                                        {resolving ? "..." : "Resolve"}
                                    </button>
                                </div>
                            </div>

                            <div style={{ marginBottom: "1rem" }}>
                                <label className="input-label">Target Telegram ID *</label>
                                <input
                                    type="text"
                                    className="input-field"
                                    value={form.target_id}
                                    onChange={(e) => setForm({ ...form, target_id: e.target.value })}
                                    placeholder="e.g. 123456789"
                                    required
                                />
                            </div>

                            <div style={{ marginBottom: "1.5rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                <input
                                    type="checkbox"
                                    id="is_active"
                                    checked={form.is_active}
                                    onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                                />
                                <label htmlFor="is_active" style={{ color: "white", cursor: "pointer" }}>Enable real-time logging</label>
                            </div>

                            <div style={{ display: "flex", gap: "0.75rem" }}>
                                <button type="button" className="btn-secondary" onClick={() => setShowModal(false)} style={{ flex: 1 }}>
                                    Cancel
                                </button>
                                <button type="submit" className="btn-primary" disabled={saving} style={{ flex: 1 }}>
                                    {saving ? "Saving..." : "Save Config"}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            <style jsx>{`
                .input-label {
                    display: block;
                    color: #9ca3af;
                    fontSize: 0.875rem;
                    marginBottom: 0.5rem;
                }
            `}</style>
        </>
    );
}
