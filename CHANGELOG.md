# Changelog

All notable changes to this project will be documented in this file.

## v0.0.1 - 2025-08-22 🚀
Initial project release.

### ✨ Added
- Core functionality to summarize academic abstracts based on a search term.
- Integration with the (arXiv API)[https://info.arxiv.org/help/api/user-manual.html] to fetch the academic publication metadata.
- Command-line interface (CLI) with options for `search_term`, width of search window (`--window-days`), number of results to return from the arXiv API (`--max-results`), model to use for summarization (`--model-name`), number of abstracts to actually summarize (`--n-summaries`), and path to store output markdown files (`--out-dir`).
- Basic support for generating Markdown output of summaries.

### 🐛 Fixed
- Addressed initial `mypy` type-hinting issues.
- Simplified dependencies using uv and configured script shortcuts in `pyproject.toml`.