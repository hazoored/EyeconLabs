"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, setToken } from "@/lib/api";

export default function AdminLoginPage() {
    const router = useRouter();
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setLoading(true);

        const response = await api<{
            access_token: string;
            user_type: string;
        }>("/auth/admin/login", {
            method: "POST",
            body: { username, password },
        });

        setLoading(false);

        if (!response.ok) {
            setError(response.error || "Login failed");
            return;
        }

        if (response.data) {
            setToken(response.data.access_token, "admin");
            router.push("/admin");
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center px-4">
            <div className="w-full max-w-md">
                {/* Logo */}
                <div className="text-center mb-8">
                    <h1 className="text-3xl font-bold text-gradient">EyeconBumps</h1>
                    <p className="text-gray-400 mt-2">Admin Dashboard</p>
                </div>

                {/* Login Card */}
                <div className="glass-card">
                    <h2 className="text-xl font-semibold text-white mb-6">Admin Login</h2>

                    <form onSubmit={handleLogin} className="space-y-4">
                        <div>
                            <label className="block text-sm text-gray-400 mb-2">
                                Username
                            </label>
                            <input
                                type="text"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                className="input-field"
                                placeholder="Enter username"
                                required
                            />
                        </div>

                        <div>
                            <label className="block text-sm text-gray-400 mb-2">
                                Password
                            </label>
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="input-field"
                                placeholder="Enter password"
                                required
                            />
                        </div>

                        {error && (
                            <div className="text-red-400 text-sm bg-red-500/10 px-4 py-2 rounded-lg">
                                {error}
                            </div>
                        )}

                        <button
                            type="submit"
                            disabled={loading}
                            className="btn-primary w-full disabled:opacity-50"
                        >
                            {loading ? "Signing in..." : "Sign In"}
                        </button>
                    </form>
                </div>

                {/* Footer */}
                <p className="text-center text-gray-500 text-sm mt-6">
                    © 2026 EyeconBumps. All rights reserved.
                </p>
            </div>
        </div>
    );
}
