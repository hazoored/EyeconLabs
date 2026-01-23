"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { api, getToken } from "@/lib/api";

type Step = "phone" | "code" | "2fa" | "success";

interface Client {
    id: number;
    name: string;
}

export default function SessionGeneratorPage() {
    const router = useRouter();
    const [step, setStep] = useState<Step>("phone");
    const [phone, setPhone] = useState("");
    const [code, setCode] = useState("");
    const [password, setPassword] = useState("");
    const [sessionString, setSessionString] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [clients, setClients] = useState<Client[]>([]);
    const [selectedClient, setSelectedClient] = useState<number>(0);
    const [displayName, setDisplayName] = useState("");

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
        if (response.ok) {
            setClients(response.data?.clients || []);
        }
    };

    const handleSendCode = async () => {
        setError("");
        setLoading(true);

        const response = await api<{ success: boolean; message: string }>("/session/send-code", {
            method: "POST",
            body: { phone_number: phone },
        });

        setLoading(false);

        if (response.ok && response.data?.success) {
            setStep("code");
        } else {
            setError(response.data?.message || response.error || "Failed to send code");
        }
    };

    const handleVerifyCode = async () => {
        setError("");
        setLoading(true);

        const response = await api<{
            success: boolean;
            message: string;
            session_string?: string;
            requires_2fa?: boolean;
        }>("/session/verify-code", {
            method: "POST",
            body: { phone_number: phone, code, password: password || undefined },
        });

        setLoading(false);

        if (response.ok && response.data?.success && response.data.session_string) {
            setSessionString(response.data.session_string);
            setStep("success");
        } else if (response.data?.requires_2fa) {
            setStep("2fa");
        } else {
            setError(response.data?.message || response.error || "Verification failed");
        }
    };

    const handleAddAccount = async () => {
        const token = getToken("admin");
        if (!token) return;

        setLoading(true);
        const response = await api("/admin/accounts", {
            method: "POST",
            body: {
                client_id: selectedClient || null,  // null = add to pool without client
                phone_number: phone,
                session_string: sessionString,
                display_name: displayName || undefined,
            },
            token,
        });

        setLoading(false);

        if (response.ok) {
            router.push("/admin/accounts");
        } else {
            setError(response.error || "Failed to add account");
        }
    };

    const reset = () => {
        setStep("phone");
        setPhone("");
        setCode("");
        setPassword("");
        setSessionString("");
        setError("");
    };

    return (
        <div style={{ display: "flex" }}>
            <Sidebar userType="admin" />

            <main style={{ marginLeft: "16rem", flex: 1, padding: "2rem", minHeight: "100vh" }}>
                <div style={{ marginBottom: "2rem" }}>
                    <h1 style={{ fontSize: "1.875rem", fontWeight: 700, color: "white" }}>
                        Session Generator
                    </h1>
                    <p style={{ color: "#9ca3af", marginTop: "0.25rem" }}>
                        Generate Telethon session strings for Telegram accounts
                    </p>
                </div>

                <div className="glass-card" style={{ maxWidth: "32rem" }}>
                    {/* Step 1: Phone Number */}
                    {step === "phone" && (
                        <div>
                            <h2 style={{ fontSize: "1.25rem", fontWeight: 600, color: "white", marginBottom: "1rem" }}>
                                Step 1: Enter Phone Number
                            </h2>
                            <div style={{ marginBottom: "1rem" }}>
                                <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>
                                    Phone Number (with country code)
                                </label>
                                <input
                                    type="text"
                                    value={phone}
                                    onChange={(e) => setPhone(e.target.value)}
                                    className="input-field"
                                    placeholder="+1234567890"
                                />
                            </div>
                            {error && (
                                <div style={{ color: "#f87171", background: "rgba(239,68,68,0.1)", padding: "0.75rem", borderRadius: "0.5rem", marginBottom: "1rem", fontSize: "0.875rem" }}>
                                    {error}
                                </div>
                            )}
                            <button onClick={handleSendCode} disabled={loading || !phone} className="btn-primary" style={{ width: "100%" }}>
                                {loading ? "Sending..." : "Send Code"}
                            </button>
                        </div>
                    )}

                    {/* Step 2: Verify Code */}
                    {step === "code" && (
                        <div>
                            <h2 style={{ fontSize: "1.25rem", fontWeight: 600, color: "white", marginBottom: "1rem" }}>
                                Step 2: Enter Verification Code
                            </h2>
                            <p style={{ color: "#9ca3af", marginBottom: "1rem", fontSize: "0.875rem" }}>
                                Check your Telegram app for the code
                            </p>
                            <div style={{ marginBottom: "1rem" }}>
                                <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>
                                    Verification Code
                                </label>
                                <input
                                    type="text"
                                    value={code}
                                    onChange={(e) => setCode(e.target.value)}
                                    className="input-field"
                                    placeholder="12345"
                                    style={{ textAlign: "center", fontSize: "1.5rem", letterSpacing: "0.5rem" }}
                                />
                            </div>
                            {error && (
                                <div style={{ color: "#f87171", background: "rgba(239,68,68,0.1)", padding: "0.75rem", borderRadius: "0.5rem", marginBottom: "1rem", fontSize: "0.875rem" }}>
                                    {error}
                                </div>
                            )}
                            <div style={{ display: "flex", gap: "0.75rem" }}>
                                <button onClick={reset} className="btn-secondary" style={{ flex: 1 }}>
                                    Back
                                </button>
                                <button onClick={handleVerifyCode} disabled={loading || !code} className="btn-primary" style={{ flex: 1 }}>
                                    {loading ? "Verifying..." : "Verify"}
                                </button>
                            </div>
                        </div>
                    )}

                    {/* Step 2.5: 2FA Password */}
                    {step === "2fa" && (
                        <div>
                            <h2 style={{ fontSize: "1.25rem", fontWeight: 600, color: "white", marginBottom: "1rem" }}>
                                Two-Factor Authentication
                            </h2>
                            <p style={{ color: "#9ca3af", marginBottom: "1rem", fontSize: "0.875rem" }}>
                                This account has 2FA enabled. Enter your password.
                            </p>
                            <div style={{ marginBottom: "1rem" }}>
                                <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>
                                    2FA Password
                                </label>
                                <input
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="input-field"
                                    placeholder="Your 2FA password"
                                />
                            </div>
                            {error && (
                                <div style={{ color: "#f87171", background: "rgba(239,68,68,0.1)", padding: "0.75rem", borderRadius: "0.5rem", marginBottom: "1rem", fontSize: "0.875rem" }}>
                                    {error}
                                </div>
                            )}
                            <button onClick={handleVerifyCode} disabled={loading || !password} className="btn-primary" style={{ width: "100%" }}>
                                {loading ? "Verifying..." : "Submit Password"}
                            </button>
                        </div>
                    )}

                    {/* Step 3: Success */}
                    {step === "success" && (
                        <div>
                            <h2 style={{ fontSize: "1.25rem", fontWeight: 600, color: "#4ade80", marginBottom: "1rem" }}>
                                ✅ Session Generated!
                            </h2>

                            <div style={{ marginBottom: "1.5rem" }}>
                                <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>
                                    Session String
                                </label>
                                <textarea
                                    readOnly
                                    value={sessionString}
                                    className="input-field"
                                    rows={4}
                                    style={{ fontFamily: "monospace", fontSize: "0.75rem" }}
                                />
                            </div>

                            <div style={{ borderTop: "1px solid rgba(255,255,255,0.1)", paddingTop: "1.5rem" }}>
                                <h3 style={{ color: "white", marginBottom: "1rem" }}>Add to Account Pool</h3>

                                <div style={{ marginBottom: "1rem" }}>
                                    <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>
                                        Assign to Client (Optional)
                                    </label>
                                    <select
                                        value={selectedClient}
                                        onChange={(e) => setSelectedClient(parseInt(e.target.value))}
                                        className="input-field"
                                    >
                                        <option value={0}>➜ Add to Pool (assign later)</option>
                                        {clients.map((c) => (
                                            <option key={c.id} value={c.id}>{c.name}</option>
                                        ))}
                                    </select>
                                    <p style={{ color: "#6b7280", fontSize: "0.75rem", marginTop: "0.25rem" }}>
                                        Leave empty to add to unassigned pool
                                    </p>
                                </div>

                                <div style={{ marginBottom: "1rem" }}>
                                    <label style={{ display: "block", fontSize: "0.875rem", color: "#9ca3af", marginBottom: "0.5rem" }}>
                                        Display Name (optional)
                                    </label>
                                    <input
                                        type="text"
                                        value={displayName}
                                        onChange={(e) => setDisplayName(e.target.value)}
                                        className="input-field"
                                        placeholder="Account nickname"
                                    />
                                </div>

                                {error && (
                                    <div style={{ color: "#f87171", background: "rgba(239,68,68,0.1)", padding: "0.75rem", borderRadius: "0.5rem", marginBottom: "1rem", fontSize: "0.875rem" }}>
                                        {error}
                                    </div>
                                )}

                                <div style={{ display: "flex", gap: "0.75rem" }}>
                                    <button onClick={reset} className="btn-secondary" style={{ flex: 1 }}>
                                        Generate Another
                                    </button>
                                    <button onClick={handleAddAccount} disabled={loading} className="btn-primary" style={{ flex: 1 }}>
                                        {loading ? "Adding..." : selectedClient ? "Add to Client" : "Add to Pool"}
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}
