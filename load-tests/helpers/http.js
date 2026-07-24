export function getBaseUrl() {
  if (!__ENV.LOADTEST_TARGET_URL) {
    throw new Error('LOADTEST_TARGET_URL environment variable is not set');
  }
  return __ENV.LOADTEST_TARGET_URL;
}

export function getJsonHeaders() {
  return {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  };
}
