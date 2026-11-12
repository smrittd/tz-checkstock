import { test } from 'node:test';
import assert from 'node:assert/strict';
import { request } from '../src/api.js';

test('Запрос отправляет JSON без дополнительного ключа и не повторяется автоматически', async t => {
  const fetch = t.mock.method(globalThis, 'fetch', async () => Response.json({ id: '123' }));
  assert.deepEqual(await request('/receipts', { method: 'POST', body: { quantity: 3 } }), { id: '123' });
  const [url, options] = fetch.mock.calls[0].arguments;
  assert.equal(url, '/api/v1/receipts');
  assert.deepEqual(options.headers, { 'Content-Type': 'application/json' });
  assert.equal(options.body, '{"quantity":3}');
  assert.equal(fetch.mock.callCount(), 1);
});

test('Нехватка передаётся форме с альтернативными складами', async t => {
  const context = { available: 1, total_available: 5, requested: 3, alternatives: [{ warehouse_name: 'Юг', available: 4 }] };
  t.mock.method(globalThis, 'fetch', async () => Response.json({ error: { message: 'Недостаточно товара', context } }, { status: 409 }));
  await assert.rejects(request('/fbs', { method: 'POST', body: {} }), error => {
    assert.equal(error.message, 'Недостаточно товара');
    assert.deepEqual(error.context, context);
    assert.equal(error.uncertain, false);
    return true;
  });
});

test('При потере ответа на запись предлагает проверить операции, без повторной отправки', async t => {
  const fetch = t.mock.method(globalThis, 'fetch', async () => { throw new TypeError('Failed to fetch'); });
  await assert.rejects(request('/receipts', { method: 'POST', body: {} }), error => error.uncertain && /проверьте операции/.test(error.message));
  assert.equal(fetch.mock.callCount(), 1);
});

test('Недоступность чтения предлагает обновление, HTML ошибки прокси не выводится', async t => {
  t.mock.method(globalThis, 'fetch', async () => new Response('<html>502 Bad Gateway</html>', { status: 502 }));
  await assert.rejects(request('/inventory'), error => !error.uncertain && /Сервер временно недоступен/.test(error.message));
});
