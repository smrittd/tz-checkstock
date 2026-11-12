import { kinds, statuses, actions, events, availableActions, escapeHtml as e } from './domain.js';

export const number = value => Number(value).toLocaleString('ru-RU');
export const date = value => new Date(value).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' });
const option = (value, text, selected) => `<option value="${e(value)}" ${String(selected) === String(value) ? 'selected' : ''}>${e(text)}</option>`;
export const options = (entries, selected) => entries.map(([value, text]) => option(value, text, selected)).join('');
const product = (inv, id) => inv.products.find(p => p.id === id);
const productCell = p => `<span class="product-name">${e(p?.name || 'Неизвестный товар')}</span><span class="muted">${e(p?.sku)}</span>`;
const warehouseName = (inv, id) => inv.warehouses.find(w => w.id === id)?.name || '—';
const warehouseLabel = w => `${e(w.name)} ${w.archived_at ? '<span class="badge">Архив</span>' : ''}`;
export const badge = value => `<span class="badge ${e(value)}">${e(statuses[value] || value)}</span>`;
const empty = (columns, message) => `<tr><td colspan="${columns}" class="empty">${e(message)}</td></tr>`;
const table = (headers, rows, numberColumns = []) => `<div class="table-scroll"><table><thead><tr>${headers.map((h, index) => `<th scope="col"${numberColumns.includes(index) ? ' class="number"' : ''}>${h}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table></div>`;

function productFilter(inv, value) {
  return `<label>Товар<select id="filter-product" data-filter="product_id">${option('', 'Все товары', value)}${options(inv.products.map(p => [p.id, `${p.sku} · ${p.name}`]), value)}</select></label>`;
}

export function inventoryView(inv, filters) {
  const products = inv.products.filter(p => `${p.name} ${p.sku}`.toLowerCase().includes(filters.search.toLowerCase().trim()));
  const warehouses = inv.warehouses.filter(w => !filters.warehouse_id || String(w.id) === filters.warehouse_id);
  const total = inv.totals;
  const rows = products.map(p => {
    const warehouseRows = warehouses.map(w => {
      const stock = p.warehouses.find(s => s.warehouse_id === w.id) || { on_hand: 0, reserved: 0, available: 0 };
      return `<tr><td>${productCell(p)}</td><td>${warehouseLabel(w)}</td><td class="number">${number(stock.on_hand)}</td><td class="number">${number(stock.reserved)}</td><td class="number available">${number(stock.available)}</td><td>${w.archived_at ? '—' : `<button class="link-button" data-create="receipt" data-product="${p.id}" data-warehouse="${w.id}">Приход</button>`}</td></tr>`;
    }).join('');
    const totalRow = !filters.warehouse_id && warehouses.length > 1
      ? `<tr class="subtotal"><td>${productCell(p)}</td><td>Все склады</td><td class="number">${number(p.totals.on_hand)}</td><td class="number">${number(p.totals.reserved)}</td><td class="number available">${number(p.totals.available)}</td><td></td></tr>`
      : '';
    return warehouseRows + totalRow;
  }).join('');
  const outside = products.map(p => `<tr><td>${productCell(p)}</td>${['transfer_in_transit', 'fbs_in_transit', 'fbo_in_transit', 'at_marketplace', 'delivered'].map(key => `<td class="number">${number(p.totals[key])}${key === 'at_marketplace' && p.marketplaces.length ? `<div class="muted">${p.marketplaces.map(m => `${e(m.destination)}: ${number(m.quantity)}`).join('<br>')}</div>` : ''}</td>`).join('')}</tr>`).join('');
  return `<div class="summary" aria-label="Итоги по всему магазину">
    <div><span>Физически на складах</span><strong>${number(total.on_hand)}</strong></div>
    <div><span>Доступно</span><strong class="available">${number(total.available)}</strong></div>
    <div><span>В резерве FBS</span><strong>${number(total.reserved)}</strong></div>
    <div><span>Всего в пути</span><strong class="transit">${number(total.transfer_in_transit + total.fbs_in_transit + total.fbo_in_transit)}</strong></div>
  </div>
  <div class="filters"><label class="search">Поиск товара<input id="filter-search" data-filter="search" type="search" placeholder="Название или артикул" value="${e(filters.search)}"></label>
  <label>Склад<select id="filter-warehouse" data-filter="warehouse_id">${option('', 'Все склады', filters.warehouse_id)}${options(inv.warehouses.map(w => [w.id, w.name + (w.archived_at ? ' (архив)' : '')]), filters.warehouse_id)}</select></label></div>
  <section class="panel"><div class="panel-heading"><h2>Остатки по складам</h2><p>Доступно = физический остаток − резерв FBS. Архивные склады сохраняют свой товар.</p></div>
  ${table(['Товар', 'Склад', 'На складе', 'В резерве', 'Доступно', 'Действие'], rows || empty(6, 'Нет товаров или складов, подходящих под фильтр.'), [2, 3, 4])}</section>
  <section class="panel"><div class="panel-heading"><h2>Товар вне складов</h2><p>По всем складам магазина. Конкретные отправления — в разделе «Операции».</p></div>
  ${table(['Товар', 'Между складами', 'К клиенту · FBS', 'На маркетплейс · FBO', 'На маркетплейсе', 'Доставлено'], outside || empty(6, 'Нет товаров, подходящих под поиск.'), [1, 2, 3, 4, 5])}</section>`;
}

export function actionButtons(movement) {
  return availableActions(movement).map(action => `<button class="small-button ${action === 'cancel' ? 'danger' : ''}" data-transition="${action}" data-id="${e(movement.id)}">${actions[action]}</button>`).join('');
}

function pager(page) {
  const start = page.total ? page.offset + 1 : 0;
  return `<div class="pager"><span>${start}–${Math.min(page.offset + page.items.length, page.total)} из ${page.total}</span><button class="small-button" data-page="-1" ${page.offset === 0 ? 'disabled' : ''}>Назад</button><button class="small-button" data-page="1" ${page.offset + page.limit >= page.total ? 'disabled' : ''}>Далее</button></div>`;
}

export function movementRoute(m, inv) {
  const source = m.source_id ? warehouseName(inv, m.source_id) : 'Поставщик';
  const target = m.destination_id ? warehouseName(inv, m.destination_id) : m.external_destination;
  return `${e(source)} → ${e(target)}`;
}

export function movementsView(page, inv, filters) {
  const rows = page.items.map(m => `<tr><td><button class="link-button" data-detail="${e(m.id)}">${e(kinds[m.kind])}</button><div class="muted">${e(date(m.created_at))}</div></td><td>${productCell(product(inv, m.product_id))}</td><td class="number">${number(m.quantity)}</td><td class="route">${movementRoute(m, inv)}${m.note ? `<small>${e(m.note)}</small>` : ''}</td><td>${badge(m.status)}</td><td><div class="actions">${actionButtons(m) || '<span class="muted">Завершено</span>'}</div></td></tr>`).join('');
  return `<div class="filters">${productFilter(inv, filters.product_id)}<label>Вид операции<select id="filter-kind" data-filter="kind">${option('', 'Все операции', filters.kind)}${options(Object.entries(kinds), filters.kind)}</select></label><label>Статус<select id="filter-status" data-filter="status">${option('', 'Все статусы', filters.status)}${options(Object.entries(statuses), filters.status)}</select></label></div><section class="panel">${table(['Операция', 'Товар', 'Кол-во', 'Откуда → куда', 'Статус', 'Действие'], rows || empty(6, 'Операций пока нет. Создайте приход или измените фильтры.'), [2])}${pager(page)}</section>`;
}

export function warehousesView(inv, filters) {
  const rows = inv.warehouses.filter(w => filters.include_archived || !w.archived_at).map(w => {
    const stocks = inv.products.flatMap(p => p.warehouses.filter(s => s.warehouse_id === w.id));
    return `<tr><td>${warehouseLabel(w)}</td>${['on_hand', 'reserved', 'available'].map(k => `<td class="number">${number(stocks.reduce((sum, s) => sum + s[k], 0))}</td>`).join('')}<td><div class="actions">${w.archived_at ? '<span class="muted">Доступный товар можно вывезти перемещением</span>' : `<button class="small-button" data-rename="${w.id}">Переименовать</button><button class="small-button danger" data-archive="${w.id}">В архив</button>`}</div></td></tr>`;
  }).join('');
  return `<div class="filters"><button class="primary" data-add-warehouse>Добавить склад</button><label><input type="checkbox" id="filter-archived" data-filter="include_archived" ${filters.include_archived ? 'checked' : ''}>Показать архивные</label></div><section class="panel"><div class="panel-heading"><h2>Склады фулфилмента</h2><p>При архивировании остатки и история сохраняются. Новые поступления на архивный склад запрещены.</p></div>${table(['Склад', 'На складе', 'В резерве', 'Доступно', 'Действия'], rows || empty(5, 'Складов нет. Добавьте первый склад.'), [1, 2, 3])}</section>`;
}

export function historyView(page, inv, filters) {
  const rows = page.items.map(event => `<tr><td>${e(date(event.created_at))}</td><td><button class="link-button" data-detail="${e(event.movement_id)}">${e(events[event.action] || event.action)}</button></td><td>${productCell(product(inv, event.product_id))}</td><td class="number">${number(event.quantity)}</td><td>${e(event.source_name)}</td><td>${e(event.destination_name)}</td></tr>`).join('');
  return `<div class="filters">${productFilter(inv, filters.product_id)}${filters.movement_id ? '<button data-clear-history>Показать все операции</button><span class="muted">История выбранной операции</span>' : ''}</div><section class="panel">${table(['Когда', 'Событие', 'Товар', 'Кол-во', 'Откуда', 'Куда'], rows || empty(6, 'Событий по выбранным условиям нет.'), [3])}${pager(page)}</section>`;
}

export function detailView(m, inv) {
  return `<dl><dt>Товар</dt><dd>${productCell(product(inv, m.product_id))}</dd><dt>Количество</dt><dd>${number(m.quantity)}</dd><dt>Маршрут</dt><dd>${movementRoute(m, inv)}</dd><dt>Статус</dt><dd>${badge(m.status)}</dd><dt>Создано</dt><dd>${e(date(m.created_at))}</dd><dt>Примечание</dt><dd>${e(m.note || '—')}</dd><dt>Номер</dt><dd>${e(m.id)}</dd></dl><div class="actions">${actionButtons(m)}<button data-movement-history="${e(m.id)}">История операции</button></div>`;
}
