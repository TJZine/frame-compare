# Compare installation routes

Use this page when the short installation chooser is not enough. The same Frame Compare
CLI runs on every route; the differences are runtime ownership, desktop integration,
and the level of reproducibility the route can provide.

## Support and dependency ownership

| Route | Host | Setup effort | Runtime owner | Support posture |
| --- | --- | ---: | --- | --- |
| Windows portable release | Windows 10/11 x64 | Lowest | Bundle | Recommended Windows route |
| Windows portable source build | Windows 10/11 x64 | Medium to high | Build scripts assemble pinned inputs | Supported packaging fallback |
| Docker default | macOS or Linux | Low to medium | Image | Recommended headless macOS/Linux route |
| Docker NVIDIA | Compatible Linux NVIDIA host | High | Image plus host driver/toolkit | Experimental until proved on the host |
| Docker X11 | Linux X11 desktop | High | Image plus host display/session | Offscreen VSView proof passes; visible X11 remains experimental until proved on the host |
| Native source with `uv` | Windows, macOS, or Linux | High | Locked Python environment plus host media stack | Advanced |
| Native source with pip | Compatible Python host | Highest | User-managed Python and media stack | Advanced integration route |

“Reproducible” does not mean identical pixels across unrelated operating systems or GPU
drivers. Use the same route and runtime when bit-for-bit output matters.

## Capability comparison

| Capability | Windows portable | Docker default | Docker NVIDIA | Docker X11 | Native source |
| --- | --- | --- | --- | --- | --- |
| Discovery, probing, selection, and alignment | Yes | Yes | Yes | Yes | Yes, with required runtime |
| SDR screenshots and offline reports | Yes | Yes | Yes | Yes | Yes, with required runtime |
| HDR tonemapping | Host Vulkan stack | Software Vulkan | Intended host GPU path | Host-dependent | Host-dependent |
| Interactive VSView alignment | Included | No | No | Experimental | Optional and host-managed |
| Browser opening and clipboard behavior | Available in an interactive desktop session | No | No | Host/session-dependent | Host/session-dependent |
| Signed code-only updates and rollback | Yes | No | No | No | No |
| Persistent history and caches | Yes | Yes through host mounts | Yes | Yes | Yes |

Browser and clipboard side effects require a suitable interactive desktop session.
Headless, SSH, service, non-TTY, and restricted native sessions should not rely on them.

## Route details

### Windows portable

Choose this for the least setup and the broadest tested Windows feature set. The bundle
contains the selected runtime, supports interactive VSView alignment, and provides
user-level install, update, backup, rollback, and uninstall commands.

Tradeoffs:

- Windows x64 only.
- Larger downloads because native media and UI runtimes are included.
- GPU behavior still depends on the host graphics driver and Vulkan support.
- Runtime-changing releases require a complete bundle refresh rather than a code-only
  update.

[Install on Windows](../windows-portable.md)

### Docker default

Choose this for an isolated, reproducible, headless setup on macOS or Linux. The normal
run mounts configuration and media read-only and writes generated data through one
explicit host directory.

Tradeoffs:

- The image is currently built from the repository rather than pulled from a promised
  public registry.
- The default route does not provide VSView.
- Containers cannot directly open the host browser or reliably use the host clipboard.
- macOS Docker Desktop does not expose a native GPU path for this workflow.

[Start with Docker](docker.md)

### Optional Docker profiles

The Linux NVIDIA and X11 routes are separate host-dependent proof surfaces. Passing the
default Docker verification does not prove either optional profile. The VSView X11
profile's offscreen dependency/session/render proof currently passes, but visible X11
desktop behavior remains unverified until exercised on a compatible Linux host. Use the
dedicated commands for the relevant proof surface.

[Advanced Docker environments](../docker-environments.md)

### Native source

Choose this when native host behavior matters and you can manage the media toolchain.
`uv` reproduces the repository's locked Python graph, but the host still owns FFmpeg,
VapourSynth, source plugins, tonemapping plugins, and Vulkan behavior where the selected
platform does not provide them through the extra.

The pip route is appropriate when Frame Compare must live in an existing environment.
It may resolve a newer dependency combination than the repository lockfile, so run
`frame-compare doctor` after every install or upgrade.

[Install from source](native.md)

## Runtime details

The authoritative component versions, profile policies, cache boundaries, native
artifact provenance, and licensing notes live in
[Supported Media Runtime](../supported-media-runtime.md). That page is the source of
truth; route guides intentionally avoid repeating the complete version matrix.
