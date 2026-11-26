# Playwright runner for the end-to-end specs (e2e/docker-compose.yml). The image version must match
# @playwright/test in package.json.
FROM mcr.microsoft.com/playwright:v1.65.1-noble

ENV NPM_CONFIG_UPDATE_NOTIFIER=false NPM_CONFIG_FUND=false NPM_CONFIG_AUDIT=false
WORKDIR /e2e
COPY package.json package-lock.json ./
RUN npm ci
COPY playwright.config.js global-setup.js ./
COPY tests ./tests

CMD ["npx", "playwright", "test"]
