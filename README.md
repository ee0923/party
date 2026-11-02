# Clash Party

Privacy-patched Windows, Win7, Linux and macOS builds from locked sources.
Set `CLASH_PARTY_CUSTOMIZE_SCRIPT`. Desktop builds are unsigned by default;
manual runs can select signed macOS builds with configured certificates and Apple credentials.
GPL-3.0; provide corresponding source and patches when distributing.

Each verified target publishes immediately to a versioned Release, independently of other targets.
Completed runs, logs and Actions artifacts are eligible for cleanup after 60 seconds on success
or 20 minutes otherwise. Releases are retained; the next invocation removes eligible older cleanup runs.
