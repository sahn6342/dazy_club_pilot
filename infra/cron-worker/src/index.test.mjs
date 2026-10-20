import test from "node:test";
import assert from "node:assert/strict";
import worker, { runSweep } from "./index.js";

const ENV = { API_BASE: "https://api.example.com/", INTERNAL_TOKEN: "s3cret" };

function fakeFetch(handlers) {
  const calls = [];
  const impl = async (url, init = {}) => {
    calls.push({ url, init });
    const h = handlers.shift();
    return new Response(h.body ?? "{}", { status: h.status ?? 200 });
  };
  impl.calls = calls;
  return impl;
}

test("posts the sweep with the token and a request id, then checks readiness", async () => {
  const f = fakeFetch([{ body: '{"expired":2,"reconciled":1}' }, { body: '{"status":"ok"}' }]);
  const result = await runSweep(ENV, f);

  assert.equal(f.calls.length, 2);
  assert.equal(f.calls[0].url, "https://api.example.com/api/v1/internal/sweep"); // trailing slash in API_BASE tolerated
  assert.equal(f.calls[0].init.method, "POST");
  assert.equal(f.calls[0].init.headers["X-Internal-Token"], "s3cret");
  assert.match(f.calls[0].init.headers["X-Request-ID"], /^cron-[0-9a-f-]{36}$/);
  assert.equal(f.calls[1].url, "https://api.example.com/api/v1/health/ready");
  assert.equal(f.calls[1].init.headers["X-Request-ID"], f.calls[0].init.headers["X-Request-ID"]);
  assert.deepEqual({ expired: result.expired, reconciled: result.reconciled }, { expired: 2, reconciled: 1 });
  assert.equal(result.requestId, f.calls[0].init.headers["X-Request-ID"]);
});

test("a rejected sweep fails the run and skips the readiness check", async () => {
  const f = fakeFetch([{ status: 401, body: '{"detail":"Invalid token."}' }]);
  await assert.rejects(runSweep(ENV, f), /sweep failed: HTTP 401 .*Invalid token/);
  assert.equal(f.calls.length, 1);
});

test("a 404 means the endpoint is disabled on the API (no DAZY_INTERNAL_TOKEN) and fails loudly", async () => {
  const f = fakeFetch([{ status: 404, body: '{"detail":"Not found."}' }]);
  await assert.rejects(runSweep(ENV, f), /HTTP 404/);
});

test("an unhealthy API fails the run even though the sweep itself worked", async () => {
  const f = fakeFetch([{ body: '{"expired":0,"reconciled":0}' }, { status: 503, body: '{"status":"degraded","db":"error"}' }]);
  await assert.rejects(runSweep(ENV, f), /API not ready: HTTP 503 .*degraded/);
});

test("missing configuration is reported by name, before any request", async () => {
  const f = fakeFetch([]);
  await assert.rejects(runSweep({ INTERNAL_TOKEN: "x" }, f), /API_BASE is not set/);
  await assert.rejects(runSweep({ API_BASE: "https://a" }, f), /INTERNAL_TOKEN is not set/);
  assert.equal(f.calls.length, 0);
});

test("network errors and timeouts propagate", async () => {
  const boom = async () => { throw new TypeError("fetch failed"); };
  await assert.rejects(runSweep(ENV, boom), /fetch failed/);
  const timedOut = async () => { throw new DOMException("The operation timed out.", "TimeoutError"); };
  await assert.rejects(runSweep(ENV, timedOut), /timed out/);
});

test("every request carries an abort signal so a hung API cannot hold the worker", async () => {
  const f = fakeFetch([{ body: "{}" }, { body: "{}" }]);
  await runSweep(ENV, f);
  assert.ok(f.calls.every((c) => c.init.signal instanceof AbortSignal));
});

test("scheduled() rethrows failures so Cloudflare marks the invocation failed", async () => {
  const realFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response("nope", { status: 500 });
  const realError = console.error;
  const logged = [];
  console.error = (m) => logged.push(m);
  try {
    await assert.rejects(worker.scheduled({}, ENV), /sweep failed: HTTP 500/);
    assert.match(logged[0], /sweep failed/);
    assert.ok(!logged[0].includes("s3cret"), "the token must never be logged");
  } finally {
    globalThis.fetch = realFetch;
    console.error = realError;
  }
});

test("the HTTP surface is closed", async () => {
  const res = await worker.fetch();
  assert.equal(res.status, 404);
});
