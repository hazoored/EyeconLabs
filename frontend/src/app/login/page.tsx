"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, setToken } from "@/lib/api";

export default function ClientLoginPage() {
    const router = useRouter();
    const [token, setTokenInput] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setLoading(true);

        const response = await api<{
            access_token: string;
            user_type: string;
        }>("/auth/client/login", {
            method: "POST",
            body: { token: token.toUpperCase() },
        });

        setLoading(false);

        if (!response.ok) {
            setError(response.error || "Login failed");
            return;
        }

        if (response.data) {
            setToken(response.data.access_token, "client");
            router.push("/dashboard");
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center px-4">
            <div className="w-full max-w-md">
                {/* Logo */}
                <div className="text-center mb-8">
                    <h1 className="text-4xl font-bold text-gradient text-glow">EyeconBumps</h1>
                    <p className="text-gray-400 mt-2">Client Portal</p>
                </div>

                {/* Login Card */}
                <div className="glass-card card-glow">
                    <h2 className="text-xl font-semibold text-white mb-2">Welcome Back</h2>
                    <p className="text-gray-400 text-sm mb-6">
                        Enter your 5-digit access token to continue
                    </p>

                    <form onSubmit={handleLogin} className="space-y-6">
                        <div>
                            <label className="block text-sm text-gray-400 mb-2">
                                Access Token
                            </label>
                            <input
                                type="text"
                                value={token}
                                onChange={(e) => setTokenInput(e.target.value.toUpperCase())}
                                className="input-field text-center text-2xl tracking-[0.5em] font-mono"
                                placeholder="XXXXX"
                                maxLength={5}
                                required
                            />
                            <p className="text-xs text-gray-500 mt-2 text-center">
                                Your 5-character token provided by the admin
                            </p>
                        </div>

                        {error && (
                            <div className="text-red-400 text-sm bg-red-500/10 px-4 py-2 rounded-lg">
                                {error}
                            </div>
                        )}

                        <button
                            type="submit"
                            disabled={loading || token.length !== 5}
                            className="btn-primary w-full disabled:opacity-50"
                        >
                            {loading ? "Verifying..." : "Access Dashboard"}
                        </button>
                    </form>
                </div>

                {/* Help Text */}
                <div className="text-center mt-6 space-y-2">
                    <p className="text-gray-500 text-sm">
                        Don&apos;t have an access token?
                    </p>
                    <a
                        href="https://t.me/apolyte"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-cyan-400 hover:text-cyan-300 text-sm inline-flex items-center gap-2"
                    >
                        Contact on Telegram →
                    </a>
                </div>

                {/* Footer */}
                <p className="text-center text-gray-600 text-xs mt-8">
                    © 2026 EyeconBumps. Telegram Ads Automation.
                </p>
            </div>
        </div>
    );
}
