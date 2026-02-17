"use client";

import { useState, useEffect, useRef, useCallback } from "react";

interface OrderData {
    order_id: string;
    product_name: string;
    status: string;
    created_at: string;
    updated_at: string;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

const statusSteps = [
    { id: 'submitted', label: 'Order Submitted', icon: '📦' },
    { id: 'processing', label: 'Processing', icon: '⚙️' },
    { id: 'in_progress', label: 'In Progress', icon: '🔄' },
    { id: 'completed', label: 'Completed', icon: '✅' },
    { id: 'delivered', label: 'Delivered', icon: '🚀' },
];

// Play notification sound using Web Audio API
const playNotificationSound = () => {
    try {
        const audioContext = new (window.AudioContext || (window as typeof window & { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();

        // Create a pleasant chime sound
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);

        oscillator.frequency.setValueAtTime(880, audioContext.currentTime); // A5 note
        oscillator.frequency.setValueAtTime(1108.73, audioContext.currentTime + 0.1); // C#6 note
        oscillator.frequency.setValueAtTime(1318.51, audioContext.currentTime + 0.2); // E6 note

        oscillator.type = 'sine';

        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);

        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.5);
    } catch (err) {
        // Audio not supported or blocked
        console.log('Audio notification not available');
    }
};

export default function TrackOrderPage() {
    const [orderId, setOrderId] = useState("");
    const [order, setOrder] = useState<OrderData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [searched, setSearched] = useState(false);
    const [isPolling, setIsPolling] = useState(false);
    const [statusChanged, setStatusChanged] = useState(false);
    const trackedOrderId = useRef<string>("");
    const previousStatus = useRef<string>("");

    // Auto-refresh polling - fetch every 5 seconds when actively tracking
    useEffect(() => {
        if (!isPolling || !trackedOrderId.current) return;

        const fetchOrder = async () => {
            try {
                const response = await fetch(`${API_BASE_URL}/api/v1/track/${trackedOrderId.current}`);
                if (response.ok) {
                    const data = await response.json();

                    // Check if status changed
                    if (previousStatus.current && data.order.status !== previousStatus.current) {
                        playNotificationSound();
                        setStatusChanged(true);
                        setTimeout(() => setStatusChanged(false), 3000); // Hide after 3s
                    }
                    previousStatus.current = data.order.status;
                    setOrder(data);
                }
            } catch (err) {
                // Silently fail on background refresh
            }
        };

        // Fetch immediately, then every 5 seconds
        const interval = setInterval(fetchOrder, 5000);
        return () => clearInterval(interval);
    }, [isPolling]);

    const handleTrack = async (e: React.FormEvent) => {
        e.preventDefault();
        if (orderId.length !== 16) {
            setError("Order ID must be exactly 16 characters");
            return;
        }

        setLoading(true);
        setError("");
        setOrder(null);
        setIsPolling(false);
        previousStatus.current = "";

        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/track/${orderId.toUpperCase()}`);
            const data = await response.json();

            if (!response.ok) {
                setError(data.detail || "Order not found");
                setSearched(true);
            } else {
                trackedOrderId.current = orderId.toUpperCase();
                previousStatus.current = data.order.status;
                setOrder(data);
                setSearched(true);
                setIsPolling(true); // Start polling for updates
            }
        } catch (err) {
            setError("Failed to connect to server");
            setSearched(true);
        } finally {
            setLoading(false);
        }
    };


    const getStatusIndex = (status: string) => {
        return statusSteps.findIndex(s => s.id === status);
    };

    const formatDate = (dateStr: string) => {
        const date = new Date(dateStr);
        return date.toLocaleDateString("en-US", {
            year: "numeric",
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit"
        });
    };

    return (
        <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", padding: "2rem 1rem" }}>
            {/* Header */}
            <div style={{ textAlign: "center", marginBottom: "3rem" }}>
                <h1 className="text-gradient" style={{ fontSize: "2.5rem", fontWeight: 800, marginBottom: "0.5rem" }}>
                    Track Your Order
                </h1>
                <p style={{ color: "#9ca3af", fontSize: "1rem" }}>
                    Enter your 16-character Order ID to check the status
                </p>
            </div>

            {/* Search Form */}
            <form onSubmit={handleTrack} style={{ width: "100%", maxWidth: "500px", marginBottom: "2rem" }}>
                <div className="glass-card" style={{ padding: "2rem" }}>
                    <div style={{ marginBottom: "1.5rem" }}>
                        <label style={{ display: "block", color: "#9ca3af", fontSize: "0.875rem", marginBottom: "0.5rem" }}>
                            Order ID
                        </label>
                        <input
                            type="text"
                            value={orderId}
                            onChange={(e) => setOrderId(e.target.value.toUpperCase().slice(0, 16))}
                            placeholder="XXXXXXXXXXXXXXXX"
                            className="input-field"
                            style={{
                                fontSize: "1.25rem",
                                textAlign: "center",
                                letterSpacing: "0.2em",
                                fontFamily: "monospace"
                            }}
                        />
                        <p style={{ color: "#6b7280", fontSize: "0.75rem", marginTop: "0.5rem", textAlign: "center" }}>
                            {orderId.length}/16 characters
                        </p>
                    </div>
                    <button
                        type="submit"
                        className="btn-primary"
                        style={{ width: "100%" }}
                        disabled={loading || orderId.length !== 16}
                    >
                        {loading ? (
                            <span style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                <span className="status-pulse" style={{ width: "8px", height: "8px", background: "#000", borderRadius: "50%" }} />
                                Tracking...
                            </span>
                        ) : (
                            "Track Order"
                        )}
                    </button>
                </div>
            </form>

            {/* Error Message */}
            {error && searched && (
                <div className="glass-card" style={{
                    width: "100%",
                    maxWidth: "500px",
                    padding: "1.5rem",
                    background: "rgba(239, 68, 68, 0.1)",
                    borderColor: "rgba(239, 68, 68, 0.3)"
                }}>
                    <p style={{ color: "#f87171", textAlign: "center" }}>❌ {error}</p>
                </div>
            )}

            {/* Order Details */}
            {order && (
                <div className="card-glow" style={{ width: "100%", maxWidth: "600px", padding: "2rem" }}>
                    {/* Order Header */}
                    <div style={{ textAlign: "center", marginBottom: "2rem", position: "relative" }}>
                        {isPolling && (
                            <div style={{
                                position: "absolute",
                                top: "-1rem",
                                right: "0",
                                display: "flex",
                                alignItems: "center",
                                gap: "0.25rem",
                                background: "rgba(34, 211, 238, 0.1)",
                                border: "1px solid rgba(34, 211, 238, 0.2)",
                                padding: "0.25rem 0.5rem",
                                borderRadius: "9999px",
                                animation: "fadeIn 0.5s ease-out"
                            }}>
                                <span className="status-pulse" style={{ width: "6px", height: "6px", background: "#22d3ee", borderRadius: "50%" }} />
                                <span style={{ color: "#22d3ee", fontSize: "0.65rem", fontWeight: 700, letterSpacing: "0.05em" }}>LIVE</span>
                            </div>
                        )}

                        {statusChanged && (
                            <div style={{
                                position: "absolute",
                                top: "-3rem",
                                left: "50%",
                                transform: "translateX(-50%)",
                                background: "linear-gradient(135deg, #06b6d4, #a855f7)",
                                color: "white",
                                padding: "0.5rem 1rem",
                                borderRadius: "0.5rem",
                                fontSize: "0.875rem",
                                fontWeight: 600,
                                boxShadow: "0 10px 25px -5px rgba(6, 182, 212, 0.5)",
                                zIndex: 10,
                                display: "flex",
                                alignItems: "center",
                                gap: "0.5rem",
                                animation: "bounceIn 0.5s cubic-bezier(0.68, -0.55, 0.265, 1.55)"
                            }}>
                                <span>✨</span> Status Updated!
                            </div>
                        )}

                        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
                            <span className="status-pulse" style={{
                                width: "10px",
                                height: "10px",
                                background: "#4ade80",
                                borderRadius: "50%",
                                display: "inline-block"
                            }} />
                            <span style={{ color: "#4ade80", fontSize: "#0.875rem", fontWeight: 600 }}>ORDER FOUND</span>
                        </div>
                        <h2 style={{ color: "white", fontSize: "1.5rem", fontWeight: 700, marginBottom: "0.5rem" }}>
                            {order.product_name}
                        </h2>
                        <code style={{
                            background: "rgba(6, 182, 212, 0.1)",
                            color: "#22d3ee",
                            padding: "0.5rem 1rem",
                            borderRadius: "0.5rem",
                            fontSize: "0.875rem"
                        }}>
                            #{order.order_id}
                        </code>
                    </div>

                    {/* Status Timeline */}
                    <div style={{ marginBottom: "2rem" }}>
                        <h3 style={{ color: "#9ca3af", fontSize: "0.875rem", marginBottom: "1rem", textAlign: "center" }}>
                            ORDER STATUS
                        </h3>
                        <div style={{ position: "relative", padding: "0 1rem" }}>
                            {/* Progress Line */}
                            <div style={{
                                position: "absolute",
                                top: "20px",
                                left: "calc(10% + 20px)",
                                right: "calc(10% + 20px)",
                                height: "4px",
                                background: "rgba(255,255,255,0.1)",
                                borderRadius: "2px",
                                zIndex: 0
                            }}>
                                <div style={{
                                    width: `${(getStatusIndex(order.status) / (statusSteps.length - 1)) * 100}%`,
                                    height: "100%",
                                    background: "linear-gradient(to right, #06b6d4, #a855f7)",
                                    borderRadius: "2px",
                                    transition: "width 0.5s ease-out"
                                }} />
                            </div>

                            {/* Status Steps */}
                            <div style={{ display: "flex", justifyContent: "space-between", position: "relative", zIndex: 1 }}>
                                {statusSteps.map((step, index) => {
                                    const currentIndex = getStatusIndex(order.status);
                                    const isCompleted = index <= currentIndex;
                                    const isCurrent = index === currentIndex;

                                    return (
                                        <div key={step.id} style={{
                                            display: "flex",
                                            flexDirection: "column",
                                            alignItems: "center",
                                            flex: 1
                                        }}>
                                            <div style={{
                                                width: "40px",
                                                height: "40px",
                                                borderRadius: "50%",
                                                display: "flex",
                                                alignItems: "center",
                                                justifyContent: "center",
                                                fontSize: "1.25rem",
                                                background: isCompleted
                                                    ? "linear-gradient(135deg, #06b6d4, #a855f7)"
                                                    : "rgba(255,255,255,0.1)",
                                                border: isCurrent ? "2px solid #22d3ee" : "none",
                                                boxShadow: isCurrent ? "0 0 20px rgba(6, 182, 212, 0.5)" : "none",
                                                transition: "all 0.3s ease"
                                            }}>
                                                {step.icon}
                                            </div>
                                            <span style={{
                                                marginTop: "0.5rem",
                                                fontSize: "0.65rem",
                                                color: isCompleted ? "#22d3ee" : "#6b7280",
                                                textAlign: "center",
                                                maxWidth: "60px"
                                            }}>
                                                {step.label}
                                            </span>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    </div>

                    {/* Order Info */}
                    <div style={{
                        display: "grid",
                        gridTemplateColumns: "1fr 1fr",
                        gap: "1rem",
                        padding: "1rem",
                        background: "rgba(255,255,255,0.05)",
                        borderRadius: "0.5rem"
                    }}>
                        <div>
                            <span style={{ color: "#6b7280", fontSize: "0.75rem" }}>Created</span>
                            <p style={{ color: "white", fontSize: "0.875rem" }}>{formatDate(order.created_at)}</p>
                        </div>
                        <div>
                            <span style={{ color: "#6b7280", fontSize: "0.75rem" }}>Last Updated</span>
                            <p style={{ color: "white", fontSize: "0.875rem" }}>{formatDate(order.updated_at)}</p>
                        </div>
                    </div>
                </div>
            )}

            {/* Footer */}
            <div style={{ marginTop: "auto", paddingTop: "3rem", textAlign: "center" }}>
                <a href="/" style={{ color: "#22d3ee", fontSize: "0.875rem" }}>
                    ← Back to Home
                </a>
            </div>

            <style jsx global>{`
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(5px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                @keyframes bounceIn {
                    0% { opacity: 0; transform: translateX(-50%) scale(0.3); }
                    50% { opacity: 1; transform: translateX(-50%) scale(1.05); }
                    70% { transform: translateX(-50%) scale(0.9); }
                    100% { transform: translateX(-50%) scale(1); }
                }
            `}</style>
        </div>
    );
}

