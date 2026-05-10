# Remediation Checklist — inc-61f4f1df
**Overall Severity:** P1  |  **Issues:** 5

---

## DB_TIMEOUT — P1
**Services:** payment-service, postgres-primary, api-gateway

- [ ] **Step 1:** Reduce immediate load on `postgres-primary` by scaling down or pausing non-critical `payment-service` traffic at `api-gateway` for `POST /api/v1/payments`, because `active_connections=195` is already near `max_connections=200` and `payment-service` is failing with `Database connection timed out while creating payment transaction`.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `payment-traffic-throttle`

- [ ] **Step 2:** Increase `postgres-primary` connection capacity temporarily if safe, and restart or recycle `payment-service` pods so stale pooled connections are dropped; the log shows `FATAL: remaining connection slots are reserved for non-replication superuser connections`, which means the pool is exhausting normal slots.
  - Owner: `Platform team`  |  Est. time: 15 min  |  Runbook: `postgres-connection-capacity`

- [ ] **Step 3:** Inspect `payment-service` database pool settings and reduce max pool size to below available PostgreSQL headroom, then redeploy `payment-service` after confirming it no longer opens connections aggressively against `postgres-primary`.
  - Owner: `Service owner`  |  Est. time: 25 min  |  Runbook: `db-pool-tuning`

- [ ] **Step 4:** Review PostgreSQL server-side activity for the `payments` database, focusing on long-running transactions and idle-in-transaction sessions that explain `wait_event=ClientRead` and the near-exhausted state on `postgres-primary`.
  - Owner: `Database administrator`  |  Est. time: 30 min  |  Runbook: `postgres-session-investigation`


## OOM_KILL — P1
**Services:** payment-service, kubelet, kubernetes

- [ ] **Step 1:** Immediately raise the memory limit for `payment-service-7d9f84c9b6-rx2pm` in namespace `prod` or scale out replicas to stop the `OOMKilled` loop; kubelet shows `restart_count=3` and the container is in `CrashLoopBackOff`.
  - Owner: `Platform team`  |  Est. time: 10 min  |  Runbook: `k8s-memory-bump`

- [ ] **Step 2:** Restart the failing `payment-service` pod after the memory change so Java can start cleanly and clear the `java.lang.OutOfMemoryError: Java heap space` condition currently seen in the container logs.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `k8s-pod-restart`

- [ ] **Step 3:** Check the JVM heap sizing and container memory request/limit for `payment-service` to ensure the Java heap is not sized too close to the Kubernetes limit that triggered `Container killed due to memory limit exceeded`.
  - Owner: `Service owner`  |  Est. time: 20 min  |  Runbook: `jvm-heap-rightsizing`

- [ ] **Step 4:** Inspect recent `payment-service` code paths and payload sizes for the workload hitting pod `payment-service-7d9f84c9b6-rx2pm`, since the heap OOM indicates either a regression or a request pattern causing excessive object retention.
  - Owner: `Service owner`  |  Est. time: 30 min  |  Runbook: `heap-oom-root-cause`


## NETWORK_ERROR — P1
**Services:** api-gateway, payment-service

- [ ] **Step 1:** Temporarily reduce or shed `POST /api/v1/payments` traffic at `api-gateway` to stop the repeated `504` and `502` responses while `upstream=payment-service` is timing out after `12030ms`, `8321ms`, and `15012ms`.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `gateway-traffic-shaping`

- [ ] **Step 2:** Verify whether `api-gateway` upstream timeouts and retry settings are masking a slower `payment-service` response path, then align the gateway timeout with the current upstream behavior to avoid retry amplification on `POST /api/v1/payments`.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `gateway-timeout-tuning`

- [ ] **Step 3:** Correlate the gateway errors with `payment-service` health and pod restarts to confirm whether the 502/504s are caused by the same degraded pod that is logging DB timeouts and OOM events.
  - Owner: `Service owner`  |  Est. time: 20 min  |  Runbook: `upstream-health-correlation`

- [ ] **Step 4:** Inspect `api-gateway` retry policy for `POST /api/v1/payments` and disable aggressive retries if they are extending latency, since the log shows `request timeout after retry attempt` on trace `e19bc1`.
  - Owner: `Platform team`  |  Est. time: 25 min  |  Runbook: `gateway-retry-policy`


## AUTH_ERROR — P1
**Services:** auth-service, redis-cache, api-gateway

- [ ] **Step 1:** Reduce session lookup pressure on `redis-prod-01` by temporarily lowering authentication concurrency or routing less critical token validation away from the hot path, because `GET key=session:98281` already shows `latency_ms=2740` and `auth-service` is failing with `Redis session lookup timeout`.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `redis-hot-key-mitigation`

- [ ] **Step 2:** Check `redis-cache` health, CPU, and latency on `redis-prod-01` and restart or reshard if necessary to clear the command latency spike causing token validation failures in `auth-service`.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `redis-latency-response`

- [ ] **Step 3:** Validate whether `auth-service` has a fallback path for token validation when Redis is slow, since `api-gateway` is returning `401` on `/api/v1/profile` due to `authentication failed due to token validation timeout`.
  - Owner: `Service owner`  |  Est. time: 25 min  |  Runbook: `auth-fallback-review`

- [ ] **Step 4:** Investigate the Redis session key pattern, eviction policy, and any recent session storm affecting `session:98281`-style lookups so the root cause of the `Redis command latency exceeded threshold` warning is identified.
  - Owner: `Database administrator`  |  Est. time: 30 min  |  Runbook: `redis-session-root-cause`


## DEPLOY_FAILURE — P2
**Services:** deployment-controller, payment-service, kubernetes

- [ ] **Step 1:** Roll back `payment-service` from `version=v2.8.4` to `previous_version=v2.8.3` in namespace `prod` because the deployment controller logged `error rate increased after deployment` and `available_replicas=1` is below the desired `6`.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `deployment-rollback`

- [ ] **Step 2:** Pause the rollout for `deployment=payment-service` and verify the remaining replica health before allowing any further progression, since only 1 of 6 replicas is available after `CHG-9182`.
  - Owner: `Platform team`  |  Est. time: 5 min  |  Runbook: `rollout-pause-check`

- [ ] **Step 3:** Compare the `v2.8.4` change set against `v2.8.3` and isolate the deployment-specific regression that correlates with the observed availability drop and increased error rate.
  - Owner: `Service owner`  |  Est. time: 30 min  |  Runbook: `deploy-regression-analysis`

- [ ] **Step 4:** After rollback or fix, verify `kubernetes` reports `available_replicas` back to the desired count for `payment-service` and confirm error rate returns to baseline before resuming rollout.
  - Owner: `Platform team`  |  Est. time: 15 min  |  Runbook: `post-rollback-verification`


---

## Post-Incident

- [ ] Confirm all services are stable and error rate is back to baseline
- [ ] Write post-mortem document within 48 hours
- [ ] Update runbooks with any new learnings
- [ ] Schedule blameless retrospective with team
