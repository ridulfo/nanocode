FROM python:3-slim

# Install git for repository operations
RUN apt-get update && \
    apt-get install -y git && \
    rm -rf /var/lib/apt/lists/*

# Copy nanocode module into Python site-packages so it's importable
COPY nanocode /usr/local/lib/python3.14/site-packages/nanocode

# Set working directory
WORKDIR /workspace

# Entrypoint script to configure git from env vars and run nanocode
RUN echo '#!/bin/bash\n\
if [ -n "$GIT_USER_NAME" ]; then\n\
  git config --global user.name "$GIT_USER_NAME"\n\
fi\n\
if [ -n "$GIT_USER_EMAIL" ]; then\n\
  git config --global user.email "$GIT_USER_EMAIL"\n\
fi\n\
exec python3 -m nanocode "$@"' > /entrypoint.sh && \
    chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
