FROM mcr.microsoft.com/devcontainers/python:1-3.11-bookworm

# Install uv (same package manager as local/CI)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1
