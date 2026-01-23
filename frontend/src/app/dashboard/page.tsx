"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { api, getToken } from "@/lib/api";

interface DashboardData {
    client: {
        id: number;
        name: string;
        subscription_type: string;
        expires_at: string | null;
    };
    stats: {
        total_accounts: number;
        total_campaigns: number;
        active_campaigns: number;
        totals: {
            total_broadcasts: number;
            successful_sends: number;
            failed_sends: number;
        };
    };
}

export default function ClientDashboardPage() {
    const router = useRouter();
    const [data, setData] = useState<DashboardData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        const token = getToken("client");
        if (!token) {
            router.push("/login");
            return;
        }

        fetchDashboard(token);
    }, [router]);

    const fetchDashboard = async (token: string) => {
        const response = await api<DashboardData>("/client/dashboard", { token });
        setLoading(false);

        if (!response.ok) {
            if (response.error?.includes("Invalid") || response.error?.includes("expired")) {
                router.push("/login");
            }
            setError(response.error || "Failed to load dashboard");
            return;
        }

        setData(response.data || null);
    };

    const formatDate = (dateStr: string | null) => {
        if (!dateStr) return "Never";
        const date = new Date(dateStr);
        return date.toLocaleDateString("en-US", {
            year: "numeric",
            month: "short",
            day: "numeric",
        });
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
                {/* Header */}
                <div className="page-header">
                    <div>
                        <h1 className="page-title">Welcome, {data?.client.name}!</h1>
                        <p className="page-subtitle">Your campaign performance at a glance</p>
                    </div>
                </div>

                {error && (
                    <div style={{ background: "rgba(239,68,68,0.1)", color: "#f87171", padding: "0.75rem 1rem", borderRadius: "0.5rem", marginBottom: "1.5rem" }}>
                        {error}
                    </div>
                )}

                {/* Subscription Info */}
                <div className="glass-card" style={{ marginBottom: "1.5rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
                        <div>
                            <span style={{ color: "#9ca3af", fontSize: "0.875rem" }}>Current Plan</span>
                            <h3 className="text-gradient" style={{ fontSize: "1.25rem", fontWeight: 700, textTransform: "capitalize" }}>
                                {data?.client.subscription_type} Plan
                            </h3>
                        </div>
                        <div style={{ textAlign: "right" }}>
                            <span style={{ color: "#9ca3af", fontSize: "0.875rem" }}>Expires</span>
                            <p style={{ color: "white", fontWeight: 500 }}>
                                {formatDate(data?.client.expires_at || null)}
                            </p>
                        </div>
                    </div>
                </div>

                {/* Stats Grid */}
                <div className="stats-grid">
                    <div className="glass-card">
                        <div className="stat-value">{data?.stats.total_accounts || 0}</div>
                        <div className="stat-label">Connected Accounts</div>
                    </div>
                    <div className="glass-card">
                        <div className="stat-value">{data?.stats.total_campaigns || 0}</div>
                        <div className="stat-label">Total Campaigns</div>
                    </div>
                    <div className="glass-card">
                        <div className="stat-value" style={{ color: "#4ade80" }}>{data?.stats.active_campaigns || 0}</div>
                        <div className="stat-label">Active Campaigns</div>
                    </div>
                    <div className="glass-card">
                        <div className="stat-value">{data?.stats.totals?.total_broadcasts || 0}</div>
                        <div className="stat-label">Total Broadcasts</div>
                    </div>
                </div>

                {/* Performance Summary */}
                <div className="glass-card">
                    <h2 style={{ fontSize: "1.125rem", fontWeight: 600, color: "white", marginBottom: "1rem" }}>
                        Overall Performance
                    </h2>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: "0.5rem" }}>
                        <div style={{ textAlign: "center", padding: "1rem 0.5rem", borderRadius: "0.5rem", background: "rgba(255,255,255,0.05)", overflow: "hidden" }}>
                            <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "#22d3ee" }}>
                                {data?.stats.totals?.total_broadcasts || 0}
                            </div>
                            <div style={{ fontSize: "0.65rem", color: "#9ca3af", marginTop: "0.25rem" }}>Broadcasts</div>
                        </div>
                        <div style={{ textAlign: "center", padding: "1rem 0.5rem", borderRadius: "0.5rem", background: "rgba(255,255,255,0.05)", overflow: "hidden" }}>
                            <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "#4ade80" }}>
                                {data?.stats.totals?.successful_sends || 0}
                            </div>
                            <div style={{ fontSize: "0.65rem", color: "#9ca3af", marginTop: "0.25rem" }}>Successful</div>
                        </div>
                        <div style={{ textAlign: "center", padding: "1rem 0.5rem", borderRadius: "0.5rem", background: "rgba(255,255,255,0.05)", overflow: "hidden" }}>
                            <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "#f87171" }}>
                                {data?.stats.totals?.failed_sends || 0}
                            </div>
                            <div style={{ fontSize: "0.65rem", color: "#9ca3af", marginTop: "0.25rem" }}>Failed</div>
                        </div>
                    </div>

                    {/* Success Rate */}
                    <div style={{ marginTop: "1.5rem", paddingTop: "1.5rem", borderTop: "1px solid rgba(255,255,255,0.1)" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                            <span style={{ color: "#9ca3af" }}>Success Rate</span>
                            <span style={{ color: "white", fontWeight: 600 }}>
                                {data?.stats.totals?.total_broadcasts
                                    ? Math.round(
                                        ((data.stats.totals.successful_sends || 0) /
                                            data.stats.totals.total_broadcasts) *
                                        100
                                    )
                                    : 0}%
                            </span>
                        </div>
                        <div style={{ width: "100%", background: "rgba(255,255,255,0.1)", borderRadius: "9999px", height: "0.5rem" }}>
                            <div
                                style={{
                                    background: "linear-gradient(to right, #06b6d4, #a855f7)",
                                    height: "0.5rem",
                                    borderRadius: "9999px",
                                    transition: "width 0.5s",
                                    width: `${data?.stats.totals?.total_broadcasts
                                        ? ((data.stats.totals.successful_sends || 0) /
                                            data.stats.totals.total_broadcasts) *
                                        100
                                        : 0
                                        }%`,
                                }}
                            />
                        </div>
                    </div>
                </div>
            </main>
        </>
    );
}
