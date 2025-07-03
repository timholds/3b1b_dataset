# CLAUDE.md - Essential Project Reference

## 📁 Architecture
See **[docs/CURRENT_ARCHITECTURE.md](docs/CURRENT_ARCHITECTURE.md)** for complete system design.

## 🎯 Core Goal
Generate self-contained ManimCE code snippets (one scene per file) from 3Blue1Brown's ManimGL codebase that can be rendered for validation.

## 🚀 Conversion Goal
- Our primary objective is to convert each scene in the original ManimGL format into self-contained ManimCE scenes
- We will render the converted scenes into videos to manually inspect and compare them against the original videos
- The goal is to achieve an exact match, with minor exceptions like Pi Creatures

## 🛠 Development Principles
- When fixing the pipeline, do not sidetracked into trying to patch symptoms instead of fixing the root cause in the pipeline