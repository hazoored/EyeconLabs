"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { api, getToken } from "@/lib/api";

interface Account {
    id: number;
    phone_number: string;
    display_name: string | null;
    is_premium: number;
    is_active: number;
    created_at: string;
}

type AddStep = "input" | "code" | "2fa" | "adding";

export default function ClientAccountsPage() {
    const router = useRouter();
    const [accounts, setAccounts] = useState<Account[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [showAddModal, setShowAddModal] = useState(false);

    // Add Account State
    const [addStep, setAddStep] = useState<AddStep>("input");
    const [phone, setPhone] = useState("");
    const [code, setCode] = useState("");
    const [password, setPassword] = useState("");
    const [displayName, setDisplayName] = useState("");
    const [sessionLoading, setSessionLoading] = useState(false);
    const [clientId, setClientId] = useState<number | null>(null);

    useEffect(() => {
        const token = getToken("client");
        if (!token) {
            router.push("/login");
            return;
        }
        fetchClientInfo(token);
        fetchAccounts(token);
    }, [router]);

    const fetchClientInfo = async (token: string) => {
        const response = await api<{ client: { id: number } }>("/client/dashboard", { token });
        if (response.ok && response.data?.client) {
            setClientId(response.data.client.id);
        }
    };

    const fetchAccounts = async (token: string) => {
        const response = await api<{ accounts: Account[] }>("/client/accounts", { token });
        setLoading(false);
        if (response.ok) {
            setAccounts(response.data?.accounts || []);
        }
    };

    // === ADD ACCOUNT FLOW ===
    const handleSendCode = async () => {
        setError("");
        setSessionLoading(true);

        const response = await api<{ success: boolean; message: string }>("/session/send-code", {
            method: "POST",
            body: { phone_number: phone },
        });

        setSessionLoading(false);

        if (response.ok && response.data?.success) {
            setAddStep("code");
        } else {
            setError(response.data?.message || response.error || "Failed to send code");
        }
    };

    const handleVerifyCode = async () => {
        setError("");
        setSessionLoading(true);

        const response = await api<{
            success: boolean;
            message: string;
            session_string?: string;
            requires_2fa?: boolean;
        }>("/session/verify-code", {
            method: "POST",
            body: { phone_number: phone, code, password: password || undefined },
        });

        setSessionLoading(false);

        if (response.ok && response.data?.success && response.data.session_string) {
            setAddStep("adding");
            await addAccountWithSession(response.data.session_string);
        } else if (response.data?.requires_2fa) {
            setAddStep("2fa");
        } else {
            setError(response.data?.message || response.error || "Verification failed");
        }
    };

    const addAccountWithSession = async (sessionString: string) => {
        const token = getToken("client");
        if (!token || !clientId) return;

        // Check account info first to get premium status
        const checkRes = await api<{
            success: boolean;
            is_premium: boolean;
            first_name: string;
        }>("/session/check-account", {
            method: "POST",
            body: { session_string: sessionString },
        });

        const isPremium = checkRes.data?.is_premium || false;
        const name = displayName || checkRes.data?.first_name || "";

        // Add account for this client
        const response = await api("/client/accounts", {
            method: "POST",
            body: {
                phone_number: phone,
                session_string: sessionString,
                display_name: name,
                is_premium: isPremium,
            },
            token,
        });

        if (response.ok) {
            closeAddModal();
            fetchAccounts(token);
        } else {
            setError(response.error || "Failed to add account");
            setAddStep("input");
        }
    };

    const closeAddModal = () => {
        setShowAddModal(false);
        setAddStep("input");
        setPhone("");
        setCode("");
        setPassword("");
        setDisplayName("");
        setError("");
    };

    const handleDelete = async (accountId: number) => {
        if (!confirm("Remove this account?")) return;
        const token = getToken("client");
        if (!token) return;

        await api(`/client/accounts/${accountId}`, { method: "DELETE", token });
        fetchAccounts(token);
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
            <Sidebar userType="client" />

            <main className="main-content">
                <div className="page-header">
                    <div>
                        <h1 className="page-title">My Accounts</h1>
                        <p className="page-subtitle">Manage your Telegram accounts</p>
                    </div>
                    <button onClick={() => setShowAddModal(true)} className="btn-primary">
                        + Add Account
                    </button>
                </div>

                {/* Stats */}
                <div className="stats-grid">
                    <div className="glass-card">
                        <div className="stat-value">{accounts.length}</div>
                        <div className="stat-label">Total Accounts</div>
                    </div>
                    <div className="glass-card">
                        <div className="stat-value" style={{ color: "#a855f7" }}>
                            {accounts.filter((a) => a.is_premium).length}
                        </div>
                        <div className="stat-label">Premium</div>
                    </div>
                    <div className="glass-card">
                        <div className="stat-value" style={{ color: "#4ade80" }}>
                            {accounts.filter((a) => a.is_active).length}
                        </div>
                        <div className="stat-label">Active</div>
                    </div>
                </div>

                {/* Accounts List */}
                <div className="glass-card">
                    <h2 style={{ fontSize: "1.125rem", fontWeight: 600, color: "white", marginBottom: "1rem" }}>
                        Your Accounts
                    </h2>
                    {accounts.length > 0 ? (
                        <div className="responsive-table">
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Phone</th>
                                        <th>Name</th>
                                        <th>Type</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {accounts.map((acc) => (
                                        <tr key={acc.id}>
                                            <td style={{ color: "white", fontFamily: "monospace" }}>{acc.phone_number}</td>
                                            <td style={{ color: "#9ca3af" }}>{acc.display_name || "-"}</td>
                                            <td>
                                                <span className={`badge ${acc.is_premium ? "badge-info" : ""}`} style={!acc.is_premium ? { background: "rgba(156,163,175,0.2)", color: "#9ca3af" } : {}}>
                                                    {acc.is_premium ? "Premium" : "Normal"}
                                                </span>
                                            </td>
                                            <td>
                                                <button onClick={() => handleDelete(acc.id)} style={{ color: "#f87171", background: "none", border: "none", cursor: "pointer" }}>
                                                    Remove
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    ) : (
                        <div style={{ textAlign: "center", padding: "2rem", color: "#9ca3af" }}>
                            <p>No accounts yet. Add your first Telegram account to get started.</p>
                        </div>
                    )}
                </div>

                {/* ADD ACCOUNT MODAL */}
                {showAddModal && (
                    <div className="modal-overlay">
                        <div className="glass-card modal-content">
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
                                <h2 style={{ fontSize: "1.25rem", fontWeight: 600, color: "white" }}>
                                    {addStep === "input" && "Add Account"}
                                    {addStep === "code" && "Enter Code"}
                                    {addStep === "2fa" && "2FA Password"}
                                    {addStep === "adding" && "Adding..."}
                                </h2>
                                <button onClick={closeAddModal} style={{ color: "#9ca3af", background: "none", border: "none", cursor: "pointer", fontSize: "1.25rem" }}>×</button>
                            </div>

                            {error && (
                                <div style={{ color: "#f87171", background: "rgba(239,68,68,0.1)", padding: "0.75rem", borderRadius: "0.5rem", marginBottom: "1rem", fontSize: "0.875rem" }}>
                                    {error}
                                </div>
                            )}

                            {addStep === "input" && (
                                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                                    <div>
                                        <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>
                                            Phone Number (with country code)
                                        </label>
                                        <input
                                            type="text"
                                            value={phone}
                                            onChange={(e) => setPhone(e.target.value)}
                                            className="input-field"
                                            placeholder="+91 12345 67890"
                                        />
                                    </div>
                                    <div>
                                        <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>
                                            Display Name (optional)
                                        </label>
                                        <input
                                            type="text"
                                            value={displayName}
                                            onChange={(e) => setDisplayName(e.target.value)}
                                            className="input-field"
                                            placeholder="My Account"
                                        />
                                    </div>
                                    <button onClick={handleSendCode} disabled={sessionLoading || !phone} className="btn-primary">
                                        {sessionLoading ? "Sending..." : "Send Code"}
                                    </button>
                                </div>
                            )}

                            {addStep === "code" && (
                                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                                    <p style={{ color: "#9ca3af", fontSize: "0.875rem" }}>Check Telegram for the code</p>
                                    <input
                                        type="text"
                                        value={code}
                                        onChange={(e) => setCode(e.target.value)}
                                        className="input-field"
                                        placeholder="12345"
                                        style={{ textAlign: "center", fontSize: "1.5rem", letterSpacing: "0.5rem" }}
                                    />
                                    <div style={{ display: "flex", gap: "0.75rem" }}>
                                        <button onClick={() => setAddStep("input")} className="btn-secondary" style={{ flex: 1 }}>Back</button>
                                        <button onClick={handleVerifyCode} disabled={sessionLoading || !code} className="btn-primary" style={{ flex: 1 }}>
                                            {sessionLoading ? "..." : "Verify"}
                                        </button>
                                    </div>
                                </div>
                            )}

                            {addStep === "2fa" && (
                                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                                    <p style={{ color: "#9ca3af", fontSize: "0.875rem" }}>Enter your 2FA password</p>
                                    <input
                                        type="password"
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        className="input-field"
                                        placeholder="2FA Password"
                                    />
                                    <button onClick={handleVerifyCode} disabled={sessionLoading || !password} className="btn-primary">
                                        {sessionLoading ? "..." : "Submit"}
                                    </button>
                                </div>
                            )}

                            {addStep === "adding" && (
                                <div style={{ textAlign: "center", padding: "2rem" }}>
                                    <p style={{ color: "#22d3ee" }}>Adding account...</p>
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </main>
        </>
    );
}
