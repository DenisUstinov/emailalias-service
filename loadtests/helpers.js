export function getBaseUrl() {
    if (!__ENV.LOADTEST_TARGET_URL) {
        throw new Error('LOADTEST_TARGET_URL environment variable is not set');
    }
    return __ENV.LOADTEST_TARGET_URL;
}

export function getJsonHeaders() {
  return { 'Content-Type': 'application/json' };
}

export function generateRandomEmail() {
  const randomString = Math.random().toString(36).substring(2, 10);
  return `user_${randomString}@example.com`;
}
