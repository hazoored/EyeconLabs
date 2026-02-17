"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { api, getToken } from "@/lib/api";

interface Order {
    id: number;
    order_id: string;
    client_id: number | null;
    client_name: string | null;
    product_name: string;
    status: string;
    notes: string | null;
    created_at: string;
    updated_at: string;
}

interface Client {
    id: number;
    name: string;
}

const statusOptions = [
    { value: 'submitted', label: 'Order Submitted', color: '#9ca3af' },
    { value: 'processing', label: 'Processing', color: '#f59e0b' },
    { value: 'in_progress', label: 'In Progress', color: '#3b82f6' },
    { value: 'completed', label: 'Completed', color: '#10b981' },
    { value: 'delivered', label: 'Delivered', color: '#a855f7' },
];

export default function AdminOrdersPage() {
    const router = useRouter();
    const [orders, setOrders] = useState<Order[]>([]);
    const [clients, setClients] = useState<Client[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    // Create modal state
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [newOrder, setNewOrder] = useState({
        product_name: "",
        client_id: "",
        notes: ""
    });
    const [creating, setCreating] = useState(false);

    // Edit modal state
    const [editingOrder, setEditingOrder] = useState<Order | null>(null);
    const [editStatus, setEditStatus] = useState("");
    const [editNotes, setEditNotes] = useState("");
    const [updating, setUpdating] = useState(false);

    useEffect(() => {
        const token = getToken("admin");
        if (!token) {
            router.push("/admin/login");
            return;
        }
        fetchOrders(token);
        fetchClients(token);
    }, [router]);

    const fetchOrders = async (token: string) => {
        const response = await api<{ orders: Order[] }>("/admin/orders", { token });
        if (response.ok && response.data) {
            setOrders(response.data.orders);
        } else {
            setError(response.error || "Failed to load orders");
        }
        setLoading(false);
    };

    const fetchClients = async (token: string) => {
        const response = await api<{ clients: Client[] }>("/admin/clients", { token });
        if (response.ok && response.data) {
            setClients(response.data.clients);
        }
    };

    const handleCreateOrder = async (e: React.FormEvent) => {
        e.preventDefault();
        setCreating(true);

        const token = getToken("admin");
        if (!token) return;

        const response = await api("/admin/orders", {
            method: "POST",
            token,
            body: {
                product_name: newOrder.product_name,
                client_id: newOrder.client_id ? parseInt(newOrder.client_id) : null,
                notes: newOrder.notes || null
            }
        });

        if (response.ok) {
            setShowCreateModal(false);
            setNewOrder({ product_name: "", client_id: "", notes: "" });
            fetchOrders(token);
        } else {
            alert(response.error || "Failed to create order");
        }
        setCreating(false);
    };

    const handleUpdateOrder = async () => {
        if (!editingOrder) return;
        setUpdating(true);

        const token = getToken("admin");
        if (!token) return;

        const response = await api(`/admin/orders/${editingOrder.order_id}`, {
            method: "PUT",
            token,
            body: {
                status: editStatus,
                notes: editNotes || null
            }
        });

        if (response.ok) {
            setEditingOrder(null);
            fetchOrders(token);
        } else {
            alert(response.error || "Failed to update order");
        }
        setUpdating(false);
    };

    const handleDeleteOrder = async (orderId: string) => {
        if (!confirm("Are you sure you want to delete this order?")) return;

        const token = getToken("admin");
        if (!token) return;

        const response = await api(`/admin/orders/${orderId}`, {
            method: "DELETE",
            token
        });

        if (response.ok) {
            fetchOrders(token);
        } else {
            alert(response.error || "Failed to delete order");
        }
    };

    const openEditModal = (order: Order) => {
        setEditingOrder(order);
        setEditStatus(order.status);
        setEditNotes(order.notes || "");
    };

    const getStatusBadge = (status: string) => {
        const option = statusOptions.find(s => s.value === status);
        return (
            <span style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.25rem",
                padding: "0.25rem 0.75rem",
                borderRadius: "9999px",
                fontSize: "0.75rem",
                fontWeight: 500,
                background: `${option?.color}20`,
                color: option?.color
            }}>
                <span style={{ width: "6px", height: "6px", background: option?.color, borderRadius: "50%" }} />
                {option?.label}
            </span>
        );
    };

    const formatDate = (dateStr: string) => {
        const date = new Date(dateStr);
        return date.toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit"
        });
    };

    const copyToClipboard = (text: string) => {
        navigator.clipboard.writeText(`https://app.eyeconlabs.com/track?id=${text}`);
        alert("Tracking link copied!");
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
                        <h1 className="page-title">Orders</h1>
                        <p className="page-subtitle">Manage client orders and track statuses</p>
                    </div>
                    <button className="btn-primary" onClick={() => setShowCreateModal(true)}>
                        + New Order
                    </button>
                </div>

                {error && (
                    <div style={{ background: "rgba(239,68,68,0.1)", color: "#f87171", padding: "0.75rem 1rem", borderRadius: "0.5rem", marginBottom: "1.5rem" }}>
                        {error}
                    </div>
                )}

                {/* Orders Table */}
                <div className="glass-card">
                    {orders.length > 0 ? (
                        <div className="responsive-table">
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Order ID</th>
                                        <th>Product</th>
                                        <th className="hide-mobile">Client</th>
                                        <th>Status</th>
                                        <th className="hide-mobile">Created</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {orders.map((order) => (
                                        <tr key={order.id}>
                                            <td>
                                                <code style={{
                                                    background: "rgba(6, 182, 212, 0.1)",
                                                    color: "#22d3ee",
                                                    padding: "0.25rem 0.5rem",
                                                    borderRadius: "0.25rem",
                                                    fontSize: "0.75rem",
                                                    cursor: "pointer"
                                                }} onClick={() => copyToClipboard(order.order_id)} title="Click to copy tracking link">
                                                    {order.order_id}
                                                </code>
                                            </td>
                                            <td style={{ color: "white", fontWeight: 500 }}>{order.product_name}</td>
                                            <td className="hide-mobile">{order.client_name || "-"}</td>
                                            <td>{getStatusBadge(order.status)}</td>
                                            <td className="hide-mobile">{formatDate(order.created_at)}</td>
                                            <td>
                                                <div style={{ display: "flex", gap: "0.5rem" }}>
                                                    <button
                                                        onClick={() => openEditModal(order)}
                                                        style={{
                                                            padding: "0.25rem 0.5rem",
                                                            background: "rgba(6, 182, 212, 0.1)",
                                                            color: "#22d3ee",
                                                            border: "none",
                                                            borderRadius: "0.25rem",
                                                            cursor: "pointer",
                                                            fontSize: "0.75rem"
                                                        }}
                                                    >
                                                        Edit
                                                    </button>
                                                    <button
                                                        onClick={() => handleDeleteOrder(order.order_id)}
                                                        style={{
                                                            padding: "0.25rem 0.5rem",
                                                            background: "rgba(239, 68, 68, 0.1)",
                                                            color: "#f87171",
                                                            border: "none",
                                                            borderRadius: "0.25rem",
                                                            cursor: "pointer",
                                                            fontSize: "0.75rem"
                                                        }}
                                                    >
                                                        Delete
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    ) : (
                        <p style={{ color: "#9ca3af", textAlign: "center", padding: "2rem" }}>
                            No orders yet. Create your first order to get started.
                        </p>
                    )}
                </div>
            </main>

            {/* Create Order Modal */}
            {showCreateModal && (
                <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
                    <div className="glass-card modal-content" onClick={(e) => e.stopPropagation()}>
                        <h2 style={{ fontSize: "1.25rem", fontWeight: 700, color: "white", marginBottom: "1.5rem" }}>
                            Create New Order
                        </h2>
                        <form onSubmit={handleCreateOrder}>
                            <div style={{ marginBottom: "1rem" }}>
                                <label style={{ display: "block", color: "#9ca3af", fontSize: "0.875rem", marginBottom: "0.5rem" }}>
                                    Product Name *
                                </label>
                                <input
                                    type="text"
                                    value={newOrder.product_name}
                                    onChange={(e) => setNewOrder({ ...newOrder, product_name: e.target.value })}
                                    className="input-field"
                                    placeholder="e.g. Premium Ad Campaign"
                                    required
                                />
                            </div>
                            <div style={{ marginBottom: "1rem" }}>
                                <label style={{ display: "block", color: "#9ca3af", fontSize: "0.875rem", marginBottom: "0.5rem" }}>
                                    Client (Optional)
                                </label>
                                <select
                                    value={newOrder.client_id}
                                    onChange={(e) => setNewOrder({ ...newOrder, client_id: e.target.value })}
                                    className="input-field"
                                >
                                    <option value="">No Client</option>
                                    {clients.map(client => (
                                        <option key={client.id} value={client.id}>{client.name}</option>
                                    ))}
                                </select>
                            </div>
                            <div style={{ marginBottom: "1.5rem" }}>
                                <label style={{ display: "block", color: "#9ca3af", fontSize: "0.875rem", marginBottom: "0.5rem" }}>
                                    Notes (Optional)
                                </label>
                                <textarea
                                    value={newOrder.notes}
                                    onChange={(e) => setNewOrder({ ...newOrder, notes: e.target.value })}
                                    className="input-field"
                                    placeholder="Any additional notes..."
                                    rows={3}
                                    style={{ resize: "vertical" }}
                                />
                            </div>
                            <div style={{ display: "flex", gap: "0.75rem" }}>
                                <button type="button" className="btn-secondary" onClick={() => setShowCreateModal(false)} style={{ flex: 1 }}>
                                    Cancel
                                </button>
                                <button type="submit" className="btn-primary" disabled={creating} style={{ flex: 1 }}>
                                    {creating ? "Creating..." : "Create Order"}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Edit Order Modal */}
            {editingOrder && (
                <div className="modal-overlay" onClick={() => setEditingOrder(null)}>
                    <div className="glass-card modal-content" onClick={(e) => e.stopPropagation()}>
                        <h2 style={{ fontSize: "1.25rem", fontWeight: 700, color: "white", marginBottom: "0.5rem" }}>
                            Update Order
                        </h2>
                        <p style={{ color: "#9ca3af", fontSize: "0.875rem", marginBottom: "1.5rem" }}>
                            #{editingOrder.order_id}
                        </p>
                        <div style={{ marginBottom: "1rem" }}>
                            <label style={{ display: "block", color: "#9ca3af", fontSize: "0.875rem", marginBottom: "0.5rem" }}>
                                Status
                            </label>
                            <select
                                value={editStatus}
                                onChange={(e) => setEditStatus(e.target.value)}
                                className="input-field"
                            >
                                {statusOptions.map(option => (
                                    <option key={option.value} value={option.value}>{option.label}</option>
                                ))}
                            </select>
                        </div>
                        <div style={{ marginBottom: "1.5rem" }}>
                            <label style={{ display: "block", color: "#9ca3af", fontSize: "0.875rem", marginBottom: "0.5rem" }}>
                                Notes
                            </label>
                            <textarea
                                value={editNotes}
                                onChange={(e) => setEditNotes(e.target.value)}
                                className="input-field"
                                placeholder="Update notes..."
                                rows={3}
                                style={{ resize: "vertical" }}
                            />
                        </div>
                        <div style={{ display: "flex", gap: "0.75rem" }}>
                            <button type="button" className="btn-secondary" onClick={() => setEditingOrder(null)} style={{ flex: 1 }}>
                                Cancel
                            </button>
                            <button type="button" className="btn-primary" onClick={handleUpdateOrder} disabled={updating} style={{ flex: 1 }}>
                                {updating ? "Updating..." : "Update Order"}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
