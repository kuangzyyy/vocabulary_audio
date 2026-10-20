/** Small fetch wrapper for the local FastAPI backend. */

async function toError(response) {
  let message = `请求失败（HTTP ${response.status}）`;
  try {
    const data = await response.json();
    if (typeof data?.detail === 'string' && data.detail.trim()) {
      message = data.detail;
    } else if (Array.isArray(data?.detail)) {
      message = data.detail.map((item) => item.msg ?? String(item)).join('；');
    }
  } catch {
    // Keep the generic HTTP message when the response is not JSON.
  }
  return new Error(message);
}

export async function uploadPdf(file) {
  const form = new FormData();
  form.append('file', file, file.name);
  const response = await fetch('/api/books', {
    method: 'POST',
    body: form,
  });
  if (!response.ok) {
    throw await toError(response);
  }
  return response.json();
}

export async function fetchPage(bookId, pageNumber) {
  const response = await fetch(
    `/api/books/${encodeURIComponent(bookId)}/pages/${pageNumber}`,
    { headers: { Accept: 'application/json' } },
  );
  if (!response.ok) {
    throw await toError(response);
  }
  return response.json();
}

export async function fetchWordAudio(word, accent = 'auto') {
  const params = new URLSearchParams({ text: word, accent });
  const response = await fetch(`/api/audio/word?${params}`, {
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    throw await toError(response);
  }
  return response.json();
}

export async function fetchSentenceAudio(text) {
  const params = new URLSearchParams({ text });
  const response = await fetch(`/api/audio/sentence?${params}`, {
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    throw await toError(response);
  }
  return response.json();
}

export function bookFileUrl(bookId) {
  return `/api/books/${encodeURIComponent(bookId)}/file`;
}
