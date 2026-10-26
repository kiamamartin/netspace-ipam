# infrastructure.md — Infrastructure Nested Rules

Applies when editing Docker, CI, deployment, and environment configuration.

- Preserve existing CI behavior; do not disable, skip, or loosen checks to pass.
- Pin base images and dependency versions where the project already does so.
- Keep secrets out of images, Compose files, and CI logs; use the documented secret store.
- Do not expose new ports or services publicly without approval.
- Provide health checks and document startup prerequisites where the project does.
- Verify documented commands work from a clean environment before declaring completion.
- Do not modify `git` identity or CI commit attribution; retain the human identity.
- Never add agent attribution to CI artifacts, image labels, or annotations.