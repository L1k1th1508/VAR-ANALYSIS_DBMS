FROM node:22-bookworm-slim AS node
FROM python:3.11-slim-bookworm
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN python -c "import tomllib; p=tomllib.load(open('uv.lock','rb'))['package']; open('/tmp/constraints.txt','w').write('\n'.join(x['name']+'=='+x['version'] for x in p if 'registry' in x.get('source',{})))" \
    && pip install --no-cache-dir -c /tmp/constraints.txt .
COPY evaluation-web ./evaluation-web
WORKDIR /app/evaluation-web
RUN npm ci && npm run build
RUN useradd --create-home portal && chown -R portal:portal /app/evaluation-web/.next
USER portal
EXPOSE 3000
CMD ["npm", "start"]
