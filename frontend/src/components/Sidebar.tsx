"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearToken } from "@/lib/api";

interface SidebarProps {
    userType: "admin" | "client";
}

// SVG Icons as components
const Icons = {
    dashboard: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="7" height="9" rx="1" />
            <rect x="14" y="3" width="7" height="5" rx="1" />
            <rect x="14" y="12" width="7" height="9" rx="1" />
            <rect x="3" y="16" width="7" height="5" rx="1" />
        </svg>
    ),
    clients: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
        </svg>
    ),
    accounts: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="5" y="2" width="14" height="20" rx="2" ry="2" />
            <path d="M12 18h.01" />
        </svg>
    ),
    campaigns: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
        </svg>
    ),
    analytics: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="20" x2="18" y2="10" />
            <line x1="12" y1="20" x2="12" y2="4" />
            <line x1="6" y1="20" x2="6" y2="14" />
        </svg>
    ),
    logout: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
        </svg>
    ),
};

const adminNavItems = [
    { href: "/admin", icon: Icons.dashboard, label: "Dashboard" },
    { href: "/admin/clients", icon: Icons.clients, label: "Clients" },
    { href: "/admin/accounts", icon: Icons.accounts, label: "Accounts" },
    { href: "/admin/campaigns", icon: Icons.campaigns, label: "Campaigns" },
];

const clientNavItems = [
    { href: "/dashboard", icon: Icons.dashboard, label: "Dashboard" },
    { href: "/accounts", icon: Icons.accounts, label: "Accounts" },
    { href: "/campaigns", icon: Icons.campaigns, label: "Campaigns" },
    { href: "/analytics", icon: Icons.analytics, label: "Analytics" },
];

export default function Sidebar({ userType }: SidebarProps) {
    const pathname = usePathname();
    const router = useRouter();
    const navItems = userType === "admin" ? adminNavItems : clientNavItems;
    const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);

    const handleLogout = () => {
        clearToken(userType);
        router.push(userType === "admin" ? "/admin/login" : "/login");
    };

    return (
        <>
            {/* Desktop Sidebar */}
            <aside className="desktop-sidebar">
                <div className="sidebar-header">
                    <Link href={userType === "admin" ? "/admin" : "/dashboard"}>
                        <h1 className="text-gradient sidebar-logo">EyeconBumps</h1>
                    </Link>
                    <p className="sidebar-subtitle">
                        {userType === "admin" ? "Admin Panel" : "Client Portal"}
                    </p>
                </div>

                <nav className="sidebar-nav">
                    {navItems.map((item) => (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={`sidebar-nav-item ${pathname === item.href ? "active" : ""}`}
                        >
                            <span className="sidebar-nav-icon">{item.icon}</span>
                            <span className="sidebar-nav-label">{item.label}</span>
                        </Link>
                    ))}
                </nav>

                <div className="sidebar-footer">
                    <button onClick={() => setShowLogoutConfirm(true)} className="sidebar-logout-btn">
                        {Icons.logout}
                        <span>Logout</span>
                    </button>
                </div>
            </aside>

            {/* Mobile Bottom Navigation */}
            <nav className="mobile-bottom-nav">
                {navItems.map((item) => (
                    <Link
                        key={item.href}
                        href={item.href}
                        className={`mobile-nav-item ${pathname === item.href ? "active" : ""}`}
                    >
                        <span className="mobile-nav-icon">{item.icon}</span>
                        <span className="mobile-nav-label">{item.label}</span>
                    </Link>
                ))}
                <button
                    onClick={() => setShowLogoutConfirm(true)}
                    className="mobile-nav-item logout"
                >
                    <span className="mobile-nav-icon">{Icons.logout}</span>
                    <span className="mobile-nav-label">Exit</span>
                </button>
            </nav>

            {/* Logout Confirmation Modal */}
            {showLogoutConfirm && (
                <div className="modal-overlay" onClick={() => setShowLogoutConfirm(false)}>
                    <div className="glass-card logout-modal" onClick={(e) => e.stopPropagation()}>
                        <h3>Logout?</h3>
                        <p>Are you sure you want to logout?</p>
                        <div className="logout-modal-actions">
                            <button onClick={() => setShowLogoutConfirm(false)} className="btn-secondary">
                                Cancel
                            </button>
                            <button onClick={handleLogout} className="btn-danger">
                                Logout
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
