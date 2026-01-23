"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { api, getToken } from "@/lib/api";

interface Account {
    id: number;
    client_id: number | null;
    client_name: string | null;
    phone_number: string;
    display_name: string | null;
    is_premium: number;
    is_active: number;
    created_at: string;
    running_campaign?: string | null;
}

interface Client {
    id: number;
    name: string;
}

type AddStep = "input" | "code" | "2fa" | "adding";

export default function AccountsPage() {
    const router = useRouter();
    const [accounts, setAccounts] = useState<Account[]>([]);
    const [clients, setClients] = useState<Client[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [showAddModal, setShowAddModal] = useState(false);
    const [showAssignModal, setShowAssignModal] = useState(false);
    const [showEditModal, setShowEditModal] = useState(false);
    const [selectedAccount, setSelectedAccount] = useState<Account | null>(null);
    const [assignClientId, setAssignClientId] = useState<number | "">("");
    const [editDisplayName, setEditDisplayName] = useState("");
    const [editIsPremium, setEditIsPremium] = useState(false);
    const [refreshing, setRefreshing] = useState(false);

    // Add Account State
    const [addStep, setAddStep] = useState<AddStep>("input");
    const [phone, setPhone] = useState("");
    const [code, setCode] = useState("");
    const [password, setPassword] = useState("");
    const [displayName, setDisplayName] = useState("");
    const [clientId, setClientId] = useState<number | "">("");
    const [sessionLoading, setSessionLoading] = useState(false);

    // Spam check state
    const [checkingSpam, setCheckingSpam] = useState(false);
    const [spamResult, setSpamResult] = useState<{ has_limits: boolean; limit_details: string; spambot_response: string } | null>(null);

    // Profile editing state
    const [editFirstName, setEditFirstName] = useState("");
    const [editLastName, setEditLastName] = useState("");
    const [editBio, setEditBio] = useState("");
    const [editUsername, setEditUsername] = useState("");
    const [savingProfile, setSavingProfile] = useState(false);
    const [profileSuccess, setProfileSuccess] = useState("");

    // OTP state
    const [fetchingOtp, setFetchingOtp] = useState(false);
    const [otpResult, setOtpResult] = useState<{ latest_code: string | null; codes: { code: string; date: string; message: string }[] } | null>(null);

    // Folder join state
    const [joiningFolders, setJoiningFolders] = useState(false);
    const [folderResult, setFolderResult] = useState<{
        total_folders: number; joined: number; failed: number; chats_added: number;
    } | null>(null);

    // Chat stats state
    const [loadingChatStats, setLoadingChatStats] = useState(false);
    const [chatStats, setChatStats] = useState<{
        total_dialogs: number;
        groups: number;
        supergroups: number;
        forums: number;
        channels: number;
        total_groups_and_forums: number;
    } | null>(null);

    useEffect(() => {
        const token = getToken("admin");
        if (!token) {
            router.push("/admin/login");
            return;
        }
        fetchData(token);
    }, [router]);

    const fetchData = async (token: string) => {
        const [accountsRes, clientsRes] = await Promise.all([
            api<{ accounts: Account[] }>("/admin/accounts", { token }),
            api<{ clients: Client[] }>("/admin/clients", { token }),
        ]);

        setLoading(false);
        if (accountsRes.ok) setAccounts(accountsRes.data?.accounts || []);
        if (clientsRes.ok) setClients(clientsRes.data?.clients || []);
    };

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
        const token = getToken("admin");
        if (!token) return;

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

        const response = await api("/admin/accounts", {
            method: "POST",
            body: {
                phone_number: phone,
                session_string: sessionString,
                display_name: name,
                is_premium: isPremium,
                client_id: clientId || null,
            },
            token,
        });

        if (response.ok) {
            closeAddModal();
            fetchData(token);
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
        setClientId("");
        setError("");
    };

    const handleAssign = async () => {
        if (!selectedAccount) return;
        const token = getToken("admin");
        if (!token) return;

        const response = await api(`/admin/accounts/${selectedAccount.id}/assign`, {
            method: "POST",
            body: { client_id: assignClientId === "" ? null : assignClientId },
            token,
        });

        if (response.ok) {
            setShowAssignModal(false);
            setSelectedAccount(null);
            setAssignClientId("");
            fetchData(token);
        }
    };

    const handleTogglePremium = async (account: Account) => {
        const token = getToken("admin");
        if (!token) return;

        await api(`/admin/accounts/${account.id}`, {
            method: "PUT",
            body: { is_premium: !account.is_premium },
            token,
        });
        fetchData(token);
    };

    const handleDelete = async (accountId: number) => {
        if (!confirm("Delete this account from the pool?")) return;
        const token = getToken("admin");
        if (!token) return;

        await api(`/admin/accounts/${accountId}`, { method: "DELETE", token });
        fetchData(token);
    };

    const openAssignModal = (account: Account) => {
        setSelectedAccount(account);
        setAssignClientId(account.client_id || "");
        setShowAssignModal(true);
    };

    const openEditModal = (account: Account) => {
        setSelectedAccount(account);
        setEditDisplayName(account.display_name || "");
        setEditIsPremium(!!account.is_premium);
        setSpamResult(null);
        setFolderResult(null);
        setChatStats(null);
        setJoiningFolders(false);
        setLoadingChatStats(false);
        setEditFirstName("");
        setEditLastName("");
        setEditBio("");
        setEditUsername("");
        setProfileSuccess("");
        setOtpResult(null);
        setShowEditModal(true);
    };

    const handleSaveEdit = async () => {
        if (!selectedAccount) return;
        const token = getToken("admin");
        if (!token) return;

        await api(`/admin/accounts/${selectedAccount.id}`, {
            method: "PUT",
            body: { display_name: editDisplayName, is_premium: editIsPremium },
            token,
        });
        setShowEditModal(false);
        fetchData(token);
    };

    const handleRefreshFromTelegram = async () => {
        if (!selectedAccount) return;
        const token = getToken("admin");
        if (!token) return;

        setRefreshing(true);
        setError("");

        const response = await api<{ display_name: string; is_premium: boolean; first_name: string; last_name: string; username: string; bio: string }>(`/admin/accounts/${selectedAccount.id}/refresh`, {
            method: "POST",
            token,
        });

        setRefreshing(false);

        if (response.ok && response.data) {
            setEditDisplayName(response.data.display_name);
            setEditIsPremium(response.data.is_premium);
            setEditFirstName(response.data.first_name || "");
            setEditLastName(response.data.last_name || "");
            setEditUsername(response.data.username || "");
            setEditBio(response.data.bio || "");
            fetchData(token);
        } else {
            setError(response.error || "Failed to refresh from Telegram");
        }
    };

    const handleCheckSpam = async () => {
        if (!selectedAccount) return;
        const token = getToken("admin");
        if (!token) return;

        setCheckingSpam(true);
        setError("");
        setSpamResult(null);

        const response = await api<{ has_limits: boolean; limit_details: string; spambot_response: string }>(`/admin/accounts/${selectedAccount.id}/check-spam`, {
            method: "POST",
            token,
        });

        setCheckingSpam(false);

        if (response.ok && response.data) {
            setSpamResult(response.data);
        } else {
            setError(response.error || "Failed to check spam status");
        }
    };

    const handleJoinFolders = async () => {
        if (!selectedAccount) return;
        const token = getToken("admin");
        if (!token) return;

        setJoiningFolders(true);
        setError("");
        setFolderResult(null);

        // Start background task
        const startResponse = await api<{ success: boolean; task_id: string }>(`/admin/accounts/${selectedAccount.id}/join-folders`, {
            method: "POST",
            token,
        });

        if (!startResponse.ok) {
            setJoiningFolders(false);
            setError(startResponse.error || "Failed to start folder join");
            return;
        }

        // Poll for status every 2 seconds
        const pollStatus = async () => {
            const statusResponse = await api<{
                status: string;
                progress: number;
                total: number;
                joined: number;
                failed: number;
                chats_added: number;
                current_folder?: string;
                error?: string;
            }>(`/admin/accounts/${selectedAccount.id}/join-folders/status`, { token });

            if (statusResponse.ok && statusResponse.data) {
                const data = statusResponse.data;

                // Update UI with current progress
                setFolderResult({
                    total_folders: data.total,
                    joined: data.joined,
                    failed: data.failed,
                    chats_added: data.chats_added
                });

                if (data.status === "completed") {
                    setJoiningFolders(false);
                } else if (data.status === "failed") {
                    setJoiningFolders(false);
                    setError(data.error || "Folder join failed");
                } else if (data.status === "running") {
                    // Continue polling
                    setTimeout(pollStatus, 2000);
                }
            } else {
                // Retry on error
                setTimeout(pollStatus, 2000);
            }
        };

        // Start polling after short delay
        setTimeout(pollStatus, 1000);
    };

    const handleGetChatStats = async () => {
        if (!selectedAccount) return;
        const token = getToken("admin");
        if (!token) return;

        setLoadingChatStats(true);
        setChatStats(null);
        setError("");

        const response = await api<{
            total_dialogs: number;
            groups: number;
            supergroups: number;
            forums: number;
            channels: number;
            total_groups_and_forums: number;
        }>(`/admin/accounts/${selectedAccount.id}/chat-stats`, { token });

        setLoadingChatStats(false);

        if (response.ok && response.data) {
            setChatStats(response.data);
        } else {
            setError(response.error || "Failed to get chat stats");
        }
    };

    const handleUpdateProfile = async () => {
        if (!selectedAccount) return;
        const token = getToken("admin");
        if (!token) return;

        setSavingProfile(true);
        setError("");
        setProfileSuccess("");

        const response = await api<{ success: boolean; message: string; current_profile: { first_name: string; last_name: string; username: string; bio: string } }>(`/admin/accounts/${selectedAccount.id}/profile`, {
            method: "PUT",
            body: {
                first_name: editFirstName || null,
                last_name: editLastName || null,
                bio: editBio || null,
                username: editUsername || null
            },
            token,
        });

        setSavingProfile(false);

        if (response.ok && response.data) {
            setProfileSuccess("Profile updated successfully!");
            const fullName = `${response.data.current_profile.first_name || ""} ${response.data.current_profile.last_name || ""}`.trim();
            setEditDisplayName(fullName);
            fetchData(token);
        } else {
            setError(response.error || "Failed to update profile");
        }
    };

    const handleGetOtp = async () => {
        if (!selectedAccount) return;
        const token = getToken("admin");
        if (!token) return;

        setFetchingOtp(true);
        setError("");
        setOtpResult(null);

        const response = await api<{ success: boolean; latest_code: string | null; codes: { code: string; date: string; message: string }[] }>(`/admin/accounts/${selectedAccount.id}/otp`, {
            method: "GET",
            token,
        });

        setFetchingOtp(false);

        if (response.ok && response.data) {
            setOtpResult(response.data);
        } else {
            setError(response.error || "Failed to get OTP");
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div style={{ color: "#22d3ee", fontSize: "1.25rem" }}>Loading...</div>
            </div>
        );
    }

    const unassignedAccounts = accounts.filter((a) => !a.client_id);
    const assignedAccounts = accounts.filter((a) => a.client_id);

    return (
        <>
            <Sidebar userType="admin" />

            <main className="main-content">
                <div className="page-header">
                    <div>
                        <h1 className="page-title">Account Pool</h1>
                        <p className="page-subtitle">Manage your Telegram accounts and assign them to clients</p>
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
                        <div className="stat-label">Premium Accounts</div>
                    </div>
                    <div className="glass-card">
                        <div className="stat-value" style={{ color: "#4ade80" }}>{assignedAccounts.length}</div>
                        <div className="stat-label">Assigned</div>
                    </div>
                    <div className="glass-card">
                        <div className="stat-value" style={{ color: "#facc15" }}>{unassignedAccounts.length}</div>
                        <div className="stat-label">Unassigned</div>
                    </div>
                </div>

                {/* Unassigned Accounts */}
                {unassignedAccounts.length > 0 && (
                    <div className="glass-card" style={{ marginBottom: "1.5rem" }}>
                        <h2 style={{ fontSize: "1.25rem", fontWeight: 600, color: "#facc15", marginBottom: "1rem" }}>
                            Unassigned Accounts ({unassignedAccounts.length})
                        </h2>
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
                                    {unassignedAccounts.map((acc) => (
                                        <tr key={acc.id}>
                                            <td style={{ color: "white", fontFamily: "monospace" }}>
                                                {acc.phone_number}
                                                {acc.running_campaign && (
                                                    <span style={{
                                                        marginLeft: "0.5rem",
                                                        background: "rgba(34, 197, 94, 0.2)",
                                                        color: "#22c55e",
                                                        padding: "0.15rem 0.4rem",
                                                        borderRadius: "0.25rem",
                                                        fontSize: "0.65rem",
                                                        fontWeight: 600
                                                    }}>
                                                        LIVE
                                                    </span>
                                                )}
                                            </td>
                                            <td style={{ color: "#9ca3af" }}>{acc.display_name || "-"}</td>
                                            <td>
                                                <button onClick={() => handleTogglePremium(acc)} style={{ cursor: "pointer", border: "none", background: "none" }}>
                                                    <span className={`badge ${acc.is_premium ? "badge-info" : ""}`} style={!acc.is_premium ? { background: "rgba(156,163,175,0.2)", color: "#9ca3af" } : {}}>
                                                        {acc.is_premium ? "Premium" : "Normal"}
                                                    </span>
                                                </button>
                                            </td>
                                            <td>
                                                <div style={{ display: "flex", gap: "0.5rem" }}>
                                                    <button onClick={() => openEditModal(acc)} style={{ color: "#22d3ee", background: "none", border: "none", cursor: "pointer", fontSize: "0.75rem" }}>Edit</button>
                                                    <button onClick={() => openAssignModal(acc)} className="btn-primary" style={{ padding: "0.25rem 0.75rem", fontSize: "0.75rem" }}>Assign</button>
                                                    <button onClick={() => handleDelete(acc.id)} style={{ color: "#f87171", background: "none", border: "none", cursor: "pointer", fontSize: "0.75rem" }}>Delete</button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {/* Assigned Accounts */}
                <div className="glass-card">
                    <h2 style={{ fontSize: "1.25rem", fontWeight: 600, color: "#4ade80", marginBottom: "1rem" }}>
                        Assigned Accounts ({assignedAccounts.length})
                    </h2>
                    {assignedAccounts.length > 0 ? (
                        <div className="responsive-table">
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Phone</th>
                                        <th>Name</th>
                                        <th>Type</th>
                                        <th>Assigned To</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {assignedAccounts.map((acc) => (
                                        <tr key={acc.id}>
                                            <td style={{ color: "white", fontFamily: "monospace" }}>
                                                {acc.phone_number}
                                                {acc.running_campaign && (
                                                    <span style={{
                                                        marginLeft: "0.5rem",
                                                        background: "rgba(34, 197, 94, 0.2)",
                                                        color: "#22c55e",
                                                        padding: "0.15rem 0.4rem",
                                                        borderRadius: "0.25rem",
                                                        fontSize: "0.65rem",
                                                        fontWeight: 600
                                                    }}>
                                                        LIVE
                                                    </span>
                                                )}
                                            </td>
                                            <td style={{ color: "#9ca3af" }}>{acc.display_name || "-"}</td>
                                            <td>
                                                <button onClick={() => handleTogglePremium(acc)} style={{ cursor: "pointer", border: "none", background: "none" }}>
                                                    <span className={`badge ${acc.is_premium ? "badge-info" : ""}`} style={!acc.is_premium ? { background: "rgba(156,163,175,0.2)", color: "#9ca3af" } : {}}>
                                                        {acc.is_premium ? "Premium" : "Normal"}
                                                    </span>
                                                </button>
                                            </td>
                                            <td style={{ color: "#22d3ee" }}>{acc.client_name}</td>
                                            <td>
                                                <div style={{ display: "flex", gap: "0.5rem" }}>
                                                    <button onClick={() => openEditModal(acc)} style={{ color: "#22d3ee", background: "none", border: "none", cursor: "pointer", fontSize: "0.75rem" }}>Edit</button>
                                                    <button onClick={() => openAssignModal(acc)} style={{ color: "#facc15", background: "none", border: "none", cursor: "pointer", fontSize: "0.75rem" }}>Reassign</button>
                                                    <button onClick={() => handleDelete(acc.id)} style={{ color: "#f87171", background: "none", border: "none", cursor: "pointer", fontSize: "0.75rem" }}>Delete</button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    ) : (
                        <p style={{ color: "#9ca3af", textAlign: "center", padding: "2rem" }}>
                            No accounts assigned to clients yet.
                        </p>
                    )}
                </div>

                {/* ADD ACCOUNT MODAL */}
                {showAddModal && (
                    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50 }}>
                        <div className="glass-card" style={{ width: "100%", maxWidth: "28rem" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
                                <h2 style={{ fontSize: "1.25rem", fontWeight: 600, color: "white" }}>
                                    {addStep === "input" && "Add Account"}
                                    {addStep === "code" && "Enter Verification Code"}
                                    {addStep === "2fa" && "Two-Factor Authentication"}
                                    {addStep === "adding" && "Adding Account..."}
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
                                        <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>Phone Number (with country code)</label>
                                        <input type="text" value={phone} onChange={(e) => setPhone(e.target.value)} className="input-field" placeholder="+91 12345 67890" />
                                    </div>
                                    <div>
                                        <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>Display Name (optional)</label>
                                        <input type="text" value={displayName} onChange={(e) => setDisplayName(e.target.value)} className="input-field" placeholder="Auto-filled from Telegram" />
                                    </div>
                                    <div>
                                        <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>Assign to Client (optional)</label>
                                        <select value={clientId} onChange={(e) => setClientId(e.target.value ? parseInt(e.target.value) : "")} className="input-field">
                                            <option value="">Add to pool (assign later)</option>
                                            {clients.map((c) => (<option key={c.id} value={c.id}>{c.name}</option>))}
                                        </select>
                                    </div>
                                    <button onClick={handleSendCode} disabled={sessionLoading || !phone} className="btn-primary" style={{ marginTop: "0.5rem" }}>
                                        {sessionLoading ? "Sending..." : "Send Verification Code"}
                                    </button>
                                </div>
                            )}

                            {addStep === "code" && (
                                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                                    <p style={{ color: "#9ca3af", fontSize: "0.875rem" }}>Check your Telegram app for the code</p>
                                    <div>
                                        <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>Verification Code</label>
                                        <input type="text" value={code} onChange={(e) => setCode(e.target.value)} className="input-field" placeholder="12345" style={{ textAlign: "center", fontSize: "1.5rem", letterSpacing: "0.5rem" }} />
                                    </div>
                                    <div style={{ display: "flex", gap: "0.75rem" }}>
                                        <button onClick={() => setAddStep("input")} className="btn-secondary" style={{ flex: 1 }}>Back</button>
                                        <button onClick={handleVerifyCode} disabled={sessionLoading || !code} className="btn-primary" style={{ flex: 1 }}>
                                            {sessionLoading ? "Verifying..." : "Verify & Add"}
                                        </button>
                                    </div>
                                </div>
                            )}

                            {addStep === "2fa" && (
                                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                                    <p style={{ color: "#9ca3af", fontSize: "0.875rem" }}>This account has 2FA enabled. Enter your password.</p>
                                    <div>
                                        <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>2FA Password</label>
                                        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="input-field" placeholder="Your 2FA password" />
                                    </div>
                                    <button onClick={handleVerifyCode} disabled={sessionLoading || !password} className="btn-primary">
                                        {sessionLoading ? "Verifying..." : "Submit & Add"}
                                    </button>
                                </div>
                            )}

                            {addStep === "adding" && (
                                <div style={{ textAlign: "center", padding: "2rem" }}>
                                    <div style={{ color: "#22d3ee", fontSize: "1rem", marginBottom: "0.5rem" }}>Loading...</div>
                                    <p style={{ color: "#9ca3af" }}>Adding account to pool...</p>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* ASSIGN MODAL */}
                {showAssignModal && selectedAccount && (
                    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50 }}>
                        <div className="glass-card" style={{ width: "100%", maxWidth: "24rem" }}>
                            <h2 style={{ fontSize: "1.25rem", fontWeight: 600, color: "white", marginBottom: "1rem" }}>
                                {selectedAccount.client_id ? "Reassign Account" : "Assign Account"}
                            </h2>
                            <p style={{ color: "#9ca3af", marginBottom: "1rem" }}>
                                <strong style={{ color: "white" }}>{selectedAccount.phone_number}</strong>
                                {selectedAccount.display_name && ` (${selectedAccount.display_name})`}
                            </p>
                            <div style={{ marginBottom: "1.5rem" }}>
                                <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>Select Client</label>
                                <select value={assignClientId} onChange={(e) => setAssignClientId(e.target.value ? parseInt(e.target.value) : "")} className="input-field">
                                    <option value="">-- Unassign (return to pool) --</option>
                                    {clients.map((c) => (<option key={c.id} value={c.id}>{c.name}</option>))}
                                </select>
                            </div>
                            <div style={{ display: "flex", gap: "0.75rem" }}>
                                <button onClick={() => setShowAssignModal(false)} className="btn-secondary" style={{ flex: 1 }}>Cancel</button>
                                <button onClick={handleAssign} className="btn-primary" style={{ flex: 1 }}>{assignClientId ? "Assign" : "Unassign"}</button>
                            </div>
                        </div>
                    </div>
                )}

                {/* EDIT ACCOUNT MODAL */}
                {showEditModal && selectedAccount && (
                    <div style={{ position: "fixed", inset: 0, background: "#0a0f1a", zIndex: 1000, overflowY: "auto" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "1rem", padding: "1rem 1.5rem", borderBottom: "1px solid rgba(255,255,255,0.1)", background: "linear-gradient(135deg, rgba(34, 211, 238, 0.15), rgba(139, 92, 246, 0.15))", position: "sticky", top: 0, zIndex: 10 }}>
                            <button onClick={() => setShowEditModal(false)} style={{ color: "white", background: "none", border: "none", cursor: "pointer", fontSize: "1.5rem", padding: "0.5rem" }}>←</button>
                            <div>
                                <h2 style={{ fontSize: "1.25rem", fontWeight: 700, color: "white", margin: 0 }}>Account Settings</h2>
                                <div style={{ fontFamily: "monospace", fontSize: "0.85rem", color: "#22d3ee", marginTop: "0.25rem" }}>{selectedAccount.phone_number}</div>
                            </div>
                        </div>

                        <div style={{ padding: "1.5rem", paddingBottom: "6rem" }}>
                            {error && (
                                <div style={{ color: "#f87171", background: "rgba(239,68,68,0.1)", padding: "0.75rem 1rem", borderRadius: "0.75rem", marginBottom: "1rem", fontSize: "0.875rem", border: "1px solid rgba(239,68,68,0.2)" }}>{error}</div>
                            )}

                            {/* Basic Info */}
                            <div style={{ background: "rgba(255,255,255,0.03)", borderRadius: "0.75rem", padding: "1rem", marginBottom: "1rem", border: "1px solid rgba(255,255,255,0.05)" }}>
                                <h3 style={{ fontSize: "0.75rem", fontWeight: 600, color: "#9ca3af", marginBottom: "0.75rem", textTransform: "uppercase" }}>Basic Info</h3>
                                <div style={{ marginBottom: "1rem" }}>
                                    <label style={{ display: "block", fontSize: "0.8rem", color: "#6b7280", marginBottom: "0.25rem" }}>Display Name</label>
                                    <input type="text" value={editDisplayName} onChange={(e) => setEditDisplayName(e.target.value)} className="input-field" placeholder="Account nickname" />
                                </div>
                                <label style={{ display: "flex", alignItems: "center", gap: "0.75rem", cursor: "pointer", padding: "0.75rem", background: editIsPremium ? "rgba(139, 92, 246, 0.15)" : "rgba(255,255,255,0.02)", borderRadius: "0.5rem", border: editIsPremium ? "1px solid rgba(139, 92, 246, 0.3)" : "1px solid rgba(255,255,255,0.05)" }}>
                                    <input type="checkbox" checked={editIsPremium} onChange={(e) => setEditIsPremium(e.target.checked)} style={{ width: "1.1rem", height: "1.1rem", accentColor: "#8b5cf6" }} />
                                    <div>
                                        <span style={{ color: "white", fontWeight: 500 }}>Premium Account</span>
                                        <p style={{ fontSize: "0.7rem", color: "#6b7280", marginTop: "0.15rem" }}>Higher limits & priority sending</p>
                                    </div>
                                </label>
                            </div>

                            {/* Account Health */}
                            <div style={{ background: "rgba(255,255,255,0.03)", borderRadius: "0.75rem", padding: "1rem", marginBottom: "1rem", border: "1px solid rgba(255,255,255,0.05)" }}>
                                <h3 style={{ fontSize: "0.75rem", fontWeight: 600, color: "#9ca3af", marginBottom: "0.75rem", textTransform: "uppercase" }}>Account Health</h3>
                                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.5rem", marginBottom: "0.75rem" }}>
                                    <button onClick={handleRefreshFromTelegram} disabled={refreshing} style={{ padding: "0.75rem", borderRadius: "0.5rem", border: "1px solid rgba(34, 211, 238, 0.3)", background: "rgba(34, 211, 238, 0.1)", color: "#22d3ee", cursor: refreshing ? "wait" : "pointer", fontSize: "0.8rem", fontWeight: 500 }}>
                                        {refreshing ? "..." : "Sync Info"}
                                    </button>
                                    <button onClick={handleCheckSpam} disabled={checkingSpam} style={{ padding: "0.75rem", borderRadius: "0.5rem", border: "1px solid rgba(251, 146, 60, 0.3)", background: "rgba(251, 146, 60, 0.1)", color: "#fb923c", cursor: checkingSpam ? "wait" : "pointer", fontSize: "0.8rem", fontWeight: 500 }}>
                                        {checkingSpam ? "..." : "Check Limits"}
                                    </button>
                                    <button onClick={handleGetChatStats} disabled={loadingChatStats} style={{ padding: "0.75rem", borderRadius: "0.5rem", border: "1px solid rgba(168, 85, 247, 0.3)", background: "rgba(168, 85, 247, 0.1)", color: "#a855f7", cursor: loadingChatStats ? "wait" : "pointer", fontSize: "0.8rem", fontWeight: 500 }}>
                                        {loadingChatStats ? "..." : "Chat Stats"}
                                    </button>
                                </div>
                                {spamResult && (
                                    <div style={{ padding: "1rem", borderRadius: "0.75rem", background: spamResult.has_limits ? "rgba(239,68,68,0.15)" : "rgba(34,197,94,0.15)", border: `1px solid ${spamResult.has_limits ? "rgba(239,68,68,0.25)" : "rgba(34,197,94,0.25)"}`, marginBottom: chatStats ? "0.75rem" : 0 }}>
                                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
                                            <span style={{ fontSize: "1.25rem" }}>{spamResult.has_limits ? "×" : "✓"}</span>
                                            <span style={{ fontSize: "0.95rem", fontWeight: 700, color: spamResult.has_limits ? "#f87171" : "#4ade80" }}>
                                                {spamResult.has_limits ? "Limits Detected" : "All Clear!"}
                                            </span>
                                        </div>
                                        <p style={{ fontSize: "0.8rem", color: "#d1d5db", marginBottom: "0.5rem" }}>{spamResult.limit_details}</p>
                                        {spamResult.spambot_response && (
                                            <div style={{ marginTop: "0.75rem", padding: "0.75rem", background: "rgba(0,0,0,0.3)", borderRadius: "0.5rem", border: "1px solid rgba(255,255,255,0.1)" }}>
                                                <div style={{ fontSize: "0.7rem", color: "#9ca3af", marginBottom: "0.5rem", fontWeight: 600 }}>SpamBot Response:</div>
                                                <p style={{ fontSize: "0.75rem", color: "#e5e7eb", whiteSpace: "pre-wrap", lineHeight: 1.4, margin: 0 }}>{spamResult.spambot_response}</p>
                                            </div>
                                        )}
                                    </div>
                                )}
                                {chatStats && (
                                    <div style={{ padding: "1rem", borderRadius: "0.75rem", background: "rgba(168, 85, 247, 0.1)", border: "1px solid rgba(168, 85, 247, 0.25)" }}>
                                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
                                            <span style={{ fontSize: "1.25rem" }}>📊</span>
                                            <span style={{ fontSize: "0.95rem", fontWeight: 700, color: "#a855f7" }}>
                                                {chatStats.total_groups_and_forums} Groups & Forums Joined
                                            </span>
                                        </div>
                                        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.5rem" }}>
                                            <div style={{ textAlign: "center", padding: "0.5rem", background: "rgba(255,255,255,0.05)", borderRadius: "0.5rem" }}>
                                                <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "#22d3ee" }}>{chatStats.supergroups}</div>
                                                <div style={{ fontSize: "0.7rem", color: "#9ca3af" }}>Supergroups</div>
                                            </div>
                                            <div style={{ textAlign: "center", padding: "0.5rem", background: "rgba(255,255,255,0.05)", borderRadius: "0.5rem" }}>
                                                <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "#f472b6" }}>{chatStats.forums}</div>
                                                <div style={{ fontSize: "0.7rem", color: "#9ca3af" }}>Forums</div>
                                            </div>
                                            <div style={{ textAlign: "center", padding: "0.5rem", background: "rgba(255,255,255,0.05)", borderRadius: "0.5rem" }}>
                                                <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "#4ade80" }}>{chatStats.channels}</div>
                                                <div style={{ fontSize: "0.7rem", color: "#9ca3af" }}>Channels</div>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                            {/* Telegram Profile Section */}
                            <div style={{ background: "rgba(255,255,255,0.03)", borderRadius: "0.75rem", padding: "1rem", marginBottom: "1rem", border: "1px solid rgba(255,255,255,0.05)" }}>
                                <h3 style={{ fontSize: "0.75rem", fontWeight: 600, color: "#9ca3af", marginBottom: "0.75rem", textTransform: "uppercase" }}>Telegram Profile</h3>
                                {profileSuccess && (
                                    <div style={{ color: "#4ade80", background: "rgba(34,197,94,0.1)", padding: "0.5rem 0.75rem", borderRadius: "0.5rem", marginBottom: "0.75rem", fontSize: "0.8rem" }}>
                                        ✓ {profileSuccess}
                                    </div>
                                )}
                                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", marginBottom: "0.5rem" }}>
                                    <div>
                                        <label style={{ fontSize: "0.65rem", color: "#6b7280", display: "block", marginBottom: "0.25rem" }}>First Name</label>
                                        <input type="text" value={editFirstName} onChange={(e) => setEditFirstName(e.target.value)} className="input-field" placeholder="First name" style={{ fontSize: "0.85rem" }} />
                                    </div>
                                    <div>
                                        <label style={{ fontSize: "0.65rem", color: "#6b7280", display: "block", marginBottom: "0.25rem" }}>Last Name</label>
                                        <input type="text" value={editLastName} onChange={(e) => setEditLastName(e.target.value)} className="input-field" placeholder="Last name" style={{ fontSize: "0.85rem" }} />
                                    </div>
                                </div>
                                <div style={{ marginBottom: "0.5rem" }}>
                                    <label style={{ fontSize: "0.65rem", color: "#6b7280", display: "block", marginBottom: "0.25rem" }}>Username</label>
                                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                        <span style={{ color: "#6b7280", fontSize: "0.9rem" }}>@</span>
                                        <input type="text" value={editUsername} onChange={(e) => setEditUsername(e.target.value.replace(/^@/, ""))} className="input-field" placeholder="username" style={{ fontSize: "0.85rem", flex: 1 }} />
                                    </div>
                                </div>
                                <div style={{ marginBottom: "0.75rem" }}>
                                    <label style={{ fontSize: "0.65rem", color: "#6b7280", display: "block", marginBottom: "0.25rem" }}>Bio</label>
                                    <textarea value={editBio} onChange={(e) => setEditBio(e.target.value)} className="input-field" placeholder="About me..." rows={2} style={{ fontSize: "0.85rem", resize: "none" }} />
                                </div>
                                <button onClick={handleUpdateProfile} disabled={savingProfile} style={{ width: "100%", padding: "0.75rem", borderRadius: "0.5rem", border: "1px solid rgba(139, 92, 246, 0.3)", background: "rgba(139, 92, 246, 0.15)", color: "#a78bfa", cursor: savingProfile ? "wait" : "pointer", fontSize: "0.8rem", fontWeight: 500, opacity: savingProfile ? 0.7 : 1 }}>
                                    {savingProfile ? "Updating..." : "Update Telegram Profile"}
                                </button>
                            </div>

                            {/* Login OTP Section */}
                            <div style={{ background: "rgba(255,255,255,0.03)", borderRadius: "0.75rem", padding: "1rem", marginBottom: "1rem", border: "1px solid rgba(255,255,255,0.05)" }}>
                                <h3 style={{ fontSize: "0.75rem", fontWeight: 600, color: "#9ca3af", marginBottom: "0.75rem", textTransform: "uppercase" }}>Login OTP</h3>
                                <button onClick={handleGetOtp} disabled={fetchingOtp} style={{ width: "100%", padding: "0.75rem", borderRadius: "0.5rem", border: "1px solid rgba(34, 211, 238, 0.3)", background: "rgba(34, 211, 238, 0.1)", color: "#22d3ee", cursor: fetchingOtp ? "wait" : "pointer", fontSize: "0.8rem", fontWeight: 500, opacity: fetchingOtp ? 0.7 : 1, marginBottom: "0.75rem" }}>
                                    {fetchingOtp ? "Fetching..." : "Get Recent Login Codes"}
                                </button>
                                {otpResult && (
                                    <div style={{ background: otpResult.latest_code ? "rgba(34,197,94,0.1)" : "rgba(251,146,60,0.1)", border: `1px solid ${otpResult.latest_code ? "rgba(34,197,94,0.25)" : "rgba(251,146,60,0.25)"}`, borderRadius: "0.5rem", padding: "0.75rem" }}>
                                        {otpResult.codes && otpResult.codes.length > 0 ? (
                                            <div>
                                                {otpResult.codes.slice(0, 3).map((codeItem, index) => (
                                                    <div key={index} style={{ marginBottom: index < 2 && otpResult.codes.length > 1 ? "0.75rem" : 0, paddingBottom: index < 2 && otpResult.codes.length > 1 ? "0.75rem" : 0, borderBottom: index < 2 && otpResult.codes.length > 1 ? "1px solid rgba(255,255,255,0.1)" : "none" }}>
                                                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.25rem" }}>
                                                            <span style={{ fontSize: "1.5rem", fontWeight: 700, color: index === 0 ? "#4ade80" : "#9ca3af", fontFamily: "monospace", letterSpacing: "0.1em" }}>{codeItem.code}</span>
                                                            {codeItem.date && (
                                                                <span style={{ fontSize: "0.7rem", color: "#9ca3af" }}>
                                                                    {new Date(codeItem.date).toLocaleString()}
                                                                </span>
                                                            )}
                                                        </div>
                                                        {codeItem.message && (
                                                            <div style={{ marginTop: "0.5rem", padding: "0.5rem", background: "rgba(0,0,0,0.2)", borderRadius: "0.375rem" }}>
                                                                <p style={{ fontSize: "0.7rem", color: "#d1d5db", margin: 0, whiteSpace: "pre-wrap", lineHeight: 1.4 }}>{codeItem.message}</p>
                                                            </div>
                                                        )}
                                                    </div>
                                                ))}
                                            </div>
                                        ) : (
                                            <div style={{ color: "#fb923c", fontSize: "0.85rem" }}>No recent login codes found</div>
                                        )}
                                    </div>
                                )}
                            </div>

                            {/* Join Folders Section */}
                            <div style={{ background: "rgba(255,255,255,0.03)", borderRadius: "0.75rem", padding: "1rem", marginBottom: "1.5rem", border: "1px solid rgba(255,255,255,0.05)" }}>
                                <h3 style={{ fontSize: "0.75rem", fontWeight: 600, color: "#9ca3af", marginBottom: "0.75rem", textTransform: "uppercase" }}>Join Chat Folders</h3>
                                <p style={{ fontSize: "0.75rem", color: "#6b7280", marginBottom: "0.75rem" }}>Joins 5 pre-configured chat folders, imports all chats, then removes the folders</p>
                                <button onClick={handleJoinFolders} disabled={joiningFolders} style={{ width: "100%", padding: "0.875rem", borderRadius: "0.5rem", border: "none", background: joiningFolders ? "rgba(34, 211, 238, 0.3)" : "linear-gradient(135deg, #22d3ee, #06b6d4)", color: "white", cursor: joiningFolders ? "wait" : "pointer", fontSize: "0.9rem", fontWeight: 600, marginBottom: folderResult ? "0.75rem" : 0 }}>
                                    {joiningFolders ? "Joining Folders..." : "Join All Folders"}
                                </button>
                                {folderResult && (
                                    <div style={{ padding: "0.875rem", borderRadius: "0.75rem", background: "rgba(34,197,94,0.1)", border: "1px solid rgba(34,197,94,0.2)" }}>
                                        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.5rem", textAlign: "center" }}>
                                            <div style={{ background: "rgba(74, 222, 128, 0.15)", padding: "0.5rem", borderRadius: "0.5rem" }}>
                                                <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "#4ade80" }}>{folderResult.joined}</div>
                                                <div style={{ fontSize: "0.6rem", color: "#4ade80" }}>Folders</div>
                                            </div>
                                            <div style={{ background: "rgba(34, 211, 238, 0.15)", padding: "0.5rem", borderRadius: "0.5rem" }}>
                                                <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "#22d3ee" }}>{folderResult.chats_added}</div>
                                                <div style={{ fontSize: "0.6rem", color: "#22d3ee" }}>Chats Added</div>
                                            </div>
                                            <div style={{ background: "rgba(248, 113, 113, 0.15)", padding: "0.5rem", borderRadius: "0.5rem" }}>
                                                <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "#f87171" }}>{folderResult.failed}</div>
                                                <div style={{ fontSize: "0.6rem", color: "#f87171" }}>Failed</div>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Action Buttons */}
                            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                                <button onClick={() => { setShowEditModal(false); setSpamResult(null); setFolderResult(null); }} style={{ padding: "0.875rem", borderRadius: "0.5rem", border: "1px solid rgba(255,255,255,0.15)", background: "rgba(255,255,255,0.05)", color: "#9ca3af", cursor: "pointer", fontSize: "0.9rem", fontWeight: 500 }}>Cancel</button>
                                <button onClick={handleSaveEdit} style={{ padding: "0.875rem", borderRadius: "0.5rem", border: "none", background: "linear-gradient(135deg, #22d3ee, #06b6d4)", color: "white", cursor: "pointer", fontSize: "0.9rem", fontWeight: 600 }}>Save Changes</button>
                            </div>
                        </div>
                    </div>
                )}
            </main>
        </>
    );
}
