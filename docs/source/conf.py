# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "Eyetracking"
copyright = "2026, Scott Huberty"
author = "Scott Huberty"
release = "v0.1.0"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ["sphinxcontrib.youtube"]

templates_path = ["_templates"]
exclude_patterns = []



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_title = "ARIA Eyetracking"
html_static_path = ["_static"]
html_css_files = ["aria.css"]

_dark_css_variables = {
    "font-stack": '"Nunito Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    "font-stack--monospace": '"Courier New", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
    "color-brand-primary": "#6cc351",
    "color-brand-content": "#6cc351",
    "color-background-primary": "#0c1716",
    "color-background-secondary": "#102321",
    "color-background-hover": "#17332f",
    "color-sidebar-background": "#102321",
    "color-sidebar-brand-text": "#d9f5d0",
    "color-sidebar-link-text--top-level": "#d9f5d0",
    "color-link": "#8fd879",
    "color-link--hover": "#c0e9b6",
    "color-api-name": "#9fb7d7",
    "color-api-pre-name": "#c5d0d5",
    "color-admonition-background": "#17332f",
    "color-admonition-title-background": "#20483f",
    "color-highlight-on-target": "#17332f",
    "color-code-background": "#0f1f1d",
    "color-code-foreground": "#e6f2ee",
}

html_theme_options = {
    "source_repository": "https://github.com/scott-huberty/aria-et/",
    "source_branch": "main",
    "source_directory": "docs/source/",
    "light_css_variables": _dark_css_variables,
    "dark_css_variables": _dark_css_variables,
}
