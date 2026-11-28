#!/usr/bin/env python3
"""hachi-probe v0: read-only egress check. Prints one JSON document.

Sends one plain GET request per sample to the endpoint you choose, reads the
public address it reports, and compares it with the address range you wrote
down. It never changes routes, DNS, proxies, firewall or system settings.

Exit codes: 0 match, 1 mismatch, 2 unverified.
"""
import argparse, ipaddress, json, sys, urllib.request, urllib.parse
from datetime import datetime, timezone

SAMPLE_TIMEOUT = 5


def fetch_ip(url):
    """Return the address from a trace-style ('ip=...') or bare-address reply."""
    # Only http(s) is allowed.
    if urllib.parse.urlparse(url).scheme not in ("http", "https"):
        raise ValueError("endpoint must be http or https")
    with urllib.request.urlopen(url, timeout=SAMPLE_TIMEOUT) as r:
        body = r.read(4096).decode("ascii", "replace")
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("ip="):
            line = line[3:]
        try:
            return ipaddress.ip_address(line)
        except ValueError:
            continue
    raise ValueError("no address in reply")


def mask(ip):
    """Hide the host part: IPv4 -> /24, IPv6 -> /48."""
    bits = 24 if ip.version == 4 else 48
    net = ipaddress.ip_network(f"{ip}/{bits}", strict=False)
    return str(net)


PLAIN = {
    "match": ("一切正常", "这台云主机现在上网用的地址，和你记录的一致。"),
    "mismatch": ("需要留意", "这台云主机现在上网用的地址，和你记录的不一样。Hachi 不会改动任何设置，请对照云服务商后台的记录确认。"),
    "unverified": ("暂时无法确认", "这次没能得到可靠的结果，所以不能说正常。"),
}


def run(endpoint, expected, label, samples, role="cloud"):
    seen, errors = [], 0
    for _ in range(samples):
        try:
            seen.append(fetch_ip(endpoint))
        except Exception:
            errors += 1
    host = urllib.parse.urlparse(endpoint).hostname
    net = ipaddress.ip_network(expected, strict=False) if expected else None
    if not seen or len(seen) < samples:
        status = "unverified"
    elif len(set(seen)) > 1:
        status = "unverified"  # changed between samples: not a stable answer
    elif net is None:
        status = "unverified"
    else:
        status = "match" if seen[0] in net else "mismatch"
    ip = seen[0] if seen else None
    head, detail = PLAIN[status]
    return {
        "schema": "hachi-probe/0",
        "status": status,
        "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "probe_role": role,
        "target_host": host,
        "ip_family": f"ipv{ip.version}" if ip else None,
        "observed_ip_masked": mask(ip) if ip else None,
        "expected_ref": label,
        "prefix_match": (ip in net) if (ip and net) else None,
        "evidence": {
            "samples_requested": samples,
            "samples_ok": len(seen),
            "samples_failed": errors,
            "stable": len(set(seen)) == 1 if seen else False,
            # The probe cannot prove it shares the agent's network path.
            "same_path_as_agent": "unknown",
        },
        "plain": {"headline": head, "detail": detail},
        "read_only": True,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--endpoint", required=True, help="URL that reports your public address")
    p.add_argument("--expected", help="address or range you wrote down, e.g. 203.0.113.0/24")
    p.add_argument("--label", default="my-static-ip", help="your own name for the record (not an address)")
    p.add_argument("--samples", type=int, default=3)
    p.add_argument("--role", choices=["cloud", "local"], default="cloud")
    a = p.parse_args(argv)
    out = run(a.endpoint, a.expected, a.label, max(1, a.samples), a.role)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return {"match": 0, "mismatch": 1}.get(out["status"], 2)


if __name__ == "__main__":
    sys.exit(main())
