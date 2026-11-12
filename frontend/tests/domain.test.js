import { test } from 'node:test';
import assert from 'node:assert/strict';
import { availableActions, eligibleWarehouses, stockAt } from '../src/domain.js';
import { operationPayload, operationFields } from '../src/forms.js';
import { inventoryView, historyView } from '../src/views.js';

const warehouses = [{ id: 1, name: 'Север', archived_at: null }, { id: 2, name: 'Юг', archived_at: '2026-01-01' }];
const totals = { on_hand: 10, reserved: 2, available: 8, transfer_in_transit: 0, fbs_in_transit: 0, fbo_in_transit: 0, at_marketplace: 0, delivered: 0 };
const inv = { warehouses, totals, products: [{ id: 1, name: '<img src=x onerror=alert(1)>', sku: 'SKU-101', warehouses: [{ warehouse_id: 1, on_hand: 10, reserved: 2, available: 8 }], totals, marketplaces: [] }] };

test('FBS предлагает только действия, подходящие текущему состоянию', () => {
  assert.deepEqual(availableActions({ kind: 'fbs', status: 'reserved' }), ['ship', 'cancel']);
  assert.deepEqual(availableActions({ kind: 'fbs', status: 'in_transit' }), ['deliver']);
  for (const status of ['delivered', 'cancelled', 'received']) {
    assert.deepEqual(availableActions({ kind: 'fbs', status }), []);
  }
});

test('Перемещения и FBO можно принять только в пути; приход уже завершён', () => {
  for (const kind of ['transfer', 'fbo']) {
    assert.deepEqual(availableActions({ kind, status: 'in_transit' }), ['receive']);
    assert.deepEqual(availableActions({ kind, status: 'received' }), []);
  }
  assert.deepEqual(availableActions({ kind: 'receipt', status: 'received' }), []);
});

test('Архивный склад доступен только как источник перемещения', () => {
  assert.deepEqual(eligibleWarehouses(warehouses, 'transfer', 'source_id'), warehouses);
  for (const [kind, field] of [['transfer', 'destination_id'], ['receipt', 'warehouse_id'], ['fbs', 'warehouse_id'], ['fbo', 'warehouse_id']]) {
    assert.deepEqual(eligibleWarehouses(warehouses, kind, field).map(w => w.id), [1]);
  }
});

test('Остаток берётся для выбранного товара и склада, а не суммарный', () => {
  assert.equal(stockAt(inv, '1', '1').available, 8);
  assert.equal(stockAt(inv, '1', '2'), undefined);
});

test('Формы отправляют типизированные данные и только поля выбранной операции', () => {
  const values = { product_id: '1', quantity: '3', warehouse_id: '2', source_id: '1', destination_id: '2', note: '  Тест  ', destination: ' Ozon ' };
  const base = { product_id: 1, quantity: 3, note: 'Тест' };
  assert.deepEqual(operationPayload({ ...values, kind: 'receipt' }), { ...base, warehouse_id: 2 });
  assert.deepEqual(operationPayload({ ...values, kind: 'transfer' }), { ...base, source_id: 1, destination_id: 2 });
  for (const kind of ['fbs', 'fbo']) {
    assert.deepEqual(operationPayload({ ...values, kind }), { ...base, warehouse_id: 2, destination: 'Ozon' });
  }
});

test('Остатки и формы экранируют пользовательские строки', () => {
  for (const html of [inventoryView(inv, { search: '', warehouse_id: '' }), operationFields(inv, { note: '</textarea><script>alert(1)</script>' })]) {
    assert.doesNotMatch(html, /<img src=x/);
    assert.match(html, /&lt;img/);
    assert.doesNotMatch(html, /<script>/);
  }
});

test('Поиск и фильтр склада скрывают чужие строки, но сохраняют итоги магазина', () => {
  const html = inventoryView(inv, { search: 'sku-101', warehouse_id: '2' });
  assert.match(html, /Архив/);
  assert.doesNotMatch(html, /data-create="receipt"/);
  assert.match(html, /Физически на складах/);
  assert.match(inventoryView(inv, { search: 'несуществующий', warehouse_id: '' }), /Нет товаров или складов/);
});

test('История использует сохранённые названия, а не переименованный склад', () => {
  const html = historyView({ items: [{ movement_id: 'abc', product_id: 1, created_at: '2026-01-01', action: 'receipt', quantity: 3, source_name: 'Поставщик', destination_name: 'Прежнее название' }], total: 1, offset: 0, limit: 20 }, inv, { product_id: '' });
  assert.match(html, /Прежнее название/);
  assert.match(html, /data-page="1" disabled/);
});
