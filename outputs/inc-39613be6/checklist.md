# Remediation Checklist — inc-39613be6
**Overall Severity:** P1  |  **Issues:** 4

---

## OOM_KILL — P1
**Services:** payment-service

- [ ] **Step 1:** Scale out the payment-service deployment immediately to reduce per-pod memory pressure while the current pod is being killed for exceeding its 512Mi limit; if horizontal scaling is already in place, temporarily add one replica to absorb traffic.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `payment-service-scale-out`

- [ ] **Step 2:** Temporarily raise the payment-service memory limit above 512Mi in the live workload spec if cluster capacity allows, and restart the affected pod to stop the repeated OOMKill pattern (#2 within 3 minutes).
  - Owner: `On-call engineer`  |  Est. time: 15 min  |  Runbook: `k8s-memory-limit-adjustment`

- [ ] **Step 3:** Check the payment-service container logs and recent request patterns for memory growth leading up to 2026-05-09T07:46:23Z and 07:49:01Z to identify whether a specific code path, batch job, or payload size is causing the leak or spike.
  - Owner: `Service owner`  |  Est. time: 25 min  |  Runbook: `payment-service-memory-investigation`

- [ ] **Step 4:** If the memory spike correlates with a recent release, roll back payment-service to the last known good version and verify the pod no longer exceeds the 512Mi limit under production traffic.
  - Owner: `Service owner`  |  Est. time: 20 min  |  Runbook: `payment-service-rollback`

- [ ] **Step 5:** After stabilization, capture a memory profile of payment-service and add a permanent request/limit right-sizing or leak fix so the container does not repeatedly OOMKill under normal revenue-path load.
  - Owner: `Platform team`  |  Est. time: 45 min  |  Runbook: `payment-service-rightsizing`

- [ ] **Step 1:** Reduce immediate pressure on the PostgreSQL pool by scaling out order-service replicas or temporarily throttling order-service concurrency, because the pool is exhausted at max=20 with 20 active and 47 waiting requests.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `order-service-load-shedding`

- [ ] **Step 2:** Validate the PostgreSQL-side connection limits and current active sessions for order-service, then close any leaked or idle-in-transaction sessions consuming the pool before more requests queue behind the 47 waiting threads.
  - Owner: `Database administrator`  |  Est. time: 20 min  |  Runbook: `postgres-connection-reclaim`

- [ ] **Step 3:** Increase the order-service database pool size only if PostgreSQL capacity and query latency permit it; align the pool to observed demand while keeping it below the database max-connection headroom to avoid amplifying contention.
  - Owner: `Platform team`  |  Est. time: 15 min  |  Runbook: `pg-pool-tuning`

- [ ] **Step 4:** Inspect order-service code paths for connection leaks or long-held transactions that would explain active=20 and waiting=47, and trace the slowest queries during the failure window around 2026-05-09T07:47:12Z.
  - Owner: `Service owner`  |  Est. time: 30 min  |  Runbook: `order-service-connection-leak`

- [ ] **Step 5:** If a recent deployment introduced the pool exhaustion, roll back order-service to the previous stable build and verify the PostgreSQL pool returns to normal utilization under live traffic.
  - Owner: `Service owner`  |  Est. time: 20 min  |  Runbook: `order-service-rollback`

- [ ] **Step 1:** Fix the notification-service image reference used by the failed rollout: ErrImagePull shows 'failed to pull and unpack image: not found', so confirm the exact image tag/digest exists in the registry and update the deployment manifest accordingly.
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `fix-image-reference`

- [ ] **Step 2:** Redeploy notification-service after correcting the image path or tag, and watch the pod events to confirm the container starts instead of returning ErrImagePull.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `notification-service-redeploy`

- [ ] **Step 3:** If the intended image was deleted or never published, restore the missing notification-service artifact in the registry from the CI pipeline or promote the last known good image used by the service.
  - Owner: `Release engineering`  |  Est. time: 25 min  |  Runbook: `registry-image-restore`

- [ ] **Step 4:** Audit the notification-service deployment pipeline to ensure the image tag is pinned and published before rollout so the 'not found' pull failure cannot recur on the next deployment.
  - Owner: `Platform team`  |  Est. time: 30 min  |  Runbook: `image-publish-validation`

- [ ] **Step 1:** Verify the JWT signing key or public key bundle used by auth-service against the issuer currently signing tokens, because validation failed with 'signature mismatch' at 2026-05-09T07:48:30Z.
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `jwt-signing-key-check`

- [ ] **Step 2:** Check for a recent auth-service key rotation or issuer configuration change and restore the correct key/version if tokens are being signed with a different secret or certificate than auth-service expects.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `auth-key-rotation-rollback`

- [ ] **Step 3:** Validate a sample token end-to-end with auth-service and the issuing system to confirm the mismatch is resolved, then monitor for continued JWT validation failures across production requests.
  - Owner: `On-call engineer`  |  Est. time: 15 min  |  Runbook: `jwt-validation-confirmation`

- [ ] **Step 4:** If the mismatch is caused by stale config, restart auth-service after updating its key/config map so all instances load the same signing material and no subset continues rejecting valid JWTs.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `auth-service-config-reload`

- [ ] **Step 5:** Review token issuance and rotation automation to prevent future signature mismatches, including overlap windows for old and new keys and explicit deployment ordering between issuer and auth-service.
  - Owner: `Service owner`  |  Est. time: 30 min  |  Runbook: `jwt-rotation-hardening`


---

## Post-Incident

- [ ] Confirm all services are stable and error rate is back to baseline
- [ ] Write post-mortem document within 48 hours
- [ ] Update runbooks with any new learnings
- [ ] Schedule blameless retrospective with team
