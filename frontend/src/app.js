import { request } from './api.js';
import { kinds, actions, escapeHtml as e, errorMessage } from './domain.js';
import { inventoryView, movementsView, warehousesView, historyView, detailView, date } from './views.js';
import { operationFields, operationPayload, stockHint } from './forms.js';

const $ = selector => document.querySelector(selector);
const titles = {
  inventory: ['Остатки', 'Товар на складах, в резерве и в пути.'],
  movements: ['Операции', 'Приходы, перемещения и отправки FBS / FBO.'],
  warehouses: ['Склады', 'Управление складами и их остатками.'],
  history: ['История', 'Все изменения учёта: какой товар, сколько, откуда и куда.'],
};
const state = {
  route: 'inventory', inventory: null, page: null, loading: false, mutating: false,
  filters: {
    inventory: { search: '', warehouse_id: '' },
    movements: { product_id: '', kind: '', status: '', offset: 0 },
    warehouses: { include_archived: true },
    history: { product_id: '', movement_id: '', offset: 0 },
  },
};
let loadId = 0;
let formMode = null;
let formBusy = false;

function notice(message, error = false) {
  $('#notice').textContent = message;
  $('#notice').className = error ? 'error' : '';
  $('#notice').hidden = !message;
}

function render() {
  const filters = state.filters[state.route];
  const inv = state.inventory;
  if (!inv) return;
  $('#store-name').textContent = inv.store;
  const renderers = { inventory: () => inventoryView(inv, filters), warehouses: () => warehousesView(inv, filters), movements: () => movementsView(state.page, inv, filters), history: () => historyView(state.page, inv, filters) };
  $('#view').innerHTML = renderers[state.route]();
}

function syncBusy() {
  $('#refresh').disabled = state.loading || state.mutating;
  $('#new-operation').disabled = !state.inventory || state.loading || state.mutating;
  $('#view').setAttribute('aria-busy', String(state.loading));
}

async function load() {
  const id = ++loadId;
  const route = state.route;
  const filters = state.filters[route];
  state.loading = true;
  syncBusy();
  $('#view').innerHTML = '<p class="empty">Загружаем данные…</p>';
  try {
    const query = new URLSearchParams(Object.entries(filters).filter(([key, value]) => key !== 'offset' && value !== ''));
    query.set('limit', '20');
    query.set('offset', String(filters.offset || 0));
    const [inventory, page] = await Promise.all([
      request('/inventory'),
      ['movements', 'history'].includes(route) ? request(`/${route}?${query}`) : Promise.resolve(null),
    ]);
    if (id !== loadId) return;
    state.inventory = inventory;
    state.page = page;
    render();
    $('#updated').textContent = `Обновлено ${date(new Date())}`;
  } catch (error) {
    if (id !== loadId) return;
    $('#view').innerHTML = `<div class="error" role="alert">${e(errorMessage(error))} <button id="retry" class="small-button">Повторить загрузку</button></div>`;
    $('#updated').textContent = '';
  } finally {
    if (id === loadId) { state.loading = false; syncBusy(); }
  }
}

function navigate() {
  if (location.hash === '#content') return;
  const route = location.hash.slice(1);
  state.route = Object.hasOwn(titles, route) ? route : 'inventory';
  $('#page-title').textContent = titles[state.route][0];
  $('#page-description').textContent = titles[state.route][1];
  document.title = `${titles[state.route][0]} — CheckStock`;
  document.querySelectorAll('.navigation a').forEach(a => {
    if (a.hash === `#${state.route}`) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  });
  load();
}

function formValues() { return Object.fromEntries(new FormData($('#editor'))); }

function updateFormHint() {
  if (formMode?.type !== 'operation') return;
  const values = formValues();
  $('#stock-hint').textContent = stockHint(state.inventory, values);
  const destination = $('#editor [name="destination_id"]');
  if (destination) destination.setCustomValidity(values.source_id === values.destination_id ? 'Выберите другой склад для приёмки.' : '');
}

function openOperation(values = {}) {
  if (state.mutating || !state.inventory) return;
  formMode = { type: 'operation' };
  $('#form-title').textContent = 'Новая операция';
  $('#form-fields').innerHTML = operationFields(state.inventory, values);
  $('#form-error').hidden = true;
  $('#save').textContent = 'Создать операцию';
  $('#form-dialog').showModal();
  updateFormHint();
}

function openWarehouse(id) {
  if (state.mutating || !state.inventory) return;
  const warehouse = state.inventory.warehouses.find(w => w.id === Number(id));
  formMode = { type: 'warehouse', id: warehouse?.id };
  $('#form-title').textContent = warehouse ? 'Переименовать склад' : 'Добавить склад';
  $('#form-fields').innerHTML = `<label>Название склада<input name="name" maxlength="120" required value="${e(warehouse?.name || '')}" placeholder="Например, Запад"></label>`;
  $('#form-error').hidden = true;
  $('#save').textContent = 'Сохранить склад';
  $('#form-dialog').showModal();
}

function showFormError(error) {
  const context = error.context || {};
  $('#form-error').innerHTML = `<p>${e(errorMessage(error))}</p>${context.available !== undefined ? `<p>Запрошено: ${context.requested}. Доступно на складе: ${context.available}. Всего доступно: ${context.total_available}.</p>` : ''}${context.alternatives?.length ? `<ul>${context.alternatives.map(w => `<li>${e(w.warehouse_name)}${w.archived ? ' (архив)' : ''}: доступно ${w.available}</li>`).join('')}</ul>` : ''}${context.fields?.length ? `<ul>${context.fields.map(f => `<li>${e(f.field)}: ${e(f.message)}</li>`).join('')}</ul>` : ''}`;
  $('#form-error').hidden = false;
}

$('#editor').addEventListener('change', event => {
  if (event.target.name === 'kind') {
    $('#form-fields').innerHTML = operationFields(state.inventory, formValues());
    $('#form-error').hidden = true;
  }
  updateFormHint();
});

$('#editor').addEventListener('submit', async event => {
  event.preventDefault();
  if (formBusy || state.mutating) return;
  const values = formValues();
  const isWarehouse = formMode.type === 'warehouse';
  if (isWarehouse && !values.name.trim()) {
    showFormError(new Error('Введите название склада.'));
    return;
  }
  if (!isWarehouse && values.destination !== undefined && !values.destination.trim()) {
    showFormError(new Error('Укажите заказ, клиента или маркетплейс.'));
    return;
  }
  const path = isWarehouse ? `/warehouses${formMode.id ? `/${formMode.id}` : ''}` : `/${({ receipt: 'receipts', transfer: 'transfers', fbs: 'fbs', fbo: 'fbo' })[values.kind]}`;
  const body = isWarehouse ? { name: values.name.trim() } : operationPayload(values);
  formBusy = state.mutating = true;
  $('#form-fields').disabled = true;
  $('#save').disabled = true;
  $('#form-error').hidden = true;
  syncBusy();
  try {
    await request(path, { method: isWarehouse && formMode.id ? 'PATCH' : 'POST', body });
    $('#form-dialog').close();
    notice(isWarehouse ? 'Склад сохранён.' : `${kinds[values.kind]}: операция создана.`);
    await load();
  } catch (error) {
    showFormError(error);
  } finally {
    formBusy = state.mutating = false;
    $('#form-fields').disabled = false;
    $('#save').disabled = false;
    syncBusy();
  }
});

async function changeMovement(id, action) {
  if (state.mutating) return;
  state.mutating = true;
  syncBusy();
  document.querySelectorAll('[data-transition]').forEach(button => { button.disabled = true; });
  try {
    await request(`/movements/${encodeURIComponent(id)}/${action}`, { method: 'POST' });
    $('#detail-dialog').close();
    notice(`${actions[action]}: действие выполнено.`);
  } catch (error) {
    $('#detail-dialog').close();
    notice(errorMessage(error), true);
  }
  finally { await load(); state.mutating = false; syncBusy(); }
}

async function archiveWarehouse(id) {
  if (state.mutating) return;
  const warehouse = state.inventory.warehouses.find(w => w.id === Number(id));
  if (!confirm(`Перенести склад «${warehouse.name}» в архив? Остатки и история сохранятся. Доступный товар можно будет вывезти на другой склад.`)) return;
  state.mutating = true;
  syncBusy();
  try {
    await request(`/warehouses/${id}`, { method: 'DELETE' });
    notice(`Склад «${warehouse.name}» перенесён в архив.`);
  } catch (error) { notice(errorMessage(error), true); }
  finally { await load(); state.mutating = false; syncBusy(); }
}

document.addEventListener('click', async event => {
  const button = event.target.closest('button');
  if (!button || button.disabled) return;
  if (button.hasAttribute('data-close')) {
    if (!formBusy && !state.mutating) button.closest('dialog').close();
  } else if (button.id === 'new-operation') openOperation();
  else if (button.id === 'refresh' || button.id === 'retry') { notice(''); load(); }
  else if (button.dataset.create) openOperation({ kind: button.dataset.create, product_id: button.dataset.product, warehouse_id: button.dataset.warehouse });
  else if (button.hasAttribute('data-add-warehouse')) openWarehouse();
  else if (button.dataset.rename) openWarehouse(button.dataset.rename);
  else if (button.dataset.archive) archiveWarehouse(button.dataset.archive);
  else if (button.dataset.transition) changeMovement(button.dataset.id, button.dataset.transition);
  else if (button.dataset.page) { state.filters[state.route].offset += Number(button.dataset.page) * 20; load(); }
  else if (button.dataset.detail) {
    try {
      const movement = await request(`/movements/${encodeURIComponent(button.dataset.detail)}`);
      $('#detail-title').textContent = kinds[movement.kind];
      $('#detail-content').innerHTML = detailView(movement, state.inventory);
      $('#detail-dialog').showModal();
    } catch (error) { notice(errorMessage(error), true); }
  } else if (button.dataset.movementHistory) {
    $('#detail-dialog').close();
    state.filters.history = { product_id: '', movement_id: button.dataset.movementHistory, offset: 0 };
    if (state.route === 'history') load(); else location.hash = 'history';
  } else if (button.hasAttribute('data-clear-history')) {
    state.filters.history.movement_id = ''; state.filters.history.offset = 0; load();
  }
});

document.querySelectorAll('dialog').forEach(dialog => dialog.addEventListener('cancel', event => {
  if (formBusy || state.mutating) event.preventDefault();
}));

$('#view').addEventListener('change', event => {
  const filter = event.target.dataset.filter;
  if (!filter || filter === 'search') return;
  state.filters[state.route][filter] = event.target.type === 'checkbox' ? event.target.checked : event.target.value;
  if (['inventory', 'warehouses'].includes(state.route)) render();
  else { state.filters[state.route].offset = 0; load(); }
});
$('#view').addEventListener('input', event => {
  if (event.target.dataset.filter !== 'search') return;
  const position = event.target.selectionStart;
  state.filters.inventory.search = event.target.value;
  render();
  $('#filter-search').focus();
  $('#filter-search').setSelectionRange(position, position);
});
window.addEventListener('hashchange', navigate);
navigate();
