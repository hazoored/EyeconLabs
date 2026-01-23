"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { api, getToken } from "@/lib/api";

interface DailyData {
    date: string;
    total_broadcasts: number;
    successful_sends: number;
    failed_sends: number;
}

interface GroupData {
    group_name: string;
    total: number;
    successful: number;
    failed: number;
    error_message?: string;
}

interface AccountData {
    id: number;
    phone_number: string;
    display_name: string | null;
    total_sends: number;
    successful: number;
    failed: number;
    success_rate: number | null;
}

interface HourlyData {
    hour: string;
    total: number;
    successful: number;
    failed: number;
}

interface CampaignData {
    id: number;
    name: string;
    status: string;
    created_at: string;
    total_sends: number;
    successful: number;
    failed: number;
}

interface AnalyticsData {
    daily: DailyData[];
    totals: {
        total_broadcasts: number;
        successful_sends: number;
        failed_sends: number;
    };
    groups: {
        top_groups: GroupData[];
        problem_groups: GroupData[];
    };
    accounts: AccountData[];
    hourly: HourlyData[];
    campaigns: CampaignData[];
}

export default function ClientAnalyticsPage() {
    const router = useRouter();
    const [data, setData] = useState<AnalyticsData | null>(null);
    const [loading, setLoading] = useState(true);
    const [days, setDays] = useState(30);
    const [activeTab, setActiveTab] = useState<"overview" | "groups" | "accounts" | "campaigns">("overview");

    useEffect(() => {
        const token = getToken("client");
        if (!token) {
            router.push("/login");
            return;
        }
        fetchAnalytics(token);
    }, [router, days]);

    const fetchAnalytics = async (token: string) => {
        setLoading(true);
        const response = await api<AnalyticsData>(`/client/analytics?days=${days}`, { token });
        setLoading(false);
        if (response.ok) {
            setData(response.data || null);
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div style={{ color: "#22d3ee", fontSize: "1.25rem" }}>Loading analytics...</div>
            </div>
        );
    }

    const successRate = data?.totals.total_broadcasts
        ? Math.round((data.totals.successful_sends / data.totals.total_broadcasts) * 100)
        : 0;

    // Calculate trend (compare last 7 days to previous 7 days)
    const recentDays = data?.daily.slice(0, 7) || [];
    const recentSuccess = recentDays.reduce((sum, d) => sum + d.successful_sends, 0);
    const previousDays = data?.daily.slice(7, 14) || [];
    const previousSuccess = previousDays.reduce((sum, d) => sum + d.successful_sends, 0);
    const trend = previousSuccess > 0 ? Math.round(((recentSuccess - previousSuccess) / previousSuccess) * 100) : 0;

    // Get max value for chart scaling
    const maxDaily = Math.max(...(data?.daily.map(d => d.total_broadcasts) || [1]));

    return (
        <>
            <Sidebar userType="client" />

            <main className="main-content">
                <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
                    <div>
                        <h1 className="page-title">Analytics Dashboard</h1>
                        <p className="page-subtitle">Comprehensive broadcast performance insights</p>
                    </div>

                    {/* Period Filter */}
                    <div style={{ display: "flex", gap: "0.5rem" }}>
                        {[7, 30, 90].map(period => (
                            <button
                                key={period}
                                onClick={() => setDays(period)}
                                style={{
                                    padding: "0.5rem 1rem",
                                    borderRadius: "0.5rem",
                                    border: "none",
                                    cursor: "pointer",
                                    fontSize: "0.875rem",
                                    fontWeight: 500,
                                    background: days === period
                                        ? "linear-gradient(135deg, #22d3ee, #3b82f6)"
                                        : "rgba(255,255,255,0.1)",
                                    color: "white",
                                    transition: "all 0.2s"
                                }}
                            >
                                {period}D
                            </button>
                        ))}
                    </div>
                </div>

                {/* Summary Cards */}
                <div className="stats-grid" style={{ marginBottom: "1.5rem" }}>
                    <div className="glass-card card-glow" style={{ position: "relative", overflow: "hidden" }}>
                        <div style={{
                            position: "absolute",
                            top: 0,
                            right: 0,
                            width: "60px",
                            height: "60px",
                            background: "linear-gradient(135deg, rgba(34, 211, 238, 0.2), transparent)",
                            borderRadius: "0 0 0 100%"
                        }} />
                        <div className="stat-value">{data?.totals.total_broadcasts.toLocaleString() || 0}</div>
                        <div className="stat-label">Total Broadcasts</div>
                    </div>
                    <div className="glass-card card-glow">
                        <div className="stat-value" style={{ color: "#4ade80" }}>
                            {data?.totals.successful_sends.toLocaleString() || 0}
                        </div>
                        <div className="stat-label">Successful</div>
                        {trend !== 0 && (
                            <div style={{
                                fontSize: "0.75rem",
                                color: trend > 0 ? "#4ade80" : "#f87171",
                                marginTop: "0.25rem"
                            }}>
                                {trend > 0 ? "↑" : "↓"} {Math.abs(trend)}% vs last week
                            </div>
                        )}
                    </div>
                    <div className="glass-card card-glow">
                        <div className="stat-value" style={{ color: "#f87171" }}>
                            {data?.totals.failed_sends.toLocaleString() || 0}
                        </div>
                        <div className="stat-label">Failed</div>
                    </div>
                    <div className="glass-card card-glow">
                        <div className="stat-value" style={{
                            color: successRate >= 70 ? "#4ade80" : successRate >= 40 ? "#facc15" : "#f87171"
                        }}>
                            {successRate}%
                        </div>
                        <div className="stat-label">Success Rate</div>
                    </div>
                </div>

                {/* Tab Navigation */}
                <div style={{
                    display: "flex",
                    gap: "0.25rem",
                    marginBottom: "1.5rem",
                    background: "rgba(0,0,0,0.3)",
                    padding: "0.25rem",
                    borderRadius: "0.5rem",
                    width: "100%",
                    overflowX: "auto",
                    WebkitOverflowScrolling: "touch"
                }}>
                    {(["overview", "groups", "accounts", "campaigns"] as const).map(tab => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab)}
                            style={{
                                padding: "0.5rem 0.75rem",
                                borderRadius: "0.375rem",
                                border: "none",
                                cursor: "pointer",
                                fontSize: "0.8rem",
                                fontWeight: 500,
                                background: activeTab === tab ? "rgba(34, 211, 238, 0.2)" : "transparent",
                                color: activeTab === tab ? "#22d3ee" : "#9ca3af",
                                transition: "all 0.2s",
                                textTransform: "capitalize",
                                whiteSpace: "nowrap",
                                flex: "1 0 auto"
                            }}
                        >
                            {tab}
                        </button>
                    ))}
                </div>

                {/* Overview Tab */}
                {activeTab === "overview" && (
                    <>
                        {/* Activity Chart */}
                        <div className="glass-card" style={{ marginBottom: "1.5rem" }}>
                            <h2 style={{ fontSize: "1rem", fontWeight: 600, color: "white", marginBottom: "1rem" }}>
                                Daily Activity
                            </h2>

                            {data?.daily && data.daily.length > 0 ? (
                                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                                    {/* Simple bar chart */}
                                    <div style={{
                                        display: "flex",
                                        alignItems: "flex-end",
                                        gap: "2px",
                                        height: "120px",
                                        padding: "0 0.5rem"
                                    }}>
                                        {data.daily.slice(0, 30).reverse().map((day, idx) => (
                                            <div
                                                key={idx}
                                                style={{
                                                    flex: 1,
                                                    display: "flex",
                                                    flexDirection: "column",
                                                    height: "100%",
                                                    justifyContent: "flex-end"
                                                }}
                                                title={`${day.date}: ${day.successful_sends} sent, ${day.failed_sends} failed`}
                                            >
                                                <div style={{
                                                    height: `${(day.successful_sends / maxDaily) * 100}%`,
                                                    background: "linear-gradient(to top, #22c55e, #4ade80)",
                                                    borderRadius: "2px 2px 0 0",
                                                    minHeight: day.successful_sends > 0 ? "2px" : "0"
                                                }} />
                                                <div style={{
                                                    height: `${(day.failed_sends / maxDaily) * 100}%`,
                                                    background: "#f87171",
                                                    borderRadius: "0",
                                                    minHeight: day.failed_sends > 0 ? "1px" : "0"
                                                }} />
                                            </div>
                                        ))}
                                    </div>
                                    <div style={{
                                        display: "flex",
                                        justifyContent: "space-between",
                                        fontSize: "0.7rem",
                                        color: "#6b7280",
                                        padding: "0 0.5rem"
                                    }}>
                                        <span>{data.daily[data.daily.length - 1]?.date || ""}</span>
                                        <span>{data.daily[0]?.date || ""}</span>
                                    </div>
                                    <div style={{ display: "flex", gap: "1rem", fontSize: "0.75rem", marginTop: "0.5rem" }}>
                                        <span><span style={{ color: "#4ade80" }}>■</span> Successful</span>
                                        <span><span style={{ color: "#f87171" }}>■</span> Failed</span>
                                    </div>
                                </div>
                            ) : (
                                <p style={{ color: "#9ca3af", textAlign: "center", padding: "2rem" }}>
                                    No activity recorded yet.
                                </p>
                            )}
                        </div>

                        {/* Hourly Pattern */}
                        {data?.hourly && data.hourly.length > 0 && (
                            <div className="glass-card" style={{ marginBottom: "1.5rem" }}>
                                <h2 style={{ fontSize: "1rem", fontWeight: 600, color: "white", marginBottom: "1rem" }}>
                                    Hourly Activity Pattern
                                </h2>
                                <div style={{
                                    display: "grid",
                                    gridTemplateColumns: "repeat(12, 1fr)",
                                    gap: "0.25rem"
                                }}>
                                    {Array.from({ length: 24 }, (_, i) => {
                                        const hourData = data.hourly.find(h => parseInt(h.hour) === i);
                                        const intensity = hourData ? (hourData.successful / Math.max(...data.hourly.map(h => h.successful || 1))) : 0;
                                        return (
                                            <div
                                                key={i}
                                                style={{
                                                    aspectRatio: "1",
                                                    borderRadius: "4px",
                                                    background: intensity > 0
                                                        ? `rgba(34, 211, 238, ${Math.max(0.1, intensity)})`
                                                        : "rgba(255,255,255,0.05)",
                                                    display: "flex",
                                                    alignItems: "center",
                                                    justifyContent: "center",
                                                    fontSize: "0.6rem",
                                                    color: "#9ca3af"
                                                }}
                                                title={`${i}:00 - ${hourData?.successful || 0} successful`}
                                            >
                                                {i}
                                            </div>
                                        );
                                    })}
                                </div>
                                <p style={{ fontSize: "0.7rem", color: "#6b7280", marginTop: "0.5rem" }}>
                                    Brighter = more activity at that hour (24h format)
                                </p>
                            </div>
                        )}
                    </>
                )}

                {/* Groups Tab */}
                {activeTab === "groups" && (
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "1rem" }}>
                        {/* Top Performing Groups */}
                        <div className="glass-card">
                            <h2 style={{ fontSize: "1rem", fontWeight: 600, color: "#4ade80", marginBottom: "1rem" }}>
                                🏆 Top Performing Groups
                            </h2>
                            {data?.groups.top_groups && data.groups.top_groups.length > 0 ? (
                                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                                    {data.groups.top_groups.slice(0, 8).map((group, idx) => (
                                        <div key={idx} style={{
                                            display: "flex",
                                            justifyContent: "space-between",
                                            alignItems: "center",
                                            padding: "0.5rem",
                                            background: "rgba(0,0,0,0.2)",
                                            borderRadius: "0.375rem"
                                        }}>
                                            <span style={{
                                                color: "white",
                                                fontSize: "0.8rem",
                                                overflow: "hidden",
                                                textOverflow: "ellipsis",
                                                whiteSpace: "nowrap",
                                                maxWidth: "180px"
                                            }}>
                                                {group.group_name}
                                            </span>
                                            <span style={{ color: "#4ade80", fontSize: "0.8rem", fontWeight: 500 }}>
                                                {group.successful} ✓
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p style={{ color: "#9ca3af", fontSize: "0.875rem" }}>No data yet</p>
                            )}
                        </div>

                        {/* Problem Groups */}
                        <div className="glass-card">
                            <h2 style={{ fontSize: "1rem", fontWeight: 600, color: "#f87171", marginBottom: "1rem" }}>
                                ⚠️ Groups with Issues
                            </h2>
                            {data?.groups.problem_groups && data.groups.problem_groups.length > 0 ? (
                                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                                    {data.groups.problem_groups.slice(0, 8).map((group, idx) => (
                                        <div key={idx} style={{
                                            display: "flex",
                                            justifyContent: "space-between",
                                            alignItems: "center",
                                            padding: "0.5rem",
                                            background: "rgba(0,0,0,0.2)",
                                            borderRadius: "0.375rem"
                                        }}>
                                            <div style={{ flex: 1, minWidth: 0 }}>
                                                <div style={{
                                                    color: "white",
                                                    fontSize: "0.8rem",
                                                    overflow: "hidden",
                                                    textOverflow: "ellipsis",
                                                    whiteSpace: "nowrap"
                                                }}>
                                                    {group.group_name}
                                                </div>
                                                {group.error_message && (
                                                    <div style={{
                                                        color: "#9ca3af",
                                                        fontSize: "0.65rem",
                                                        overflow: "hidden",
                                                        textOverflow: "ellipsis",
                                                        whiteSpace: "nowrap"
                                                    }}>
                                                        {group.error_message}
                                                    </div>
                                                )}
                                            </div>
                                            <span style={{ color: "#f87171", fontSize: "0.8rem", fontWeight: 500, marginLeft: "0.5rem" }}>
                                                {group.failed} ✗
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p style={{ color: "#4ade80", fontSize: "0.875rem" }}>No problem groups! 🎉</p>
                            )}
                        </div>
                    </div>
                )}

                {/* Accounts Tab */}
                {activeTab === "accounts" && (
                    <div className="glass-card">
                        <h2 style={{ fontSize: "1rem", fontWeight: 600, color: "white", marginBottom: "1rem" }}>
                            Account Performance
                        </h2>
                        {data?.accounts && data.accounts.length > 0 ? (
                            <div className="responsive-table">
                                <table className="data-table">
                                    <thead>
                                        <tr>
                                            <th>Account</th>
                                            <th>Total</th>
                                            <th>Successful</th>
                                            <th>Failed</th>
                                            <th>Rate</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {data.accounts.map((acc) => (
                                            <tr key={acc.id}>
                                                <td style={{ color: "white" }}>
                                                    {acc.display_name || acc.phone_number}
                                                </td>
                                                <td>{acc.total_sends || 0}</td>
                                                <td style={{ color: "#4ade80" }}>{acc.successful || 0}</td>
                                                <td style={{ color: "#f87171" }}>{acc.failed || 0}</td>
                                                <td>
                                                    <span style={{
                                                        padding: "0.125rem 0.5rem",
                                                        borderRadius: "9999px",
                                                        fontSize: "0.75rem",
                                                        background: (acc.success_rate || 0) >= 70
                                                            ? "rgba(74, 222, 128, 0.2)"
                                                            : (acc.success_rate || 0) >= 40
                                                                ? "rgba(250, 204, 21, 0.2)"
                                                                : "rgba(248, 113, 113, 0.2)",
                                                        color: (acc.success_rate || 0) >= 70
                                                            ? "#4ade80"
                                                            : (acc.success_rate || 0) >= 40
                                                                ? "#facc15"
                                                                : "#f87171"
                                                    }}>
                                                        {acc.success_rate || 0}%
                                                    </span>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        ) : (
                            <p style={{ color: "#9ca3af", textAlign: "center", padding: "2rem" }}>
                                No account data yet.
                            </p>
                        )}
                    </div>
                )}

                {/* Campaigns Tab */}
                {activeTab === "campaigns" && (
                    <div className="glass-card">
                        <h2 style={{ fontSize: "1rem", fontWeight: 600, color: "white", marginBottom: "1rem" }}>
                            Campaign History
                        </h2>
                        {data?.campaigns && data.campaigns.length > 0 ? (
                            <div className="responsive-table">
                                <table className="data-table">
                                    <thead>
                                        <tr>
                                            <th>Campaign</th>
                                            <th>Status</th>
                                            <th>Total</th>
                                            <th>Success</th>
                                            <th>Failed</th>
                                            <th>Date</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {data.campaigns.map((campaign) => (
                                            <tr key={campaign.id}>
                                                <td style={{ color: "white" }}>{campaign.name}</td>
                                                <td>
                                                    <span style={{
                                                        padding: "0.125rem 0.5rem",
                                                        borderRadius: "9999px",
                                                        fontSize: "0.7rem",
                                                        background: campaign.status === "running"
                                                            ? "rgba(34, 211, 238, 0.2)"
                                                            : campaign.status === "completed"
                                                                ? "rgba(74, 222, 128, 0.2)"
                                                                : "rgba(107, 114, 128, 0.2)",
                                                        color: campaign.status === "running"
                                                            ? "#22d3ee"
                                                            : campaign.status === "completed"
                                                                ? "#4ade80"
                                                                : "#9ca3af"
                                                    }}>
                                                        {campaign.status}
                                                    </span>
                                                </td>
                                                <td>{campaign.total_sends || 0}</td>
                                                <td style={{ color: "#4ade80" }}>{campaign.successful || 0}</td>
                                                <td style={{ color: "#f87171" }}>{campaign.failed || 0}</td>
                                                <td style={{ fontSize: "0.75rem", color: "#9ca3af" }}>
                                                    {campaign.created_at ? new Date(campaign.created_at).toLocaleDateString() : "-"}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        ) : (
                            <p style={{ color: "#9ca3af", textAlign: "center", padding: "2rem" }}>
                                No campaigns yet.
                            </p>
                        )}
                    </div>
                )}
            </main>
        </>
    );
}
