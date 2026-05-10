# Remediation Checklist — inc-a2966527
**Overall Severity:** P1  |  **Issues:** 5

---

## DB_TIMEOUT — P1
**Services:** api-gateway, payment-service, postgres-primary

- [ ] **Step 1:** Mitigate the immediate payment-path timeout by temporarily reducing pressure on `payment-service` and `postgres-primary`: scale `payment-service` down to a safe level or pause nonessential payment traffic while `postgres-primary` is at `active_connections=195` of `max_connections=200` and `api-gateway` is returning `504` for `POST /api/v1/payments`.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `payment-path-pressure-mitigation`

- [ ] **Step 2:** Increase PostgreSQL connection headroom on `postgres-primary` for the `payments` database by raising `max_connections` only if capacity allows, and verify the pooler/application-side limits so `payment-service` can stop failing with `DB_CONN_TIMEOUT` while creating payment transactions.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `postgres-connection-pool-tuning`

- [ ] **Step 3:** Investigate and resolve the slow insert on `payment_transactions` (`query_hash=ab91ff`, `slow_query_ms=8421`) by checking indexes, query plan, and write contention, since `postgres-primary` also logged `lock_wait_ms=6032` with `blocking_pid=4421` and `blocked_query_hash=cd77aa`.
  - Owner: `Database engineer`  |  Est. time: 45 min  |  Runbook: `postgres-slow-query-lock-wait`

- [ ] **Step 4:** Identify the session or transaction held by `blocking_pid=4421` on `postgres-primary`, terminate the blocker if it is safe, and confirm the lock wait clears so `payment-service` can again initialize payments without `PAYMENT_INIT_FAILED`.
  - Owner: `Database engineer`  |  Est. time: 15 min  |  Runbook: `postgres-blocking-session-removal`


## OOM_KILL — P1
**Services:** payment-service, payment-service-7d9f84c9b6-rx2pm

- [ ] **Step 1:** Stop the crash loop on `payment-service-7d9f84c9b6-rx2pm` by rolling back or restarting the affected pod after the `OOMKilled` event and `java.lang.OutOfMemoryError: Java heap space` so the deployment can regain a stable process.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `k8s-oom-crashloop-stabilization`

- [ ] **Step 2:** Increase the `payment-service` container memory limit and heap settings to fit observed runtime needs, because Kubernetes explicitly reported `Container killed due to memory limit exceeded` for the pod in `namespace=prod`.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `java-heap-memory-rightsizing`

- [ ] **Step 3:** Inspect the `payment-service` pod for the memory spike source by reviewing heap usage, recent code paths, and request volume tied to the crashing container `payment-service-7d9f84c9b6-rx2pm` with `restart_count=3`.
  - Owner: `Service owner`  |  Est. time: 30 min  |  Runbook: `java-service-heap-analysis`

- [ ] **Step 4:** After stabilization, validate that `payment-service` no longer emits `OutOfMemoryError` and that Kubernetes no longer reports `CrashLoopBackOff` or `OOMKilled` for the production pod before restoring full traffic.
  - Owner: `On-call engineer`  |  Est. time: 15 min  |  Runbook: `k8s-pod-recovery-validation`


## DB_TIMEOUT — P1
**Services:** api-gateway, payment-service, postgres-primary

- [ ] **Step 1:** Reduce write contention on `postgres-primary` by pausing or throttling the payment insert path tied to `payment_transactions` while `slow_query_ms=8421` and `lock_wait_ms=6032` are occurring, since `payment-service` is already failing with `Unable to initialize payment due to database connection failure`.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `payment-write-throttle`

- [ ] **Step 2:** Examine the blocking transaction for `blocked_query_hash=cd77aa` and `blocking_pid=4421` on `postgres-primary`, then clear the blocker if it is a stale or unsafe long-running transaction so lock waits stop affecting payment initialization.
  - Owner: `Database engineer`  |  Est. time: 20 min  |  Runbook: `postgres-lock-blocker-removal`

- [ ] **Step 3:** Profile the `payment_transactions` insert path behind `query_hash=ab91ff` and add the missing index or query fix that is causing the `slow insert query detected` warning, because the database latency is directly contributing to `payment-service` failures.
  - Owner: `Service owner`  |  Est. time: 60 min  |  Runbook: `postgres-insert-query-optimization`

- [ ] **Step 4:** Verify connection acquisition behavior in `payment-service` after the database changes, ensuring new payments no longer fail with `PAYMENT_INIT_FAILED` or database connection failure when hitting `postgres-primary`.
  - Owner: `On-call engineer`  |  Est. time: 15 min  |  Runbook: `payment-db-recovery-check`


## AUTH_ERROR — P1
**Services:** auth-service, api-gateway, redis-cache

- [ ] **Step 1:** Mitigate the user-facing 401s by temporarily reducing dependency on Redis session lookup in `auth-service` or routing around the slow `redis-prod-01` instance if possible, because `GET key=session:98281` is taking `latency_ms=2740` and causing `TOKEN_VALIDATION_FAILED`.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `auth-redis-lookup-mitigation`

- [ ] **Step 2:** Investigate `redis-prod-01` for saturation or latency spikes and check whether the cache is under-resourced or blocked, since `redis-cache` already warned that command latency exceeded threshold for session lookups.
  - Owner: `Platform team`  |  Est. time: 25 min  |  Runbook: `redis-latency-investigation`

- [ ] **Step 3:** Validate `auth-service` timeout settings and retry behavior for Redis session reads, then tune them so token validation does not fail when `redis-cache` is briefly slow for `session:98281`.
  - Owner: `Service owner`  |  Est. time: 30 min  |  Runbook: `auth-timeout-retry-tuning`

- [ ] **Step 4:** Confirm `api-gateway` stops returning `401` for `GET /api/v1/profile` with `upstream=auth-service` once Redis session lookup latency returns to normal and token validation succeeds.
  - Owner: `On-call engineer`  |  Est. time: 15 min  |  Runbook: `auth-gateway-validation`


## DEPLOY_FAILURE — P1
**Services:** deployment-controller, payment-service

- [ ] **Step 1:** Freeze further rollout of `payment-service` version `v2.8.4` in `namespace=prod` because the deployment controller already detected `error rate increased after deployment` and availability is only `available_replicas=1` out of `desired_replicas=6`.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `deployment-freeze-on-regression`

- [ ] **Step 2:** Rollback `payment-service` from `v2.8.4` to `previous_version=v2.8.3` using change `CHG-9182` to restore replica health and reduce the error rate introduced within the last 30 minutes.
  - Owner: `Release engineer`  |  Est. time: 15 min  |  Runbook: `k8s-deployment-rollback`

- [ ] **Step 3:** Compare `v2.8.4` and `v2.8.3` configuration, image, and runtime changes for `payment-service` to identify the regression that caused the production availability drop from 6 desired replicas to 1 available replica.
  - Owner: `Service owner`  |  Est. time: 45 min  |  Runbook: `release-regression-analysis`

- [ ] **Step 4:** Re-deploy `payment-service` only after the regression is fixed and validate replica availability and error rate in `namespace=prod` before resuming full rollout.
  - Owner: `Release engineer`  |  Est. time: 20 min  |  Runbook: `safe-redeploy-validation`


---

## Post-Incident

- [ ] Confirm all services are stable and error rate is back to baseline
- [ ] Write post-mortem document within 48 hours
- [ ] Update runbooks with any new learnings
- [ ] Schedule blameless retrospective with team
