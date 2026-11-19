# ADR-0028: HKR HR restart inbox

HKR HR uses its own restart inbox on its existing internal file share. A Windows task on the mini PC consumes restart markers while the HKR HR operator account is signed in, independently of the web app. The inbox accepts only one action, invoking the same fixed restart script as the manual launcher. The request carries no arguments, scripts, or business data. There is no additional network service or dependency on TMC.

Each request has its own result and log. The worker claims a request before restarting, so a lost response or interrupted task does not cause an automatic second restart. The manual launcher remains available for local recovery. See [deployment instructions](../../README.md#deployment) for installation and verification.
