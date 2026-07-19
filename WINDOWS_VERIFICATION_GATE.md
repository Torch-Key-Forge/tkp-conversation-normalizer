# Windows Verification Gate

This pull request exists to exercise the repository's Windows release workflow against a clean branch event.

The gate requires:

- source tests;
- wheel construction;
- fresh virtual-environment installation;
- CLI execution from a clean temporary directory;
- PASS receipt with zero exceptions;
- no known private-path markers in tracked files.

A passing workflow closes the automated Windows publication-candidate verification. The first tagged release still requires an explicit license decision.
