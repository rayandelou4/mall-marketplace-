import { apiRequest, unwrap } from "../../lib/apiClient";

export function createOrder({ shippingAddress, privateAddressId, items }) {
  return apiRequest("/orders/orders/", {
    method: "POST",
    body: {
      ...(privateAddressId
        ? { private_address_id: privateAddressId }
        : { shipping_address: shippingAddress }),
      items: items.map((i) => ({
        product_id: i.product.id,
        quantity: i.quantity,
        unit_price: i.product.price,
        shipping_cost: i.product.shipping_cost || 0,
      })),
    },
  });
}

export function cancelOrder(orderId) {
  return apiRequest(`/orders/orders/${orderId}/cancel/`, { method: "POST" });
}

export function deleteOrder(orderId) {
  return apiRequest(`/orders/orders/${orderId}/`, { method: "DELETE" });
}

export function confirmReceipt(orderId) {
  return apiRequest(`/orders/orders/${orderId}/confirm_receipt/`, { method: "POST" });
}

export const fetchOrders = () => apiRequest("/orders/orders/").then(unwrap);

export const fetchOrderDetails = (orderId) => apiRequest(`/orders/orders/${orderId}/`);
