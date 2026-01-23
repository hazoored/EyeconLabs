"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { api, getToken } from "@/lib/api";

interface DashboardData {
    analytics: {
        total_clients: number;
        total_accounts: number;
        total_campaigns: number;
        active_campaigns: number;
        today: {
            today_broadcasts: number;
            today_success: number;
            today_failed: number;
        };
    };
    recent_clients: Array<{
        id: number;
        name: string;
        access_token: string;
        subscription_type: string;
        is_active: number;
        created_at: string;
    }>;
}

export default function AdminDashboardPage() {
    const router = useRouter();
    const [data, setData] = useState<DashboardData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        const token = getToken("admin");
        if (!token) {
            router.push("/admin/login");
            return;
        }

        fetchDashboard(token);
    }, [router]);

    const fetchDashboard = async (token: string) => {
        const response = await api<DashboardData>("/admin/dashboard", { token });
        setLoading(false);

        if (!response.ok) {
            if (response.error?.includes("Invalid") || response.error?.includes("expired")) {
                router.push("/admin/login");
            }
            setError(response.error || "Failed to load dashboard");
            return;
        }

        setData(response.data || null);
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
                        <h1 className="page-title">Dashboard</h1>
                        <p className="page-subtitle">Welcome back, Admin</p>
                    </div>
                </div>

                {error && (
                    <div style={{ background: "rgba(239,68,68,0.1)", color: "#f87171", padding: "0.75rem 1rem", borderRadius: "0.5rem", marginBottom: "1.5rem" }}>
                        {error}
                    </div>
                )}

                {/* Stats Grid */}
                <div className="stats-grid">
                    <div className="glass-card">
                        <div className="stat-value">{data?.analytics.total_clients || 0}</div>
                        <div className="stat-label">Total Clients</div>
                    </div>
                    <div className="glass-card">
                        <div className="stat-value">{data?.analytics.total_accounts || 0}</div>
                        <div className="stat-label">Total Accounts</div>
                    </div>
                    <div className="glass-card">
                        <div className="stat-value">{data?.analytics.total_campaigns || 0}</div>
                        <div className="stat-label">Total Campaigns</div>
                    </div>
                    <div className="glass-card">
                        <div className="stat-value" style={{ color: "#4ade80" }}>{data?.analytics.active_campaigns || 0}</div>
                        <div className="stat-label">Active Campaigns</div>
                    </div>
                </div>

                {/* Today's Stats */}
                <div className="glass-card" style={{ marginBottom: "1.5rem" }}>
                    <h2 style={{ fontSize: "1.125rem", fontWeight: 600, color: "white", marginBottom: "1rem" }}>Today&apos;s Activity</h2>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1rem" }}>
                        <div style={{ textAlign: "center" }}>
                            <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#22d3ee" }}>
                                {data?.analytics.today?.today_broadcasts || 0}
                            </div>
                            <div style={{ fontSize: "0.75rem", color: "#9ca3af" }}>Broadcasts</div>
                        </div>
                        <div style={{ textAlign: "center" }}>
                            <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#4ade80" }}>
                                {data?.analytics.today?.today_success || 0}
                            </div>
                            <div style={{ fontSize: "0.75rem", color: "#9ca3af" }}>Successful</div>
                        </div>
                        <div style={{ textAlign: "center" }}>
                            <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#f87171" }}>
                                {data?.analytics.today?.today_failed || 0}
                            </div>
                            <div style={{ fontSize: "0.75rem", color: "#9ca3af" }}>Failed</div>
                        </div>
                    </div>
                </div>

                {/* Recent Clients */}
                <div className="glass-card">
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "0.5rem" }}>
                        <h2 style={{ fontSize: "1.125rem", fontWeight: 600, color: "white" }}>Recent Clients</h2>
                        <a href="/admin/clients" style={{ color: "#22d3ee", fontSize: "0.875rem" }}>
                            View all →
                        </a>
                    </div>

                    {data?.recent_clients && data.recent_clients.length > 0 ? (
                        <div className="responsive-table">
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Name</th>
                                        <th>Access Token</th>
                                        <th className="hide-mobile">Plan</th>
                                        <th>Status</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.recent_clients.map((client) => (
                                        <tr key={client.id}>
                                            <td style={{ color: "white", fontWeight: 500 }}>{client.name}</td>
                                            <td>
                                                <code style={{ background: "rgba(255,255,255,0.1)", padding: "0.25rem 0.5rem", borderRadius: "0.25rem", color: "#22d3ee" }}>
                                                    {client.access_token}
                                                </code>
                                            </td>
                                            <td className="hide-mobile capitalize">{client.subscription_type}</td>
                                            <td>
                                                <span className={`badge ${client.is_active ? "badge-success" : "badge-error"}`}>
                                                    {client.is_active ? "Active" : "Inactive"}
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    ) : (
                        <p style={{ color: "#9ca3af", textAlign: "center", padding: "2rem" }}>
                            No clients yet. Create your first client to get started.
                        </p>
                    )}
                </div>
            </main>
        </>
    );
}
