// Client-side signing (WebCrypto ECDSA P-256).
// Private key: stored non-extractable in IndexedDB (origin-bound).
// Public key (SPKI, base64): cached in localStorage for server registration.
// Pilot trade-off: the key pair is generated extractable so the SPKI can be exported;
// the private key never leaves IndexedDB. Do not treat this as FIDO2-grade custody.

const DB_NAME = 'mineassure-keys'
const STORE = 'keys'
const spkiKey = (userId: string) => `mineassure.spki.${userId}`

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1)
    req.onupgradeneeded = () => {
      req.result.createObjectStore(STORE)
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

export interface KeyPair {
  privateKey: CryptoKey
  publicKey: CryptoKey
  spkiB64: string
}

export async function generateSigningKey(userId: string): Promise<KeyPair> {
  const keyPair = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, [
    'sign',
    'verify',
  ])
  const spkiB64 = await exportPublicKeySpki(keyPair.publicKey)
  const db = await openDb()
  const tx = db.transaction(STORE, 'readwrite')
  tx.objectStore(STORE).put(keyPair.privateKey, userId)
  await new Promise<void>((res, rej) => {
    tx.oncomplete = () => res()
    tx.onerror = () => rej(tx.error)
  })
  localStorage.setItem(spkiKey(userId), spkiB64)
  return { privateKey: keyPair.privateKey, publicKey: keyPair.publicKey, spkiB64 }
}

export async function getSigningKey(userId: string): Promise<CryptoKey | null> {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const req = db.transaction(STORE, 'readonly').objectStore(STORE).get(userId)
    req.onsuccess = () => resolve(req.result ?? null)
    req.onerror = () => reject(req.error)
  })
}

export function getStoredSpki(userId: string): string | null {
  return localStorage.getItem(spkiKey(userId))
}

export async function exportPublicKeySpki(publicKey: CryptoKey): Promise<string> {
  const spki = await crypto.subtle.exportKey('spki', publicKey)
  return btoa(String.fromCharCode(...new Uint8Array(spki)))
}

export async function signPayload(privateKey: CryptoKey, payload: string): Promise<string> {
  const sig = await crypto.subtle.sign(
    { name: 'ECDSA', hash: 'SHA-256' },
    privateKey,
    new TextEncoder().encode(payload)
  )
  return btoa(String.fromCharCode(...new Uint8Array(sig)))
}

export async function verifyPayload(
  publicKey: CryptoKey,
  payload: string,
  signatureB64: string
): Promise<boolean> {
  try {
    const sig = Uint8Array.from(atob(signatureB64), (c) => c.charCodeAt(0))
    return await crypto.subtle.verify(
      { name: 'ECDSA', hash: 'SHA-256' },
      publicKey,
      sig,
      new TextEncoder().encode(payload)
    )
  } catch {
    return false
  }
}

// Stable canonical message shared with the API: keys sorted, no whitespace.
export function canonicalMessage(fields: Record<string, string | number>): string {
  const keys = Object.keys(fields).sort()
  return JSON.stringify(Object.fromEntries(keys.map((k) => [k, fields[k]])))
}
