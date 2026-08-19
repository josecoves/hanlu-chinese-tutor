export type OfflineWritingDraft = {
  mode: "prompt" | "message" | "translation" | "guided";
  level: number;
  promptIndex: number;
  responseText: string;
  attemptId: string;
  targetWords: string[];
};

const DATABASE_NAME = "hanlu-writing";
const STORE_NAME = "drafts";
const CURRENT_DRAFT = "current";

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = window.indexedDB.open(DATABASE_NAME, 1);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        database.createObjectStore(STORE_NAME);
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function loadWritingDraft(): Promise<OfflineWritingDraft | null> {
  const database = await openDatabase();
  try {
    return await new Promise((resolve, reject) => {
      const request = database.transaction(STORE_NAME, "readonly").objectStore(STORE_NAME).get(CURRENT_DRAFT);
      request.onsuccess = () => resolve((request.result as OfflineWritingDraft | undefined) ?? null);
      request.onerror = () => reject(request.error);
    });
  } finally {
    database.close();
  }
}

export async function saveWritingDraft(draft: OfflineWritingDraft): Promise<void> {
  const database = await openDatabase();
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = database.transaction(STORE_NAME, "readwrite");
      transaction.objectStore(STORE_NAME).put(draft, CURRENT_DRAFT);
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error);
    });
  } finally {
    database.close();
  }
}
