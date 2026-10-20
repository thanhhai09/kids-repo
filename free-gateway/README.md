# Free A30s HTTPS gateway (deployment pending)

Render hosts only this stateless transport. SQLite accounts, device grants and
profile data remain on A30s. No database or device/account secrets belong in this
repository. Admin routes are not forwarded.

Deploy `server.py`, `requirements.txt`, `render.yaml` as a Free Python web service.
Set a random A30_TUNNEL_KEY (at least 40 characters). Store the same key and public
HTTPS gateway URL on A30s in a private JSON config (mode 600): gateway/key fields.
Run `a30_agent.py` on A30s using Python with websockets>=14,<16. The agent opens
an outbound WSS connection; no modem port forwarding or Cloudflare domain zone is
required. A30s must remain powered and online. Connection loss triggers reconnect.

DNSHE custom domain should be added in Render, then use Render's exact DNS
instructions. Do not point at a guessed IP, and do not move nameservers merely to
enable this gateway. Update every native app/enrollment endpoint before testing
4G; current DEBs still use the A30s LAN IP.

Free hosting has limits and may cold-start. Do not add payment details, paid disks
or extra paid services. This code has not yet been deployed or tested end-to-end.
