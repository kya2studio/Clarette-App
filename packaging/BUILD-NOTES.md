# Apple Silicon standalone build

This is a developer build recipe, not a finished standalone installer. Build it on an Apple Silicon Mac; the M1 Pro is the target architecture. PyInstaller cannot produce a supported macOS application from this Linux development environment.

Run `packaging/build-mac.sh` on the build Mac with native Python 3.11–3.13. The resulting onedir .app bundles Python and dependencies, opens a native window without Terminal, and reuses the same persistent subprocess engine. No user-side pip setup is intended for that bundle. Model weights still download on first use and remain cached. The script has only been syntax-checked here; its output must be tested on a clean Mac.

Release gates before calling this standalone production-ready:

1. Build arm64 and verify every bundled native dependency resolves without an external Python installation.
2. Test the windowed worker's stdin/stdout pipes, cancellation, subsequent restart, and normal shutdown on M1 Pro.
3. Test Detect Subject cold and warm, both CPU and optional Core ML. Record elapsed times, peak memory, UI interaction latency and hair quality on representative opaque original photos. Do not infer M1 Pro speeds from NVIDIA benchmarks.
4. Verify pywebview WKWebView supports the bundled color Web Worker and UI controls. Verify Finder, notifications, export folder selection, close warnings, and instance handling.
5. Sign with the publisher's Developer ID, notarize and staple using Apple's release tools. Distribute the tested signed bundle in a drag-to-Applications DMG or signed installer. Do not disable Gatekeeper or company controls.

References:
- https://www.pyinstaller.org/en/stable/usage.html
- https://pyinstaller.org/en/stable/feature-notes.html

# Image technology assessment

BiRefNet's official repository includes high-resolution matting models; they are candidates for a later quality evaluation, not a promise of real-time Apple Silicon performance. Its published 17 FPS example is for an RTX 4090 and cannot be carried over to the M1 Pro. General Lite / Portrait remain this app's existing backends, with U2Net Small exposed as Fast preview. Fast preview trades edge quality for a smaller model. This release does not install a new high-resolution model.

CodeFormer offers a restoration/fidelity control, but generative face restoration can change details. It needs side-by-side identity review, licensing/dependency review and M1 Pro evaluation before inclusion. This release uses existing-detail sharpening and optional EDSR upscaling; it does not claim to reconstruct missing face detail.

- https://github.com/ZhengPeng7/BiRefNet
- https://github.com/sczhou/CodeFormer

# API panel

The dedicated API Keys panel is an explicitly disabled layout preview. No API key is saved and no provider API is called. Browser handoff remains functional. Actual integration needs a separate secure credential setup decision and provider-specific implementation. Never paste keys into a chat message.
