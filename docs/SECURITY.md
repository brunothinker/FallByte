# Security Policy

## Supported Versions

Security fixes are provided for the **latest released version** of FallByte. Please update to the newest release from the [Releases page](https://github.com/brunothinker/FallByte/releases) before reporting.

## Reporting a Vulnerability

**Please do not open a public issue for security problems.**

Use GitHub's private reporting instead: go to the **Security** tab of this repository and click **Report a vulnerability**.

Please include:

- A description of the issue and its potential impact
- Steps to reproduce (a sample file, if relevant)
- Your OS, FallByte version (`fallbyte --version`), and package type (.deb, .rpm, AppImage, .zip)

You can expect an initial response within a few days. Once a fix is released, we will credit you in the release notes unless you prefer to stay anonymous.

## Scope

FallByte runs entirely locally and does not send data over the network. Reports of interest include, for example, crashes or code execution triggered by crafted media files, unsafe file handling (overwriting or deleting files outside the chosen output folder), and issues in the bundled binaries. Vulnerabilities in third-party components (FFmpeg, Pillow, Flet, ...) should also be reported upstream; see [THIRD_PARTY_NOTICES.md](docs/THIRD_PARTY_NOTICES.md).