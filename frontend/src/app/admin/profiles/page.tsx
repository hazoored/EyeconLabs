"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { api, getToken } from "@/lib/api";

interface Account {
    id: number;
    phone_number: string;
    display_name: string;
    is_active: boolean;
}

interface PrivacySettings {
    phone_number: string;
    last_seen: string;
    profile_photos: string;
    forwards: string;
    calls: string;
    voice_messages: string;
    groups: string;
    birthday: string;
}

const PRIVACY_OPTIONS = ["Everybody", "Contacts", "Nobody"];

export default function ProfilesPage() {
    const router = useRouter();
    const [accounts, setAccounts] = useState<Account[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedAccount, setSelectedAccount] = useState<string>("");
    const [accountDetails, setAccountDetails] = useState<any>(null);
    const [privacy, setPrivacy] = useState<PrivacySettings | null>(null);
    const [twoFA, setTwoFA] = useState<any>(null);
    const [updating, setUpdating] = useState(false);

    // Profile Form State
    const [profileForm, setProfileForm] = useState({
        first_name: "",
        last_name: "",
        bio: "",
        username: "",
        birthday: ""
    });

    // 2FA Form State
    const [twoFAForm, setTwoFAForm] = useState({
        current_password: "",
        new_password: "",
        hint: ""
    });

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

    const fetchAccountData = useCallback(async (accId: string) => {
        if (!accId) {
            setAccountDetails(null);
            setPrivacy(null);
            setTwoFA(null);
            return;
        }
        const token = getToken("admin");
        setLoading(true);

        try {
            const [infoRes, privacyRes, twoFARes] = await Promise.all([
                api<any>(`/admin/accounts/${accId}/info`, { token: token! }),
                api<{ privacy: PrivacySettings }>(`/admin/accounts/${accId}/privacy`, { token: token! }),
                api<any>(`/admin/accounts/${accId}/2fa`, { token: token! })
            ]);

            if (infoRes.ok && infoRes.data) {
                setAccountDetails(infoRes.data);
                setProfileForm({
                    first_name: infoRes.data.first_name || "",
                    last_name: infoRes.data.last_name || "",
                    bio: infoRes.data.bio || "",
                    username: infoRes.data.username || "",
                    birthday: "" // To be filled manually or from a future DB field
                });
            } else if (infoRes.error) {
                console.error("Info error:", infoRes.error);
            }

            if (privacyRes.ok && privacyRes.data) {
                setPrivacy(privacyRes.data.privacy);
            } else {
                console.error("Privacy error:", privacyRes.error);
                setPrivacy(null);
            }

            if (twoFARes.ok && twoFARes.data) {
                setTwoFA(twoFARes.data);
            }
        } catch (e) {
            console.error("Fetch error:", e);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        if (selectedAccount) fetchAccountData(selectedAccount);
    }, [selectedAccount, fetchAccountData]);

    const fileInputRef = useRef<HTMLInputElement>(null);

    const handlePhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setUpdating(true);
        const token = getToken("admin");

        try {
            const formData = new FormData();
            formData.append("file", file);

            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"}/admin/accounts/${selectedAccount}/profile-photo`, {
                method: "POST",
                headers: {
                    "Authorization": `Bearer ${token}`
                },
                body: formData
            });

            const data = await response.json();

            if (response.ok) {
                alert("Profile photo updated successfully!");
                fetchAccountData(selectedAccount);
            } else {
                alert(data.detail || "Failed to update profile photo");
            }
        } catch (err) {
            console.error(err);
            alert("Error uploading photo");
        } finally {
            setUpdating(false);
            if (fileInputRef.current) fileInputRef.current.value = "";
        }
    };

    const handleUpdateProfile = async (e: React.FormEvent) => {
        e.preventDefault();
        setUpdating(true);
        const token = getToken("admin");
        const res = await api(`/admin/accounts/${selectedAccount}/profile-extended`, {
            method: "PUT",
            token: token!,
            body: profileForm
        });
        if (res.ok) {
            alert("Profile updated successfully!");
            fetchAccountData(selectedAccount);
        } else {
            alert(res.error || "Failed to update profile");
        }
        setUpdating(false);
    };

    const handleUpdate2FA = async (action: "set" | "remove") => {
        if (action === "set" && !twoFAForm.new_password) {
            alert("Please enter a new password");
            return;
        }
        if (twoFA.has_2fa && !twoFAForm.current_password) {
            alert("Please enter current password to make changes");
            return;
        }

        const confirmMsg = action === "remove"
            ? "Are you sure you want to REMOVE Two-Step Verification? This will make your account less secure."
            : "Update Two-Step Verification settings?";

        if (!confirm(confirmMsg)) return;

        setUpdating(true);
        const token = getToken("admin");
        const res = await api(`/admin/accounts/${selectedAccount}/2fa`, {
            method: "POST",
            token: token!,
            body: {
                current_password: twoFAForm.current_password || null,
                new_password: action === "remove" ? "" : twoFAForm.new_password,
                hint: twoFAForm.hint
            }
        });

        if (res.ok) {
            alert(action === "remove" ? "2FA removed successfully" : "2FA updated successfully");
            setTwoFAForm({ current_password: "", new_password: "", hint: "" });
            fetchAccountData(selectedAccount);
        } else {
            alert(res.error || "Failed to update 2FA");
        }
        setUpdating(false);
    };

    const handlePrivacyChange = async (key: keyof PrivacySettings, value: string) => {
        if (!privacy) return;
        const newPrivacy = { ...privacy, [key]: value };
        setPrivacy(newPrivacy); // Optimistic update

        const token = getToken("admin");
        const res = await api(`/admin/accounts/${selectedAccount}/privacy`, {
            method: "PUT",
            token: token!,
            body: { [key]: value }
        });
        if (!res.ok) {
            alert(res.error || "Failed to update privacy");
            fetchAccountData(selectedAccount); // Revert
        }
    };

    if (loading && !selectedAccount) return <div className="loading-screen">Loading Accounts...</div>;

    return (
        <>
            <Sidebar userType="admin" />
            <main className="main-content">
                <div className="page-header">
                    <div>
                        <h1 className="page-title">Profiles</h1>
                        <p className="page-subtitle">Fully control account details and security settings</p>
                    </div>
                </div>

                <div className="glass-card" style={{ marginBottom: "2rem" }}>
                    <label className="input-label">Select Account to Manage</label>
                    <select
                        className="input-field"
                        value={selectedAccount}
                        onChange={(e) => setSelectedAccount(e.target.value)}
                    >
                        <option value="">-- Choose Account --</option>
                        {accounts.map(acc => (
                            <option key={acc.id} value={acc.id}>
                                {acc.display_name} ({acc.phone_number})
                            </option>
                        ))}
                    </select>
                </div>

                {selectedAccount && (
                    <div className="profile-grid" style={{ opacity: loading ? 0.6 : 1, pointerEvents: loading ? "none" : "auto", transition: "opacity 0.2s" }}>
                        {/* Profile Info Form */}
                        <div className="glass-card">
                            <h2 className="section-title">Edit Profile {loading && "..."}</h2>
                            <form onSubmit={handleUpdateProfile}>
                                <div style={{ marginBottom: "1.5rem", textAlign: "center" }}>
                                    <div
                                        style={{
                                            width: "100px", height: "100px", borderRadius: "50%",
                                            background: "rgba(255,255,255,0.1)", margin: "0 auto 1rem",
                                            display: "flex", alignItems: "center", justifyContent: "center",
                                            overflow: "hidden", border: "2px solid rgba(255,255,255,0.1)"
                                        }}
                                    >
                                        <span style={{ fontSize: "2rem" }}>👤</span>
                                    </div>
                                    <input
                                        type="file"
                                        ref={fileInputRef}
                                        style={{ display: "none" }}
                                        accept="image/*"
                                        onChange={handlePhotoUpload}
                                    />
                                    <button
                                        type="button"
                                        className="btn-secondary"
                                        style={{ fontSize: "0.8rem", padding: "0.25rem 0.75rem" }}
                                        onClick={() => fileInputRef.current?.click()}
                                        disabled={updating}
                                    >
                                        Change Photo
                                    </button>
                                </div>
                                <div className="form-group">
                                    <label className="input-label">First Name</label>
                                    <input
                                        className="input-field"
                                        value={profileForm.first_name}
                                        onChange={(e) => setProfileForm({ ...profileForm, first_name: e.target.value })}
                                    />
                                </div>
                                <div className="form-group">
                                    <label className="input-label">Last Name</label>
                                    <input
                                        className="input-field"
                                        value={profileForm.last_name}
                                        onChange={(e) => setProfileForm({ ...profileForm, last_name: e.target.value })}
                                    />
                                </div>
                                <div className="form-group">
                                    <label className="input-label">Username</label>
                                    <div style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
                                        <span style={{ color: "#9ca3af" }}>@</span>
                                        <input
                                            className="input-field"
                                            value={profileForm.username}
                                            onChange={(e) => setProfileForm({ ...profileForm, username: e.target.value })}
                                        />
                                    </div>
                                </div>
                                <div className="form-group">
                                    <label className="input-label">Birthday</label>
                                    <input
                                        type="date"
                                        className="input-field"
                                        value={profileForm.birthday}
                                        onChange={(e) => setProfileForm({ ...profileForm, birthday: e.target.value })}
                                    />
                                </div>
                                <div className="form-group">
                                    <label className="input-label">Bio (About)</label>
                                    <textarea
                                        className="input-field"
                                        rows={3}
                                        value={profileForm.bio}
                                        onChange={(e) => setProfileForm({ ...profileForm, bio: e.target.value })}
                                    />
                                </div>
                                <button className="btn-primary" style={{ width: "100%" }} disabled={updating}>
                                    {updating ? "Saving..." : "Save Profile Details"}
                                </button>
                            </form>

                            {/* 2FA Section */}
                            <div style={{ marginTop: "2rem", paddingTop: "2rem", borderTop: "1px solid rgba(255,255,255,0.05)" }}>
                                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
                                    <h3 style={{ color: "white", fontSize: "1rem", margin: 0 }}>Two-Step Verification</h3>
                                    {twoFA && (
                                        <div className={`status-badge ${twoFA.has_2fa ? "active" : "inactive"}`}>
                                            {twoFA.has_2fa ? "🔒 Enabled" : "🔓 Not Set"}
                                        </div>
                                    )}
                                </div>

                                <div className="form-group">
                                    <label className="input-label">Current Password {twoFA?.has_2fa && <span style={{ color: "#ef4444" }}>*</span>}</label>
                                    <input
                                        type="password"
                                        className="input-field"
                                        placeholder="Required to change or remove"
                                        value={twoFAForm.current_password}
                                        onChange={(e) => setTwoFAForm({ ...twoFAForm, current_password: e.target.value })}
                                    />
                                </div>

                                <div className="form-group">
                                    <label className="input-label">New Password</label>
                                    <input
                                        type="password"
                                        className="input-field"
                                        placeholder="Leave empty to remove 2FA"
                                        value={twoFAForm.new_password}
                                        onChange={(e) => setTwoFAForm({ ...twoFAForm, new_password: e.target.value })}
                                    />
                                </div>

                                <div className="form-group">
                                    <label className="input-label">Password Hint</label>
                                    <input
                                        className="input-field"
                                        placeholder="Optional"
                                        value={twoFAForm.hint}
                                        onChange={(e) => setTwoFAForm({ ...twoFAForm, hint: e.target.value })}
                                    />
                                </div>

                                <div style={{ display: "flex", gap: "0.5rem" }}>
                                    <button
                                        className="btn-primary"
                                        style={{ flex: 1 }}
                                        disabled={updating}
                                        onClick={() => handleUpdate2FA("set")}
                                    >
                                        {twoFA?.has_2fa ? "Change Password" : "Set 2FA"}
                                    </button>
                                    {twoFA?.has_2fa && (
                                        <button
                                            className="btn-danger"
                                            style={{ flex: 1, background: "rgba(239, 68, 68, 0.1)", color: "#ef4444", borderColor: "rgba(239, 68, 68, 0.2)" }}
                                            disabled={updating}
                                            onClick={() => handleUpdate2FA("remove")}
                                        >
                                            Remove 2FA
                                        </button>
                                    )}
                                </div>
                                {twoFA?.hint && !twoFAForm.current_password && (
                                    <p style={{ fontSize: "0.8rem", color: "#9ca3af", marginTop: "1rem", textAlign: "center" }}>
                                        Current Hint: <span style={{ color: "#22d3ee" }}>{twoFA.hint}</span>
                                    </p>
                                )}
                            </div>
                        </div>

                        {/* Privacy Settings Section */}
                        <div className="glass-card">
                            <h2 className="section-title">Privacy Settings</h2>
                            <div className="privacy-list">
                                {privacy && Object.entries(privacy).map(([key, value]) => (
                                    <div key={key} className="privacy-item">
                                        <div className="privacy-info">
                                            <span className="privacy-label">{key.replace(/_/g, ' ').toUpperCase()}</span>
                                            <span className="privacy-status">{value}</span>
                                        </div>
                                        <div className="privacy-actions">
                                            {PRIVACY_OPTIONS.map(opt => (
                                                <button
                                                    key={opt}
                                                    className={`privacy-opt-btn ${value === opt ? "active" : ""}`}
                                                    onClick={() => handlePrivacyChange(key as keyof PrivacySettings, opt)}
                                                >
                                                    {opt}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                )}
            </main>

            <style jsx>{`
                .profile-grid {
                    display: grid;
                    grid-template-columns: 400px 1fr;
                    gap: 2rem;
                }
                .section-title {
                    font-size: 1.125rem;
                    color: white;
                    margin-bottom: 2rem;
                    font-weight: 700;
                }
                .form-group {
                    margin-bottom: 1.25rem;
                }
                .input-label {
                    display: block;
                    color: #9ca3af;
                    font-size: 0.8rem;
                    margin-bottom: 0.5rem;
                    text-transform: uppercase;
                    letter-spacing: 0.05em;
                }
                .privacy-list {
                    display: flex;
                    flex-direction: column;
                    gap: 1.5rem;
                }
                .privacy-item {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding-bottom: 1.5rem;
                    border-bottom: 1px solid rgba(255,255,255,0.05);
                }
                .privacy-info {
                    display: flex;
                    flex-direction: column;
                }
                .privacy-label {
                    font-size: 0.75rem;
                    color: #9ca3af;
                    font-weight: 600;
                }
                .privacy-status {
                    font-size: 1rem;
                    color: #22d3ee;
                    font-weight: 500;
                }
                .privacy-actions {
                    display: flex;
                    gap: 0.25rem;
                    background: rgba(0,0,0,0.2);
                    padding: 0.25rem;
                    border-radius: 0.5rem;
                }
                .privacy-opt-btn {
                    padding: 0.4rem 0.75rem;
                    font-size: 0.75rem;
                    border-radius: 0.375rem;
                    border: none;
                    background: transparent;
                    color: #9ca3af;
                    cursor: pointer;
                    transition: all 0.2s;
                }
                .privacy-opt-btn.active {
                    background: #22d3ee;
                    color: #0c0a09;
                    font-weight: 600;
                }
                .status-badge {
                    display: inline-block;
                    padding: 0.25rem 0.75rem;
                    border-radius: 9999px;
                    font-size: 0.75rem;
                    font-weight: 600;
                }
                .status-badge.active { background: rgba(16, 185, 129, 0.1); color: #10b981; }
                .status-badge.inactive { background: rgba(239, 68, 68, 0.1); color: #f87171; }
                
                select.input-field {
                    appearance: none;
                    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%239ca3af'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'%3E%3C/path%3E%3C/svg%3E");
                    background-repeat: no-repeat;
                    background-position: right 1rem center;
                    background-size: 1.25rem;
                    padding-right: 3rem;
                    background-color: rgba(255, 255, 255, 0.03);
                    backdrop-filter: blur(8px);
                    cursor: pointer;
                    max-width: 100%;
                }
                select.input-field:hover {
                    background-color: rgba(255, 255, 255, 0.05);
                    border-color: rgba(6, 182, 212, 0.4);
                }
                select.input-field option {
                    background-color: #0c0a09;
                    color: white;
                }

                .loading-screen {
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: #22d3ee;
                    font-size: 1.25rem;
                }
            `}</style>
        </>
    );
}
