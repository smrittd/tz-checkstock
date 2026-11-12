import { kinds, eligibleWarehouses, stockAt, escapeHtml as e } from './domain.js';
import { options, number } from './views.js';

export function operationFields(inv, values = {}) {
  const kind = values.kind || 'receipt';
  const explanation = {
    receipt: 'Товар сразу появится на выбранном складе.',
    transfer: 'Товар сразу отправится в путь. По прибытии нажмите «Принять» в операциях.',
    fbs: 'Товар будет зарезервирован на складе. Затем резерв можно отправить или отменить в операциях.',
    fbo: 'Товар сразу отправится на маркетплейс. По прибытии нажмите «Принять» в операциях.',
  };
  const warehouseSelect = (name, title) => {
    const list = eligibleWarehouses(inv.warehouses, kind, name);
    const selected = values[name] || (name === 'destination_id' ? list.find(w => String(w.id) !== String(values.source_id || inv.warehouses[0]?.id))?.id : list[0]?.id);
    return `<label>${title}<select name="${name}" required>${list.length ? options(list.map(w => [w.id, w.name + (w.archived_at ? ' (архив)' : '')]), selected) : '<option value="">Нет доступных складов</option>'}</select></label>`;
  };
  return `<label>Вид операции<select name="kind">${options(Object.entries(kinds), kind)}</select></label>
    <p class="hint">${explanation[kind]}</p>
    <label>Товар<select name="product_id" required>${inv.products.length ? options(inv.products.map(p => [p.id, `${p.sku} · ${p.name}`]), values.product_id || inv.products[0]?.id) : '<option value="">Нет товаров в каталоге</option>'}</select></label>
    ${kind === 'transfer' ? `<div class="form-pair">${warehouseSelect('source_id', 'Откуда')}${warehouseSelect('destination_id', 'Куда')}</div>` : warehouseSelect('warehouse_id', kind === 'receipt' ? 'Склад приёмки' : 'Склад отправки')}
    <p class="hint" id="stock-hint"></p>
    <label>Количество<input name="quantity" type="number" min="1" max="1000000" step="1" required value="${e(values.quantity || '')}" placeholder="Например, 5"></label>
    ${['fbs', 'fbo'].includes(kind) ? `<label>${kind === 'fbs' ? 'Заказ или клиент' : 'Маркетплейс'}<input name="destination" maxlength="120" required value="${e(values.destination || '')}" placeholder="${kind === 'fbs' ? 'Заказ №1001' : 'Ozon'}"></label>` : ''}
    <label>Примечание <span class="muted">(необязательно)</span><textarea name="note" maxlength="500">${e(values.note || '')}</textarea></label>`;
}

export function stockHint(inv, values) {
  const warehouseId = values.source_id || values.warehouse_id;
  const stock = stockAt(inv, values.product_id, warehouseId);
  if (!warehouseId) return 'Сначала добавьте действующий склад в разделе «Склады».';
  if (!stock) return '';
  return `На выбранном складе: ${number(stock.on_hand)} · резерв: ${number(stock.reserved)} · доступно: ${number(stock.available)}`;
}

export function operationPayload(values) {
  const data = { product_id: Number(values.product_id), quantity: Number(values.quantity), note: values.note.trim() };
  if (values.kind === 'transfer') {
    data.source_id = Number(values.source_id);
    data.destination_id = Number(values.destination_id);
  } else {
    data.warehouse_id = Number(values.warehouse_id);
    if (['fbs', 'fbo'].includes(values.kind)) data.destination = values.destination.trim();
  }
  return data;
}
