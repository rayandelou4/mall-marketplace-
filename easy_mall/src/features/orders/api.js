import { apiRequest, unwrap } from "../../lib/apiClient";

function serializeOrderItems(items) {
  return items.map((i) => ({
    product_id: i.product.id,
    ...(i.variant?.id ? { variant_id: i.variant.id } : {}),
    ...(i.negotiation?.id ? { negotiation_id: i.negotiation.id } : {}),
    quantity: i.quantity,
    ...(i.visitorId ? { conversion_visitor_id: i.visitorId } : {}),
    unit_price: i.negotiation?.accepted_price ?? i.product.price,
    shipping_cost: i.product.shipping_cost || 0,
  }));
}

export function createOrder({ shippingAddress, privateAddressId, items, pointsToRedeem = 0 }) {
  return apiRequest("/orders/orders/", {
    method: "POST",
    body: {
      ...(privateAddressId
        ? { private_address_id: privateAddressId }
        : { shipping_address: shippingAddress }),
      items: serializeOrderItems(items),
      points_to_redeem: Number(pointsToRedeem) || 0,
    },
  });
}

export function buildCheckoutQuotePayload(items, pointsToRedeem = 0) {
  return {
    items: serializeOrderItems(items),
    points_to_redeem: Number(pointsToRedeem) || 0,
  };
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
