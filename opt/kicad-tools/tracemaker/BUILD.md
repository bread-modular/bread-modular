# Pinned external CPU runtime — manual review and provisioning only

No installer, bootstrap, automatic download, global package change or bundled engine.
The first-party Python controllers are covered by the distribution's MIT LICENSE;
TraceMaker remains an **external GPL-3.0-or-later** engine (NOTICE's CUDA linking
permission does not relicense it). Dependency licenses remain separate. Review upstream
[LICENSE](https://github.com/DingoOz/TraceMaker/blob/c5e1e8497ffef194206a012ee98f0ba156827f71/LICENSE)
and [NOTICE](https://github.com/DingoOz/TraceMaker/blob/c5e1e8497ffef194206a012ee98f0ba156827f71/NOTICE)
before any redistribution; this toolkit does not distribute/link vendor code.

[provision.json](provision.json) is a standalone compact record containing **all eight
exact package/version/architecture/archive filenames/SHA256s**, signed index hashes,
index byte sizes, archive signature identity, pin and historical tool versions.
It is a record of prior verification, **not a signature, current authorization or a
substitute for verifying the signed archive**. No experiment JSON is required to read
these mandatory steps in a relocated bundle.

- Source repository: `https://github.com/DingoOz/TraceMaker`.
- Exact pin: `c5e1e8497ffef194206a012ee98f0ba156827f71`.
- Reviewed clean source-tree digest (prior tree-manifest convention):
  `5189882867d1d1f5ce280aec285f5e17e0359b267dc2d8cd7e9aca559dd139b6`.
- Reviewed CPU binary SHA256:
  `b469a1502f0f825aa431a7fbee57e19f1cc80f8bb940df7c17d295f81e0669fe`.
  The controller checks both the supplied digest and this reviewed build identity;
  other builds require separate review/code-pin change, not a permissive flag.
- Linux amd64; Python 3.11+; Bubblewrap with user namespaces and `--size`;
  native judge requires matching CLI/pcbnew 10.0.x (tested 10.0.6).

## Authorized manual reconstruction

Use a **NEW ignored `tracemaker-rebuild.tmp/` in this workspace**, not another workspace.
Do not run these steps merely for help, bundling, unit tests or cosmetic integration.

1. Read the exact records in `provision.json`. Verify Ubuntu archive `InRelease`
   using `gpgv --keyring /usr/share/keyrings/ubuntu-archive-keyring.gpg`, checking
   the recorded archive origin/key identity, not a wildcard matching a PPA.
   Extract signed Release to a private file. Decompress the relevant apt index via
   `/usr/lib/apt/apt-helper cat-file`; verify its uncompressed byte size/SHA256 against
   the **currently authenticated Release**, checking suite, component, architecture
   and validity. Match **all eight** exact package/version/architecture/Filename/SHA256
   stanzas from `provision.json`, not just names. **Stop** for any dependency pin/byte
   mismatch, missing record, wrong origin/key, unsigned/mismatched index or expired catalog.

   A newly signed **catalog refresh** can change Release/index hashes as unrelated
   packages change; it is not a dependency-pin change. With explicit review authorization,
   authenticate refreshed metadata using the SAME trusted archive/key, then require all
   eight pinned records to match exactly. Retain both historical manifest hashes and
   refreshed signed Release/index hashes, signature identity and exact-match results in
   a new compact provenance record; **never silently replace `provision.json`**. A pinned
   package version/filename/architecture/digest change still needs separate review and
   cannot pass as a catalog refresh. Never add keys or waive authentication because an
   old signed index expired/disappeared. No automatic provisioning in tests or commands.
2. With explicit network authorization, fetch only the exact archive URLs recorded
   in the manifest into private `packages/`. Hash each against the authenticated record.
   `dpkg-deb --extract FILE PRIVATE_DEPS` only: no maintainer scripts, apt install,
   sudo, global changes or unreviewed wrappers. Retain signed Release/index evidence.
3. `git -c core.hooksPath=/dev/null init PRIVATE_UPSTREAM`; fetch only the exact pin
   with `git -c core.hooksPath=/dev/null -C PRIVATE_UPSTREAM fetch --depth 1
   https://github.com/DingoOz/TraceMaker PIN`; detached checkout `FETCH_HEAD`.
   Verify HEAD, clean source and byte hashes before/after. No patches, submodules,
   upstream install scripts or HOME hooks. A commit ID is not an upstream signature.
4. Create a NEW private build directory. Both commands below must use this exact
   **networkless** mount plan (replace only the outer private paths):

```text
bwrap --unshare-all --die-with-parent --new-session --clearenv
  --ro-bind /usr /usr --ro-bind /bin /bin --ro-bind /lib /lib --ro-bind /lib64 /lib64
  --proc /proc --dev /dev --tmpfs /tmp --dir /etc
  --ro-bind /etc/ld.so.cache /etc/ld.so.cache
  --ro-bind PRIVATE_UPSTREAM /source --ro-bind PRIVATE_DEPS /deps --bind PRIVATE_BUILD /build
  --setenv PATH /usr/bin --setenv HOME /tmp/home --setenv LC_ALL C
  --setenv PKG_CONFIG_PATH /deps/usr/lib/x86_64-linux-gnu/pkgconfig
  --setenv LD_LIBRARY_PATH /deps/usr/lib/x86_64-linux-gnu --chdir /build
```

Configure: `/usr/bin/cmake -S /source -B /build -G Ninja -DCMAKE_BUILD_TYPE=Release
-DCMAKE_CXX_COMPILER=/usr/bin/g++-15 -DCMAKE_PREFIX_PATH=/deps/usr
-DTM_ENABLE_CUDA=OFF -DTM_BUILD_TESTS=OFF -DTM_BUILD_PYTHON=OFF`.
Build: `/usr/bin/cmake --build /build --target tracemaker --parallel 4`.
Apply externally supervised 360 s wall, 4 GiB address-space, 256 MiB per-file and
900 MiB aggregate build-output limits. Probe denied outside writes/network; do not
weaken isolation if a failure occurs. The runner separately applies 120 s wall,
4 GiB AS, 16 MiB file, 64 MiB aggregate output and 32 MiB private tmp caps.

5. Hash `PRIVATE_BUILD/src/app/tracemaker`, verify the reviewed digest and pin/build
   provenance; retain a new compact record of source/package/tool identities, mount
   argv, limits, statuses and confinement checks. A matching executable hash binds the
   reviewed build but does not alone authenticate provenance or the mounted deps.
   Verify private extracted dependencies against their authenticated packages before use.

Historical evidence (repository-only, deliberately **not bundled**):
`experiments/tracemaker-8bit/evidence/final/common/{provision,engine,build,build-confinement,runtime-confinement}.json`.
The immutable retained trial took 37.894 s to build. A separate focused synthetic
reconstruction after main `6715058` took 38.296 s and reproduced the exact binary
digest; repository-only evidence: `synthetic-verification.json` (not bundled or needed to build). No retained trial
was rerun or modified. The signed catalog refresh left all eight dependency pins intact.
