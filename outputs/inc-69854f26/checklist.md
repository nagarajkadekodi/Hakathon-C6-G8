# Remediation Checklist — inc-69854f26
**Overall Severity:** P1  |  **Issues:** 5

---

## DB_TIMEOUT — P1
**Services:** payment-service, postgres-primary

- [ ] **Step 1:** Reduce immediate pressure on postgres-primary by temporarily scaling down payment-service in namespace prod from the failing 6 replicas to a smaller safe count, since postgres-primary already shows active_connections=195/200 and payment-service is emitting DB_CONN_TIMEOUT errors on order ORD-78219.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `payment-service-db-throttle`

- [ ] **Step 2:** Investigate and terminate any long-lived or stuck payment-service database sessions against db=payments on postgres-primary, focusing on the ClientRead wait_event and the error "remaining connection slots are reserved for non-replication superuser connections" to free connection slots for live transactions.
  - Owner: `Database administrator`  |  Est. time: 15 min  |  Runbook: `postgres-connection-slot-recovery`

- [ ] **Step 3:** Restart the payment-service pod(s) that are holding stale database connections after confirming current traffic is throttled, so new pods can establish fresh connections instead of repeatedly timing out while creating payment transactions.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `payment-service-connection-reset`

- [ ] **Step 4:** Inspect payment-service connection pool settings and deploy a configuration change to lower per-pod pool size so the fleet does not drive postgres-primary above max_connections=200 during checkout bursts; align the pool with the observed 195 active connections and current replica count.
  - Owner: `Service owner`  |  Est. time: 30 min  |  Runbook: `pg-pool-tuning`

- [ ] **Step 5:** Review postgres-primary capacity and workload patterns for db=payments, including why active_connections reached 195 and whether slow queries or leaked transactions are prolonging ClientRead waits; implement the permanent fix after confirming the payment transaction path is not over-allocating connections.
  - Owner: `Database administrator`  |  Est. time: 45 min  |  Runbook: `postgres-root-cause-analysis`


## OOM_KILL — P1
**Services:** payment-service, kubelet, kubernetes

- [ ] **Step 1:** Stabilize the CrashLoopBackOff pod payment-service-7d9f84c9b6-rx2pm in namespace prod by temporarily reducing rollout pressure and, if needed, pinning traffic away from the restarting container while kubelet reports restart_count=3 and OOMKilled events.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `payment-service-crashloop-mitigation`

- [ ] **Step 2:** Increase the Kubernetes memory limit for the payment-service container above the current value that is triggering "Container killed due to memory limit exceeded", then restart the deployment so the Java process can start without immediate OOMKilled events.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `k8s-memory-limit-bump`

- [ ] **Step 3:** Adjust Java heap sizing for payment-service to fit within the updated pod memory budget, because the application is throwing java.lang.OutOfMemoryError: Java heap space before kubelet kills the container.
  - Owner: `Service owner`  |  Est. time: 20 min  |  Runbook: `jvm-heap-sizing`

- [ ] **Step 4:** Collect a heap dump or memory profile from payment-service-7d9f84c9b6-rx2pm after stabilization to determine whether the heap exhaustion is caused by a leak or an oversized in-memory workload in the payment path.
  - Owner: `Service owner`  |  Est. time: 30 min  |  Runbook: `java-heap-investigation`

- [ ] **Step 5:** Validate the corrected memory request/limit and heap settings by observing that kubelet no longer reports OOMKilled and the payment-service replica count recovers beyond the current crash-looping pod.
  - Owner: `Platform team`  |  Est. time: 15 min  |  Runbook: `k8s-oom-verification`


## NETWORK_ERROR — P1
**Services:** api-gateway, payment-service

- [ ] **Step 1:** Mitigate user-facing failures by temporarily routing api-gateway POST /api/v1/payments away from the unhealthy payment-service instance(s) that are returning 504 upstream request timeout and 502 bad gateway responses.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `gateway-circuit-breaker`

- [ ] **Step 2:** Check the health of payment-service pods behind api-gateway and remove any pod that is timing out after retry attempt, because the gateway logs show repeated latency_ms values of 12030, 8321, and 15012 against upstream=payment-service.
  - Owner: `Platform team`  |  Est. time: 15 min  |  Runbook: `payment-upstream-health-check`

- [ ] **Step 3:** Confirm whether the payment-service latency is being caused by the concurrent DB_TIMEOUT and OOM_KILL conditions, then prioritize the payment-service recovery path so gateway retries stop amplifying the outage.
  - Owner: `Incident commander`  |  Est. time: 20 min  |  Runbook: `incident-correlation-payment`

- [ ] **Step 4:** Tune api-gateway timeout and retry settings for POST /api/v1/payments only after the upstream payment-service is stable, to avoid repeated 12030ms/15012ms waits causing extra 504s during recovery.
  - Owner: `Platform team`  |  Est. time: 25 min  |  Runbook: `gateway-timeout-tuning`

- [ ] **Step 5:** Verify end-to-end payment request success from api-gateway to payment-service by replaying a POST /api/v1/payments test and confirming 2xx responses instead of 502/504 for the affected trace IDs.
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `payment-end-to-end-validation`


## AUTH_ERROR — P1
**Services:** auth-service, redis-cache, api-gateway

- [ ] **Step 1:** Inspect redis-cache instance redis-prod-01 immediately and check whether the GET session:98281 latency of 2740ms reflects a broader Redis slowdown that is causing auth-service TOKEN_VALIDATION_FAILED timeouts.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `redis-latency-triage`

- [ ] **Step 2:** Reduce load on auth-service token validation by temporarily increasing Redis capacity or shifting session reads away from redis-prod-01 if it is saturated, so api-gateway stops returning 401 for trace_id=c91f12.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `redis-capacity-relief`

- [ ] **Step 3:** Restart or recycle the auth-service pods after Redis responsiveness is restored, to clear any stuck token-validation workers that are failing with reason="Redis session lookup timeout".
  - Owner: `Service owner`  |  Est. time: 10 min  |  Runbook: `auth-service-restart`

- [ ] **Step 4:** Check Redis latency, connection counts, and keyspace behavior on redis-cache to identify whether session lookups are slowed by hot keys, eviction pressure, or an overloaded instance rather than auth-service code alone.
  - Owner: `Database administrator`  |  Est. time: 30 min  |  Runbook: `redis-root-cause-analysis`

- [ ] **Step 5:** Validate that auth-service returns successful token validations and that api-gateway GET /api/v1/profile no longer emits 401 status for the affected trace_ids after Redis recovery.
  - Owner: `QA / Service owner`  |  Est. time: 15 min  |  Runbook: `auth-validation-check`


## DEPLOY_FAILURE — P1
**Services:** deployment-controller, payment-service, kubernetes

- [ ] **Step 1:** Roll back deployment payment-service in namespace prod from version v2.8.4 to previous_version=v2.8.3 because deployment-controller detected increased error rate after deployment and kubernetes reports available_replicas=1 of desired_replicas=6.
  - Owner: `Release engineer`  |  Est. time: 10 min  |  Runbook: `k8s-rollback-payment-service`

- [ ] **Step 2:** Freeze further rollout of change_id=CHG-9182 until the service is stable, to stop the deployment-controller from continuing a version that correlates with reduced availability and higher error rate.
  - Owner: `Incident commander`  |  Est. time: 5 min  |  Runbook: `change-freeze`

- [ ] **Step 3:** Compare v2.8.4 versus v2.8.3 configuration, image, and resource changes for payment-service, with particular attention to memory settings and database pool changes that could explain the post-deploy degradation.
  - Owner: `Service owner`  |  Est. time: 30 min  |  Runbook: `deployment-diff-review`

- [ ] **Step 4:** After rollback, verify kubernetes deployment availability recovers toward desired_replicas=6 and confirm payment-service error rate drops from the level observed after the recent deployment.
  - Owner: `Platform team`  |  Est. time: 15 min  |  Runbook: `deployment-health-verification`

- [ ] **Step 5:** Only reintroduce v2.8.4 through a controlled canary once the DB_TIMEOUT, OOM_KILL, and NETWORK_ERROR conditions are cleared, so the deployment-controller can distinguish rollout regressions from existing infrastructure incidents.
  - Owner: `Release engineer`  |  Est. time: 25 min  |  Runbook: `canary-release-validation`


---

## Post-Incident

- [ ] Confirm all services are stable and error rate is back to baseline
- [ ] Write post-mortem document within 48 hours
- [ ] Update runbooks with any new learnings
- [ ] Schedule blameless retrospective with team
