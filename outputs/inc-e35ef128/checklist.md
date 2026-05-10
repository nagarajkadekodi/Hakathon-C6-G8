# Remediation Checklist — inc-e35ef128
**Overall Severity:** P1  |  **Issues:** 5

---

## DB_TIMEOUT — P1
**Services:** payment-service, postgres-primary, api-gateway

- [ ] **Step 1:** Immediately reduce load on `postgres-primary` by pausing or throttling `payment-service` payment transaction traffic via `api-gateway` for `POST /api/v1/payments`, since logs show `active_connections=195 max_connections=200` and `remaining connection slots are reserved` errors.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `postgres-connection-exhaustion-mitigation`

- [ ] **Step 2:** Scale out `payment-service` only after confirming it is not creating excessive database sessions; check for stuck connection usage in the payment transaction path that is producing `DB_CONN_TIMEOUT` on trace `a81d11`.
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `payment-service-db-client-tuning`

- [ ] **Step 3:** Increase PostgreSQL capacity on `postgres-primary` by raising `max_connections` only if the instance memory headroom allows it, and validate that reserved superuser slots are preserved; current evidence shows the primary is already at 195/200 active connections.
  - Owner: `Database administrator`  |  Est. time: 20 min  |  Runbook: `postgres-max-connections-tuning`

- [ ] **Step 4:** Inspect `payment-service` database client pool settings for the production payment path and reduce pool size or add connection reuse so it stops saturating `postgres-primary`; align the app pool below the current `max_connections=200` minus admin reserve.
  - Owner: `Service owner`  |  Est. time: 30 min  |  Runbook: `jdbc-pool-tuning`

- [ ] **Step 5:** Investigate which code path on `payment-service` is leaking or holding connections during transaction creation for `order_id=ORD-78219`, and confirm whether long-running queries or retries are holding connections until timeout.
  - Owner: `Platform team`  |  Est. time: 45 min  |  Runbook: `postgres-slow-query-investigation`


## OOM_KILL — P1
**Services:** payment-service, kubelet, kubernetes

- [ ] **Step 1:** Immediately roll back or pause the current `payment-service-7d9f84c9b6-rx2pm` rollout in `namespace=prod` because the pod is in `CrashLoopBackOff`, has `restart_count=3`, and is being `OOMKilled`.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `k8s-rollout-pause`

- [ ] **Step 2:** Temporarily raise the `payment-service` container memory limit/request in the prod deployment to stop the `Java heap space` failures while keeping it within node capacity, then restart the pod `payment-service-7d9f84c9b6-rx2pm`.
  - Owner: `Platform team`  |  Est. time: 15 min  |  Runbook: `k8s-memory-limit-adjustment`

- [ ] **Step 3:** Check JVM heap configuration for `payment-service` and lower heap usage or set a safer `-Xmx` below the Kubernetes memory limit so the pod does not exceed the cgroup limit again.
  - Owner: `Service owner`  |  Est. time: 25 min  |  Runbook: `jvm-heap-sizing`

- [ ] **Step 4:** Review recent memory growth in `payment-service` around the `java.lang.OutOfMemoryError` to identify cache growth, large payload handling, or leak behavior before re-enabling full traffic.
  - Owner: `Service owner`  |  Est. time: 40 min  |  Runbook: `java-memory-leak-investigation`

- [ ] **Step 5:** After the pod is stable, restore normal replica count and confirm the `prod` deployment no longer reports `OOMKilled` events for `payment-service-7d9f84c9b6-rx2pm`.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `k8s-oom-recovery`


## NETWORK_ERROR — P1
**Services:** api-gateway, payment-service

- [ ] **Step 1:** Reduce or temporarily shed `POST /api/v1/payments` traffic at `api-gateway` to prevent repeated `504` and `502` responses while `payment-service` is timing out at `latency_ms=12030`, `8321`, and `15012`.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `gateway-circuit-breaker`

- [ ] **Step 2:** Check `payment-service` health and response latency from the gateway path, because the gateway evidence shows `upstream=payment-service` timeout and bad gateway failures rather than a gateway-only issue.
  - Owner: `On-call engineer`  |  Est. time: 15 min  |  Runbook: `upstream-health-check`

- [ ] **Step 3:** Increase `api-gateway` upstream timeout and retry policy only enough to avoid false failures while the downstream is recovering; the current `request timeout after retry attempt` indicates retry behavior is already exhausting the request budget.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `gateway-timeout-tuning`

- [ ] **Step 4:** Correlate `payment-service` timeout spikes with the concurrent DB and OOM incidents to confirm whether the upstream 504/502s are a symptom of service saturation rather than a network path failure.
  - Owner: `Service owner`  |  Est. time: 30 min  |  Runbook: `cross-service-latency-correlation`

- [ ] **Step 5:** Restore normal gateway routing only after `payment-service` returns stable 2xx latency and no further `upstream request timeout` errors appear on `trace_id=a81d11`, `b12c44`, and `e19bc1`.
  - Owner: `Platform team`  |  Est. time: 15 min  |  Runbook: `gateway-traffic-restoration`


## AUTH_ERROR — P1
**Services:** auth-service, redis-cache, api-gateway

- [ ] **Step 1:** Mitigate the `redis-cache` latency spike on `instance=redis-prod-01` by checking current load and pausing nonessential session reads, since `GET key=session:98281 latency_ms=2740` is causing auth timeouts.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `redis-latency-mitigation`

- [ ] **Step 2:** Verify `auth-service` token validation failure path for `trace_id=c91f12` and confirm the Redis session lookup timeout is the direct cause of the `401` responses through `api-gateway`.
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `auth-token-validation-debug`

- [ ] **Step 3:** Scale or fail over `redis-cache` for `redis-prod-01` if it is resource constrained, then re-test session lookup latency to bring `GET` latency below the timeout threshold.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `redis-scale-or-failover`

- [ ] **Step 4:** Tune `auth-service` to use a short bounded timeout and graceful fallback for Redis session reads so token validation does not block the `/api/v1/profile` path when Redis is slow.
  - Owner: `Service owner`  |  Est. time: 25 min  |  Runbook: `auth-service-redis-timeout-tuning`

- [ ] **Step 5:** Investigate why `redis-prod-01` command latency is elevated and check for hot keys, CPU saturation, or network contention affecting session lookup performance.
  - Owner: `Platform team`  |  Est. time: 35 min  |  Runbook: `redis-performance-investigation`


## DEPLOY_FAILURE — P1
**Services:** deployment-controller, payment-service, kubernetes

- [ ] **Step 1:** Freeze further rollout of `payment-service` version `v2.8.4` in `namespace=prod` because the deployment is already down to `available_replicas=1` of `desired_replicas=6` and error rate increased after change `CHG-9182`.
  - Owner: `Deployment controller`  |  Est. time: 5 min  |  Runbook: `deployment-freeze`

- [ ] **Step 2:** Rollback `payment-service` from `v2.8.4` to `previous_version=v2.8.3` to restore availability while the incident is active; the deployment controller already flagged the recent deployment as the likely trigger.
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `k8s-deployment-rollback`

- [ ] **Step 3:** Verify Kubernetes replica health after rollback and wait for `available_replicas` to return toward the `desired_replicas=6` target before re-enabling traffic.
  - Owner: `Platform team`  |  Est. time: 15 min  |  Runbook: `k8s-replica-recovery`

- [ ] **Step 4:** Compare `v2.8.4` against `v2.8.3` for changes that could explain the increased errors, especially the payment transaction and memory paths that coincide with the OOM and DB timeout evidence.
  - Owner: `Service owner`  |  Est. time: 40 min  |  Runbook: `release-diff-investigation`

- [ ] **Step 5:** Re-deploy `payment-service` only after fixing the identified regression and validating a canary against production traffic thresholds; do not advance beyond one replica until error rates normalize.
  - Owner: `Deployment controller`  |  Est. time: 45 min  |  Runbook: `canary-release-validation`


---

## Post-Incident

- [ ] Confirm all services are stable and error rate is back to baseline
- [ ] Write post-mortem document within 48 hours
- [ ] Update runbooks with any new learnings
- [ ] Schedule blameless retrospective with team
