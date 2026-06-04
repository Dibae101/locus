# Hosting Locus Hub at locus.dibyadarshankhanal.com.np (Cloudflare)

Locus Hub is a Python web app, so Cloudflare must point the subdomain at a machine that
runs it. Pick the route that matches what you have.

---

## Route B — Cloudflare Tunnel (recommended "for now"; no public IP, no VM needed)

Runs the Hub from any machine (even your laptop or a tiny box) and exposes it through
Cloudflare. Nothing is open to the internet directly.

1. **Create a tunnel in Cloudflare**
   - Cloudflare dashboard → Zero Trust → Networks → Tunnels → Create a tunnel
   - Name it `locus`. Copy the **tunnel token** it shows.
   - Add a **public hostname**:
     - Subdomain: `locus`
     - Domain: `dibyadarshankhanal.com.np`
     - Service: `HTTP` → `hub-ui:8800`  (when running via compose below)

2. **Run the stack with the tunnel**
   ```bash
   git clone https://github.com/Dibae101/locus && cd locus
   TUNNEL_TOKEN=<paste-token> \
     docker compose -f deploy/cloudflare/docker-compose.yml --profile tunnel up -d
   ```

3. **Seed the catalog into the hub's registry**
   ```bash
   pip install "locus-etl[oci]"
   LOCUS_REGISTRY=localhost:5000 LOCUS_INSECURE=1 locus catalog seed
   ```

4. **Visit** https://locus.dibyadarshankhanal.com.np  — TLS is handled by Cloudflare.

---

## Route A — Public VM (if you have a server with a public IP)

1. **DNS in Cloudflare**: add an `A` record
   - Name: `locus`
   - IPv4: your VM's public IP
   - Proxy status: **Proxied** (orange cloud) — gives you Cloudflare TLS + protection

2. **On the VM**
   ```bash
   git clone https://github.com/Dibae101/locus && cd locus
   docker compose -f deploy/cloudflare/docker-compose.yml up -d   # no --profile tunnel
   LOCUS_REGISTRY=localhost:5000 LOCUS_INSECURE=1 locus catalog seed
   ```

3. **Expose :8800 to Cloudflare.** Simplest: set Cloudflare SSL/TLS mode to "Flexible"
   and open port 80→8800 with a tiny reverse proxy (Caddy/nginx), or set an Origin Rule
   routing the host to port 8800. For real TLS to the origin, run Caddy with a cert and
   use "Full (strict)".

---

## How users consume the hosted hub

```bash
# browse:   https://locus.dibyadarshankhanal.com.np
pip install locus-etl
export LOCUS_REGISTRY=locus.dibyadarshankhanal.com.np
locus search                       # list images on your hub
locus pull doc-to-tables           # pull from your hub
```

> Note: pulling over the public hostname requires the **registry** (:5000) to also be
> reachable, not just the UI. For a single-hostname setup, front both the UI and the
> OCI API with one reverse proxy (path-routing `/v2/` to the registry, everything else
> to the Hub UI). For production, deploy full **Harbor** which serves UI + OCI on one
> host with auth — see `deploy/harbor/README.md`.

---

## What you need vs what's ready

| Piece | Status |
|---|---|
| Hub UI + registry stack | ✅ built (`deploy/cloudflare/docker-compose.yml`) |
| `locus hub --host 0.0.0.0` (bind for proxy/tunnel) | ✅ supported |
| Catalog seeding | ✅ `locus catalog seed` |
| Cloudflare DNS/Tunnel + a machine to run it | ⬜ your action |
| TLS | ✅ handled by Cloudflare |
