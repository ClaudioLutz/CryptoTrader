# Update README Documentation

## Summary

Rewrote the README.md with comprehensive documentation covering all project features, installation, configuration, CLI usage, dashboard setup, and development workflow.

## Context / Problem

The existing README had encoding issues (appeared with spaces between characters) and was outdated, missing documentation for:
- The new Streamlit dashboard
- API server options
- uv package manager support
- Risk management features
- Additional CLI tools
- Development and testing workflows

## What Changed

- **README.md**: Complete rewrite with:
  - Updated project description highlighting production-grade features
  - Full feature list including dashboard, risk management, alerting
  - Architecture diagram showing both bot and dashboard structure
  - Installation instructions for both uv and pip
  - Comprehensive configuration section with security notes
  - CLI options documentation including new `--api-port` and `--no-api` flags
  - **Live Trading section** with pre-flight checklist and safety features
  - Dashboard setup and usage instructions
  - Development section with testing, code quality, and integration test commands
  - Documentation of additional CLI tools (secrets, security, audit)
  - Links to project documentation folders

## How to Test

1. View the README.md file to verify formatting renders correctly
2. Verify all documented commands work:
   ```bash
   crypto-bot --help
   crypto-bot --version
   ```
3. Check that referenced files exist:
   - `.env.example`
   - `trading_dashboard/requirements.txt`
   - `docs/` folders

## Risk / Rollback Notes

**Risks:**
- None - documentation only change

**Rollback:**
- Revert the commit with `git revert`
