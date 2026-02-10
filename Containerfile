FROM python:3-slim

# Install git for repository operations
RUN apt-get update && \
    apt-get install -y git && \
    rm -rf /var/lib/apt/lists/*

# Copy nanocode into the container
COPY nanocode.py /usr/local/bin/nanocode.py
RUN chmod +x /usr/local/bin/nanocode.py

# Set working directory
WORKDIR /workspace

# Entrypoint script to configure git from env vars
RUN echo '#!/bin/bash\n\
if [ -n "$GIT_USER_NAME" ]; then\n\
  git config --global user.name "$GIT_USER_NAME"\n\
fi\n\
if [ -n "$GIT_USER_EMAIL" ]; then\n\
  git config --global user.email "$GIT_USER_EMAIL"\n\
fi\n\
exec python3 /usr/local/bin/nanocode.py "$@"' > /entrypoint.sh && \
    chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
