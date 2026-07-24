import { check } from 'k6';

export function hasProblemJsonContract(response) {
  const ct = response.headers['Content-Type'] || response.headers['content-type'] || '';
  return check(response, {
    'has application/problem+json content-type': () => ct.includes('application/problem+json'),
    'has required error fields': (r) => {
      try {
        const body = r.json();
        return (
          typeof body.type === 'string' &&
          typeof body.title === 'string' &&
          typeof body.status === 'number' &&
          typeof body.detail === 'string' &&
          typeof body.instance === 'string'
        );
      } catch {
        return false;
      }
    },
  });
}
