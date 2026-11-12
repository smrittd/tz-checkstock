export class ApiError extends Error {
  constructor(message, context = {}, uncertain = false) {
    super(message);
    this.context = context;
    this.uncertain = uncertain;
  }
}

export async function request(path, { method = 'GET', body } = {}) {
  let response;
  try {
    response = await fetch(`/api/v1${path}`, {
      method,
      headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(15000),
    });
  } catch {
    throw new ApiError(method === 'GET'
      ? 'Нет связи с сервером. Проверьте подключение и нажмите «Обновить».'
      : 'Ответ сервера не получен. Перед повторной отправкой проверьте операции: действие могло выполниться.', {}, method !== 'GET');
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(data?.error?.message || 'Сервер временно недоступен. Обновите данные перед повторной попыткой.', data?.error?.context, method !== 'GET' && response.status >= 500);
  }
  return data;
}
