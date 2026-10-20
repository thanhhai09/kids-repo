# Free A30s HTTPS gateway

Render hosts only this stateless transport. SQLite accounts, device grants and
profile data remain on A30s. No database or device/account secrets belong in this
repository. The existing A30s admin login page and its exact API routes are
forwarded over HTTPS. Admin sessions remain validated by A30s; cookies are
Secure, HttpOnly and SameSite=Strict and modifying requests require its CSRF token.
Unknown admin paths remain denied. The root URL redirects to `/admin`.

Deploy `server.py`, `requirements.txt`, `render.yaml` as a Free Python web service.
Set a random A30_TUNNEL_KEY (at least 40 characters). Store the same key and public
HTTPS gateway URL on A30s in a private JSON config (mode 600): gateway/key fields.
Run `a30_agent.py` on A30s using Python with websockets>=14,<16. The agent opens
an outbound WSS connection; no modem port forwarding or Cloudflare domain zone is
required. A30s must remain powered and online. Connection loss triggers reconnect.

DNSHE custom domain should be added in Render, then use Render's exact DNS
instructions. Do not point at a guessed IP, and do not move nameservers merely to
enable this gateway. KidsAuto 0.14.12+ routes the native app and enrollment through
the public gateway. The DNSHE custom domain is pending; use the Render hostname.

Free hosting has limits and may cold-start. Do not add payment details, paid disks
or extra paid services. Keep A30s powered and connected to the Internet.
