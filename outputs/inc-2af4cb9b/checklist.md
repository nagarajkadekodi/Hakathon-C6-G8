# Remediation Checklist — inc-2af4cb9b
**Overall Severity:** P0  |  **Issues:** 3

---

## OOM_KILL — P0
**Services:** payment-service, kubelet

- [ ] **Step 1:** Immediately scale up the payment-service deployment to 0 replicas to stop the CrashLoopBackOff cycle and prevent kubelet from burning restart budget: `kubectl scale deployment payment-service --replicas=0 -n <namespace>`
  - Owner: `On-call engineer`  |  Est. time: 2 min  |  Runbook: `payment-service-crashloop-halt`

- [ ] **Step 2:** Check whether a stable prior image tag exists for payment-service. If yes, patch the deployment to roll back to it immediately: `kubectl rollout undo deployment/payment-service -n <namespace>` and verify rollout status with `kubectl rollout status deployment/payment-service`
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `payment-service-rollback`

- [ ] **Step 3:** Raise the payment-service container memory limit from 512Mi to 1024Mi (and request from current value to 768Mi) as an emergency patch to restore service while root cause is investigated: `kubectl set resources deployment/payment-service -c payment-service --limits=memory=1024Mi --requests=memory=768Mi -n <namespace>`
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `k8s-memory-limit-emergency-bump`

- [ ] **Step 4:** Scale payment-service back to the desired replica count (e.g., 3): `kubectl scale deployment payment-service --replicas=3 -n <namespace>`. Monitor pod status with `kubectl get pods -l app=payment-service -n <namespace> -w` to confirm pods reach Running state without OOMKill.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `payment-service-scale-restore`

- [ ] **Step 5:** Validate payment-service health end-to-end by triggering a synthetic payment transaction through the payment gateway and confirming a 2xx response. Alert the on-call payment team lead and update the P0 incident channel with service restoration status.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `payment-service-smoke-test`

- [ ] **Step 6:** Pull memory metrics from Prometheus/Grafana for payment-service over the last 24 hours to identify when memory consumption began trending toward 512Mi. Check for recent code changes, new transaction volume spikes, or unbounded caches/connection pools that may have caused the OOMKill.
  - Owner: `Service owner`  |  Est. time: 20 min  |  Runbook: `payment-service-memory-profiling`

- [ ] **Step 7:** Capture a heap dump or memory profile from a running payment-service pod (if available via JVM flags, pprof, or py-spy depending on runtime) to identify the specific memory leak or allocation spike: e.g., `kubectl exec -it <pod> -n <namespace> -- <heap-dump-command>`
  - Owner: `Service owner`  |  Est. time: 30 min  |  Runbook: `payment-service-heap-dump`

- [ ] **Step 8:** Update the payment-service Helm values or Kubernetes manifest in the GitOps repo to permanently reflect the new memory limits (1024Mi) and requests (768Mi), and add a HorizontalPodAutoscaler memory utilization threshold at 70% to prevent future OOMKills under load spikes. Open a follow-up ticket to root-cause and fix the memory regression in code.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `k8s-resource-quota-update`


## DB_TIMEOUT — P0
**Services:** order-service, api-gateway

- [ ] **Step 1:** Immediately identify and kill long-running or idle PostgreSQL connections blocking pool slots. Connect to the order-service PostgreSQL instance and run: `SELECT pid, usename, application_name, state, query_start, query FROM pg_stat_activity WHERE state != 'idle' ORDER BY query_start ASC;` then terminate blocking queries with `SELECT pg_terminate_backend(pid) WHERE ...` as appropriate.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `pg-kill-blocking-connections`

- [ ] **Step 2:** Emergency-increase the order-service PostgreSQL connection pool max size from 20 to 40 via environment variable or config update (e.g., `DB_POOL_MAX=40`) and perform a rolling restart of order-service pods: `kubectl rollout restart deployment/order-service -n <namespace>`. This directly addresses the pool exhausted state (max=20, active=20, waiting=47).
  - Owner: `On-call engineer`  |  Est. time: 8 min  |  Runbook: `pg-pool-exhaustion-emergency-resize`

- [ ] **Step 3:** Monitor the api-gateway circuit breaker state for order-service. Once order-service pods are healthy and returning 2xx responses, force the circuit breaker to half-open/closed if it does not self-recover: check api-gateway circuit breaker admin endpoint or config (e.g., Hystrix dashboard, Resilience4j actuator at `/actuator/circuitbreakers`) and reset the `order-service` breaker.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `api-gateway-circuit-breaker-reset`

- [ ] **Step 4:** Validate order creation is restored end-to-end: submit a synthetic test order through the api-gateway and confirm a successful response with a valid order ID. Confirm the api-gateway logs no longer show `Upstream order-service returning 500` and the circuit breaker is closed.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `order-service-smoke-test`

- [ ] **Step 5:** Investigate root cause of pool exhaustion: query `pg_stat_activity` to determine if connection leaks exist (connections stuck in `idle in transaction` state), and review order-service application logs around 2026-05-09T07:47:12Z for any transaction that failed to release connections. Check if a traffic spike, batch job, or deployment event triggered the surge to 47 waiting connections.
  - Owner: `Service owner`  |  Est. time: 20 min  |  Runbook: `pg-connection-leak-investigation`

- [ ] **Step 6:** Review whether a PgBouncer or equivalent connection pooler is deployed in front of the order-service PostgreSQL instance. If not, plan and implement PgBouncer in transaction pooling mode to multiplex the 40+ application pool connections into a smaller set of actual PostgreSQL server connections, preventing future exhaustion.
  - Owner: `Platform team`  |  Est. time: 60 min  |  Runbook: `pgbouncer-connection-pooler-setup`

- [ ] **Step 7:** Update the order-service Helm values or ConfigMap in the GitOps repo to set `DB_POOL_MAX=40`, `DB_POOL_ACQUIRE_TIMEOUT=10000` (raise from 5000ms to reduce false timeout failures under load), and `DB_POOL_IDLE_TIMEOUT=30000` to aggressively reclaim idle connections. Add a Prometheus alert on `pg_stat_activity` connection count exceeding 35 to catch future pool pressure early.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `pg-pool-config-hardening`


## DEPLOY_FAILURE — P2
**Services:** notification-service, kubelet

- [ ] **Step 1:** Verify whether the image `registry.prod.internal/notification-service:v1.2.3` exists in the internal registry. Log in to the registry and check: `curl -u <user>:<pass> https://registry.prod.internal/v2/notification-service/tags/list` or use the registry UI. Determine if the tag was never pushed, was deleted, or was mistyped in the deployment manifest.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `registry-image-tag-verification`

- [ ] **Step 2:** If `v1.2.3` does not exist in `registry.prod.internal`, immediately roll the notification-service deployment back to the last known-good image tag (e.g., `v1.2.2`): `kubectl set image deployment/notification-service notification-service=registry.prod.internal/notification-service:v1.2.2 -n <namespace>` and confirm pods reach Running state.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `notification-service-image-rollback`

- [ ] **Step 3:** If `v1.2.3` was built but not pushed, locate the CI/CD pipeline run for notification-service:v1.2.3 (e.g., in Jenkins, GitHub Actions, or GitLab CI), identify the failed or skipped push step, and re-trigger the pipeline to push the image to `registry.prod.internal/notification-service:v1.2.3`. Then patch the deployment to use `v1.2.3` once confirmed present.
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `notification-service-cicd-repush`

- [ ] **Step 4:** Verify that the kubelet on the affected node has valid pull credentials for `registry.prod.internal`. Check the imagePullSecrets on the notification-service pod spec and confirm the referenced secret exists and is not expired: `kubectl get secret <pull-secret-name> -n <namespace> -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d`
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `k8s-imagepullsecret-validation`

- [ ] **Step 5:** Add a CI/CD pipeline gate that validates the image tag exists in `registry.prod.internal` before updating the Kubernetes deployment manifest. Implement this as a pre-deploy step: `docker manifest inspect registry.prod.internal/notification-service:<tag>` — fail the pipeline if the image is not present, preventing future ImagePullBackOff incidents for notification-service.
  - Owner: `Platform team`  |  Est. time: 30 min  |  Runbook: `cicd-image-existence-gate`


---

## Post-Incident

- [ ] Confirm all services are stable and error rate is back to baseline
- [ ] Write post-mortem document within 48 hours
- [ ] Update runbooks with any new learnings
- [ ] Schedule blameless retrospective with team
