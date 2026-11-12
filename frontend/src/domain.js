export const kinds = { receipt: 'Приход', transfer: 'Перемещение', fbs: 'Заказ FBS', fbo: 'Поставка FBO' };
export const statuses = { received: 'Принято', reserved: 'В резерве', in_transit: 'В пути', delivered: 'Доставлено', cancelled: 'Отменено' };
export const actions = { receive: 'Принять', ship: 'Отправить', cancel: 'Отменить резерв', deliver: 'Доставлено' };
export const events = { receipt: 'Приход', transfer_shipped: 'Перемещение отправлено', transfer_received: 'Перемещение принято', fbs_reserved: 'Резерв FBS', fbs_shipped: 'FBS отправлен', fbs_cancelled: 'Резерв FBS отменён', fbs_delivered: 'FBS доставлен', fbo_shipped: 'FBO отправлен', fbo_received: 'FBO принят' };

export function availableActions(movement) {
  if (movement.kind === 'fbs' && movement.status === 'reserved') return ['ship', 'cancel'];
  if (movement.kind === 'fbs' && movement.status === 'in_transit') return ['deliver'];
  if (['transfer', 'fbo'].includes(movement.kind) && movement.status === 'in_transit') return ['receive'];
  return [];
}

export function eligibleWarehouses(warehouses, kind, field) {
  return warehouses.filter(w => !w.archived_at || (kind === 'transfer' && field === 'source_id'));
}

export function stockAt(inventory, productId, warehouseId) {
  return inventory.products.find(p => p.id === Number(productId))?.warehouses.find(w => w.warehouse_id === Number(warehouseId));
}

export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
}

export function errorMessage(error) {
  return error.message || 'Не удалось выполнить запрос. Попробуйте обновить страницу.';
}
