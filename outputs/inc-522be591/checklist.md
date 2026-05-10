# Remediation Checklist — inc-522be591
**Overall Severity:** P0  |  **Issues:** 3

---

## OOM_KILL — P0
**Services:** payment-service, kubelet

- [ ] **Step 1:** Immediately increase the payment-service container memory limit from 512Mi to 1024Mi by patching the Deployment: `kubectl set resources deployment/payment-service -c payment-service --limits=memory=1024Mi --requests=memory=768Mi -n <namespace>`. This unblocks the CrashLoopBackOff and restores payment processing while root cause is investigated.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `k8s-memory-limit-patch`

- [ ] **Step 2:** Verify pod payment-service-7d9f8b-xk2p9 (and any new replacement pods) recover from CrashLoopBackOff and reach Running state: `kubectl get pods -l app=payment-service -n <namespace> -w`. Confirm restart count stabilizes at 0 for new pod.
  - Owner: `On-call engineer`  |  Est. time: 3 min  |  Runbook: `k8s-pod-recovery-verify`

- [ ] **Step 3:** Validate payment processing is functional end-to-end by checking the payment-service health endpoint and confirming successful transactions are flowing through (check APM/payment transaction success rate dashboard). Alert the incident channel once payments are confirmed live.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `payment-service-health-check`

- [ ] **Step 4:** Capture current memory usage telemetry on the recovered payment-service pod: `kubectl top pod -l app=payment-service -n <namespace>` and pull container memory metrics from Prometheus/Datadog for the window 07:40–07:50Z on 2026-05-09. Determine if 1024Mi is sufficient or if further tuning is required.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `k8s-memory-usage-audit`

- [ ] **Step 5:** Pull heap/memory profiles from the payment-service at current load: enable pprof endpoint or retrieve existing APM memory profiling data to identify whether the OOM is caused by a memory leak, unexpected payload size, or insufficient baseline allocation. Focus on allocations that spiked at ~07:46Z.
  - Owner: `Service owner`  |  Est. time: 20 min  |  Runbook: `payment-service-memory-profile`

- [ ] **Step 6:** Review the payment-service changelog and recent deployments prior to 07:46Z on 2026-05-09. Check if a recent code or config change introduced a memory regression (e.g., unbounded caching, large in-memory transaction buffers, missing pagination on DB result sets).
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `payment-service-deploy-regression`

- [ ] **Step 7:** Update the payment-service Kubernetes Deployment manifest in the GitOps repository (Helm values or Kustomize overlay) to permanently set memory limit to the validated safe value (at minimum 1024Mi, or higher if profiling indicates). Add a HorizontalPodAutoscaler memory utilization target at 75% to prevent recurrence under load spikes.
  - Owner: `Platform team`  |  Est. time: 15 min  |  Runbook: `k8s-resource-quota-update`

- [ ] **Step 8:** Set up or validate a Prometheus alerting rule firing at payment-service container memory usage >80% of limit (currently 512Mi, updated to 1024Mi) with a 5-minute window so OOM risk is caught before the next kill event. Verify alert routes to the on-call payment team PagerDuty policy.
  - Owner: `Platform team`  |  Est. time: 10 min  |  Runbook: `k8s-oom-alert-tuning`


## DB_TIMEOUT — P0
**Services:** order-service, api-gateway

- [ ] **Step 1:** Immediately increase the order-service PostgreSQL connection pool size by patching the runtime configuration (environment variable or config map, e.g. `DB_POOL_MAX=50`) and rolling the order-service deployment: `kubectl set env deployment/order-service DB_POOL_MAX=50 -n <namespace>`. This directly addresses the exhausted pool (max=20, active=20, waiting=47) and unblocks queued connection acquisition.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `pg-pool-size-increase`

- [ ] **Step 2:** Verify the PostgreSQL server's `max_connections` setting can accommodate the increased pool: `psql -h <pg-host> -U <admin> -c 'SHOW max_connections;'` and cross-check current active connections: `SELECT count(*) FROM pg_stat_activity WHERE datname='orders';`. Ensure server-side capacity is not the bottleneck before confirming the pool increase.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `pg-max-connections-check`

- [ ] **Step 3:** Manually reset the api-gateway circuit breaker for the order-service upstream if it does not auto-recover after order-service stabilizes. Locate the circuit breaker admin endpoint or config (based on evidence at 07:47:22Z) and force it to half-open/closed state: e.g., `curl -X POST http://api-gateway:8080/admin/circuit-breaker/order-service/reset`.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `api-gateway-circuit-breaker-reset`

- [ ] **Step 4:** Monitor order-service connection pool metrics and error rate in real time: watch for `active` count dropping below `max`, `waiting` queue draining to 0, and HTTP 500 rate from order-service falling to baseline. Confirm in APM that order creation is succeeding before declaring mitigation complete.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `order-service-recovery-verify`

- [ ] **Step 5:** Identify what caused the sudden pool exhaustion at 07:47:12Z. Query PostgreSQL for long-running or idle-in-transaction connections: `SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state FROM pg_stat_activity WHERE state != 'idle' AND datname='orders' ORDER BY duration DESC;`. Terminate any stale/blocking connections with `SELECT pg_terminate_backend(pid)` as needed.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `pg-idle-connection-cleanup`

- [ ] **Step 6:** Correlate the DB pool exhaustion onset at 07:47:12Z with order-service deployment history, traffic spike data, and slow query logs. Run `SELECT query, calls, mean_exec_time, total_exec_time FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 20;` to identify any newly introduced slow queries that are holding connections longer than expected.
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `pg-slow-query-investigation`

- [ ] **Step 7:** Evaluate deploying PgBouncer as a connection pooler in front of the orders PostgreSQL instance if not already present. With 47 queued connections at pool max=20, the application concurrency model requires a proxy-level pool to multiplex safely. Plan and schedule this as a P0 follow-up architectural fix with the Platform team.
  - Owner: `Platform team`  |  Est. time: 30 min  |  Runbook: `pgbouncer-deploy-orders`

- [ ] **Step 8:** Update Prometheus/Alertmanager rules to fire a P1 alert when order-service pool `waiting` connections exceed 10 for more than 60 seconds and a P0 alert when `active == max` for more than 30 seconds. Validate these alerts route to the on-call order-service team.
  - Owner: `Platform team`  |  Est. time: 10 min  |  Runbook: `pg-pool-exhaustion-alert`


## DEPLOY_FAILURE — P2
**Services:** notification-service, kubelet

- [ ] **Step 1:** Confirm whether a previous stable version of notification-service is still running (prior to the failed rollout): `kubectl get pods -l app=notification-service -n <namespace>`. If old pods are Running, the service is partially available and urgency is reduced. Document current pod state before taking action.
  - Owner: `On-call engineer`  |  Est. time: 3 min  |  Runbook: `k8s-pod-state-audit`

- [ ] **Step 2:** Verify whether the image `registry.prod.internal/notification-service:v1.2.3` exists in the internal registry. Log in and inspect: `crane digest registry.prod.internal/notification-service:v1.2.3` or `docker manifest inspect registry.prod.internal/notification-service:v1.2.3`. Determine if the tag was never pushed, was deleted, or if there is a registry connectivity issue.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `registry-image-existence-check`

- [ ] **Step 3:** If `registry.prod.internal/notification-service:v1.2.3` does not exist, immediately roll back the notification-service Deployment to the last known good image tag using: `kubectl rollout undo deployment/notification-service -n <namespace>`. Verify rollback completes: `kubectl rollout status deployment/notification-service -n <namespace>`.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `k8s-deployment-rollback`

- [ ] **Step 4:** If the image was simply never pushed (CI/CD pipeline gap), trigger a rebuild and push of `notification-service:v1.2.3` from the correct commit SHA in the CI system (Jenkins/GitHub Actions/Tekton). Validate the push succeeded by re-inspecting the registry manifest after the pipeline completes.
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `cicd-image-rebuild-push`

- [ ] **Step 5:** Check kubelet image pull credentials for `registry.prod.internal`: `kubectl get secret -n <namespace> | grep registry` and validate the imagePullSecret attached to the notification-service ServiceAccount has a valid, non-expired token for `registry.prod.internal`. Rotate the secret if expired.
  - Owner: `Platform team`  |  Est. time: 10 min  |  Runbook: `k8s-imagepull-secret-validate`

- [ ] **Step 6:** Once the correct image is available in `registry.prod.internal`, re-apply the notification-service Deployment manifest (or re-trigger the CD pipeline) targeting `notification-service:v1.2.3`. Monitor pod rollout until all pods reach Running state and ImagePullBackOff is cleared: `kubectl rollout status deployment/notification-service -n <namespace>`.
  - Owner: `Service owner`  |  Est. time: 10 min  |  Runbook: `k8s-deployment-redeploy`

- [ ] **Step 7:** Add an image existence gate to the notification-service CI/CD pipeline: before updating the Kubernetes Deployment manifest, the pipeline must verify that the target image tag exists in `registry.prod.internal` using a pre-deploy validation step (e.g., `crane digest` check or registry API call). Block the deploy and fail the pipeline if the image is absent.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `cicd-image-preflight-gate`


---

## Post-Incident

- [ ] Confirm all services are stable and error rate is back to baseline
- [ ] Write post-mortem document within 48 hours
- [ ] Update runbooks with any new learnings
- [ ] Schedule blameless retrospective with team
