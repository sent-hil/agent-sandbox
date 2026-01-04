FROM debian:bookworm-slim

# Avoid prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install essential tools and fish shell
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    sudo \
    wget \
    unzip \
    build-essential \
    ca-certificates \
    fish \
    direnv \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (for Claude Code and other JS tools)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install uv (Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Create a non-root user
ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# Remove existing user/group with same UID/GID if present, then create our user
RUN (userdel -r $(getent passwd $USER_UID | cut -d: -f1) 2>/dev/null || true) \
    && (groupdel $(getent group $USER_GID | cut -d: -f1) 2>/dev/null || true) \
    && groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# Install Claude Code CLI globally (as root, before switching user)
RUN npm install -g @anthropic-ai/claude-code

# Install OpenCode CLI (download to /usr/local/bin for all users)
RUN curl -fsSL https://opencode.ai/install | HOME=/tmp bash \
    && mv /tmp/.opencode/bin/opencode /usr/local/bin/opencode \
    && chmod 755 /usr/local/bin/opencode

# Install Neovim (latest stable, architecture-aware)
RUN ARCH=$(uname -m) \
    && if [ "$ARCH" = "aarch64" ]; then NVIM_ARCH="arm64"; else NVIM_ARCH="x86_64"; fi \
    && curl -LO "https://github.com/neovim/neovim/releases/latest/download/nvim-linux-${NVIM_ARCH}.tar.gz" \
    && tar -C /opt -xzf "nvim-linux-${NVIM_ARCH}.tar.gz" \
    && rm "nvim-linux-${NVIM_ARCH}.tar.gz" \
    && ln -s /opt/nvim-linux-${NVIM_ARCH}/bin/nvim /usr/local/bin/nvim

# Set the default user
USER $USERNAME
WORKDIR /home/$USERNAME

# Keep container running
CMD ["sleep", "infinity"]
