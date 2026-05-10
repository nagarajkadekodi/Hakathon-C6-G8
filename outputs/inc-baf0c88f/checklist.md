# Remediation Checklist — inc-baf0c88f
**Overall Severity:** P1  |  **Issues:** 5

---

## DB_TIMEOUT — P1
**Services:** payment-service, postgres-primary

- [ ] **Step 1:** Temporarily reduce load on `postgres-primary` by pausing or rate-limiting `payment-service` payment-creation traffic, since logs show `active_connections=195 max_connections=200` and `FATAL: remaining connection slots are reserved for non-replication superuser connections`.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `postgres-connection-pressure-mitigation`

- [ ] **Step 2:** Check `payment-service` connection pool settings and lower concurrent DB acquisition pressure for the `payments` database to stop `error_code=DB_CONN_TIMEOUT` while the pool is exhausted.
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `payment-service-db-pool-tuning`

- [ ] **Step 3:** Inspect `postgres-primary` for long-lived or idle connections contributing to `wait_event=ClientRead` and close stale sessions that are consuming slots needed by `payment-service`.
  - Owner: `Database administrator`  |  Est. time: 20 min  |  Runbook: `postgres-stale-connection-cleanup`

- [ ] **Step 4:** Validate whether the `payments` workload needs a higher `max_connections` or a transaction pooler in front of `postgres-primary`, because the current ceiling is `max_connections=200` and the database is already near exhaustion.
  - Owner: `Platform team`  |  Est. time: 30 min  |  Runbook: `postgres-capacity-expansion`

- [ ] **Step 5:** Review the `payment-service` code path for connection leaks around `trace_id=a81d11` payment transaction creation and confirm connections are returned on both success and failure paths.
  - Owner: `Service owner`  |  Est. time: 45 min  |  Runbook: `payment-service-connection-leak-investigation`


## OOM_KILL — P1
**Services:** payment-service, payment-service-7d9f84c9b6-rx2pm

- [ ] **Step 1:** Scale `payment-service-7d9f84c9b6-rx2pm` up by increasing replica count or restarting onto a node with enough memory to stop the `CrashLoopBackOff` and restore availability while the memory issue is investigated.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `k8s-oom-immediate-recovery`

- [ ] **Step 2:** Increase the Kubernetes memory limit for the `payment-service` container to exceed the current limit that triggered `event=OOMKilled` and `Container killed due to memory limit exceeded`.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `k8s-memory-limit-adjustment`

- [ ] **Step 3:** Tune the Java heap settings for `payment-service` to fit within the pod memory limit, since the application logged `java.lang.OutOfMemoryError message="Java heap space"` before being killed.
  - Owner: `Service owner`  |  Est. time: 25 min  |  Runbook: `java-heap-sizing`

- [ ] **Step 4:** Inspect the `payment-service-7d9f84c9b6-rx2pm` memory profile and recent code changes for leaks or unbounded object growth that caused `restart_count=3` and repeated OOMs.
  - Owner: `Service owner`  |  Est. time: 40 min  |  Runbook: `java-memory-leak-investigation`

- [ ] **Step 5:** Validate whether the deployment request/limit ratio for `payment-service` matches the observed production load and adjust the pod spec so the container is not repeatedly killed under normal payment traffic.
  - Owner: `Platform team`  |  Est. time: 30 min  |  Runbook: `k8s-resource-rightsizing`


## NETWORK_ERROR — P1
**Services:** api-gateway, payment-service

- [ ] **Step 1:** Reduce or shed `/api/v1/payments` traffic at `api-gateway` while `payment-service` is returning `504` and `502` with latencies of `12030`, `8321`, and `15012` ms to prevent retry amplification.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `gateway-traffic-shedding`

- [ ] **Step 2:** Check `payment-service` health, pod readiness, and restart status to confirm the upstream is actually responding before `api-gateway` continues routing payment requests to it.
  - Owner: `On-call engineer`  |  Est. time: 15 min  |  Runbook: `upstream-health-check`

- [ ] **Step 3:** Inspect `api-gateway` upstream timeout and retry policy for `upstream=payment-service`, because the logs show `message="upstream request timeout"` and `message="request timeout after retry attempt"` on the same endpoint.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `gateway-timeout-retry-tuning`

- [ ] **Step 4:** Correlate the gateway failures with `payment-service` pod events and application logs to determine whether the 502s are caused by crash loops, slow DB calls, or saturated worker threads.
  - Owner: `Service owner`  |  Est. time: 30 min  |  Runbook: `payment-upstream-failure-correlation`

- [ ] **Step 5:** Verify any ingress or service-mesh sidecar configuration affecting `api-gateway -> payment-service` traffic, especially if upstream requests are timing out before the backend can respond.
  - Owner: `Platform team`  |  Est. time: 45 min  |  Runbook: `gateway-mesh-routing-investigation`


## AUTH_ERROR — P1
**Services:** auth-service, redis-cache, api-gateway

- [ ] **Step 1:** Stabilize authentication by checking `redis-prod-01` latency and temporarily reducing session validation pressure, because `GET key=session:98281` is taking `2740ms` and `auth-service` is returning `TOKEN_VALIDATION_FAILED reason="Redis session lookup timeout"`.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `redis-auth-latency-mitigation`

- [ ] **Step 2:** Inspect Redis load, CPU, and memory on `redis-cache`/`redis-prod-01` to determine why session lookups are exceeding threshold and causing 401s through `auth-service`.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `redis-performance-triage`

- [ ] **Step 3:** Validate `auth-service` timeout configuration for Redis session lookup so token validation does not fail at the observed `latency_ms=2740` level.
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `auth-service-redis-timeout-tuning`

- [ ] **Step 4:** Check whether `api-gateway` is amplifying auth retries on `/api/v1/profile`, since it is logging `status=401 latency_ms=3102 upstream=auth-service` after the Redis lookup timeout.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `gateway-auth-retry-review`

- [ ] **Step 5:** Investigate whether Redis session key churn, eviction, or backend saturation is causing the timeout for `session:98281`, and confirm the session data path used by `auth-service` remains healthy under production load.
  - Owner: `Service owner`  |  Est. time: 35 min  |  Runbook: `redis-session-path-investigation`


## DEPLOY_FAILURE — P1
**Services:** deployment-controller, payment-service

- [ ] **Step 1:** Roll back `payment-service` from `v2.8.4` to `previous_version=v2.8.3` because the deployment controller detected `error rate increased after deployment` and availability dropped to `available_replicas=1 desired_replicas=6`.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `rollback-bad-deployment`

- [ ] **Step 2:** Pause the `payment-service` rollout in namespace `prod` to prevent further exposure while the `change_id=CHG-9182` release is investigated.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `deployment-pause-control`

- [ ] **Step 3:** Compare `v2.8.4` against `v2.8.3` for application, config, and resource changes that could explain the post-deploy error-rate increase in `payment-service`.
  - Owner: `Service owner`  |  Est. time: 30 min  |  Runbook: `release-diff-analysis`

- [ ] **Step 4:** Check Kubernetes events, readiness probes, and replica scheduling for `payment-service` to understand why only `1` of `6` replicas is available after the rollout.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `deployment-readiness-investigation`

- [ ] **Step 5:** Once the root cause is identified, re-deploy `payment-service` with the fixed artifact or configuration and confirm availability returns to `6/6` replicas before re-enabling normal traffic.
  - Owner: `Service owner`  |  Est. time: 25 min  |  Runbook: `safe-redeploy-verification`


---

## Post-Incident

- [ ] Confirm all services are stable and error rate is back to baseline
- [ ] Write post-mortem document within 48 hours
- [ ] Update runbooks with any new learnings
- [ ] Schedule blameless retrospective with team
