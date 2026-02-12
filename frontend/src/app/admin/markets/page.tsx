"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { api, getToken } from "@/lib/api";

interface Account {
    id: number;
    phone_number: string;
    display_name: string;
    is_active: boolean;
}

export default function MarketsPage() {
    const router = useRouter();

    // Global Joiner State
    const [globalJoining, setGlobalJoining] = useState(false);
    const [globalSingleJoin, setGlobalSingleJoin] = useState({ identifier: "", joining: false });
    const [showGlobalModal, setShowGlobalModal] = useState(false);
    const [globalLinks, setGlobalLinks] = useState("");
    const [globalProgress, setGlobalProgress] = useState<any>(null);

    // Bulk Global Joiner State
    const [bulkGlobalJoining, setBulkGlobalJoining] = useState(false);
    const [showBulkGlobalModal, setShowBulkGlobalModal] = useState(false);
    const [bulkGlobalLinks, setBulkGlobalLinks] = useState("");
    const [bulkGlobalProgress, setBulkGlobalProgress] = useState<any>(null);
    const [bulkSelectedAccount, setBulkSelectedAccount] = useState<string>("");
    const [bulkUseAllAccounts, setBulkUseAllAccounts] = useState(false);

    // Core Data State
    const [accounts, setAccounts] = useState<Account[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedAccount, setSelectedAccount] = useState<string>("");

    // Join Single Chat State
    const [joinChat, setJoinChat] = useState({ identifier: "", joining: false });

    // Join Single Folder State
    const [joinFolder, setJoinFolder] = useState({ link: "", joining: false });

    // Nuclear Join State
    const [nuclear, setNuclear] = useState({ links: "", running: false, progress: null as any });

    useEffect(() => {
        const token = getToken("admin");
        if (!token) {
            router.push("/admin/login");
            return;
        }
        fetchAccounts(token);
    }, [router]);

    const fetchAccounts = async (token: string) => {
        const res = await api<{ accounts: Account[] }>("/admin/accounts", { token });
        if (res.ok && res.data) {
            setAccounts(res.data.accounts.filter(a => a.is_active));
        }
        setLoading(false);
    };

    const handleJoinChat = async () => {
        if (!selectedAccount || !joinChat.identifier) return;
        setJoinChat(prev => ({ ...prev, joining: true }));
        const token = getToken("admin");
        const res = await api<any>("/admin/markets/join-chat", {
            method: "POST",
            token: token!,
            body: { account_id: parseInt(selectedAccount), identifier: joinChat.identifier }
        });
        if (res.ok && res.data?.success !== false) {
            alert("Join request successful!");
            setJoinChat({ identifier: "", joining: false });
        } else {
            const errMsg = res.data?.message || res.error || "Failed to join";
            alert(`⚠️ Error: ${errMsg}`);
            setJoinChat(prev => ({ ...prev, joining: false }));
        }
    };

    const handleJoinFolder = async () => {
        if (!selectedAccount || !joinFolder.link) return;
        setJoinFolder(prev => ({ ...prev, joining: true }));
        const token = getToken("admin");
        const res = await api<any>("/admin/markets/join-folder", {
            method: "POST",
            token: token!,
            body: { account_id: parseInt(selectedAccount), folder_link: joinFolder.link }
        });
        if (res.ok && res.data?.success !== false) {
            alert("Folder join successful!");
            setJoinFolder({ link: "", joining: false });
        } else {
            const errMsg = res.data?.message || res.error || "Failed to join folder";
            alert(`⚠️ Error: ${errMsg}`);
            setJoinFolder(prev => ({ ...prev, joining: false }));
        }
    };

    const handleNuclearJoin = async () => {
        if (!selectedAccount || !nuclear.links) return;
        if (!confirm("WARNING: This will WIP ALL CHATS and PMs on the account before joining. This is irreversible. Proceed?")) return;

        setNuclear(prev => ({ ...prev, running: true }));
        const token = getToken("admin");
        const linksArr = nuclear.links.split('\n').map(l => l.trim()).filter(l => l);

        const res = await api<any>("/admin/markets/nuclear-join", {
            method: "POST",
            token: token!,
            body: { account_id: parseInt(selectedAccount), folder_links: linksArr }
        });

        if (res.ok && res.data?.success !== false) {
            alert("Nuclear join sequence started in background!");
            startPollingStatus(parseInt(selectedAccount));
        } else {
            const errMsg = res.data?.message || res.error || "Failed to start sequence";
            alert(`☣️ Nuclear failure: ${errMsg}`);
            setNuclear(prev => ({ ...prev, running: false }));
        }
    };

    const handleGlobalJoin = () => {
        setShowGlobalModal(true);
    };

    const executeGlobalJoin = async () => {
        if (!globalLinks) return;
        const linksArr = globalLinks.split('\n').map(l => l.trim()).filter(l => l);

        if (linksArr.length === 0) {
            alert("No valid folder links provided.");
            return;
        }

        setGlobalJoining(true);
        const token = getToken("admin");
        const res = await api<any>("/admin/markets/global-join", {
            method: "POST",
            token: token!,
            body: { folder_links: linksArr }
        });

        if (res.ok && res.data?.task_id) {
            // Switch to progress view immediately
            setGlobalProgress({
                status: "running",
                progress: 0,
                total: accounts.length,
                message: "Initializing core system...",
                logs: ["> Terminal initialized.", `> Sequence ID: ${res.data.task_id}`, "> Deploying to all active accounts..."]
            });
            startGlobalPolling(res.data.task_id);
        } else {
            const errMsg = res.data?.message || res.error || "Failed to initialize global sequence";
            alert(`❌ CORE FAILURE: ${errMsg}`);
            setGlobalJoining(false);
        }
    };

    const startGlobalPolling = async (taskId: string) => {
        const token = getToken("admin");

        const poll = async () => {
            const res = await api<any>(`/admin/markets/global-status/${taskId}`, { token: token! });
            if (res.ok && res.data) {
                setGlobalProgress(res.data);
                if (res.data.status === "completed" || res.data.status === "failed") {
                    return true;
                }
            } else {
                return true; // Stop on error
            }
            return false;
        };

        const firstStop = await poll();
        if (firstStop) {
            setGlobalJoining(false);
            return;
        }

        const interval = setInterval(async () => {
            const stop = await poll();
            if (stop) {
                clearInterval(interval);
                setGlobalJoining(false);
            }
        }, 3000);
    };

    const handleGlobalSingleJoin = async () => {
        if (!globalSingleJoin.identifier) return;

        setGlobalSingleJoin(prev => ({ ...prev, joining: true }));
        const token = getToken("admin");
        const res = await api<any>("/admin/markets/global-join-anything", {
            method: "POST",
            token: token!,
            body: { identifier: globalSingleJoin.identifier }
        });

        if (res.ok && res.data?.task_id) {
            setShowGlobalModal(true);
            setGlobalProgress({
                status: "running",
                progress: 0,
                total: accounts.length,
                message: `Targeting: ${globalSingleJoin.identifier}`,
                logs: ["> Broadcaster ready.", `> Stream ID: ${res.data.task_id}`, "> Synchronizing all accounts..."]
            });
            startGlobalPolling(res.data.task_id);
            setGlobalSingleJoin({ identifier: "", joining: false });
        } else {
            const errMsg = res.data?.message || res.error || "Failed to broadcast";
            alert(`🛰️ Broadcast Error: ${errMsg}`);
            setGlobalSingleJoin(prev => ({ ...prev, joining: false }));
        }
    };

    const handleBulkGlobalJoin = () => {
        setShowBulkGlobalModal(true);
    };

    const executeBulkGlobalJoin = async () => {
        if (!bulkGlobalLinks || (!bulkSelectedAccount && !bulkUseAllAccounts)) return;
        const linksArr = bulkGlobalLinks.split('\n').map(l => l.trim()).filter(l => l);

        if (linksArr.length === 0) {
            alert("No valid links provided.");
            return;
        }

        setBulkGlobalJoining(true);
        const token = getToken("admin");
        const res = await api<any>("/admin/markets/bulk-global-join", {
            method: "POST",
            token: token!,
            body: {
                account_id: bulkUseAllAccounts ? null : parseInt(bulkSelectedAccount),
                urls: linksArr,
                use_all_accounts: bulkUseAllAccounts
            }
        });

        if (res.ok && res.data?.task_id) {
            setBulkGlobalProgress({
                status: "running",
                progress: 0,
                total: linksArr.length,
                message: bulkUseAllAccounts ? `Initializing global bulk join...` : "Initializing bulk join...",
                logs: ["> System ready.", `> Task ID: ${res.data.task_id}`, "> Starting bulk join sequence..."]
            });
            startBulkGlobalPolling(res.data.task_id);
        } else {
            const errMsg = res.data?.message || res.error || "Failed to start bulk join";
            alert(`❌ Error: ${errMsg}`);
            setBulkGlobalJoining(false);
        }
    };

    const startBulkGlobalPolling = async (taskId: string) => {
        const token = getToken("admin");

        const poll = async () => {
            const res = await api<any>(`/admin/markets/bulk-global-join/status/${taskId}`, { token: token! });
            if (res.ok && res.data) {
                setBulkGlobalProgress(res.data);
                if (res.data.status === "completed" || res.data.status === "failed") {
                    return true;
                }
            } else {
                return true;
            }
            return false;
        };

        const interval = setInterval(async () => {
            const stop = await poll();
            if (stop) {
                clearInterval(interval);
                setBulkGlobalJoining(false);
            }
        }, 3000);
    };

    const startPollingStatus = (accId: number) => {
        const interval = setInterval(async () => {
            const token = getToken("admin");
            const res = await api<any>(`/admin/accounts/${accId}/join-folders/status`, { token: token! });
            if (res.ok && res.data) {
                setNuclear(prev => ({ ...prev, progress: res.data }));
                if (res.data.status === "completed" || res.data.status === "failed") {
                    clearInterval(interval);
                    setNuclear(prev => ({ ...prev, running: false }));
                }
            }
        }, 2000);
    };

    if (loading) return <div className="loading-screen">SYNCING CORE ACCOUNTS...</div>;

    return (
        <>
            <Sidebar userType="admin" />
            <main className="main-content">
                <div className="page-header">
                    <div>
                        <h1 className="page-title">Markets</h1>
                        <p className="page-subtitle">Mass management and market expansion protocols</p>
                    </div>
                    <button
                        className="btn-danger"
                        onClick={handleGlobalJoin}
                        disabled={globalJoining}
                        style={{
                            background: "rgba(6, 182, 212, 0.1)",
                            borderColor: "#06b6d4",
                            color: "#22d3ee",
                            boxShadow: "0 0 15px rgba(6, 182, 212, 0.2)",
                            marginRight: "1rem"
                        }}
                    >
                        {globalJoining ? "CORE ACTIVE..." : "🚀 GLOBAL JOINER"}
                    </button>
                    <button
                        className="btn-primary"
                        onClick={handleBulkGlobalJoin}
                        disabled={bulkGlobalJoining}
                        style={{
                            background: "rgba(168, 85, 247, 0.1)",
                            borderColor: "#a855f7",
                            color: "#d8b4fe",
                            boxShadow: "0 0 15px rgba(168, 85, 247, 0.2)"
                        }}
                    >
                        {bulkGlobalJoining ? "JOINING..." : "📦 BULK GLOBAL"}
                    </button>
                </div>

                {/* Global Single Joiner Card */}
                <div className="glass-card" style={{ marginBottom: "2rem", border: "1px solid rgba(6, 182, 212, 0.2)" }}>
                    <h2 style={{ fontSize: "1.125rem", color: "white", marginBottom: "1rem" }}>🌍 Global Broadcast Join</h2>
                    <p style={{ fontSize: "0.875rem", color: "#9ca3af", marginBottom: "1rem" }}>
                        Join a single chat, channel, or folder across <b>all</b> active accounts with one command.
                    </p>
                    <div style={{ display: "flex", gap: "1rem" }}>
                        <input
                            className="input-field"
                            placeholder="@username, t.me link, or folder link"
                            value={globalSingleJoin.identifier}
                            onChange={(e) => setGlobalSingleJoin({ ...globalSingleJoin, identifier: e.target.value })}
                        />
                        <button
                            className="btn-primary"
                            disabled={!globalSingleJoin.identifier || globalSingleJoin.joining}
                            onClick={handleGlobalSingleJoin}
                            style={{ whiteSpace: "nowrap" }}
                        >
                            {globalSingleJoin.joining ? "TRANSMITTING..." : "BROADCAST JOIN"}
                        </button>
                    </div>
                </div>

                <div className="glass-card" style={{ marginBottom: "2rem" }}>
                    <h2 style={{ fontSize: "1.125rem", color: "white", marginBottom: "1rem" }}>Target Account</h2>
                    <select
                        className="input-field"
                        value={selectedAccount}
                        onChange={(e) => setSelectedAccount(e.target.value)}
                    >
                        <option value="">-- SELECT COMMAND TARGET --</option>
                        {accounts.map(acc => (
                            <option key={acc.id} value={acc.id}>
                                {acc.display_name} ({acc.phone_number})
                            </option>
                        ))}
                    </select>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2rem" }}>
                    <div className="glass-card">
                        <h2 style={{ fontSize: "1.125rem", color: "white", marginBottom: "1.5rem" }}>Direct Connection</h2>
                        <div style={{ marginBottom: "2rem" }}>
                            <label className="input-label">Individual Chat/Channel</label>
                            <div style={{ display: "flex", gap: "0.5rem" }}>
                                <input
                                    className="input-field"
                                    placeholder="@username or t.me link"
                                    value={joinChat.identifier}
                                    onChange={(e) => setJoinChat({ ...joinChat, identifier: e.target.value })}
                                />
                                <button
                                    className="btn-primary"
                                    disabled={!selectedAccount || joinChat.joining}
                                    onClick={handleJoinChat}
                                >
                                    {joinChat.joining ? "..." : "JOIN"}
                                </button>
                            </div>
                        </div>

                        <div>
                            <label className="input-label">Individual Folder</label>
                            <div style={{ display: "flex", gap: "0.5rem" }}>
                                <input
                                    className="input-field"
                                    placeholder="https://t.me/addlist/..."
                                    value={joinFolder.link}
                                    onChange={(e) => setJoinFolder({ ...joinFolder, link: e.target.value })}
                                />
                                <button
                                    className="btn-primary"
                                    disabled={!selectedAccount || joinFolder.joining}
                                    onClick={handleJoinFolder}
                                >
                                    {joinFolder.joining ? "..." : "JOIN"}
                                </button>
                            </div>
                        </div>
                    </div>

                    <div className="glass-card" style={{ border: "1px solid rgba(239, 68, 68, 0.2)" }}>
                        <h3 style={{ color: "#ef4444", marginBottom: "1rem", fontWeight: "700" }}>☢️ NUCLEAR PROTOCOL</h3>
                        <p style={{ fontSize: "0.85rem", color: "#9ca3af", marginBottom: "1rem" }}>
                            Wipe all existing chats and join multiple folders in a bulk sequence.
                        </p>

                        <textarea
                            className="input-field"
                            rows={8}
                            placeholder="Paste folder links here..."
                            value={nuclear.links}
                            onChange={(e) => setNuclear({ ...nuclear, links: e.target.value })}
                            style={{ fontFamily: "monospace", fontSize: "0.8rem" }}
                        />

                        <button
                            className="btn-danger"
                            style={{ width: "100%", marginTop: "1rem" }}
                            disabled={!selectedAccount || nuclear.running}
                            onClick={handleNuclearJoin}
                        >
                            {nuclear.running ? "NUCLEAR ACTIVE..." : "EXECUTE NUCLEAR SEQUENCE"}
                        </button>

                        {nuclear.progress && (
                            <div style={{ marginTop: "1.5rem", padding: "1rem", background: "rgba(0,0,0,0.3)", borderRadius: "8px", border: "1px solid rgba(239, 68, 68, 0.1)" }}>
                                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                                    <span style={{ color: "white", fontSize: "0.8rem" }}>{nuclear.progress.message}</span>
                                    <span style={{ color: "#ef4444", fontSize: "0.8rem" }}>{nuclear.progress.progress}/{nuclear.progress.total}</span>
                                </div>
                                <div style={{ height: "4px", background: "rgba(255,255,255,0.05)", borderRadius: "2px", overflow: "hidden" }}>
                                    <div style={{
                                        height: "100%",
                                        background: "#ef4444",
                                        width: `${(nuclear.progress.progress / nuclear.progress.total) * 100}%`,
                                        transition: "width 0.3s ease"
                                    }} />
                                </div>
                                {nuclear.progress.logs && (
                                    <div style={{ marginTop: "0.75rem", maxHeight: "100px", overflowY: "auto", fontSize: "0.7rem", color: "#9ca3af", fontFamily: "monospace" }}>
                                        {nuclear.progress.logs.map((l: string, i: number) => <div key={i}>{l}</div>)}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>

                {/* Global Joiner Modal */}
                {showGlobalModal && (
                    <div style={{
                        position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
                        backgroundColor: "rgba(0, 0, 0, 0.9)", backdropFilter: "blur(12px)",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        zIndex: 1000, animation: "fadeIn 0.2s ease-out"
                    }}>
                        <div className="glass-card" style={{
                            width: "90%", maxWidth: "650px",
                            border: "1px solid rgba(6, 182, 212, 0.3)",
                            boxShadow: "0 0 50px rgba(6, 182, 212, 0.15)",
                            position: "relative", padding: "2.5rem"
                        }}>
                            <div style={{ marginBottom: "2rem" }}>
                                <h2 style={{ fontSize: "1.75rem", color: "white", marginBottom: "0.5rem", fontWeight: "900", background: "linear-gradient(to right, #22d3ee, #06b6d4)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
                                    CORE SEQUENCE
                                </h2>
                                <p style={{ color: "#9ca3af", fontSize: "0.9rem" }}>
                                    Global broadcasing and massive account synchronization protocol.
                                </p>
                            </div>

                            {!globalProgress ? (
                                <>
                                    <label className="input-label" style={{ color: "#22d3ee", fontWeight: "600" }}>FOLDER QUEUE (ONE PER LINE)</label>
                                    <textarea
                                        className="input-field" rows={10}
                                        placeholder="https://t.me/addlist/..."
                                        value={globalLinks}
                                        onChange={(e) => setGlobalLinks(e.target.value)}
                                        style={{ fontFamily: "monospace", fontSize: "0.9rem", marginBottom: "2rem", backgroundColor: "rgba(0,0,0,0.4)" }}
                                    />
                                </>
                            ) : (
                                <div style={{ marginBottom: "2rem" }}>
                                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.75rem", alignItems: "baseline" }}>
                                        <span style={{ color: "#22d3ee", fontSize: "0.9rem", fontWeight: "700", textTransform: "uppercase" }}>
                                            {globalProgress.status === "completed" ? "🏁 PROTOCOL FINISHED" : "⚡ STREAMING DATA"}
                                        </span>
                                        <span style={{ color: "white", fontSize: "0.85rem", fontFamily: "monospace" }}>
                                            [{globalProgress.progress}/{globalProgress.total}] SYNCED
                                        </span>
                                    </div>
                                    <div style={{ height: "8px", backgroundColor: "rgba(255,255,255,0.05)", borderRadius: "10px", overflow: "hidden", marginBottom: "1.5rem", border: "1px solid rgba(6, 182, 212, 0.2)" }}>
                                        <div style={{ width: `${(globalProgress.progress / globalProgress.total) * 100}%`, height: "100%", backgroundColor: "#22d3ee", boxShadow: "0 0 15px #22d3ee", transition: "width 0.5s ease-out" }} />
                                    </div>
                                    <div style={{ backgroundColor: "rgba(0,0,0,0.6)", borderRadius: "12px", padding: "1.25rem", height: "250px", overflowY: "auto", fontSize: "0.85rem", fontFamily: "monospace", border: "1px solid rgba(255,255,255,0.05)" }}>
                                        {globalProgress.logs && globalProgress.logs.map((log: string, idx: number) => (
                                            <div key={idx} style={{ color: log.includes("✅") ? "#4ade80" : log.includes("❌") ? "#f87171" : "#9ca3af", marginBottom: "0.5rem", display: "flex", gap: "0.75rem" }}>
                                                <span style={{ color: "rgba(6, 182, 212, 0.4)" }}>[{idx.toString().padStart(3, '0')}]</span>
                                                <span style={{ wordBreak: "break-all" }}>{log}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            <div style={{ display: "flex", gap: "1rem" }}>
                                <button className="btn-primary" style={{ flex: 1, backgroundColor: "transparent", border: "1px solid rgba(255,255,255,0.1)", color: "#9ca3af" }}
                                    onClick={() => { setShowGlobalModal(false); setGlobalProgress(null); setGlobalJoining(false); }}>
                                    {globalProgress?.status === "completed" ? "DISMISS" : "CANCEL"}
                                </button>
                                {!globalProgress && (
                                    <button className="btn-primary" style={{ flex: 2, background: "linear-gradient(135deg, #06b6d4 0%, #0891b2 100%)", fontWeight: "800" }}
                                        disabled={!globalLinks || globalJoining} onClick={executeGlobalJoin}>
                                        {globalJoining ? "INIT..." : "LAUNCH SEQUENCE"}
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                )}

                {/* Bulk Global Modal */}
                {showBulkGlobalModal && (
                    <div style={{
                        position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
                        backgroundColor: "rgba(0, 0, 0, 0.9)", backdropFilter: "blur(12px)",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        zIndex: 1000, animation: "fadeIn 0.2s ease-out"
                    }}>
                        <div className="glass-card" style={{
                            width: "90%", maxWidth: "650px",
                            border: "1px solid rgba(168, 85, 247, 0.3)",
                            boxShadow: "0 0 50px rgba(168, 85, 247, 0.15)",
                            position: "relative", padding: "2.5rem"
                        }}>
                            <div style={{ marginBottom: "2rem" }}>
                                <h2 style={{ fontSize: "1.75rem", color: "white", marginBottom: "0.5rem", fontWeight: "900", background: "linear-gradient(to right, #22d3ee, #a855f7)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
                                    BULK GLOBAL JOINER
                                </h2>
                                <p style={{ color: "#9ca3af", fontSize: "0.9rem" }}>
                                    Mass join sequence for single account.
                                </p>
                            </div>

                            {!bulkGlobalProgress ? (
                                <>
                                    <div style={{ marginBottom: "1.5rem" }}>
                                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                                            <label className="input-label" style={{ color: "#d8b4fe", fontWeight: "600", marginBottom: 0 }}>SELECT ACCOUNT</label>
                                            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
                                                <input
                                                    type="checkbox"
                                                    checked={bulkUseAllAccounts}
                                                    onChange={(e) => setBulkUseAllAccounts(e.target.checked)}
                                                    style={{ accentColor: "#a855f7" }}
                                                />
                                                <span style={{ color: "white", fontSize: "0.85rem", fontWeight: "600" }}>TARGET ALL ACCOUNTS</span>
                                            </label>
                                        </div>
                                        <select
                                            className="input-field"
                                            value={bulkSelectedAccount}
                                            onChange={(e) => setBulkSelectedAccount(e.target.value)}
                                            disabled={bulkUseAllAccounts}
                                            style={{ opacity: bulkUseAllAccounts ? 0.5 : 1, cursor: bulkUseAllAccounts ? "not-allowed" : "pointer" }}
                                        >
                                            <option value="">-- SELECT ACCOUNT --</option>
                                            {accounts.map(acc => (
                                                <option key={acc.id} value={acc.id}>
                                                    {acc.display_name} ({acc.phone_number})
                                                </option>
                                            ))}
                                        </select>
                                    </div>
                                    <label className="input-label" style={{ color: "#d8b4fe", fontWeight: "600" }}>GROUP URLS (ONE PER LINE)</label>
                                    <textarea
                                        className="input-field" rows={10}
                                        placeholder="https://t.me/..."
                                        value={bulkGlobalLinks}
                                        onChange={(e) => setBulkGlobalLinks(e.target.value)}
                                        style={{ fontFamily: "monospace", fontSize: "0.9rem", marginBottom: "2rem", backgroundColor: "rgba(0,0,0,0.4)" }}
                                    />
                                </>
                            ) : (
                                <div style={{ marginBottom: "2rem" }}>
                                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.75rem", alignItems: "baseline" }}>
                                        <span style={{ color: "#d8b4fe", fontSize: "0.9rem", fontWeight: "700", textTransform: "uppercase" }}>
                                            {bulkGlobalProgress.status === "completed" ? "🏁 SEQUENCE FINISHED" : "⚡ PROCESSING"}
                                        </span>
                                        <span style={{ color: "white", fontSize: "0.85rem", fontFamily: "monospace" }}>
                                            [{bulkGlobalProgress.progress}/{bulkGlobalProgress.total}] JOINED
                                        </span>
                                    </div>
                                    <div style={{ height: "8px", backgroundColor: "rgba(255,255,255,0.05)", borderRadius: "10px", overflow: "hidden", marginBottom: "1.5rem", border: "1px solid rgba(168, 85, 247, 0.2)" }}>
                                        <div style={{ width: `${(bulkGlobalProgress.progress / bulkGlobalProgress.total) * 100}%`, height: "100%", backgroundColor: "#a855f7", boxShadow: "0 0 15px #a855f7", transition: "width 0.5s ease-out" }} />
                                    </div>
                                    <div style={{ backgroundColor: "rgba(0,0,0,0.6)", borderRadius: "12px", padding: "1.25rem", height: "250px", overflowY: "auto", fontSize: "0.85rem", fontFamily: "monospace", border: "1px solid rgba(255,255,255,0.05)" }}>
                                        {bulkGlobalProgress.logs && bulkGlobalProgress.logs.map((log: string, idx: number) => (
                                            <div key={idx} style={{ color: log.includes("Joined") ? "#4ade80" : log.includes("Failed") ? "#f87171" : "#9ca3af", marginBottom: "0.5rem", display: "flex", gap: "0.75rem" }}>
                                                <span style={{ color: "rgba(168, 85, 247, 0.4)" }}>[{idx.toString().padStart(3, '0')}]</span>
                                                <span style={{ wordBreak: "break-all" }}>{log}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            <div style={{ display: "flex", gap: "1rem" }}>
                                <button className="btn-primary" style={{ flex: 1, backgroundColor: "transparent", border: "1px solid rgba(255,255,255,0.1)", color: "#9ca3af" }}
                                    onClick={() => { setShowBulkGlobalModal(false); setBulkGlobalProgress(null); setBulkGlobalJoining(false); }}>
                                    {bulkGlobalProgress?.status === "completed" ? "DISMISS" : "CANCEL"}
                                </button>
                                {!bulkGlobalProgress && (
                                    <button className="btn-primary" style={{ flex: 2, background: "linear-gradient(135deg, #a855f7 0%, #7c3aed 100%)", fontWeight: "800" }}
                                        disabled={!bulkGlobalLinks || (!bulkSelectedAccount && !bulkUseAllAccounts) || bulkGlobalJoining} onClick={executeBulkGlobalJoin}>
                                        {bulkGlobalJoining ? "STARTING..." : (bulkUseAllAccounts ? "START GLOBAL BULK JOIN" : "START BULK JOIN")}
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                )}
            </main>

            <style jsx>{`
                @keyframes fadeIn { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }
                .input-label { display: block; color: #9ca3af; font-size: 0.875rem; margin-bottom: 0.5rem; }
                select.input-field {
                    appearance: none;
                    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%239ca3af'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'%3E%3C/path%3E%3C/svg%3E");
                    background-repeat: no-repeat;
                    background-position: right 1rem center;
                    background-size: 1.25rem;
                    padding-right: 3rem;
                }
                .loading-screen { min-height: 100vh; display: flex; align-items: center; justify-content: center; color: #22d3ee; font-size: 1.25rem; letter-spacing: 2px; font-family: monospace; }
            `}</style>
        </>
    );
}
