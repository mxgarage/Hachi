#!/usr/bin/env python3
"""hachi-probe v0: read-only egress check. Prints one JSON document.

Sends one plain GET request per sample to the endpoint you choose, reads the
public address it reports, and compares it with the address range you wrote
down. It never changes routes, DNS, proxies, firewall or system settings.

Exit codes: 0 match, 1 mismatch, 2 unverified (this includes bad options and
any case where the answer cannot be trusted).
"""
import argparse, ipaddress, json, os, sys, urllib.error, urllib.request, urllib.parse
from datetime import datetime, timezone

SAMPLE_TIMEOUT = 5


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """An address service should answer directly; a redirect is not a trusted answer."""
    def redirect_request(self, *a, **k):
        return None


PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")


def proxy_env_detected():
    return any(os.environ.get(v) or os.environ.get(v.lower()) for v in PROXY_VARS)


def fetch_ip(url, use_env_proxy=False):
    """Return the address from a trace-style ('ip=...') or bare-address reply.

    Proxy environment variables are ignored unless use_env_proxy is set, so the
    probe never silently reports a proxy's address as the machine's own."""
    # Only http(s) is allowed.
    if urllib.parse.urlparse(url).scheme not in ("http", "https"):
        raise ValueError("endpoint must be http or https")
    handlers = [_NoRedirect()]
    if not use_env_proxy:
        handlers.append(urllib.request.ProxyHandler({}))
    opener = urllib.request.build_opener(*handlers)
    with opener.open(url, timeout=SAMPLE_TIMEOUT) as r:
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


SUBJECT = {"cloud": "这台云主机", "local": "这台电脑"}


def plain(status, role, reason=None):
    who = SUBJECT.get(role, "这台机器")
    if status == "match":
        return "一切正常", f"{who}现在上网用的地址，和你记录的一致。"
    if status == "mismatch":
        return "需要留意", (f"{who}现在上网用的地址，和你记录的不一样。Hachi 不会改动任何设置，"
                           "请对照云服务商后台或公司的记录确认。")
    why = {
        "bad_expected": "你填写的“记录的地址”格式不对，没法拿来对照。请检查后重填。",
        "family_differs": "这次看到的地址类型（IPv4 或 IPv6）和你记录的不同，没法直接对照。",
    }.get(reason, "这次没能得到可靠的结果，所以不能说正常。")
    return "暂时无法确认", why


def run(endpoint, expected, label, samples, role="cloud", use_env_proxy=False):
    seen, errors = [], 0
    for _ in range(samples):
        try:
            seen.append(fetch_ip(endpoint, use_env_proxy))
        except Exception:
            errors += 1
    host = urllib.parse.urlparse(endpoint).hostname
    reason = None
    net = None
    if expected:
        try:
            net = ipaddress.ip_network(expected, strict=False)
        except ValueError:
            reason = "bad_expected"
    if reason:
        status = "unverified"
    elif not seen or len(seen) < samples:
        status = "unverified"
    elif len(set(seen)) > 1:
        status = "unverified"  # changed between samples: not a stable answer
    elif net is None:
        status = "unverified"
    elif seen[0].version != net.version:
        status, reason = "unverified", "family_differs"
    else:
        status = "match" if seen[0] in net else "mismatch"
    ip = seen[0] if seen else None
    head, detail = plain(status, role, reason)
    detected = proxy_env_detected()
    if detected and not use_env_proxy:
        detail += "（这台机器设置了代理环境变量，本次检查没有使用它。）"
    return {
        "schema": "hachi-probe/0",
        "status": status,
        "reason": reason,
        "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "probe_role": role,
        "target_host": host,
        "ip_family": f"ipv{ip.version}" if ip else None,
        "observed_ip_masked": mask(ip) if ip else None,
        "expected_ref": label,
        "prefix_match": (ip in net) if (ip and net and ip.version == net.version) else None,
        "evidence": {
            "samples_requested": samples,
            "samples_ok": len(seen),
            "samples_failed": errors,
            "stable": len(set(seen)) == 1 if seen else False,
            "proxy_env_detected": detected,
            "proxy_env_used": bool(use_env_proxy),
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
    p.add_argument("--use-env-proxy", action="store_true",
                   help="honor HTTP(S)_PROXY from the environment (off by default)")
    a = p.parse_args(argv)
    out = run(a.endpoint, a.expected, a.label, max(1, a.samples), a.role, a.use_env_proxy)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return {"match": 0, "mismatch": 1}.get(out["status"], 2)


if __name__ == "__main__":
    sys.exit(main())
