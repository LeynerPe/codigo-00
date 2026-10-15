// Compuerta G7 — prueba de rendimiento con k6.
// Simula comercios que autorizan y consultan pagos de forma concurrente.
// Umbrales: p95 < 300 ms y tasa de error < 1 %. Si no se cumplen, k6 termina
// con código distinto de cero y el pipeline bloquea el despliegue.
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8000';
const API_KEY = __ENV.API_KEY_A;

export const options = {
  scenarios: {
    comercios: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '10s', target: 20 },  // subida
        { duration: '30s', target: 20 },  // carga sostenida
        { duration: '5s', target: 0 },    // bajada
      ],
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<300'],
    http_req_failed: ['rate<0.01'],
    checks: ['rate>0.99'],
  },
};

const headers = { 'Content-Type': 'application/json', 'X-API-Key': API_KEY };

function stan() {
  // STAN único por iteración: VU (3 dígitos) + iteración (3 dígitos)
  return `${String(__VU % 1000).padStart(3, '0')}${String(__ITER % 1000).padStart(3, '0')}`;
}

export default function () {
  const body = JSON.stringify({
    card_number: '4111111111111111',
    exp_month: 12,
    exp_year: 2030,
    amount: '150000.00',
    currency: 'COP',
    stan: stan(),
  });
  const auth = http.post(`${BASE_URL}/v1/authorizations`, body, { headers, tags: { op: 'autorizacion' } });
  const ok = check(auth, {
    'autorización 201': (r) => r.status === 201,
    'código 00 o 94': (r) => ['00', '94'].includes(r.json('response_code')),
  });
  if (ok) {
    const id = auth.json('transaction_id');
    const query = http.get(`${BASE_URL}/v1/transactions/${id}`, { headers, tags: { op: 'consulta' } });
    check(query, { 'consulta 200': (r) => r.status === 200 });
  }
  sleep(0.2);
}

export function handleSummary(data) {
  return { [__ENV.SUMMARY_PATH || 'k6-summary.json']: JSON.stringify(data, null, 2) };
}
